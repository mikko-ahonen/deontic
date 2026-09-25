"""The filter sub-language on its own (design §7).

A filter is the `where` half of a term or subject, and it is also useful
alone: a dataset's row filter, a pattern's `where`, a query an application
lets an operator type. `parse_filter` reads one; `render_filter` writes the
canonical English for a filter AST, so a stored tree round-trips to text.
"""

from __future__ import annotations

import json

from .lexer import tokens
from .parser import Parser, clean

_VALUE_OPS = {
    "is": "is", "is_not": "is not", "contains": "contains", "starts_with": "starts with",
    "ends_with": "ends with", "at_least": "is at least", "at_most": "is at most",
    "more_than": "is more than", "less_than": "is less than", "before": "is before", "after": "is after",
}


def parse_filter(text: str) -> dict:
    """Parse a filter written on its own, with or without a leading `where`
    and with or without the final period. Raises the parser's errors."""
    source = text.strip()
    if source.lower().startswith("where "):
        source = source[6:]
    if not source.endswith("."):
        source += "."
    _, toks = tokens(source)
    p = Parser(toks)
    node = p.or_expr()
    p.end()
    return clean(node)


def render_value(v: dict) -> str:
    if "text" in v:
        t = v["text"]
        if t and " " not in t and not any(c in t for c in '"(),') and t.lower() not in ("true", "false", "today", "and", "or"):
            return t
        return json.dumps(t, ensure_ascii=False)
    if "number" in v:
        return repr(v["number"])
    if "boolean" in v:
        return "true" if v["boolean"] else "false"
    if "date" in v:
        return v["date"]
    if "today" in v:
        return "today"
    if "parameter" in v:
        return f"<{v['parameter']}>"
    raise ValueError(f"not a value: {v!r}")


def render_path(path: list[str]) -> str:
    return "'s ".join(path)


def render_filter(node: dict, *, top: bool = True) -> str:
    op = node["op"]
    if op in ("and", "or"):
        parts = []
        for item in node["items"]:
            s = render_filter(item, top=False)
            if op == "and" and item["op"] == "or":
                s = f"({s})"
            parts.append(s)
        return f" {op} ".join(parts)
    if op == "tagged":
        return "tagged " + " and ".join(node["tags"])
    if op == "that":
        from .parser import render_predicate
        return "that " + render_predicate(node["predicate"])
    path = render_path(node["path"])
    if op == "is_empty":
        return f"{path} is empty"
    if op == "is_not_empty":
        return f"{path} is not empty"
    if op == "equals":
        return f"{path} equals {render_path(node['other'])}"
    if op == "is_one_of":
        return f"{path} is one of " + ", ".join(render_value(v) for v in node["values"])
    if op == "between":
        a, b = node["values"]
        return f"{path} is between {render_value(a)} and {render_value(b)}"
    words = _VALUE_OPS[op]
    if node.get("exact"):
        words += " exactly"
    return f"{path} {words} {render_value(node['value'])}"


__all__ = ["parse_filter", "render_filter", "render_value", "render_path"]
