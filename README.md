# deontic

A constraint language for **obligation**, **permission** and **prohibition** —
the things a system must do, may do, and must not do.

> **Status: planning.** This repository carries the packaging, the release
> pipeline, the design and the conformance corpus. The grammar, AST and
> parser are not implemented yet. It is published so the name and the corpus
> are stable for implementers; do not depend on it for behaviour yet.

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

## Install

```bash
pip install deontic
```

Stdlib only, no runtime dependencies — a grammar meant to be implemented by
other people should not put a parser generator in everyone's dependency tree.

## License

MIT.
