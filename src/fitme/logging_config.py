"""Single place to configure logging for every entry point.

Call ``setup()`` once at the very top of each entry point (``app.py``,
``fitme.login``, future CLIs). After that, every module should do::

    import logging
    logger = logging.getLogger(__name__)

and use ``logger.info(...)``, ``logger.warning(...)``, etc. — never ``print``.
"""
from __future__ import annotations

import logging
import os

_DEFAULT_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup(level: int | str | None = None) -> None:
    """Configure the root logger. Idempotent.

    ``LOG_LEVEL`` in ``.env`` overrides the default ``INFO``.
    """
    resolved = level or os.getenv("LOG_LEVEL", "INFO")
    logging.basicConfig(level=resolved, format=_DEFAULT_FORMAT, force=False)
    # garminconnect itself is chatty at DEBUG — keep it at WARNING by default.
    logging.getLogger("garminconnect").setLevel(logging.WARNING)
