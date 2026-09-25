"""The deontic constraint language.

The grammar, AST and parser are pending. What exists is the conformance
corpus (data, under conformance/) and `deontic.hooks`, the contract between a
lexicon's code half and any implementation.

The version is read from installed metadata rather than written as a literal,
so the value in a published wheel and the value this module reports cannot
disagree.
"""

from importlib.metadata import PackageNotFoundError, version as _version

try:
    __version__ = _version("deontic")
except PackageNotFoundError:  # running from a source tree, not installed
    __version__ = "0.0.0+unknown"

from .hooks import (  # noqa: E402
    ENTRY_POINT_GROUP, Attestation, Context, Entity, Hook, Lexicon, Relation, Witness, World,
)

__all__ = [
    "__version__", "ENTRY_POINT_GROUP", "Attestation", "Context", "Entity", "Hook",
    "Lexicon", "Relation", "Witness", "World",
]
