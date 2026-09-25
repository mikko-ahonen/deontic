"""The filter sub-language on its own: every filter in the parse corpus
parses standalone, renders to English, and parses back to the same AST."""

import json
from pathlib import Path

import pytest

from deontic import parse_filter, render_filter

CONFORMANCE = Path(__file__).resolve().parent.parent / "conformance"


def filters_in_corpus():
    out = []
    for f in sorted((CONFORMANCE / "parse").glob("*.json")):
        ast = json.loads(f.read_text())["ast"]
        stack = [ast]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if "filter" in node:
                    out.append(pytest.param(node["filter"], id=f"{f.stem}"))
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    return out


@pytest.mark.parametrize("node", filters_in_corpus())
def test_filter_round_trips(node):
    text = render_filter(node)
    assert parse_filter(text) == node, text


def test_parse_filter_accepts_where_and_no_period():
    assert parse_filter("where status is active") == parse_filter("status is active.")
    assert parse_filter("status is active") == {"op": "is", "path": ["status"], "value": {"text": "active"}}


def test_snake_case_identifiers_are_single_words():
    """A field written as `customer_type` is one path step, and `is_active`
    does not collide with the operator `is`."""
    assert parse_filter("is_active is true") == {"op": "is", "path": ["is_active"], "value": {"boolean": True}}
    assert parse_filter("service's customer's customer_type is external")["path"] == ["service", "customer", "customer_type"]


def test_render_quotes_what_needs_quoting():
    assert render_filter({"op": "is", "path": ["name"], "value": {"text": "Main Hall"}}) == 'name is "Main Hall"'
    assert render_filter({"op": "is", "path": ["name"], "value": {"text": "true"}}) == 'name is "true"'
    assert render_filter({"op": "is", "path": ["version"], "value": {"parameter": "selected version"}}) == "version is <selected version>"
    assert render_filter({"op": "and", "items": [{"op": "is", "path": ["a"], "value": {"number": 1}},
                                                 {"op": "or", "items": [{"op": "is", "path": ["b"], "value": {"number": 2}},
                                                                        {"op": "is", "path": ["c"], "value": {"number": 3}}]}]}) == "a is 1 and (b is 2 or c is 3)"
