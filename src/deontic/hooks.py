"""The Python form of a lexicon's code half (docs/hooks.md §4).

A verb the dictionary declares without a `pattern` is a hook verb. A lexicon
may ship a callable for it; an implementation that can run the callable
evaluates the verb, one that cannot skips constraints using it. This module
is the whole contract: the witness record, the read-only world and context
a hook receives, and the entry-point group lexicons register under.

Stdlib only, and no evaluator lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

ENTRY_POINT_GROUP = "deontic.lexicons"
"""Python lexicons register here, named after their dictionary. The entry
point resolves to an object with a `hooks` mapping from verb name to Hook."""


@dataclass(frozen=True)
class Entity:
    id: str
    type: str
    tags: frozenset[str] = frozenset()
    fields: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Relation:
    name: str
    subject: str
    object: str


@dataclass(frozen=True)
class Attestation:
    subject: str
    attester: str
    claim: str
    date: date
    confidence: float | None = None
    system: str | None = None
    attester_id: str | None = None


@dataclass(frozen=True)
class Witness:
    """One piece of evidence that a verb holds of a subject.

    `object` is the entity the verb relates the subject to, if the verb takes
    one; `at` is when, if the verb is dated; `via` is the record that carries
    the evidence when it is neither the subject nor the object.
    """
    object: str | None = None
    at: date | None = None
    via: str | None = None


class World(Protocol):
    """Read access to the closed world, and nothing outside it."""

    def entity(self, id: str) -> Entity | None: ...
    def entities(self, type: str) -> Iterable[Entity]: ...
    def relations(self, name: str) -> Iterable[Relation]: ...
    def attestations(self, subject: str) -> Iterable[Attestation]: ...


@dataclass(frozen=True)
class Context:
    as_of: date
    parameters: Mapping[str, Any]
    verb: Mapping[str, Any]
    """The verb's declaration from the dictionary, as loaded."""


Hook = Callable[[Entity, World, Context], Iterable[Witness]]
"""A hook is pure: the same subject, world and context give the same
witnesses. It sees no sentence, filter or time expression."""


class Lexicon(Protocol):
    """What an entry point in ENTRY_POINT_GROUP resolves to."""

    hooks: Mapping[str, Hook]


def dated(hook: Hook) -> bool:
    """Whether a hook's witnesses carry a date, per its `dated` attribute; a
    hook without one is undated, so a time expression on its verb is an
    `undated_verb` error rather than a silent pass."""
    return bool(getattr(hook, "dated", False))


__all__ = [
    "ENTRY_POINT_GROUP", "Entity", "Relation", "Attestation", "Witness",
    "World", "Context", "Hook", "Lexicon", "dated",
]
