"""Loading a dictionary (conformance/dictionary.schema.json) into a form the
resolver can query: every declared name with its role, field kinds, tag
sets, relations by possessive word, verbs with their patterns.

Loading checks what the JSON Schema cannot: that references point at
declared types, that a pattern names real fields of the right kind, and
that no name is declared in two roles.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCALARS = ("text", "number", "date", "boolean")


class DictionaryError(ValueError):
    pass


def field_kind(f: Any) -> str:
    return f if isinstance(f, str) else f["kind"]


@dataclass
class Dictionary:
    data: dict
    types: dict[str, dict] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)       # name (lower) → type | plural | event | cadence | metric | attester | attester_plural | term | reference
    canonical: dict[str, str] = field(default_factory=dict)   # name (lower) → declared spelling
    plural_of: dict[str, str] = field(default_factory=dict)   # plural (lower) → singular type
    verbs: dict[str, dict] = field(default_factory=dict)      # canonical verb → declaration
    verb_of: dict[str, str] = field(default_factory=dict)     # any spelling → canonical
    relations: dict[str, dict] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def strictness(self) -> str:
        return self.data.get("strictness", "permissive")

    # --- queries ---------------------------------------------------------------------

    def role(self, name: str) -> str | None:
        return self.roles.get(name.lower())

    def type_of(self, name: str) -> str | None:
        """The type a marked name denotes: itself, or the singular of a plural."""
        r = self.role(name)
        if r == "type":
            return self.canonical[name.lower()]
        if r == "plural":
            return self.plural_of[name.lower()]
        return None

    def fields(self, type_name: str) -> dict:
        return self.types[type_name].get("fields", {})

    def tags(self, type_name: str) -> set[str]:
        return {t if isinstance(t, str) else t["name"] for t in self.types[type_name].get("tags", [])}

    def step(self, type_name: str, word: str) -> tuple[str | None, str | None]:
        """Follow one possessive step. Returns (target type, error code or None)."""
        f = self.fields(type_name).get(word)
        if f is not None:
            if field_kind(f) == "reference":
                return f["to"], None
            return None, "not_a_reference"
        for r in self.relations.values():
            if type_name in r["from"] and r.get("as", r["to"]) == word:
                return r["to"], None
        return None, "unknown_field"

    def verb(self, spelling: str) -> dict | None:
        c = self.verb_of.get(spelling.lower())
        return self.verbs[c] if c else None

    def verb_dated(self, decl: dict) -> bool:
        if "pattern" in decl:
            return "at" in decl["pattern"]
        return bool(decl.get("dated", False))

    def suggest(self, type_name: str, word: str) -> str | None:
        import difflib
        names = list(self.fields(type_name))
        m = difflib.get_close_matches(word, names, n=1, cutoff=0.75)
        return m[0] if m else None


def _declare(d: Dictionary, name: str, role: str, canonical: str | None = None):
    key = name.lower()
    if key in d.roles and d.roles[key] != role:
        raise DictionaryError(f"{name!r} declared as both {d.roles[key]} and {role}")
    d.roles[key] = role
    d.canonical[key] = canonical or name


def load(source: dict | str | Path) -> Dictionary:
    data = source if isinstance(source, dict) else json.loads(Path(source).read_text())
    d = Dictionary(data=data)
    d.types = data.get("types", {})
    for name, t in d.types.items():
        _declare(d, name, "type")
        plural = t.get("plural", name + "s")
        _declare(d, plural, "plural")
        d.plural_of[plural.lower()] = name
        for fname, f in t.get("fields", {}).items():
            k = field_kind(f)
            if k == "reference":
                if f["to"] not in d.types:
                    raise DictionaryError(f"{name}.{fname} refers to undeclared type {f['to']!r}")
            elif k == "list":
                if f["of"] not in SCALARS:
                    raise DictionaryError(f"{name}.{fname}: list of {f['of']!r}")
            elif k not in SCALARS:
                raise DictionaryError(f"{name}.{fname}: unknown kind {k!r}")
    for name, r in data.get("relations", {}).items():
        for s in r["from"]:
            if s not in d.types:
                raise DictionaryError(f"relation {name}: undeclared subject type {s!r}")
        if r["to"] not in d.types:
            raise DictionaryError(f"relation {name}: undeclared object type {r['to']!r}")
        d.relations[name] = r
    for key, role in (("events", "event"), ("cadences", "cadence"), ("metrics", "metric"), ("attesters", "attester")):
        for name, decl in data.get(key, {}).items():
            _declare(d, name, role)
            if role == "attester" and "plural" in decl:
                _declare(d, decl["plural"], "attester_plural", canonical=name)
            if role == "event":
                if decl["type"] not in d.types or field_kind(d.fields(decl["type"]).get(decl["field"], "text")) != "date":
                    raise DictionaryError(f"event {name}: not a date field of a declared type")
            if role == "metric" and decl["of"] not in d.types:
                raise DictionaryError(f"metric {name}: undeclared type {decl['of']!r}")
    for name, v in data.get("verbs", {}).items():
        d.verbs[name] = v
        d.verb_of[name.lower()] = name
        for syn in v.get("synonyms", []):
            d.verb_of[syn.lower()] = name
        _check_pattern(d, name, v)
    for sentence in data.get("definitions", []):
        from .lexer import fragments
        first = next(f for f in fragments(sentence) if f.kind == "term")
        _declare(d, first.text, "reference" if " refers to " in sentence else "term")
    return d


def _check_pattern(d: Dictionary, name: str, v: dict):
    p = v.get("pattern")
    if p is None:
        if "dated" not in v:
            raise DictionaryError(f"verb {name}: a hook verb must declare dated")
        return
    if "dated" in v:
        raise DictionaryError(f"verb {name}: a verb is data or code, never both")
    subj, obj = v.get("subject"), v.get("object", "entity")

    def ref(type_name, fname, to):
        f = d.fields(type_name).get(fname)
        if f is None or field_kind(f) != "reference" or (to and f["to"] != to):
            raise DictionaryError(f"verb {name}: {type_name}.{fname} is not a reference to {to}")

    def date(type_name, fname):
        f = d.fields(type_name).get(fname)
        if f is None or field_kind(f) != "date":
            raise DictionaryError(f"verb {name}: {type_name}.{fname} is not a date")

    if p["kind"] == "field":
        if subj is None:
            raise DictionaryError(f"verb {name}: a field pattern needs a subject type")
        if "object" in p:
            ref(subj, p["object"], obj)
        if "at" in p:
            date(subj, p["at"])
    elif p["kind"] == "record":
        if p["via"] not in d.types:
            raise DictionaryError(f"verb {name}: via type {p['via']!r} undeclared")
        ref(p["via"], p["subject"], subj)
        if p.get("object") == "self":
            if obj != p["via"]:
                raise DictionaryError(f"verb {name}: object self means the object type is {p['via']}")
        elif "object" in p:
            ref(p["via"], p["object"], obj if obj not in ("entity", "none") else None)
        if "at" in p:
            date(p["via"], p["at"])
    elif p["kind"] == "relation":
        r = d.relations.get(p["name"])
        if r is None:
            raise DictionaryError(f"verb {name}: relation {p['name']!r} undeclared")
        if subj and subj not in r["from"]:
            raise DictionaryError(f"verb {name}: subject {subj} is not a subject of {p['name']}")
        if obj not in ("entity", "none") and obj != r["to"]:
            raise DictionaryError(f"verb {name}: object {obj} is not the object of {p['name']}")
    elif p["kind"] == "reference":
        if obj != "entity":
            raise DictionaryError(f"verb {name}: a reference pattern takes any entity")


__all__ = ["Dictionary", "DictionaryError", "load", "field_kind"]
