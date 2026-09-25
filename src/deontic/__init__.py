"""The deontic constraint language.

`parse` turns one sentence into the AST the conformance corpus fixes
(conformance/ast.schema.json); `load` reads a dictionary; `resolve` checks a
parsed sentence against it. `deontic.hooks` is the contract between a
lexicon's code half and any implementation. No evaluator lives here.

The version is read from installed metadata rather than written as a literal,
so the value in a published wheel and the value this module reports cannot
disagree.
"""

from importlib.metadata import PackageNotFoundError, version as _version

try:
    __version__ = _version("deontic")
except PackageNotFoundError:  # running from a source tree, not installed
    __version__ = "0.0.0+unknown"

from .dictionary import Dictionary, DictionaryError, load  # noqa: E402
from .errors import DeonticError, LexicalError, ResolutionError  # noqa: E402
from .parser import parse  # noqa: E402
from .resolve import Scope, resolve  # noqa: E402
from .hooks import (  # noqa: E402
    ENTRY_POINT_GROUP, Attestation, Context, Entity, Hook, Lexicon, Relation, Witness, World,
)

__all__ = [
    "__version__", "parse", "resolve", "load", "Dictionary", "DictionaryError", "Scope",
    "DeonticError", "LexicalError", "ResolutionError", "ENTRY_POINT_GROUP", "Attestation", "Context", "Entity", "Hook",
    "Lexicon", "Relation", "Witness", "World",
]
