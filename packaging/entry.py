"""Entry script for the packaged build.

PyInstaller needs a top-level module; a relative import inside
``shotrenamer/__main__.py`` does not work once it is run as a script.

``freeze_support()`` must come first: dependencies create multiprocessing
semaphores, and without it CPython's resource tracker re-executes this binary
with ``-B -S -I -c`` and lands in our argument parser.
"""

import multiprocessing

multiprocessing.freeze_support()

from shotrenamer.cli import main  # noqa: E402

raise SystemExit(main())
