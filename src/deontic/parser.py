"""The grammar: token stream → AST (conformance/ast.schema.json).

Recursive descent over the lexer's tokens. Each shape is a function that
either returns an AST dict having consumed the whole sentence, or raises
`Miss`, in which case the next shape is tried. Nothing here knows a
dictionary: names inside markers are recorded as written, and resolution
against a lexicon is `deontic.resolve`.

The AST is plain dicts in the corpus's canonical form: keys whose value
would be null, false, an empty list or an empty object are omitted.
"""

from __future__ import annotations

from typing import Any

from .errors import LexicalError, NoShape, UnresolvedAnaphora
from .lexer import CALENDAR_UNITS, NUMBER_WORDS, UNITS, Fragment, Token, quantity, tokens

# Filter operators, longest first. Each maps to (op, kind of right-hand side).
_OPERATORS: list[tuple[tuple[str, ...], str, str]] = [
    (("is", "not", "empty"), "is_not_empty", "none"),
    (("is", "empty"), "is_empty", "none"),
    (("is", "one", "of"), "is_one_of", "list"),
    (("is", "at", "least"), "at_least", "value"),
    (("is", "at", "most"), "at_most", "value"),
    (("is", "more", "than"), "more_than", "value"),
    (("is", "less", "than"), "less_than", "value"),
    (("is", "between"), "between", "range"),
    (("is", "before"), "before", "value"),
    (("is", "after"), "after", "value"),
    (("is", "not"), "is_not", "value"),
    (("is",), "is", "value"),
    (("equals",), "equals", "path"),
    (("contains",), "contains", "value"),
    (("starts", "with"), "starts_with", "value"),
    (("ends", "with"), "ends_with", "value"),
]
_OPERATOR_FIRST_WORDS = {ops[0] for ops, _, _ in _OPERATORS}
_THRESHOLD_OPS = [(("at", "least"), "at_least"), (("at", "most"), "at_most"), (("exactly",), "exactly"),
                  (("more", "than"), "more_than"), (("less", "than"), "less_than")]
_STOP_WORDS = {"and", "or", "must", "may", "then", "ordered", "within", "before", "after", "every", "in", "claiming", "with", "per"}


class Miss(Exception):
    """This shape does not apply; try the next."""


_FLAGS = {"plural", "every", "anaphora", "exact"}


def clean(x):
    """The corpus's canonical form: null, empty and false *flags* are omitted.
    A boolean literal (`{"boolean": false}`) is a value, not a flag, and stays."""
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()
                if not (v is None or v == [] or v == {} or (v is False and k in _FLAGS))}
    if isinstance(x, list):
        return [clean(v) for v in x]
    return x


def _title_cased(name: str) -> bool:
    return name[:1].isupper()


