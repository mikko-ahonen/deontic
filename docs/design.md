# deontic — language design

**Status:** planning; the [conformance corpus](../conformance/README.md)
exists and is the specification. This document states what the language is
meant to be; the grammar, AST and parser are not implemented yet. When they
are, the corpus is the test and this document is the rationale. Where the
two disagree, the corpus wins and this document is wrong. Nothing here describes an evaluator: how a conformant
implementation computes results is its own business.

## 1. What it is

deontic is a controlled English for constraints that **judge recorded
state**: sentences that say what must, may, and must not be true of a closed
world of typed, tagged entities with fields, and that an implementation can
decide — satisfied, violated with the offending entities, or skipped with a
reason.

```
Every employee must have completed Basic Security Training within the last year.
No document tagged draft may be distributed to a customer.
The availability of Payment Service must be at least 99.9 percent per calendar month.
At least one Incident Manager must exist.
Current Security Policy must be attested by a Top Management Profile every year.
```

Its natural domain is **non-functional requirements**: qualities of something
that exists, measured against what has been recorded. Availability, latency,
coverage, currency, review cadence, completeness. A service, a codebase, a
management system and a contract are four subjects of the same kind of
sentence. Behaviour — what should happen, in what order, with what inputs —
is out of scope on purpose.

## 2. Core and lexicon

The core is a grammar with **closed-class words** and no vocabulary of its
own: a grammar with function words and no content words, which is a language
you cannot say anything in. The closed class, in full, is what defines the
core:

- quantifiers and cardinality: `every`, `no`, `only`, `at least one`,
  `exactly one`, `zero or one`, `one or more`, `at least N`, `at most N`,
  `exactly N`, `between N and M`, the number words one to ten, `percent`;
- modals: `must`, `may`, `must not`;
- selection: `the latest`, `ordered by`;
- filters: `tagged`, `where`, `that`, `is`, `is not`, `equals`, `contains`,
  `starts with`, `ends with`, `is one of`, `is empty`, `is not empty`, `is
  true`, `is false`, `is at least`, `is at most`, `is more than`, `is less
  than`, `is between … and`, `is before`, `is after`, `exactly`, `today`;
- time: `within the last`, `within … after`, `within … before`, `every`,
  `before`, `after`, `per`, `occur`, and the period units `hour`, `day`,
  `week`, `month`, `quarter`, `year`, `calendar week`, `calendar month`,
  `calendar year`;
- definition: `means any`, `refers to`;
- core predicates: `exist`, `be tagged`;
- evidence: `attested by`, `or by`, `claiming`, `with confidence at least`;
- scope: `in scope of`;
- connectives and anaphora: `and`, `or`, `either … or`, `if … then`, `the
  <noun>`, `a`, `an`, `of`, the possessive `'s`.

This is the list the corpus fixes (its README, *Decisions*, item 4). Words
that earlier drafts listed but no case exercises — `the approved`,
`evidenced by`, `on` — are not in the language.

A word not on this list is lexicon. A **lexicon** makes the core usable by
supplying:

- **entity types, fields, tags, terms and references** — data;
- **verbs** — declared as data (name, synonyms, what kind of object each
  takes), so that a sentence can be validated with nothing but the lexicon
  files; what a verb means at evaluation time is a **pattern** in the same
  declaration (a path through the recorded world that any implementation
  can follow) or, when no pattern can express it, code the lexicon ships
  under the witness contract in [`hooks.md`](hooks.md);
