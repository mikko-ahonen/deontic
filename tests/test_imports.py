"""Dictionary composition: `imports` (dictionary.schema.json: "Names are
resolved across all of them; a name declared twice is an error")."""

import json
from pathlib import Path

import pytest

import deontic
from deontic import DictionaryError

LEXICON = json.loads((Path(__file__).resolve().parents[1] / "conformance" / "lexicon.json").read_text())


def split_lexicon():
    """The fixture lexicon cut in two: a base with every type, relation and
    event, and an extension with the verbs, cadences, metrics, attesters and
    definitions that importing the base."""
    base = {k: LEXICON[k] for k in ("types", "relations", "events") if k in LEXICON}
    base.update(name="museum-core", version="1")
    ext = {k: LEXICON[k] for k in ("verbs", "cadences", "metrics", "attesters", "definitions") if k in LEXICON}
    ext.update(name="museum", version="1", imports=[{"name": "museum-core", "version": "1"}])
    return base, ext


def test_imports_compose_into_the_same_dictionary():
    base, ext = split_lexicon()
    composed = deontic.load(ext, imports={("museum-core", "1"): base})
    whole = deontic.load(LEXICON)
    assert composed.roles == whole.roles
    assert composed.types == whole.types
    assert composed.verbs == whole.verbs
    assert composed.data["definitions"] == whole.data.get("definitions", [])


def test_a_resolver_callable_is_accepted():
    base, ext = split_lexicon()
    asked = []

    def resolve(name, version):
        asked.append((name, version))
        return base
    deontic.load(ext, imports=resolve)
    assert asked == [("museum-core", "1")]


def test_imports_without_a_resolver_is_an_error():
    _, ext = split_lexicon()
    with pytest.raises(DictionaryError, match="museum-core"):
        deontic.load(ext)


def test_a_name_declared_twice_is_an_error():
    base, ext = split_lexicon()
    ext = dict(ext, types={"gallery": base["types"]["gallery"]})
    with pytest.raises(DictionaryError, match="gallery"):
        deontic.load(ext, imports={("museum-core", "1"): base})


def test_import_cycles_are_an_error():
    a = {"name": "a", "version": "1", "types": {}, "imports": [{"name": "b", "version": "1"}]}
    b = {"name": "b", "version": "1", "types": {}, "imports": [{"name": "a", "version": "1"}]}
    with pytest.raises(DictionaryError, match="cycle"):
        deontic.load(a, imports={("a", "1"): a, ("b", "1"): b})


def test_a_dictionary_without_imports_loads_as_before():
    assert deontic.load(LEXICON).roles
