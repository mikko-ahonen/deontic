"""Resolution: checking a parsed sentence against a dictionary (design §2,
interpretation rule 7, corpus reject/resolve-*).

Every marked name must be declared in exactly one role; every field path
must follow declared fields of the right kind; every tag must be in its
type's closed set; every verb must be declared (strict) and take the kind of
object it declares; a time expression needs a dated verb; a bare claim must
name a rubric declared next to a designated system; confidence belongs to a
system. The parse tree is returned annotated with the type each noun phrase
denotes, which is what an evaluator consumes.
"""

from __future__ import annotations

from typing import Any

from .dictionary import Dictionary, field_kind
from .errors import (
    ConfidenceRequiresSystem, NotAReference, ObjectKindMismatch, TypeMismatch, UndatedVerb,
    UnknownField, UnknownRubric, UnknownTag, UnknownTerm, UnknownVerb,
)

_NUMERIC_OPS = {"at_least", "at_most", "more_than", "less_than", "between"}
_DATE_OPS = {"before", "after"}
_TEXT_OPS = {"contains", "starts_with", "ends_with"}


class Scope:
    """Names defined by earlier sentences in the same profile: term → base type."""

    def __init__(self):
        self.terms: dict[str, str | None] = {}   # lower name → resolved type (None until known)

    def define(self, name: str, type_name: str | None):
        self.terms[name.lower()] = type_name