class Parser:
    def __init__(self, toks: list[Token]):
        self.t = toks
        self.i = 0
        self.nps: list[dict] = []          # noun phrases seen, for anaphora (rule 4)

    # --- token helpers ---------------------------------------------------------------

    def peek(self, k: int = 0) -> Token | None:
        j = self.i + k
        return self.t[j] if j < len(self.t) else None

    def at_word(self, *words: str, k: int = 0) -> bool:
        for n, w in enumerate(words):
            tok = self.peek(k + n)
            if tok is None or tok.kind != "word" or tok.value != w:
                return False
        return True

    def kw(self, *words: str) -> bool:
        if self.at_word(*words):
            self.i += len(words)
            return True
        return False

    def need_kw(self, *words: str):
        if not self.kw(*words):
            raise Miss()

    def at_punct(self, p: str, k: int = 0) -> bool:
        tok = self.peek(k)
        return tok is not None and tok.kind == "punct" and tok.value == p

    def punct(self, p: str) -> bool:
        if self.at_punct(p):
            self.i += 1
            return True
        return False

    def take(self, kind: str) -> Token:
        tok = self.peek()
        if tok is None or tok.kind != kind:
            raise Miss()
        self.i += 1
        return tok

    def end(self):
        if not (self.at_punct(".") and self.i == len(self.t) - 1):
            raise Miss()
        self.i += 1

    def save(self) -> tuple[int, int]:
        return self.i, len(self.nps)

    def restore(self, state: tuple[int, int]):
        self.i, n = state
        del self.nps[n:]

    # --- small pieces ----------------------------------------------------------------------

    def number(self) -> int | float:
        tok = self.peek()
        if tok is not None and tok.kind == "number":
            self.i += 1
            return tok.value
        if tok is not None and tok.kind == "word" and tok.value in NUMBER_WORDS:
            self.i += 1
            return NUMBER_WORDS[tok.value]
        raise Miss()

    def integer(self) -> int:
        n = self.number()
        if isinstance(n, float):
            raise Miss()
        return n

    def cardinality(self) -> dict | None:
        """`at least one`, `exactly 2`, `zero or one`, `one or more`, `between 2 and 4`, `no`."""
        if self.kw("zero", "or", "one"):
            return {"op": "at_most", "value": 1}
        if self.kw("one", "or", "more"):
            return {"op": "at_least", "value": 1}
        if self.kw("at", "least"):
            return {"op": "at_least", "value": self.integer()}
        if self.kw("at", "most"):
            return {"op": "at_most", "value": self.integer()}
        if self.kw("exactly"):
            return {"op": "exactly", "value": self.integer()}
        if self.kw("between"):
            lo = self.integer()
            self.need_kw("and")
            return {"op": "between", "value": lo, "max": self.integer()}
        return None

    def bare_quantity(self) -> dict:
        """A `#…#` marker, a number, or a bare unit word (`year` is one year)."""
        tok = self.peek()
        if tok is None:
            raise Miss()
        if tok.kind == "quantity":
            self.i += 1
            if tok.value is None:
                raise Miss()
            return tok.value
        if tok.kind == "number":
            self.i += 1
            nxt = self.peek()
            if nxt is not None and nxt.kind == "word" and (nxt.value in UNITS or self.at_word("calendar")):
                unit_words = [nxt.value]
                self.i += 1
                if unit_words[0] == "calendar":
                    unit_words.append(self.take("word").value)
                return quantity(f"{tok.raw} {' '.join(unit_words)}")
            return {"value": tok.value}
        if tok.kind == "word":
            if tok.value in NUMBER_WORDS:
                self.i += 1
                unit = self.take("word").value
                return quantity(f"{tok.value} {unit}")
            if tok.value == "calendar":
                self.i += 1
                unit = self.take("word").value
                return quantity(f"calendar {unit}")
            if tok.value in UNITS and tok.value != "percent":
                self.i += 1
                return quantity(tok.value)
        raise Miss()

    def value(self) -> dict:
        tok = self.peek()
        if tok is None:
            raise Miss()
        self.i += 1
        if tok.kind == "string":
            return {"text": tok.value}
        if tok.kind == "number":
            return {"number": tok.value}
        if tok.kind == "date":
            return {"date": tok.value}
        if tok.kind == "parameter":
            return {"parameter": tok.value}
        if tok.kind == "word":
            if tok.value == "true":
                return {"boolean": True}
            if tok.value == "false":
                return {"boolean": False}
            if tok.value == "today":
                return {"today": True}
            if tok.value in _STOP_WORDS or tok.value in _OPERATOR_FIRST_WORDS:
                raise Miss()
            return {"text": tok.raw}
        raise Miss()

    def path(self) -> list[str]:
        """Words up to an operator or stop word; `'s` separates steps."""
        steps: list[list[str]] = [[]]
        while True:
            tok = self.peek()
            if tok is None:
                break
            if tok.kind == "punct" and tok.value == "'s":
                if not steps[-1]:
                    raise Miss()
                steps.append([])
                self.i += 1
                continue
            if tok.kind != "word" or tok.value in _STOP_WORDS or self._operator_here():
                break
            steps[-1].append(tok.raw.lower())
            self.i += 1
        if not steps[-1]:
            raise Miss()
        return [" ".join(s) for s in steps]

    def _operator_here(self) -> bool:
        return any(self.at_word(*ops) for ops, _, _ in _OPERATORS)

    def looks_like_condition(self) -> bool:
        """From here, does a path followed by an operator begin?"""
        k = 0
        seen_word = False
        while True:
            tok = self.peek(k)
            if tok is None:
                return False
            if tok.kind == "punct" and tok.value == "'s":
                k += 1
                continue
            if tok.kind != "word" or tok.value in _STOP_WORDS:
                return False
            if any(self.at_word(*ops, k=k) for ops, _, _ in _OPERATORS):
                return seen_word
            seen_word = True
            k += 1

    # --- filters ---------------------------------------------------------------------------

    def condition(self) -> dict:
        p = self.path()
        for ops, op, rhs in _OPERATORS:
            if self.kw(*ops):
                break
        else:
            raise Miss()
        node: dict = {"op": op, "path": p}
        if rhs == "none":
            return node
        if rhs == "path":
            node["other"] = self.path()
            return node
        if rhs == "range":
            lo = self.value()
            self.need_kw("and")
            node["values"] = [lo, self.value()]
            return node
        if rhs == "list":
            vals = [self.value()]
            while self.punct(","):
                vals.append(self.value())
            node["values"] = vals
            return node
        exact = self.kw("exactly")
        node["value"] = self.value()
        if exact:
            node["exact"] = True
        return node

    def tag_word(self) -> str:
        tok = self.take("word")
        if tok.value in _STOP_WORDS:
            raise Miss()
        return tok.raw.lower()

    def filter_atom(self) -> dict:
        if self.kw("tagged"):
            tags = [self.tag_word()]
            while self.at_word("and") and not self._condition_after_and() and not self.at_word("and", "that") \
                    and not self.at_word("and", "tagged") and not self.at_word("and", "where") \
                    and not self.at_word("and", "either") and not self.at_punct("(", 1):
                self.i += 1
                tags.append(self.tag_word())
            return {"op": "tagged", "tags": tags}
        if self.kw("where"):
            return self.condition()
        if self.kw("that"):
            return {"op": "that", "predicate": self.predicate()}
        if self.punct("("):
            node = self.or_expr()
            if not self.punct(")"):
                raise Miss()
            return node
        if self.kw("either"):
            return self.or_expr()
        if self.looks_like_condition():
            return self.condition()
        raise Miss()

    def _condition_after_and(self) -> bool:
        state = self.save()
        self.i += 1
        ok = self.looks_like_condition()
        self.restore(state)
        return ok

    def and_expr(self) -> dict:
        items = [self.filter_atom()]
        while self.at_word("and"):
            state = self.save()
            self.i += 1
            try:
                items.append(self.filter_atom())
            except Miss:
                self.restore(state)
                break
        return items[0] if len(items) == 1 else {"op": "and", "items": items}

    def or_expr(self) -> dict:
        items = [self.and_expr()]
        while self.at_word("or"):
            state = self.save()
            self.i += 1
            try:
                items.append(self.and_expr())
            except Miss:
                self.restore(state)
                break
        return items[0] if len(items) == 1 else {"op": "or", "items": items}

    def filter_opt(self) -> dict | None:
        if self.at_word("tagged") or self.at_word("where") or self.at_word("that") or self.at_punct("("):
            return self.or_expr()
        return None

    # --- noun phrases ---------------------------------------------------------------------

    def term(self) -> Token:
        return self.take("term")

    def noun_phrase(self, *, article: bool = True, every: bool = False, cardinality: bool = False) -> dict:
        """A term with optional article/quantifier and filter. Registers the phrase for anaphora."""
        np: dict = {}
        if every and self.kw("every"):
            np["every"] = True
        elif cardinality:
            c = self.cardinality()
            if c:
                np["cardinality"] = c
        anaphora = False
        if not np.get("every") and "cardinality" not in np and article:
            if self.kw("the"):
                anaphora = True
            else:
                self.kw("a") or self.kw("an")
        tok = self.term()
        np["term"] = tok.value
        if tok.plural:
            np["plural"] = True
        if anaphora:
            if any(p["term"].lower() == tok.value.lower() and p.get("plural", False) == tok.plural for p in self.nps):
                np["anaphora"] = True
            elif not _title_cased(tok.value):
                raise UnresolvedAnaphora("no antecedent", noun=tok.value)
        f = self.filter_opt()
        if f:
            np["filter"] = f
        self.nps.append(np)
        return np

    # --- predicates and time -----------------------------------------------------------------

    def event(self) -> dict:
        if self.kw("the"):
            tok = self.term()
            if not any(p["term"].lower() == tok.value.lower() for p in self.nps):
                raise UnresolvedAnaphora("no antecedent", noun=tok.value)
            if not self.punct("'s"):
                raise Miss()
            return {"term": tok.value, "anaphora": True, "path": self.path()}
        return {"term": self.term().value}

    def period(self) -> dict:
        tok = self.peek()
        if tok is not None and tok.kind == "term":
            self.i += 1
            return {"cadence": tok.value}
        return self.bare_quantity()

    def time_opt(self) -> dict | None:
        if self.kw("within", "the", "last"):
            return {"kind": "within_last", "duration": self.bare_quantity()}
        if self.at_word("within"):
            self.i += 1
            d = self.bare_quantity()
            if self.kw("after"):
                return {"kind": "within_after", "duration": d, "event": self.event()}
            if self.kw("before"):
                return {"kind": "within_before", "duration": d, "event": self.event()}
            raise Miss()
        if self.kw("before"):
            return {"kind": "before", "event": self.event()}
        if self.kw("after"):
            return {"kind": "after", "event": self.event()}
        return None

    def predicate(self) -> dict:
        if self.kw("be", "tagged"):
            tags = [self.tag_word()]
            while self.kw("and"):
                tags.append(self.tag_word())
            return {"tagged": tags}
        verb = self.take("verb")
        pred: dict = {"verb": verb.value.lower()}
        tok = self.peek()
        if tok is not None and (tok.kind == "term" or (tok.kind == "word" and tok.value in ("a", "an", "the", "at", "exactly", "zero", "one", "between"))):
            state = self.save()
            try:
                pred["object"] = self.noun_phrase(cardinality=True)
            except Miss:
                self.restore(state)
        t = self.time_opt()
        if t:
            pred["time"] = t
        return pred

    # --- shapes ---------------------------------------------------------------------------------

    def term_definition(self) -> dict:
        name = self.term().value
        self.need_kw("means", "any")
        base = self.noun_phrase(article=False)
        f = base.pop("filter", None)
        node = {"shape": "term_definition", "name": name, "type": base, "filter": f}
        self.end()
        return node

    def reference_definition(self) -> dict:
        name = self.term().value
        self.need_kw("refers", "to")
        node: dict = {"shape": "reference_definition", "name": name}
        if self.kw("the", "latest"):
            node["selection"] = "latest"
        else:
            c = self.cardinality()
            if c:
                node["cardinality"] = c
        base = self.noun_phrase(article=False)
        node["filter"] = base.pop("filter", None)
        node["type"] = base
        if self.kw("ordered", "by"):
            order = [self.path()]
            while self.punct(","):
                order.append(self.path())
            node["order_by"] = order
        self.end()
        return node

    def threshold(self) -> dict:
        self.need_kw("the")
        metric = self.term().value
        self.need_kw("of")
        subject = self.noun_phrase(every=True)
        self.need_kw("must", "be")
        for ops, op in _THRESHOLD_OPS:
            if self.kw(*ops):
                break
        else:
            raise Miss()
        tok = self.peek()
        if tok is not None and tok.kind == "parameter":
            self.i += 1
            value: dict = {"parameter": tok.value}
        else:
            value = self.bare_quantity()
        node = {"shape": "threshold", "metric": metric, "subject": subject, "op": op, "value": value}
        if self.kw("per"):
            node["window"] = self.bare_quantity()
        self.end()
        return node

    def sequencing(self) -> dict:
        ev = self.term().value
        self.need_kw("must", "occur")
        node: dict = {"shape": "sequencing", "event": {"term": ev}}
        if self.kw("within"):
            node["duration"] = self.bare_quantity()
            if self.kw("after"):
                node["relation"] = "within_after"
            elif self.kw("before"):
                node["relation"] = "within_before"
            else:
                raise Miss()
        elif self.kw("before"):
            node["relation"] = "before"
        elif self.kw("after"):
            node["relation"] = "after"
        else:
            raise Miss()
        node["anchor"] = {"term": self.term().value}
        self.end()
        return node

    def existence_or_aggregate(self) -> dict:
        if self.kw("no"):
            card: dict | None = {"op": "exactly", "value": 0}
            subject = self.noun_phrase(article=False)
            self.need_kw("may")
            verb = self.take("verb")
            if verb.value.lower() not in ("exist", "exists"):
                raise Miss()
            self.end()
            return {"shape": "existence", "cardinality": card, "subject": subject}
        state = self.save()
        percent = None
        for ops, op in (("at", "least"), "at_least"), (("at", "most"), "at_most"), (("exactly",), "exactly"):
            if self.at_word(*ops):
                tok = self.peek(len(ops))
                if tok is not None and tok.kind == "quantity" and tok.value and tok.value.get("unit") == "percent":
                    self.i += len(ops) + 1
                    percent = tok.value
                elif tok is not None and tok.kind == "number" and self.at_word("percent", k=len(ops) + 1):
                    self.i += len(ops) + 2
                    percent = {"value": tok.value, "unit": "percent"}
                if percent:
                    card = {"op": op, "value": percent}
                break
        if percent is None:
            card = self.cardinality()
            if card is None:
                raise Miss()
        if self.kw("of") or percent:
            subject = self.noun_phrase(article=False)
            scope = self.noun_phrase(article=False) if self.kw("in", "scope", "of") else None
            modal = "must" if self.kw("must") else ("may" if self.kw("may") else None)
            if modal is None:
                raise Miss()
            node = {"shape": "aggregate", "cardinality": card, "subject": subject, "scope": scope,
                    "modal": modal, "predicate": self.predicate()}
            self.end()
            return node
        subject = self.noun_phrase(article=False)
        if self.kw("must"):
            tok = self.peek()
            if tok is not None and tok.kind == "verb" and tok.value.lower() in ("exist", "exists"):
                self.i += 1
                self.end()
                return {"shape": "existence", "cardinality": card, "subject": subject}
            node = {"shape": "aggregate", "cardinality": card, "subject": subject, "modal": "must",
                    "predicate": self.predicate()}
            self.end()
            return node
        if self.kw("may"):
            node = {"shape": "aggregate", "cardinality": card, "subject": subject, "modal": "may",
                    "predicate": self.predicate()}
            self.end()
            return node
        self.restore(state)
        raise Miss()

    def conditional(self) -> dict:
        self.need_kw("if")
        self.kw("a") or self.kw("an")
        tok = self.term()
        cond: dict = {"term": tok.value}
        if tok.plural:
            cond["plural"] = True
        if self.punct("'s"):
            p = self.path()
            for ops, op, rhs in _OPERATORS:
                if self.kw(*ops):
                    break
            else:
                raise Miss()
            if rhs != "value":
                raise Miss()
            cond["filter"] = {"op": op, "path": p, "value": self.value()}
        elif self.kw("is", "tagged"):
            tags = [self.tag_word()]
            while self.kw("and"):
                tags.append(self.tag_word())
            cond["filter"] = {"op": "tagged", "tags": tags}
        else:
            cond["filter"] = self.filter_opt()
            if cond["filter"] is None:
                raise Miss()
        self.nps.append(cond)
        if not self.punct(","):
            raise Miss()
        self.need_kw("then")
        subject = self.noun_phrase(every=True)
        self.need_kw("must")
        node = {"shape": "conditional", "condition": cond, "subject": subject, "predicate": self.predicate()}
        self.end()
        return node

    def prohibition_no(self) -> dict:
        self.need_kw("no")
        subject = self.noun_phrase(article=False)
        self.need_kw("may")
        node = {"shape": "prohibition", "form": "no_may", "subject": subject, "predicate": self.predicate()}
        self.end()
        return node

    def permission(self) -> dict:
        self.need_kw("only")
        subject = self.noun_phrase(article=False)
        self.need_kw("may")
        node = {"shape": "permission", "subject": subject, "predicate": self.predicate()}
        self.end()
        return node

    def attester(self) -> dict:
        self.kw("a") or self.kw("an")
        tok = self.term()
        att: dict = {"attester": {"term": tok.value, "plural": tok.plural}}
        if self.kw("claiming"):
            c = self.peek()
            if c is None:
                raise Miss()
            self.i += 1
            att["claim"] = {"text": c.value} if c.kind == "string" else {"rubric": c.raw if c.kind == "word" else str(c.value)}
        if self.kw("with", "confidence", "at", "least"):
            tok = self.peek()
            if tok is not None and tok.kind == "parameter":
                self.i += 1
                att["confidence_at_least"] = {"parameter": tok.value}
            else:
                att["confidence_at_least"] = self.number()
        return att

    def subject_then_modal(self) -> tuple[dict, str]:
        subject = self.noun_phrase(every=True)
        if self.kw("must", "not"):
            return subject, "must not"
        if self.kw("must", "be", "attested", "by"):
            return subject, "attested"
        if self.kw("must"):
            return subject, "must"
        raise Miss()

    def obligation_family(self) -> dict:
        subject, modal = self.subject_then_modal()
        if modal == "must not":
            node = {"shape": "prohibition", "form": "must_not", "subject": subject, "predicate": self.predicate()}
            self.end()
            return node
        if modal == "attested":
            node = {"shape": "attestation", "subject": subject}
            if self.kw("at", "least"):
                node["min_attesters"] = self.integer()
            atts = [self.attester()]
            while self.kw("or", "by"):
                atts.append(self.attester())
            node["attesters"] = atts
            if self.kw("every"):
                node["window"] = {"kind": "every", "period": self.period()}
            else:
                node["window"] = self.time_opt()
                if node["window"] is None:
                    raise Miss()
            self.end()
            return node
        # cadence: subject must verb [target] every period
        state = self.save()
        try:
            verb = self.take("verb")
            target = None
            tok = self.peek()
            if tok is not None and (tok.kind == "term" or (tok.kind == "word" and tok.value in ("a", "an", "the"))):
                target = self.noun_phrase()
            self.need_kw("every")
            period = self.period()
            self.end()
            return {"shape": "cadence", "subject": subject, "verb": verb.value.lower(), "target": target, "period": period}
        except Miss:
            self.restore(state)
        pred = self.predicate()
        if self.kw("or", "must"):
            preds = [pred, self.predicate()]
            while self.kw("or", "must"):
                preds.append(self.predicate())
            self.end()
            return {"shape": "disjunction", "subject": subject, "predicates": preds}
        self.end()
        return {"shape": "obligation", "subject": subject, "predicate": pred}

    SHAPES = ("term_definition", "reference_definition", "threshold", "sequencing", "conditional",
              "permission", "existence_or_aggregate", "prohibition_no", "obligation_family")

    def sentence(self) -> dict | None:
        for name in self.SHAPES:
            self.i = 0
            self.nps = []
            try:
                return clean(getattr(self, name)())
            except Miss:
                continue
        return None


