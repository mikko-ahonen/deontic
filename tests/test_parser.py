"""The parser reproduces the corpus: every parse case and every reject case
that needs no lexicon."""

import json
from pathlib import Path

import pytest

from deontic import errors
from deontic.parser import parse

CONFORMANCE = Path(__file__).resolve().parent.parent / "conformance"


def cases(sub, pred=lambda c: True):
    out = []
    for f in sorted((CONFORMANCE / sub).glob("*.json")):
        c = json.loads(f.read_text())
        if pred(c):
            out.append(pytest.param(c, id=f.stem))
    return out


@pytest.mark.parametrize("case", cases("parse"))
def test_parse_case(case):
    got = parse(case["source"], strictness=case.get("strictness", "permissive"))
    assert got == case["ast"]


@pytest.mark.parametrize("case", cases("reject", lambda c: "lexicon" not in c))
def test_reject_case_without_lexicon(case):
    with pytest.raises(errors.DeonticError) as e:
        parse(case["source"], strictness=case.get("strictness", "permissive"))
    assert e.value.as_dict() == case["error"]


@pytest.mark.parametrize("case", cases("reject", lambda c: "lexicon" not in c and c.get("strictness") == "strict"))
def test_strict_rejects_are_pre_formal_in_permissive(case):
    assert parse(case["source"])["shape"] == "pre_formal"


# --- resolution against the fixture lexicon ------------------------------------------

from deontic import dictionary as dictionary_module  # noqa: E402
from deontic.resolve import Scope, resolve  # noqa: E402

LEXICON = dictionary_module.load(CONFORMANCE / "lexicon.json")


@pytest.mark.parametrize("case", cases("reject", lambda c: "lexicon" in c))
def test_reject_case_with_lexicon(case):
    strictness = case.get("strictness", "permissive")
    ast = parse(case["source"], strictness=strictness)
    with pytest.raises(errors.ResolutionError) as e:
        resolve(ast, LEXICON, strictness=strictness)
    assert e.value.as_dict() == case["error"]


@pytest.mark.parametrize("case", cases("evaluate"))
def test_evaluate_sentences_resolve(case):
    """Every evaluate case's sentences parse and resolve; strict cases with an
    expected error raise it."""
    strictness = case.get("strictness", "permissive")
    scope = Scope()
    for i, s in enumerate(case["sentences"]):
        ast = parse(s, strictness=strictness)
        expected = next((o for o in case["outcomes"] if o["sentence"] == i and "error" in o), None)
        if expected:
            with pytest.raises(errors.ResolutionError) as e:
                resolve(ast, LEXICON, scope, strictness=strictness)
            assert e.value.as_dict() == expected["error"]
        else:
            resolve(ast, LEXICON, scope, strictness=strictness)


def test_profile_sentences_resolve():
    profile = json.loads((CONFORMANCE / "profile.json").read_text())
    scope = Scope()
    for s in profile.get("definitions", []):
        resolve(parse(s), LEXICON, scope)
    for c in profile["constraints"]:
        resolve(parse(c["source"]), LEXICON, scope)


def test_lexicon_loads_and_rejects_bad_patterns():
    import copy
    bad = copy.deepcopy(LEXICON.data)
    bad["verbs"]["be located in"]["pattern"] = {"kind": "field", "object": "title"}
    with pytest.raises(dictionary_module.DictionaryError):
        dictionary_module.load(bad)
    bad = copy.deepcopy(LEXICON.data)
    bad["verbs"]["have"]["dated"] = True
    with pytest.raises(dictionary_module.DictionaryError):
        dictionary_module.load(bad)