- **event anchors** for time expressions ("within 30 days after the
  incident" needs the lexicon to say what an incident's date is);
- **named cadences** that time windows may reference instead of literal
  periods ("every review period");
- **attester kinds** and, for designated-system attesters, the **rubrics**
  they judge under (§9);
- **a strictness setting** — *permissive*: an unknown verb parses and the
  constraint is reported as skipped, so precision can increase over time;
  *strict*: anything unrecognised is an error, for domains that must fail
  closed.

A language is the core plus one lexicon. The core ships with none. The data
half of a lexicon is a **dictionary**, whose file format is
`conformance/dictionary.schema.json`; the museum fixture in the corpus is
the first dictionary written against it. Constraints are evaluated together
as a **profile** (`conformance/profile.schema.json`): sentences with stable
ids, written against pinned dictionaries, taking declared parameters, and
grouped by names whose meaning belongs to the application.

## 3. What the core refuses

Permanently, not for now:

- **actions and effects** — no "then do X", no remediation, no enforcement;
- **computation** — comparison against a quantity, counts and percentages,
  nothing more; arithmetic is a metric the lexicon names, not the sentence;
- **control flow and variables** — anaphora ("the employee") and, at most,
  a `self` binding; nothing else;
- **data definition** — a lexicon is a vocabulary, not a schema;
- **workflow and state** — approvals, versions, waivers and exceptions live
  in the application that uses the language.

The result is a language that can only judge. That is the property that
keeps it small.

## 4. Governance: the rule of two

A construct enters the core when a **second** lexicon needs it, and stays in
the lexicon that invented it until then. Domain-flavoured vocabulary that
looks general — "framework clause", "audit period", "release" — is the usual
candidate for mistaken promotion.

## 5. Terminology

Sentences are not formal or informal; they are on a gradient, and the
language is designed so that a document can sit anywhere on it.

- **Unconscious** — plain prose. The implementation cannot see it.
- **Pre-formal** — *marked*: terms and quantities are typed but no shape is
  recognised. One step from evaluation.
- **Formal** — shaped and evaluable.
- **Attested** — formal about its confirmation, unconscious about its
  content: a claim no data can decide, reduced to "a current attestation by
  an authorised attester exists".
- **Semi-formal** — a document mixing those states.

The process is *incremental formalization* (Shipman & McCall, 1994), with
its standing caution (Shipman & Marshall, *Formality Considered Harmful*,
1999): forcing structure before people understand the content drives them
away, so formalization must be optional, gradual and reversible. The
pre-formal state is a product feature, not a transition.

## 6. Shapes

Every sentence is one of a small set of shapes, each carrying a modal:

| Shape | Form |
|---|---|
| definition | `<Term> means any <type> [filter].` · `<Reference> refers to <selection> <type> [filter] [ordered by …].` |
| universal obligation | `Every <term> must <predicate>.` |
| direct obligation | `<Reference> must <predicate>.` |
| conditional | `If <condition>, then <subject> must <predicate>.` |
| prohibition | `No <term> may <predicate>.` · `<subject> must not <predicate>.` |
| permission | `Only <term> may <predicate>.` |
| existence | `At least one <term> must exist.` · `Exactly one …` · `No … may exist.` |
| aggregate | `At least N percent of <term> [in scope of <term>] must <predicate>.` |
| threshold | `The <metric> of <subject> must be at least <quantity> [per <window>].` |
| cadence | `<subject> must <verb> a <target> every <period>.` |
| sequencing | `<event> must occur within <duration> after <event>.` |
| attestation | `<subject> must be attested by [at least N] <attester> [claiming "<text or rubric-id>"] [with confidence at least <n>] every <period>.` |
| disjunction | `<subject> must <predicate> or must <predicate>.` |

Predicate verbs come from the lexicon. The shapes do not.

## 7. Filters and paths

A filter is the `where` half of a term or subject. It reads as English, is
forgiving on the surface and strict in meaning:

```
status is active
status is not active
name contains "Acme"
name starts with "Acme"
priority is at least 3
priority is between 1 and 3
status is one of active, pending, approved
end date is empty
end date is before today
customer's type is external
status is active and (name contains "Acme" or name contains "ACME")
version is <selected version>
```

- Text comparison is case-insensitive unless `exactly` is used.
- Traversal is the possessive: `customer's type`. One path notation, used
  everywhere the language addresses a field. Each step follows a reference
  field the lexicon declares.
- A reverse relation — the entities that some other entity points at — is
  reached with a lexicon predicate as a filter: `any curator that approves a
  loan`. `that` is the only filter word that takes a verb.
- `<name>` is a **parameter**, bound from outside the sentence — a profile,
  a dataset, a configuration. Thresholds that vary per deployment are
  parameters, never literals copied into every sentence.
- Grouping by parentheses is allowed but not the normal form; flat
  and-lists and `either … or …` are.

## 8. Time

Windows are relative (`within the last 90 days`), anchored (`within 30 days
after the incident`, where the lexicon says what an incident's date is), or
periodic (`every quarter`). A period may name a **cadence** the lexicon
defines rather than a literal, so a lexicon can retune "quarterly" in one
place. Evaluation happens *as of* a date, which is an input, not `today`;
this is what lets a result be recomputed for a past moment.

## 9. Attestation and rubrics

Some claims are true or false only to a reader: "the policy sets the
strategic direction", "this change matches its specification". The language
does not pretend to decide them. It decides whether a recorded **act of
confirmation** exists: who attested, what they claimed, when, and with what
confidence. The attester may be a person, a role, or a **designated
system** — a program, including a language model, that reads and records a
judgement. The sentence that consumes the attestation is deterministic
either way, and it is where the threshold on confidence lives:

```
Every change must be attested by the Reviewer claiming review-v3
  with confidence at least 0.8 within the last 30 days.
```

An attestation is a fact with at least: the **subject**, the **attester**,
the **claim**, the **date**, and, for designated systems, a **confidence**
and the identity of the system that judged. It is evaluated like any other
fact. Nothing in the language calls a judge; a judge runs elsewhere and
leaves attestations behind.

**What the claim names.** For a person, the claim is text: what they
confirmed. For a designated system, the claim names a **rubric** — the
versioned, written statement of *what is being assessed and by what
criteria*, which the lexicon supplies next to the attester kind. The word is
borrowed from grading, a scoring guide with criteria and levels. A rubric
states the claim in the language's own terms, the inputs the judge is
given and nothing else, the criteria with a severity scale for findings,
the output contract that becomes the attestation fact (verdict, findings
with severity and location, confidence with a stated meaning), which
systems may execute it, labelled examples that fix what a confidence value
means, and a version. An edit is a new version.

Rules reference rubrics by id and version, never by content. That is what
keeps the policy complete and cheap to change: the threshold on confidence,
the accepted rubric version and the freshness window are sentences in the
policy, reviewed with everything else; raising the threshold or requiring a
newer version re-evaluates from stored attestations without asking any judge
again; and a judgement ages and can be absent exactly like a scan result,
so the outcome model (§12) applies to it unchanged. A human confirmation and
a system's judgement are the same kind of fact, so "attested by a human or
by the Reviewer with confidence at least 0.9" is one sentence rather than a
special case.

This is how a language that refuses to reason about prose still covers the
part of any policy that is prose: the reasoning happens outside, under a
rubric, and only its recorded result enters the world the language judges.

## 10. Storage form and authoring

The authored surface is English. The stored form is the same text with
**markers** on the typed spans: `$Term$`, `$$Terms$$` (plural), `@verb@`,
`#90 days#`, `<parameter>`, with everything between them kept as prose. A
constraint is therefore an ordered list of typed fragments in which the
prose survives untouched, which is what makes the pre-formal state
representable at all: mark what you know, leave the rest as written.

Authors do not type sigils. Markers are produced by an editor that lets an
author select a span and name what it is — the same interaction as tagging
text — and a predictive editor can offer, at each point, only the
continuations the grammar allows. The lexer is strict in return: any
unmarked sigil is an error, because only editors ever write markers.

## 11. Interpretation rules

Ambiguity is removed by rule, not by forbidding constructions. The rules,
several of them borrowed from Attempto Controlled English:

1. A relative clause or filter modifies the nearest preceding noun.
2. A quantifier scopes from its position to the end of the sentence.
3. `and` binds tighter than `or`; `either … or …` is the explicit form.
4. `the <noun>` resolves to the most recent accessible noun phrase that
   agrees in number; if none exists, it is an error.
5. Plurals and singulars name the same entity type.
6. Keywords are case-insensitive; term and reference names are title-cased
   and may contain the connectors `for`, `of`, `in`, `at`, `on`, `by`,
   `the`, `an`, `and` between capitalised words.
7. A filter on a field the lexicon does not declare is an error at
   resolution, with a suggestion when a near match exists.

## 12. Outcomes

A conformant implementation reports, per constraint and as of the
evaluation date: **satisfied**; **violated**, with the offending entities or
counts; or **skipped**, with a reason. Two rules protect the meaning of
"satisfied":

- A construct the implementation does not support **skips**; it never
  degrades into an empty subject set, because a universal obligation over an
  empty set is vacuously satisfied and would report success for a check that
  never ran.
- A definition (term or reference) is not a constraint and produces no
  outcome.

Skipped is a first-class answer. A check that cannot fail must not report
success.

## 13. English

The language is English and its keywords are not localised. Its authors are
not programmers, but they are experienced people with working English —
analysts, coaches, auditors, operators — and a grammar with one surface is
the one they can learn from each other. Localisation belongs to the display
of results and of labels, not to the authored text.

## 14. Prior art

**Attempto Controlled English** (University of Zurich, 1995–2013) is the
closest relative. It splits vocabulary into fixed function words and
user-defined content words exactly as §2 does, removes ambiguity by
published interpretation rules rather than by forbidding constructions, and
has `every` / `a` / `no` / `at least N`, `must` / `may` / `can` / `should`,
relative clauses as filters, the possessive `'s`, and anaphora resolved to
the most recent accessible antecedent.

It differs on purpose. ACE targets first-order logic and open-world
reasoning: a sentence becomes a formula. deontic targets closed-world
judgement: a sentence becomes a query with offenders. ACE has no time
windows, selection, aggregates or attestation, and has questions, commands
and full boolean formulas, which deontic refuses. And ACE is all-or-nothing —
a sentence parses or is rejected — with no pre-formal state; that is right
for a logic front end and wrong for the authors in §13. In the PENS scheme
of Kuhn's 2014 survey (precision, expressiveness, naturalness, simplicity),
ACE is high on expressiveness by design and deontic is low on it by design.

Other neighbours: InSpec and Semgrep for the ergonomics of readable checks;
Gherkin for a controlled surface non-programmers actually write; Cedar for
the idea that a policy set should be statically analysable.

## 15. On deontic logic

The name borrows the vocabulary of deontic logic — obligation, permission,
prohibition — and not its proof theory. Standard deontic logic licenses
inferences that plainly fail for real norms (Ross's paradox, the Good
Samaritan, the gentle murder, Chisholm's contrary-to-duty set, free-choice
permission). None of them arise here, for one reason: the language never
derives an obligation from another. Every constraint is evaluated on its own
against recorded state. Conflicting obligations are reported side by side,
not resolved. Free-choice permission is adopted by convention ("may read or
list" permits both). The one genuine deontic problem, what you ought to do
*given* a violation — escalate, waive, compensate — is deferred to the
application by §3, and deliberately so: a waiver is a recorded decision, not
a norm.

## 16. Decisions the corpus settled

The questions this section used to hold are closed by the conformance
corpus; its README records each with the case that fixes it:

- the parameter sigil is `<name>`;
- the path notation is the possessive; there is no dotted form;
- `self` is not in the core, by the rule of two;
- the closed-class list in §2 is the one the cases exercise; a word with no
  case is not in the language;
- `that <verb> <object>` is a filter and `be tagged` is a core predicate,
  both needed by the first two lexicons;
- markers are required on lexicon names, lexicon verbs, quantities with a
  unit and parameters, and on nothing else;
- anaphora resolves within the sentence;
- a sentence ends with a period.

## References

- Fuchs, Kaljurand, Kuhn — Attempto Controlled English: construction and
  interpretation rules, <http://attempto.ifi.uzh.ch/site/docs/>.
- Kuhn, *A Survey and Classification of Controlled Natural Languages*,
  Computational Linguistics, 2014.
- Shipman & McCall, *Supporting knowledge-base evolution with incremental
  formalization*, CHI 1994.
- Shipman & Marshall, *Formality Considered Harmful*, CSCW 1999.