def pre_formal(frags: list[Fragment]) -> dict:
    out = []
    for f in frags:
        if f.kind == "prose":
            out.append({"prose": f.text})
        elif f.kind == "term":
            out.append({"term": f.text, "plural": f.plural})
        elif f.kind == "verb":
            out.append({"verb": f.text})
        elif f.kind == "quantity":
            out.append({"quantity": quantity(f.text)})
        elif f.kind == "parameter":
            out.append({"parameter": f.text})
    return clean({"shape": "pre_formal", "fragments": out})


def parse(source: str, *, strictness: str = "permissive") -> dict:
    """Parse one sentence. Raises a LexicalError, UnresolvedAnaphora, or NoShape (strict)."""
    frags, toks = tokens(source)
    if all(f.kind == "prose" for f in frags):
        return {"shape": "unconscious"}
    ast = Parser(toks).sentence()
    if ast is not None:
        return ast
    if strictness == "strict":
        raise NoShape("no shape matches")
    return pre_formal(frags)


__all__ = ["parse", "Parser", "Miss", "clean", "pre_formal", "LexicalError"]


def render_predicate(pred: dict) -> str:
    """Canonical English for a predicate AST (used by filter rendering)."""
    if "tagged" in pred:
        return "be tagged " + " and ".join(pred["tagged"])
    out = f"@{pred['verb']}@"
    obj = pred.get("object")
    if obj:
        from .filters import render_filter
        card = obj.get("cardinality")
        if card:
            n = card["value"]
            prefix = {"at_least": f"at least {n}", "at_most": f"at most {n}", "exactly": f"exactly {n}",
                      "between": f"between {n} and {card.get('max')}"}[card["op"]]
            out += f" {prefix}"
        elif not obj.get("plural"):
            out += " a"
        marker = "$$" if obj.get("plural") else "$"
        out += f" {marker}{obj['term']}{marker}"
        if "filter" in obj:
            f = obj["filter"]
            out += " " + (render_filter(f) if f["op"] in ("tagged", "that") else "where " + render_filter(f))
    return out
