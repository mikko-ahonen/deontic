"""Errors, named by the codes the conformance corpus uses."""

from __future__ import annotations


class DeonticError(Exception):
    code = "error"

    def __init__(self, message: str = "", **details):
        super().__init__(message or self.code)
        self.message = message or self.code
        self.details = details

    def as_dict(self) -> dict:
        return {"code": self.code, **{k: v for k, v in self.details.items() if v is not None}}


class LexicalError(DeonticError):
    """A sentence that cannot be read at all, in either strictness setting."""


class UnmatchedMarker(LexicalError):
    code = "unmatched_marker"


class EmptyMarker(LexicalError):
    code = "empty_marker"


class SigilInsideMarker(LexicalError):
    code = "sigil_inside_marker"


class UnterminatedString(LexicalError):
    code = "unterminated_string"


class UnbalancedParenthesis(LexicalError):
    code = "unbalanced_parenthesis"


class MissingPeriod(LexicalError):
    code = "missing_period"


class NoShape(DeonticError):
    """Strict only: marked text matching no shape."""
    code = "no_shape"


class UnresolvedAnaphora(DeonticError):
    code = "unresolved_anaphora"


class ResolutionError(DeonticError):
    """An error found against a dictionary."""


class UnknownTerm(ResolutionError):
    code = "unknown_term"


class UnknownField(ResolutionError):
    code = "unknown_field"


class NotAReference(ResolutionError):
    code = "not_a_reference"


class UnknownTag(ResolutionError):
    code = "unknown_tag"


class TypeMismatch(ResolutionError):
    code = "type_mismatch"


class UnknownVerb(ResolutionError):
    code = "unknown_verb"


class ObjectKindMismatch(ResolutionError):
    code = "object_kind_mismatch"


class UnknownRubric(ResolutionError):
    code = "unknown_rubric"


class ConfidenceRequiresSystem(ResolutionError):
    code = "confidence_requires_system"


class UndatedVerb(ResolutionError):
    code = "undated_verb"
