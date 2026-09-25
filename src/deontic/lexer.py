"""Marker lexing and word tokenising (design §10, corpus README).

Two passes. The first splits the source into typed fragments: `$Term$`,
`$$Terms$$`, `@verb@`, `#90 days#`, `<parameter>` and the prose between
them. Only editors write markers, so any unmatched or empty marker is an
error. The second turns the prose into words, numbers, dates, strings and
punctuation, giving the parser one flat token stream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .errors import (
    EmptyMarker, MissingPeriod, SigilInsideMarker, UnbalancedParenthesis,
    UnmatchedMarker, UnterminatedString,
)

SIGILS = "$@#<>"
UNITS = {
    "hour": "hour", "hours": "hour", "day": "day", "days": "day", "week": "week", "weeks": "week",
    "month": "month", "months": "month", "quarter": "quarter", "quarters": "quarter",
    "year": "year", "years": "year", "percent": "percent",
}
CALENDAR_UNITS = {"calendar week": "calendar week", "calendar weeks": "calendar week",
                  "calendar month": "calendar month", "calendar months": "calendar month",
                  "calendar year": "calendar year", "calendar years": "calendar year"}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10}


@dataclass(frozen=True)
class Fragment:
    kind: str            # prose | term | verb | quantity | parameter
    text: str
    pos: int
    plural: bool = False


@dataclass(frozen=True)
class Token:
    kind: str            # word | punct | string | number | date | term | verb | quantity | parameter
    value: Any
    pos: int
    plural: bool = False
    raw: str = ""


def normalise(text: str) -> str:
    return " ".join(text.split())


def quantity(text: str) -> dict:
    """`90 days` → {value: 90, unit: day}; `7` → {value: 7}; `year` → {value: 1, unit: year}."""
    words = normalise(text).lower().split()
    if not words:
        raise ValueError("empty quantity")
    value = None
    if re.fullmatch(r"\d+(\.\d+)?", words[0]):
        value = float(words[0]) if "." in words[0] else int(words[0])
        words = words[1:]
    elif words[0] in NUMBER_WORDS:
        value = NUMBER_WORDS[words[0]]
        words = words[1:]
    unit = " ".join(words)
    if unit in CALENDAR_UNITS:
        unit = CALENDAR_UNITS[unit]
    elif unit in UNITS:
        unit = UNITS[unit]
    elif unit:
        raise ValueError(f"unknown unit {unit!r}")
    if value is None:
        if not unit:
            raise ValueError("quantity without a value")
        value = 1
    out: dict = {"value": value}
    if unit:
        out["unit"] = unit
    return out


def fragments(source: str) -> list[Fragment]:
    out: list[Fragment] = []
    i, n, prose_start = 0, len(source), 0
    while i < n:
        c = source[i]
        if c not in "$@#<":
            i += 1
            continue
        if prose_start < i:
            out.append(Fragment("prose", source[prose_start:i], prose_start))
        if c == "$" and source.startswith("$$", i):
            open_m, close_m, kind, plural = "$$", "$$", "term", True
        else:
            open_m = c
            close_m = {"$": "$", "@": "@", "#": "#", "<": ">"}[c]
            kind = {"$": "term", "@": "verb", "#": "quantity", "<": "parameter"}[c]
            plural = False
        start = i + len(open_m)
        end = source.find(close_m, start)
        if end < 0:
            raise UnmatchedMarker(f"unmatched {open_m!r}", position=i)
        content = source[start:end]
        if any(s in content for s in SIGILS):
            raise SigilInsideMarker("markers do not nest", position=i)
        content = normalise(content)
        if not content:
            raise EmptyMarker("empty marker", position=i)
        out.append(Fragment(kind, content, i, plural))
        i = end + len(close_m)
        prose_start = i
    if prose_start < n:
        out.append(Fragment("prose", source[prose_start:], prose_start))
    # A stray closing sigil in prose
    for f in out:
        if f.kind == "prose" and ">" in f.text:
            raise UnmatchedMarker("unmatched '>'", position=f.pos + f.text.index(">"))
    return out


_WORD_RE = re.compile(r"""
    (?P<date>\d{4}-\d{2}-\d{2})(?![\w-])
  | (?P<number>\d+(?:\.\d+)?)(?![\w-])(?!\.\d)
  | (?P<poss>'s)(?![\w-])
  | (?P<word>[^\s"()',.]+?)(?=[\s"()',.]|$|'s\b)
  | (?P<punct>[(),.])
  | (?P<space>\s+)
""", re.VERBOSE)


def _prose_tokens(text: str, base: int) -> list[Token]:
    out: list[Token] = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == '"':
            end = text.find('"', i + 1)
            if end < 0:
                raise UnterminatedString("unterminated string", position=base + i)
            out.append(Token("string", text[i + 1:end], base + i))
            i = end + 1
            continue
        m = _WORD_RE.match(text, i)
        if not m:
            raise UnmatchedMarker("unreadable text", position=base + i)
        kind = m.lastgroup
        if kind == "space":
            pass
        elif kind == "date":
            out.append(Token("date", m.group(), base + i))
        elif kind == "number":
            s = m.group()
            out.append(Token("number", float(s) if "." in s else int(s), base + i, raw=s))
        elif kind == "poss":
            out.append(Token("punct", "'s", base + i))
        elif kind == "punct":
            out.append(Token("punct", m.group(), base + i))
        else:
            out.append(Token("word", m.group().lower(), base + i, raw=m.group()))
        i = m.end()
    return out


def tokens(source: str) -> tuple[list[Fragment], list[Token]]:
    frags = fragments(source)
    out: list[Token] = []
    for f in frags:
        if f.kind == "prose":
            out.extend(_prose_tokens(f.text, f.pos))
        elif f.kind == "quantity":
            try:
                out.append(Token("quantity", quantity(f.text), f.pos, raw=f.text))
            except ValueError:
                out.append(Token("quantity", None, f.pos, raw=f.text))
        else:
            out.append(Token(f.kind, f.text, f.pos, plural=f.plural))
    depth = 0
    first_open = None
    for t in out:
        if t.kind == "punct" and t.value == "(":
            depth += 1
            if first_open is None:
                first_open = t.pos
        elif t.kind == "punct" and t.value == ")":
            depth -= 1
            if depth < 0:
                raise UnbalancedParenthesis("unbalanced parenthesis", position=t.pos)
    if depth > 0:
        raise UnbalancedParenthesis("unbalanced parenthesis", position=first_open)
    if not out or not (out[-1].kind == "punct" and out[-1].value == "."):
        raise MissingPeriod("a sentence ends with a period")
    return frags, out
