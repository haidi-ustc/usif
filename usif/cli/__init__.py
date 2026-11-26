"""The ``usif`` command-line interface (Typer) over :mod:`usif.io`, datasets and the agent.

- :mod:`usif.cli.root`: the ``usif`` app, file commands and :func:`main`;
- :mod:`usif.cli.dataset`: ``usif dataset ...``;
- :mod:`usif.cli.agent`: ``usif agent ...``;
- :mod:`usif.cli.plans`: reviewing and applying change plans (shared by both groups);
- :mod:`usif.cli.common`: options, output and error messages.
"""

from usif.cli.root import app, main

__all__ = ["app", "main"]
