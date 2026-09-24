"""Packaging invariants.

Thin on purpose while the grammar is unimplemented — but not absent, because
these are the two things that break silently in a published wheel.
"""

from importlib.metadata import version

import deontic


def test_version_comes_from_installed_metadata():
    """Not a literal in __init__.py.

    The release workflow stamps the version into pyproject.toml at build time
    and never edits the module, so a hardcoded constant would report the wrong
    version out of every installed copy.
    """
    assert deontic.__version__ == version("deontic")


def test_no_runtime_dependencies():
    """A grammar meant to be implemented by others stays stdlib-only.

    Anything added here lands in every consumer's dependency tree, including
    implementations that only want the conformance corpus.
    """
    from importlib.metadata import requires

    runtime = [r for r in (requires("deontic") or []) if "extra ==" not in r]
    assert runtime == [], f"unexpected runtime dependencies: {runtime}"
