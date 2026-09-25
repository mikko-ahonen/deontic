"""The corpus is data; these tests keep the data well-formed.

They do not parse or evaluate anything (there is no parser yet). They check
that every case file has the documented structure, that expected ASTs carry
only the documented node kinds, that reject codes and positions are
consistent with their sources, and that evaluate cases refer only to things
the fixture lexicon declares. Stdlib only, like the package.
"""

import json
import re
from pathlib import Path

import pytest

CONFORMANCE = Path(__file__).resolve().parent.parent / "conformance"
LEXICON = json.loads((CONFORMANCE / "lexicon.json").read_text())
SCHEMA = json.loads((CONFORMANCE / "ast.schema.json").read_text())
DICTIONARY_SCHEMA = json.loads((CONFORMANCE / "dictionary.schema.json").read_text())

SHAPES = {
    "term_definition", "reference_definition", "obligation", "conditional",
    "prohibition", "permission", "existence", "aggregate", "threshold",
    "cadence", "sequencing", "attestation", "disjunction", "pre_formal",
    "unconscious",
}
REJECT_CODES = {
    "undated_verb", "unmatched_marker", "empty_marker", "sigil_inside_marker",
    "unterminated_string", "unbalanced_parenthesis", "missing_period",
    "no_shape", "unresolved_anaphora", "unknown_term", "unknown_field",
    "not_a_reference", "unknown_tag", "type_mismatch", "unknown_verb",
    "object_kind_mismatch", "unknown_rubric", "confidence_requires_system",
}
POSITIONED = {
    "unmatched_marker", "empty_marker", "sigil_inside_marker",
    "unterminated_string", "unbalanced_parenthesis",
}
FILTER_OPS = {
    "and", "or", "tagged", "that", "is", "is_not", "contains", "starts_with",
    "ends_with", "at_least", "at_most", "more_than", "less_than", "before",
    "after", "is_one_of", "between", "is_empty", "is_not_empty", "equals",
}
UNITS = {
    "hour", "day", "week", "month", "quarter", "year",
    "calendar week", "calendar month", "calendar year", "percent",
}
SIGILS = "$@#<>"


def cases(sub):
    files = sorted((CONFORMANCE / sub).glob("*.json"))
    assert files, f"no cases under {sub}"
    return [pytest.param(json.loads(f.read_text()), id=f.stem) for f in files]


