"""The deontic constraint language.

Implementation pending. This package currently carries packaging, metadata and
the conformance-corpus layout only; the grammar, AST and parser land here.

The version is read from installed metadata rather than written as a literal,
so the value in a published wheel and the value this module reports cannot
disagree.
"""

from importlib.metadata import PackageNotFoundError, version as _version

try:
    __version__ = _version("deontic")
except PackageNotFoundError:  # running from a source tree, not installed
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
