#!/usr/bin/env python3
"""Render a `brando.v1.MarkProgram` to layered SVGs. The binary `brand_mark_program` runs.

WHY THIS LAUNCHER IS NOT IN `marklib/`. Python puts a script's own directory on
`sys.path` ahead of everything else, and `marklib/` contains `marklib.py`. A
binary whose main file lived there would therefore resolve `import marklib` to
the MODULE rather than to the package, and `from marklib import expr` fails with
a message that names neither cause:

    ImportError: cannot import name 'expr' from 'marklib' (marklib/marklib.py)

`//marklib:contrast` and `//marklib:theme_css` do not hit this only because
`palette.py` and `tokens.py` import nothing from their own package. The
interpreter does, so its entry point lives out here where the shadowing cannot
happen — the same class of problem as the empty `__init__.py` Bazel used to
invent, and worth removing rather than working around.

All the logic is in `marklib.program`; this file is the ten lines that make it a
command.
"""
import sys

from marklib import program

if __name__ == "__main__":
    sys.exit(program.main())