def walk(node):
    """Yield every dict in an expected result, depth first."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def assert_canonical(node, where):
    """No null / false / empty values anywhere (README, Canonical form)."""
    for d in walk(node):
        for k, v in d.items():
            assert v is not None and v is not False and v != [] and v != {}, \
                f"{where}: key {k!r} has a value the canonical form omits"


def assert_markers_balanced(source):
    """Every sigil opens a marker that closes; used for sources that must lex."""
    for open_m, close_m in (("$$", "$$"), ("$", "$"), ("@", "@"), ("#", "#"), ("<", ">")):
        stripped = source.replace("$$", "") if open_m == "$" else source
        if open_m == "$$":
            assert source.count("$$") % 2 == 0, source
        elif open_m == "<":
            assert source.count("<") == source.count(">"), source
        else:
            assert stripped.count(open_m) % 2 == 0, f"unbalanced {open_m!r} in {source!r}"


# --- parse ------------------------------------------------------------------------

@pytest.mark.parametrize("case", cases("parse"))
def test_parse_case_structure(case):
    assert set(case) <= {"source", "strictness", "note", "ast"}
    assert case["source"].endswith("."), "a sentence ends with a period"
    assert_markers_balanced(case["source"])
    ast = case["ast"]
    assert ast["shape"] in SHAPES
    assert_canonical(ast, case["source"])


@pytest.mark.parametrize("case", cases("parse"))
def test_parse_case_nodes(case):
    ast = case["ast"]
    for d in walk(ast):
        if "op" in d and "shape" not in d:
            assert d["op"] in FILTER_OPS | {"at_least", "at_most", "exactly", "between", "more_than", "less_than"}, d
        if "unit" in d:
            assert d["unit"] in UNITS, d
        if "path" in d and isinstance(d["path"], list):
            assert all(isinstance(p, str) and p for p in d["path"]), d
        if "term" in d:
            assert d["term"] == d["term"].strip() and "  " not in d["term"], d
            assert not any(s in d["term"] for s in SIGILS), d
        if "verb" in d:
            assert d["verb"] == d["verb"].lower(), "verbs are recorded lower-cased"


@pytest.mark.parametrize("case", cases("parse"))
def test_parse_case_matches_schema(case):
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(case["ast"], SCHEMA)


def test_parse_covers_every_shape():
    seen = {json.loads(f.read_text())["ast"]["shape"] for f in (CONFORMANCE / "parse").glob("*.json")}
    assert seen == SHAPES, f"shapes without a parse case: {SHAPES - seen}"


def test_parse_covers_every_filter_operator():
    seen = set()
    for f in (CONFORMANCE / "parse").glob("*.json"):
        for d in walk(json.loads(f.read_text())["ast"]):
            if "op" in d and "path" in d or d.get("op") in ("and", "or", "tagged", "that"):
                seen.add(d["op"])
    assert FILTER_OPS <= seen, f"filter operators without a case: {FILTER_OPS - seen}"


# --- reject -------------------------------------------------------------------------

@pytest.mark.parametrize("case", cases("reject"))
def test_reject_case_structure(case):
    assert set(case) <= {"source", "strictness", "lexicon", "note", "error"}
    err = case["error"]
    assert err["code"] in REJECT_CODES
    if err["code"] in POSITIONED:
        pos = err["position"]
        assert 0 <= pos < len(case["source"])
        assert case["source"][pos] in SIGILS + '"(' , \
            f"position {pos} does not point at the offending character: {case['source'][pos]!r}"
    if case.get("lexicon"):
        assert case["lexicon"] == LEXICON["name"]
    if "strictness" in case:
        assert case["strictness"] == "strict"


def test_reject_lexical_cases_need_no_lexicon():
    for f in (CONFORMANCE / "reject").glob("lexical-*.json"):
        case = json.loads(f.read_text())
        assert "lexicon" not in case and "strictness" not in case, f.name


def test_reject_resolve_cases_use_the_lexicon():
    for f in (CONFORMANCE / "reject").glob("resolve-*.json"):
        case = json.loads(f.read_text())
        assert case.get("lexicon") == LEXICON["name"], f.name


# --- evaluate --------------------------------------------------------------------------

def lexicon_names():
    names = set(LEXICON["types"])
    names |= {t["plural"] for t in LEXICON["types"].values()}
    for key in ("events", "cadences", "metrics", "attesters"):
        names |= set(LEXICON.get(key, {}))
    names |= {a["plural"] for a in LEXICON["attesters"].values() if "plural" in a}
    names |= {marked_terms(d)[0] for d in LEXICON.get("definitions", [])}
    return names


def marked_terms(sentence):
    return re.findall(r"\$\$?([^$]+?)\$\$?", sentence)


@pytest.mark.parametrize("case", cases("evaluate"))
def test_evaluate_case_structure(case):
    assert set(case) <= {"lexicon", "strictness", "as_of", "parameters", "note", "sentences", "world", "outcomes"}
    assert case["lexicon"] == LEXICON["name"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", case["as_of"])
    assert case["sentences"] and all(s.endswith(".") for s in case["sentences"])
    assert case["outcomes"], "an evaluate case states at least one outcome"
    for o in case["outcomes"]:
        assert 0 <= o["sentence"] < len(case["sentences"])
        if "error" in o:
            assert case.get("strictness") == "strict"
            assert o["error"]["code"] in REJECT_CODES
        else:
            assert o["outcome"] in ("satisfied", "violated", "skipped")
            if o["outcome"] == "skipped":
                assert o["reason"] in ("unknown_verb", "unsupported_verb", "unbound_parameter", "missing_value")
    assert_canonical(case["outcomes"], "outcomes")


@pytest.mark.parametrize("case", cases("evaluate"))
def test_evaluate_world_uses_the_lexicon(case):
    ids = set()
    for e in case["world"]["entities"]:
        assert set(e) <= {"id", "type", "tags", "fields"}
        assert e["id"] not in ids, f"duplicate id {e['id']}"
        ids.add(e["id"])
        t = LEXICON["types"][e["type"]]
        assert set(e.get("tags", [])) <= set(t.get("tags", [])), (e["type"], e.get("tags"))
        assert set(e["fields"]) <= set(t["fields"]), (e["type"], set(e["fields"]) - set(t["fields"]))
    for e in case["world"]["entities"]:
        t = LEXICON["types"][e["type"]]
        for k, v in e["fields"].items():
            kind = t["fields"][k]
            if isinstance(kind, dict) and kind["kind"] == "reference":
                assert v in ids, f"{e['id']}.{k} points at unknown id {v}"
    for r in case["world"].get("relations", []):
        decl = LEXICON["relations"][r["name"]]
        assert r["subject"] in ids and r["object"] in ids, r
        assert LEXICON["types"][next(e["type"] for e in case["world"]["entities"] if e["id"] == r["subject"])] and \
            next(e["type"] for e in case["world"]["entities"] if e["id"] == r["subject"]) in decl["from"], r
        assert next(e["type"] for e in case["world"]["entities"] if e["id"] == r["object"]) == decl["to"], r
    for a in case["world"].get("attestations", []):
        assert a["subject"] in ids
        assert a["attester"] in LEXICON["attesters"]
    for o in case["outcomes"]:
        for off in o.get("offenders", []):
            assert off in ids, f"offender {off} is not in the world"
        assert o.get("offenders", []) == sorted(o.get("offenders", [])), "offenders are sorted"


@pytest.mark.parametrize("case", cases("evaluate"))
def test_evaluate_sentences_name_only_declared_or_defined_things(case):
    defined = set()
    for s in case["sentences"]:
        terms = marked_terms(s)
        if " means any " in s or " refers to " in s:
            defined.add(terms[0])
            terms = terms[1:]
        for t in terms:
            assert t in lexicon_names() | defined, f"{t!r} is neither in the lexicon nor defined earlier in {s!r}"


def test_evaluate_covers_every_outcome():
    seen = set()
    for f in (CONFORMANCE / "evaluate").glob("*.json"):
        for o in json.loads(f.read_text())["outcomes"]:
            seen.add(o.get("outcome", "error"))
    assert seen == {"satisfied", "violated", "skipped", "error"}


# --- lexicon ------------------------------------------------------------------------------

def field_kind(f):
    return f if isinstance(f, str) else f["kind"]


def test_lexicon_matches_dictionary_schema():
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(LEXICON, DICTIONARY_SCHEMA)


def test_schemas_are_valid_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    jsonschema.Draft202012Validator.check_schema(DICTIONARY_SCHEMA)


def test_lexicon_references_point_at_declared_types():
    """Cross-references a JSON Schema cannot express."""
    types = LEXICON["types"]
    for name, t in types.items():
        for field, f in t["fields"].items():
            assert field_kind(f) in ("text", "number", "date", "boolean", "reference", "list"), (name, field)
            if field_kind(f) == "reference":
                assert f["to"] in types, (name, field, f["to"])
    for name, r in LEXICON.get("relations", {}).items():
        assert set(r["from"]) <= set(types) and r["to"] in types, name
    for name, ev in LEXICON["events"].items():
        assert field_kind(types[ev["type"]]["fields"][ev["field"]]) == "date", name
    for name, m in LEXICON["metrics"].items():
        assert m["of"] in types, name
    for name, v in LEXICON["verbs"].items():
        obj = v.get("object", "entity")
        assert obj in ("none", "entity") or obj in types, (name, obj)
        if "subject" in v:
            assert v["subject"] in types, (name, v["subject"])
    for a in LEXICON["attesters"].values():
        if a["kind"] != "system":
            assert "rubrics" not in a


def test_lexicon_names_are_declared_in_one_role_each():
    roles = []
    for name, t in LEXICON["types"].items():
        roles += [name, t.get("plural", name + "s")]
    for key in ("events", "cadences", "metrics", "attesters"):
        roles += list(LEXICON.get(key, {}))
    roles += [a["plural"] for a in LEXICON["attesters"].values() if "plural" in a]
    roles += [marked_terms(d)[0] for d in LEXICON.get("definitions", [])]
    dupes = {n for n in roles if roles.count(n) > 1}
    assert not dupes, f"declared in more than one role: {dupes}"


def test_lexicon_definitions_name_only_declared_things():
    known = lexicon_names()
    for d in LEXICON.get("definitions", []):
        assert d.endswith(".")
        for t in marked_terms(d)[1:]:
            assert t in known, (d, t)


# --- profile ------------------------------------------------------------------------------

PROFILE = json.loads((CONFORMANCE / "profile.json").read_text())
PROFILE_SCHEMA = json.loads((CONFORMANCE / "profile.schema.json").read_text())
PROFILE_DIGEST = json.loads((CONFORMANCE / "profile.digest.json").read_text())


def test_profile_matches_schema():
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator.check_schema(PROFILE_SCHEMA)
    jsonschema.validate(PROFILE, PROFILE_SCHEMA)


def test_profile_pins_the_fixture_dictionary():
    assert {"name": LEXICON["name"], "version": LEXICON["version"]} in PROFILE["dictionaries"]


def test_profile_constraint_ids_are_unique():
    ids = [c["id"] for c in PROFILE["constraints"]]
    assert len(ids) == len(set(ids))


def test_profile_groups_form_a_dag_and_are_declared():
    groups = PROFILE.get("groups", {})
    for c in PROFILE["constraints"]:
        assert set(c.get("groups", [])) <= set(groups), c["id"]
    for name, g in groups.items():
        assert set(g.get("includes", [])) <= set(groups), name

    def reaches(start, target, seen=()):
        for inc in groups[start].get("includes", []):
            if inc == target or (inc not in seen and reaches(inc, target, seen + (start,))):
                return True
        return False

    for name in groups:
        assert not reaches(name, name), f"group {name} includes itself"


def test_profile_parameters_declared_and_used():
    declared = set(PROFILE.get("parameters", {}))
    used = set()
    for c in PROFILE["constraints"]:
        used |= set(re.findall(r"<([^<>]+)>", c["source"]))
    for d in PROFILE.get("definitions", []):
        used |= set(re.findall(r"<([^<>]+)>", d))
    assert used <= declared, f"undeclared parameters: {used - declared}"
    assert declared <= used, f"declared but unused parameters: {declared - used}"


def test_profile_sentences_name_only_declared_or_defined_things():
    known = lexicon_names()
    for d in PROFILE.get("definitions", []):
        known.add(marked_terms(d)[0])
        for t in marked_terms(d)[1:]:
            assert t in known, (d, t)
    for c in PROFILE["constraints"]:
        for t in marked_terms(c["source"]):
            assert t in known, (c["id"], t)


def digest_input(profile):
    d = {
        "name": profile["name"],
        "version": profile["version"],
        "dictionaries": profile["dictionaries"],
        "constraints": sorted(
            [{"id": c["id"], "source": c["source"]} for c in profile["constraints"]],
            key=lambda c: c["id"]),
    }
    for k in ("strictness", "parameters", "definitions"):
        if k in profile:
            d[k] = profile[k]
    return d


def policy_digest(profile):
    import hashlib
    canon = json.dumps(digest_input(profile), sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()


def test_profile_digest_rule_is_reproducible():
    assert PROFILE_DIGEST["algorithm"] == "sha256"
    assert policy_digest(PROFILE) == PROFILE_DIGEST["digest"]


def test_profile_digest_ignores_prose_groups_refs_and_extensions():
    import copy
    p = copy.deepcopy(PROFILE)
    p["description"] = "changed"
    p["constraints"][0]["title"] = "changed"
    p["constraints"][0]["groups"] = []
    p["constraints"][0]["refs"] = [{"scheme": "x", "id": "y"}]
    p["groups"]["daily"]["title"] = "changed"
    p["extensions"] = {"other": {"k": 1}}
    assert policy_digest(p) == PROFILE_DIGEST["digest"]


def test_profile_digest_changes_with_source_dictionary_or_default():
    import copy
    for mutate in (
        lambda p: p["constraints"][0].__setitem__("source", p["constraints"][0]["source"].replace("fragile", "featured")),
        lambda p: p["dictionaries"][0].__setitem__("version", "2"),
        lambda p: p["parameters"]["maximum humidity"].__setitem__("default", 60),
        lambda p: p["definitions"].pop(),
    ):
        p = copy.deepcopy(PROFILE)
        mutate(p)
        assert policy_digest(p) != PROFILE_DIGEST["digest"]


# --- patterns (docs/hooks.md) ------------------------------------------------------------

def test_every_pattern_names_real_fields_and_types():
    types = LEXICON["types"]
    for name, v in LEXICON["verbs"].items():
        p = v.get("pattern")
        if p is None:
            assert "dated" in v, f"hook verb {name} must declare dated"
            continue
        assert "dated" not in v, f"{name}: a verb is data or code, never both"
        if p["kind"] == "field":
            subj = types[v["subject"]]["fields"]
            if "object" in p:
                assert field_kind(subj[p["object"]]) == "reference" and subj[p["object"]]["to"] == v["object"], name
            if "at" in p:
                assert field_kind(subj[p["at"]]) == "date", name
        elif p["kind"] == "record":
            via = types[p["via"]]["fields"]
            assert field_kind(via[p["subject"]]) == "reference" and via[p["subject"]]["to"] == v["subject"], name
            if p.get("object") not in (None, "self"):
                assert field_kind(via[p["object"]]) == "reference" and via[p["object"]]["to"] == v["object"], name
            if p.get("object") == "self":
                assert v["object"] == p["via"], name
            if "at" in p:
                assert field_kind(via[p["at"]]) == "date", name
        elif p["kind"] == "relation":
            r = LEXICON["relations"][p["name"]]
            assert v["subject"] in r["from"] and v["object"] == r["to"], name
        elif p["kind"] == "reference":
            assert v.get("object", "entity") == "entity", name
    for name, m in LEXICON["metrics"].items():
        p = m["pattern"]
        if p["kind"] == "field":
            assert field_kind(types[m["of"]]["fields"][p["name"]]) == "number", name
        else:
            via = types[p["via"]]["fields"]
            assert field_kind(via[p["subject"]]) == "reference" and via[p["subject"]]["to"] == m["of"], name
            if "at" in p:
                assert field_kind(via[p["at"]]) == "date", name
            if "value" in p:
                assert field_kind(via[p["value"]]) == "number", name


def test_time_expressions_in_cases_use_dated_verbs():
    """The undated_verb rule, checked over the parse and evaluate sources."""
    verbs = LEXICON["verbs"]

    def is_dated(name):
        v = verbs.get(name)
        if v is None:
            return True  # unknown verb: not this test's concern
        return v.get("dated", False) if "pattern" not in v else "at" in v["pattern"]

    time_words = ("within the last", "within #", "before $", "after $", "after the $")
    sources = [c["source"] for c in (json.loads(f.read_text()) for f in (CONFORMANCE / "parse").glob("*.json"))]
    sources += [s for f in (CONFORMANCE / "evaluate").glob("*.json") for s in json.loads(f.read_text())["sentences"]]
    for src in sources:
        for part in src.split(" or must "):
            for verb in re.findall(r"@([^@]+)@", part):
                if any(w in part for w in time_words) and " must be attested" not in part and " must occur " not in part:
                    assert is_dated(verb), f"time expression on undated verb {verb!r}: {src}"


def test_hooks_module_is_the_contract():
    import deontic
    from deontic import hooks
    assert deontic.ENTRY_POINT_GROUP == hooks.ENTRY_POINT_GROUP == "deontic.lexicons"
    w = hooks.Witness(object="x1", at=None, via="l1")
    assert (w.object, w.at, w.via) == ("x1", None, "l1")
    assert not hooks.dated(lambda s, w, c: [])
    hook = lambda s, w, c: []  # noqa: E731
    hook.dated = True
    assert hooks.dated(hook)
