"""lua_deobf - rename obfuscated FiveM Lua variables (L0_1, A0_2, ...) to
meaningful names, add explanatory comments, and verify nothing changed.

    from lua_deobf import deobfuscate
    result = deobfuscate(open("client.lua").read())
    print(result.code)
    print(result.report("client.lua"))
"""

import re
import sys

from .annotate import Annotator
from .lexer import LuaSyntaxError
from .naming import DEFAULT_PATTERN, Deobfuscator
from .parser import parse
from .printer import to_source
from .report import build_report
from .verify import verify

__all__ = ["deobfuscate", "DeobfuscationResult", "LuaSyntaxError", "DEFAULT_PATTERN"]
__version__ = "1.0.0"

# Deeply nested expressions (long `..` chains) need a deeper Python stack.
sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))


class DeobfuscationResult:
    def __init__(self, code, renames, summary, verification, skipped_globals):
        self.code = code
        self.renames = renames
        self.summary = summary
        self.verification = verification
        self.skipped_globals = skipped_globals

    def report(self, title="script"):
        return build_report(self, title)


def deobfuscate(source, pattern=DEFAULT_PATTERN, comments=True, split=True,
                side=None, indent="    ", check=True, rename_globals=False):
    """De-obfuscate Lua ``source``.

    pattern         regex matching obfuscated variable names
    comments        add explanatory comments and a summary header
    split           split reused decompiler temporaries into separate variables
    side            'client' / 'server' / None (auto-detect)
    check           re-parse the output and verify it is equivalent
    rename_globals  also rename *global* variables matching the pattern
    """
    chunk = parse(source)
    deob = Deobfuscator(chunk, pattern=pattern, split=split, side=side,
                        rename_globals=rename_globals).run()
    annotator = Annotator(deob, indent)
    if comments:
        annotator.run(chunk)
        chunk.header_comments = annotator.header_lines(deob.renames)
    else:
        annotator.summarize(chunk)
    code = to_source(chunk, indent)
    global_renames = {r.old: r.new for r in deob.renames if r.kind == "global"}
    verification = verify(source, code, global_renames=global_renames) if check else None
    skipped = set()
    if not rename_globals:
        rx = re.compile(pattern)
        skipped = {g for g in deob.globals if rx.match(g)}
    return DeobfuscationResult(code, deob.renames, annotator.summary, verification, skipped)
