# Verbs and metrics — what a lexicon supplies at evaluation time

Normative, like the corpus. `docs/design.md` §2 says a verb is declared as
data so that a sentence can be validated with nothing but the lexicon files,
and that what a verb *means* at evaluation time is the implementation's
concern. This document fixes the boundary: the smallest thing a lexicon has
to supply for an implementation to evaluate its verbs and metrics, in a form
that does not presume how the implementation evaluates.

## 1. The division of labour

The core owns every closed-class word. Given a predicate `@verb@ <object>
[time]` on a subject, the core decides quantification, the object's filter
and cardinality, the time expression, aggregation, disjunction and the
outcome. The lexicon supplies one thing per verb: **which witnesses exist**.

A **witness** is a record that a verb holds of a subject: at most one
*object* entity, at most one *date*, and the *via* entity that carries the
evidence when there is one. Everything the core does with a predicate is
defined over the subject's witnesses:

| The sentence says | The core checks, as of the evaluation date |
|---|---|
| `must @verb@` | at least one witness exists |
| `must @verb@ a $T$ [filter]` | a witness exists whose object is a `T` matching the filter |
| `must @verb@ at least N $T$` | at least N distinct such objects |
| `… within the last D` | a qualifying witness whose date lies in (as-of − D, as-of] |
| `… within D after $E$` | a qualifying witness dated in (E, E + D], where E is the subject's event |
| `… before $E$` / `after $E$` | a qualifying witness dated before / after E |
| `… every P` (cadence) | a qualifying witness dated within the last P |
| `No … may @verb@ …` / `must not` | no qualifying witness exists |
| aggregate `N percent of` | the share of subjects for which the predicate holds |

A time expression needs dated witnesses. A verb whose witnesses carry no
date is **undated**; applying a time expression to it is a resolution
error, `undated_verb`, never a silent pass.

The core's own predicates, `@exist@` and `be tagged`, have no witnesses:
they are closed-class, a dictionary does not declare them, and the core
evaluates them directly.

## 2. Patterns: verbs as data

Most verbs are a path through the recorded world, and a path can be
declared. A verb declaration in the dictionary may carry a `pattern`, one of
four kinds. A pattern is complete: an implementation of any kind, including
one that compiles constraints to queries, evaluates a patterned verb with no
code from the lexicon.

**`field`** — the witness is on the subject itself.

    {"kind": "field", "object": "gallery", "at": "returned on"}

The object, if any, is the entity the subject's reference field `object`
points at; the date, if any, is the subject's date field `at`. A witness
exists when every named field is set. With neither key the pattern is
meaningless and rejected.

**`record`** — the witness is another record that points back at the subject.

    {"kind": "record", "via": "completion", "subject": "curator",
     "object": "course", "at": "completed on", "where": "course's status is active"}

One witness per record of type `via` whose reference field `subject` is the
subject. Its object is the via record's reference field `object`, or the via
record itself when `object` is `"self"`, or nothing when `object` is absent.
Its date is the via record's date field `at`, if given. `where` is a filter
in the language's own filter sub-language over the via record, applied
before the witness is produced; it may use the possessive.

**`relation`** — the witness is a relation triple.

    {"kind": "relation", "name": "located_in"}

One witness per triple of that name whose subject is the subject; the object
is the triple's object. Relations are undated. With `"direction":
"reverse"` the subject is matched against the triple's object and the
witness's object is the triple's subject.

**`reference`** — the generic *have*.

    {"kind": "reference"}

The object type is taken from the sentence. A witness exists for every
entity of that type reachable from the subject by a declared reference field
or relation in either direction, one step. Undated. This is the pattern for
a verb like `have`, whose meaning is the dictionary's own structure.

A verb's `subject` and `object` declarations are checked against its
pattern at dictionary load: a `field` pattern's `object` field must be a
reference to the declared object type, a `record` pattern's `via` type must
have the named fields, and so on. The dictionary is invalid otherwise.

## 3. Metrics as data

A metric declaration may carry a `pattern` of two kinds.

**`field`** — `{"kind": "field", "name": "condition score"}`: the subject's
number field, as of the evaluation date. A missing field makes the
constraint skip with `missing_value`.

**`aggregate`** — over records that point at the subject:

    {"kind": "aggregate", "via": "reading", "subject": "gallery",
     "at": "measured on", "value": "humidity", "function": "mean",
     "where": "device's status is active"}

`function` is one of `count`, `sum`, `mean`, `min`, `max`, or `share`. The
via records are those whose reference field `subject` is the subject,
filtered by `where` if given, and, when the threshold has a window,
restricted to those whose date field `at` falls in it. `count` needs no
`value`; `share` needs a `where` and reports the percentage of the
subject's via records in the window that match it (the denominator is the
unfiltered set). An empty set makes `mean`, `min` and `max` skip with
`missing_value`; `count` and `sum` are 0; `share` skips.

## 4. Hooks: verbs as code

A verb with no pattern is a **hook verb**. The corpus supplies no code, so
in the corpus a hook verb's constraint is `skipped` with reason
`unsupported_verb`. Outside the corpus, a lexicon may ship code for it, and
an implementation that can run that code evaluates it; one that cannot
skips it the same way. Skipping is the contract that lets a query-compiling
implementation and a record-walking one agree on every outcome they both
produce.

The code is a callable with this signature, in whatever language the
implementation runs; `deontic.hooks` gives the Python form:

    hook(subject, world, context) -> iterable of Witness

- `subject` is the entity being judged: its id, type, tags and fields.
- `world` is read access to the closed world: entities by id and by type,
  relations by name, attestations. It is the same world the evaluate cases
  give, and nothing else: a hook that reaches outside it is not a deontic
  hook.
- `context` carries the evaluation date and the bound parameters, and the
  verb's declaration.
- Each `Witness` has `object` (an entity id or `None`), `at` (a date or
  `None`) and `via` (an entity id or `None`).

A hook declares itself `dated` or not; the same `undated_verb` rule applies.
A hook is pure: same subject, world and context, same witnesses. It sees no
sentence, no object filter and no time expression; those are the core's, and
the core applies them to what the hook returns. That is what keeps a verb's
meaning independent of every sentence that uses it.

Python lexicons register hooks under the entry-point group
`deontic.lexicons`. The entry point is named after the dictionary and
resolves to an object with a `hooks` mapping from verb name to callable.
A hook for a verb the dictionary declares with a pattern is an error: a verb
is data or code, never both.

## 5. What this fixes

- A lexicon is validated, and mostly evaluated, from its files alone. The
  museum fixture has no hooks; every one of its verbs and metrics is a
  pattern, and every expected outcome in the corpus follows from the
  patterns and this document without prose.
- The core never learns a domain. A verb's meaning is a path or a witness
  set; the words around it are the language's.
- Adding a backend adds no lexicon work for patterned verbs, and the
  set of constraints a backend cannot evaluate is exactly the set that uses
  hook verbs, reported as skipped.
