# Conformance corpus

The normative test data for the language: each case is source text plus the
result every implementation must agree on. An implementation is conformant
when it reproduces these, which is what lets the private evaluator and any
outside implementation claim to speak the same language.

Kept as data rather than as Python tests on purpose: an implementation in
another language has to be able to consume it. Nothing here says *how* to
parse or evaluate.

## Layout

    conformance/
      dictionary.schema.json   JSON Schema for a dictionary, a lexicon's data half
      lexicon.json             the fixture dictionary every case that needs one uses
      ast.schema.json          JSON Schema for the `ast` of a parse case
      parse/*.json        source → expected AST (no lexicon needed)
      reject/*.json       source → the error it must be rejected with
      evaluate/*.json     sentences + world + evaluation date → outcomes

One JSON file per case; the file name is the case id. Files are grouped by
prefix (`definition-`, `filter-`, `obligation-`, `existence-`, `lexical-`,
`resolve-`, …) and nothing depends on the order.

The fixture lexicon is a museum: exhibits, galleries, curators, loans. It is
invented and deliberately dull. It exists so that every construct can be
exercised once, not to model anything; do not read domain intent into it.
It conforms to `dictionary.schema.json` and is the first dictionary written
against it.

## Dictionary

A dictionary is the data half of a lexicon: the names a sentence may use and
what kind of thing each is. `dictionary.schema.json` is normative. Its
sections, all keyed by the name as written inside a marker:

- `types` — entity types with `plural`, `fields` and a closed `tags` set. A
  field is a scalar kind (`text`, `number`, `date`, `boolean`), a
  `reference` to another type, or a `list` of a scalar kind; it may be
  `optional`, and a text field may list its closed `values`.
- `relations` — named many-to-one relations recorded as triples rather than
  as a field, with the subject types they hold `from`, the type they point
  `to`, and the word the possessive uses (`as`).
- `verbs` — declarations with `synonyms`, the required `subject` kind, the
  `object` kind (`none`, `entity`, or a type or term) and a prose
  `description` of what the verb means over recorded state. The
  description is not consumed by an implementation; it is what lets a
  second implementation reproduce the first's outcomes.
- `events` (type plus date field), `cadences` (value plus unit), `metrics`
  (the type they are `of`, a `unit`), and `attesters` (`person`, `role` or
  `system`; a system carries its `rubrics` by id, each with a `version` and
  a `claim`).
- `definitions` — term and reference sentences shipped with the dictionary.
- `imports` — other dictionaries by name and version; names resolve across
  all of them and a name declared twice is an error.

**Paths.** A possessive step from a type is either one of its `reference`
fields, or a relation whose `from` includes the type, addressed by its `as`
word. `not_a_reference` is the error for any other field. Traversal through
a `list` field is not fixed by any case and is therefore not in the language.

**Names.** A marked name must be declared in exactly one role: type, plural
of a type, defined term or reference, event, cadence, metric, or attester
(or its plural). `unknown_term` is the error otherwise. A dictionary's
`name` and `version` are what a policy digest pins; within a major version,
changes only add.

## Canonical form

Every JSON object in an expected result omits keys whose value is `null`,
`false`, an empty list or an empty object. An implementation produces its
result, drops the same keys, and compares for plain JSON equality. Strings
inside markers keep their case and have surrounding whitespace stripped and
internal whitespace collapsed to one space; keywords are matched
case-insensitively and never appear in the AST.

## Case formats

### parse

    { "source": "...", "note": "...", "ast": { "shape": "...", ... } }

`strictness` is `"permissive"` unless given. The AST is described by
`ast.schema.json`; the shapes are the ones in `docs/design.md` §6 with these
naming decisions:

| Design §6 | `shape` |
|---|---|
| universal obligation, direct obligation | `obligation` (`subject.every` distinguishes them) |
| conditional | `conditional` |
| prohibition | `prohibition` (`form`: `no_may` or `must_not`) |
| permission | `permission` |
| existence | `existence` |
| aggregate | `aggregate` |
| threshold | `threshold` |
| cadence | `cadence` |
| sequencing | `sequencing` |
| attestation | `attestation` |
| disjunction | `disjunction` |
| definition | `term_definition`, `reference_definition` |
| pre-formal (§5) | `pre_formal` with the typed `fragments` |
| unconscious (§5) | `unconscious` |

Parsing needs no lexicon. Names inside markers are recorded as written; the
parser does not know whether `$exhibit$` is a type, a term, a reference, an
event, a cadence, a metric or an attester. Resolution does, with the lexicon.

### reject

    { "source": "...", "strictness": "strict", "lexicon": "museum",
      "note": "...", "error": { "code": "...", ... } }

`lexicon` present means the error is found at resolution against
`lexicon.json`; absent means the error is found from the source alone.
`strictness` present means the error occurs only in that setting; absent
means both. The codes:

| Code | When | Extra keys |
|---|---|---|
| `unmatched_marker` | an opening sigil with no close; there is no escape syntax | `position` |
| `empty_marker` | a marker whose content is blank | `position` |
| `sigil_inside_marker` | markers do not nest | `position` |
| `unterminated_string` | a `"` with no closing `"` | `position` |
| `unbalanced_parenthesis` | | `position` |
| `missing_period` | a sentence ends with `.` in both settings | |
| `no_shape` | strict only; marked text matching no shape (permissive: `pre_formal`) | |
| `unresolved_anaphora` | `the <noun>` with no antecedent agreeing in number (rule 4) | `noun` |
| `unknown_term` | a marked name the lexicon does not declare in any role | `term` |
| `unknown_field` | a filter on an undeclared field (rule 7) | `type`, `field`, `suggestion` when a near match exists |
| `not_a_reference` | the possessive applied to a field that is not a reference | `type`, `field` |
| `unknown_tag` | a tag outside the type's closed set | `type`, `tag` |
| `type_mismatch` | an operator that does not apply to the field's kind | `type`, `field`, `expected`, `actual` |
| `unknown_verb` | strict only; a marked verb the lexicon does not declare (permissive: skipped) | `verb` |
| `object_kind_mismatch` | the object is not of the kind the verb declaration takes | `verb`, `expected`, `actual` |
| `unknown_rubric` | a bare claim naming no rubric declared next to the attester | `attester`, `rubric` |
| `confidence_requires_system` | a confidence threshold on an attester that is not a designated system | `attester` |

`position` is the 0-based character offset into `source`.

### evaluate

    { "lexicon": "museum", "as_of": "YYYY-MM-DD", "parameters": {...},
      "sentences": ["...", ...],
      "world": { "entities": [...], "attestations": [...] },
      "outcomes": [ { "sentence": i, "outcome": "...", ... }, ... ] }

`sentences` are parsed and resolved together, in order, so definitions
precede the constraints that use them. `outcomes` lists one entry per
*constraint* sentence, by index; definitions produce none. An entry is one
of:

    { "sentence": i, "outcome": "satisfied" }
    { "sentence": i, "outcome": "violated", "offenders": ["id", ...], "counts": {...} }
    { "sentence": i, "outcome": "skipped", "reason": "...", ... }
    { "sentence": i, "error": { "code": "...", ... } }          (strict only)

`offenders` are entity ids of the subject entities for which the predicate
does not hold, sorted. `counts` is present where the shape counts (existence,
aggregate, threshold, minimum attesters) and its keys are given per case.
`reason` is `unknown_verb` (permissive) or `unbound_parameter`.

The world is the closed world. Entities are `{id, type, tags, fields}`;
reference fields hold an entity id; dates are ISO calendar dates. Attestations
are `{subject, attester, claim, date, confidence?, system?, attester_id?}`,
where `attester` names an attester kind from the lexicon. A reference field
holds the id of the entity it points at; a relation from the dictionary's
`relations` section may be given the same way, as a field of the subject
named by the relation's `as` word. What each lexicon verb and metric means
over this world is stated in prose in `lexicon.json` under `description`,
which is what makes the expected outcomes reproducible.

Time windows are half-open: `within the last year` as of D covers
(D − 1 year, D]. `per calendar month` is the calendar month containing D.
`every <period>` is judged as "an occurrence exists within the last period".

**The outcome rule.** An implementation that does not support a construct a
case uses must answer `skipped` for that sentence. Answering `satisfied`
where the corpus expects `violated` or `skipped` is non-conformance;
answering `skipped` where the corpus expects `satisfied` or `violated` is
incomplete support, which the harness reports separately. A check that
cannot fail must not report success.

## Decisions the corpus fixes

These were open in `docs/design.md` §16 or unstated; the cases settle them.

1. **Parameter sigil** is `<name>`; the parser records `{"parameter": name}`
   wherever a value or quantity may stand. A parameter with no binding at
   evaluation time skips with `unbound_parameter`.
2. **Path notation** is the possessive: `lender's type` is `["lender", "type"]`.
   Each step must be a reference field. There is no dotted form.
3. **`self` is not in the core.** Nothing in the fixture or the two lexicons
   the language is being built for needs a bound subject inside a filter.
   Rule of two: it waits for the second lexicon that does.
4. **The closed class**, as exercised here: `every`, `no`, `only`, `at
   least`, `at most`, `exactly`, `more than`, `less than`, `between … and`,
   `zero or one`, `one or more`, the number words one to ten, `percent`;
   `must`, `may`, `must not`; `means any`, `refers to`, `the latest`,
   `ordered by`; `tagged`, `where`, `that`, `is`, `is not`, `equals`,
   `contains`, `starts with`, `ends with`, `is one of`, `is empty`, `is not
   empty`, `is true`, `is false`, `exactly` (as a comparison modifier),
   `today`; `within the last`, `within … after`, `within … before`,
   `before`, `after`, `every`, `per`, `occur`; `exist`, `be tagged`;
   `attested by`, `claiming`, `with confidence at least`, `or by`; `in scope
   of`; `if … then`, `and`, `or`, `either … or`, `the`, `a`, `an`, `of`, the
   possessive `'s`; and the period units `hour`, `day`, `week`, `month`,
   `quarter`, `year`, `calendar week`, `calendar month`, `calendar year`.
   Words listed in the design but with no case here (`the approved`,
   `evidenced by`, `on`) are not part of the language until a case exists.
5. **`that <verb> <object>`** is a filter atom: a lexicon predicate used as a
   filter, the only way to reach a reverse relation. The verb inside is a
   marked lexicon verb, so the sentence still validates against the lexicon
   files alone.
6. **`be tagged <tags>`** is a core predicate, the predicate form of the
   `tagged` filter, unmarked because it is not a lexicon verb.
7. **Markers** are required on lexicon names (`$…$`, `$$…$$`), on lexicon
   verbs (`@…@`), on quantities with a unit (`#…#`) and on parameters
   (`<…>`). Bare numbers, number words, period words, tags, field paths and
   quoted strings are never marked. A bare period word is a quantity of one:
   `year` is `#1 year#`.
8. **Only `and` continues a tag list** (`tagged mandatory and safety`); after
   `or` a new filter atom must start. A word after `and` that is followed by
   a filter operator starts a field path instead.
9. **`equals`** compares two fields of the same entity; `is` compares a
   field with a value. `exactly` before a text value makes the comparison
   case-sensitive and is a flag on the comparison, not a node.
10. **`No … may exist`** is the existence shape with cardinality exactly
    zero. A count prefix with a lexicon verb is an aggregate; with `exist` it
    is existence.
11. **Anaphora is resolved within the sentence.** Constraints are evaluated
    on their own, so `the <noun>` never reaches into another sentence.
12. **A sentence ends with a period** in both strictness settings; a decimal
    point inside a number is not a terminator.
13. **Attesters may be listed as alternatives** with `or by`, each with its
    own claim and confidence. A quoted claim is text; a bare claim is a
    rubric id, which must be declared next to a designated-system attester.
14. **Units normalise to the singular** (`days` → `day`); `calendar month`
    is a unit of its own, distinct from `month`, because windows align to
    the calendar and durations do not.
15. **There is no `unless`.** An exception clause was considered and
    declined: §3 of the design keeps waivers and exceptions in the
    application, §15 says a waiver is a recorded decision and not a norm,
    and no lexicon has needed one in data (the one request, a source-level
    suppression, is honoured by the application that renders verdicts:
    the rule fires, its offenders are matched against recorded suppression
    facts, and the match is shown as a waiver, the way a static-analysis
    server marks an issue accepted rather than teaching its rules to skip).
    If a second lexicon needs an exception clause, that is the signal for a
    sibling package with its own evaluator, not for entry into the core.

## Coverage

The parse cases cover every shape in §6, every filter operator in §7, every
time form in §8, the attestation options in §9, the storage-form markers in
§10, and interpretation rules 1, 3, 4, 5, 6 and 7 of §11 by name in their
notes. The reject cases cover the lexical errors, the strict setting, rule
4 and rule 7. The evaluate cases cover each outcome of §12 including the
two rules that protect "satisfied", and one case per shape whose meaning
depends on the evaluation date.
