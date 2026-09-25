# deontic

A constraint language for **obligation**, **permission** and **prohibition** —
the things a system must do, may do, and must not do.

> **Status: alpha.** The grammar is implemented and reproduces the whole
> conformance corpus: `deontic.parse` gives the AST, `deontic.load` reads a
> dictionary and `deontic.resolve` checks a sentence against it. There is no
> evaluator in this package, by design; the corpus's `evaluate/` cases are
> for implementations that add one.

## Why a language rather than a library

Deontic statements are usually buried in imperative checks, where the rule and
the enforcement of the rule are the same code. Writing them down as data makes
them reviewable by the people who own the policy rather than only by the people
who own the codebase, and lets more than one evaluator agree on what a rule
means.

## Design

[docs/design.md](docs/design.md) states what the language is meant to be:
the closed-class vocabulary, the shapes, filters and paths, attestation,
the storage form, the interpretation rules, the outcome model, and how it
relates to Attempto Controlled English and to deontic logic.

## Conformance

`conformance/` is the normative test data: source text plus the result every
implementation must agree on, kept as data rather than Python tests so that an
implementation in another language can consume it too. An implementation is
conformant when it reproduces the corpus. It has three parts — `parse/`
(source to AST, no lexicon needed), `reject/` (source to error) and
`evaluate/` (sentences, a world and a date to outcomes) — over one invented
fixture lexicon, and its README records the language decisions the cases fix.

## Use

```python
import deontic

ast = deontic.parse("Every $exhibit$ tagged fragile must @be located in@ a $gallery$ tagged storage.")
# {'shape': 'obligation', 'subject': {...}, 'predicate': {...}}

lexicon = deontic.load("conformance/lexicon.json")
deontic.resolve(ast, lexicon)   # raises a ResolutionError with the corpus's error code otherwise
```

Sentences are authored as English and stored with markers on the typed
spans (`$Term$`, `@verb@`, `#90 days#`, `<parameter>`); editors write the
markers, people do not. A verb's meaning is a `pattern` in the dictionary
or, failing that, code under the contract in [docs/hooks.md](docs/hooks.md).

## Install

```bash
pip install deontic
```

Stdlib only, no runtime dependencies — a grammar meant to be implemented by
other people should not put a parser generator in everyone's dependency tree.

## License

MIT.