class Resolver:
    def __init__(self, dictionary: Dictionary, scope: Scope | None = None, *, strictness: str | None = None):
        self.d = dictionary
        self.scope = scope or Scope()
        self.strictness = strictness or dictionary.strictness

    # --- names -------------------------------------------------------------------------

    def type_for(self, name: str) -> str | None:
        """The entity type a noun phrase denotes, or None for a name with no type (a cadence, an attester)."""
        t = self.d.type_of(name)
        if t:
            return t
        key = name.lower()
        if key in self.scope.terms:
            return self.scope.terms[key]
        role = self.d.role(name)
        if role in ("term", "reference"):
            return None
        if role is None:
            raise UnknownTerm(f"unknown name {name!r}", term=name)
        return None

    def require_role(self, name: str, *roles: str):
        role = self.d.role(name)
        if role not in roles:
            raise UnknownTerm(f"{name!r} is not a {' or '.join(roles)}", term=name)

    # --- filters -------------------------------------------------------------------------

    def path(self, type_name: str | None, path: list[str]) -> tuple[str | None, Any]:
        """Walk a path; return (type it ends on, field declaration of its last step)."""
        if type_name is None:
            return None, None
        t = type_name
        for step in path[:-1]:
            target, err = self.d.step(t, step)
            if err == "not_a_reference":
                raise NotAReference(f"{step!r} is not a reference", type=t, field=step)
            if err:
                raise UnknownField(f"unknown field {step!r}", type=t, field=step, suggestion=self.d.suggest(t, step))
            t = target
        last = path[-1]
        f = self.d.fields(t).get(last)
        if f is None:
            for r in self.d.relations.values():
                if t in r["from"] and r.get("as", r["to"]) == last:
                    return t, {"kind": "reference", "to": r["to"]}
            raise UnknownField(f"unknown field {last!r}", type=t, field=last, suggestion=self.d.suggest(t, last))
        return t, f

    def filter(self, type_name: str | None, node: dict):
        op = node["op"]
        if op in ("and", "or"):
            for item in node["items"]:
                self.filter(type_name, item)
            return
        if op == "tagged":
            if type_name:
                declared = self.d.tags(type_name)
                for tag in node["tags"]:
                    if tag not in declared:
                        raise UnknownTag(f"unknown tag {tag!r}", type=type_name, tag=tag)
            return
        if op == "that":
            self.predicate(type_name, node["predicate"], time_allowed=True)
            return
        t, f = self.path(type_name, node["path"])
        if f is None:
            return
        kind = field_kind(f)
        if op == "equals":
            self.path(type_name, node["other"])
            return
        expected = None
        if op in _NUMERIC_OPS:
            expected = "number"
        elif op in _DATE_OPS:
            expected = "date"
        elif op in _TEXT_OPS:
            expected = "text"
        elif op in ("is", "is_not", "is_one_of"):
            values = node.get("values") or [node.get("value")]
            for v in values:
                if "boolean" in v:
                    expected = "boolean"
                elif "date" in v or "today" in v:
                    expected = "date"
                elif "number" in v:
                    expected = "number"
        if expected and kind != expected and not (kind == "list" and expected == "text") and not (kind == "reference"):
            if not (expected == "number" and kind == "text" and op in ("is", "is_not", "is_one_of")):
                raise TypeMismatch(f"{op} on a {kind} field", type=t, field=node["path"][-1], expected=expected, actual=kind)

    # --- noun phrases and predicates --------------------------------------------------------

    def noun_phrase(self, np: dict) -> str | None:
        t = self.type_for(np["term"])
        if "filter" in np:
            self.filter(t, np["filter"])
        return t

    def predicate(self, subject_type: str | None, pred: dict, *, time_allowed: bool = True) -> None:
        if "tagged" in pred:
            if subject_type:
                declared = self.d.tags(subject_type)
                for tag in pred["tagged"]:
                    if tag not in declared:
                        raise UnknownTag(f"unknown tag {tag!r}", type=subject_type, tag=tag)
            return
        decl = self.d.verb(pred["verb"])
        if decl is None:
            if self.strictness == "strict":
                raise UnknownVerb(f"unknown verb {pred['verb']!r}", verb=pred["verb"])
            pred["unknown_verb"] = True
            return
        object_type = None
        if "object" in pred:
            object_type = self.noun_phrase(pred["object"])
            expected = decl.get("object", "entity")
            if expected not in ("entity", "none") and object_type and object_type != expected \
                    and self.d.type_of(expected) != object_type:
                raise ObjectKindMismatch(f"{pred['verb']} takes a {expected}", verb=pred["verb"],
                                         expected=expected, actual=object_type)
        if "time" in pred and not self.d.verb_dated(decl):
            raise UndatedVerb(f"{pred['verb']} is undated", verb=pred["verb"])
        if "time" in pred:
            self.time(pred["time"])

    def time(self, t: dict):
        if "event" in t:
            ev = t["event"]
            if "anaphora" in ev:
                base = self.type_for(ev["term"])
                if base:
                    self.path(base, ev["path"])
            else:
                self.require_role(ev["term"], "event")
        if t.get("kind") == "every" and "cadence" in t.get("period", {}):
            self.require_role(t["period"]["cadence"], "cadence")

    # --- sentences ------------------------------------------------------------------------------

    def sentence(self, ast: dict) -> dict:
        shape = ast["shape"]
        if shape in ("unconscious", "pre_formal"):
            return ast
        if shape == "term_definition":
            base = self.type_for(ast["type"]["term"])
            if "filter" in ast:
                self.filter(base, ast["filter"])
            self.scope.define(ast["name"], base)
            return ast
        if shape == "reference_definition":
            base = self.type_for(ast["type"]["term"])
            if "filter" in ast:
                self.filter(base, ast["filter"])
            for p in ast.get("order_by", []):
                self.path(base, p)
            self.scope.define(ast["name"], base)
            return ast
        if shape == "threshold":
            self.require_role(ast["metric"], "metric")
            self.noun_phrase(ast["subject"])
            return ast
        if shape == "sequencing":
            self.require_role(ast["event"]["term"], "event")
            self.require_role(ast["anchor"]["term"], "event")
            return ast
        if shape == "existence":
            self.noun_phrase(ast["subject"])
            return ast
        if shape == "cadence":
            st = self.noun_phrase(ast["subject"])
            decl = self.d.verb(ast["verb"])
            if decl is None:
                if self.strictness == "strict":
                    raise UnknownVerb(f"unknown verb {ast['verb']!r}", verb=ast["verb"])
                ast["unknown_verb"] = True
            if "target" in ast:
                self.noun_phrase(ast["target"])
            if "cadence" in ast["period"]:
                self.require_role(ast["period"]["cadence"], "cadence")
            return ast
        if shape == "attestation":
            self.noun_phrase(ast["subject"])
            for a in ast["attesters"]:
                name = a["attester"]["term"]
                self.require_role(name, "attester", "attester_plural")
                decl = self.d.data["attesters"][self.d.canonical[name.lower()]]
                if "confidence_at_least" in a and decl["kind"] != "system":
                    raise ConfidenceRequiresSystem("confidence needs a designated system", attester=name)
                claim = a.get("claim", {})
                if "rubric" in claim and claim["rubric"] not in decl.get("rubrics", {}):
                    raise UnknownRubric(f"unknown rubric {claim['rubric']!r}", attester=name, rubric=claim["rubric"])
            self.time(ast["window"])
            return ast
        if shape == "conditional":
            self.noun_phrase(ast["condition"])
            st = self.noun_phrase(ast["subject"])
            self.predicate(st, ast["predicate"])
            return ast
        if shape == "aggregate":
            st = self.noun_phrase(ast["subject"])
            if "scope" in ast:
                self.noun_phrase(ast["scope"])
            self.predicate(st, ast["predicate"])
            return ast
        if shape == "disjunction":
            st = self.noun_phrase(ast["subject"])
            for p in ast["predicates"]:
                self.predicate(st, p)
            return ast
        # obligation, prohibition, permission
        st = self.noun_phrase(ast["subject"])
        self.predicate(st, ast["predicate"])
        return ast


def resolve(ast: dict, dictionary: Dictionary, scope: Scope | None = None, *, strictness: str | None = None) -> dict:
    return Resolver(dictionary, scope, strictness=strictness).sentence(ast)


__all__ = ["resolve", "Resolver", "Scope"]
