"""Command line interface.

    python -m lua_deobf client.lua                  # print de-obfuscated code
    python -m lua_deobf client.lua -o clean.lua     # write it to a file
    python -m lua_deobf client.lua --markdown       # explanation + ```lua block
    python -m lua_deobf src/ -o out/ --report       # whole folder, + report files
"""

import argparse
import os
import sys

from . import DEFAULT_PATTERN, LuaSyntaxError, __version__, deobfuscate


def build_parser():
    p = argparse.ArgumentParser(
        prog="lua_deobf",
        description="Rename obfuscated FiveM Lua variables (L0_1, A0_2, ...) to meaningful "
                    "names, add explanatory comments, and verify the logic is unchanged.")
    p.add_argument("inputs", nargs="+", help="Lua file(s) or folder(s) to process")
    p.add_argument("-o", "--output",
                   help="output file (single input) or folder (several inputs / folders); "
                        "default: print to stdout")
    p.add_argument("--markdown", action="store_true",
                   help="print/write a Markdown report (explanation, rename table, ```lua code) "
                        "instead of plain Lua")
    p.add_argument("--report", nargs="?", const="", metavar="PATH",
                   help="also write the Markdown report (default: <output>.report.md)")
    p.add_argument("--no-comments", action="store_true", help="do not add explanatory comments")
    p.add_argument("--no-split", action="store_true",
                   help="never split reused temporaries; only rename (one name per variable)")
    p.add_argument("--rename-globals", action="store_true",
                   help="also rename obfuscated-looking *global* variables")
    p.add_argument("--pattern", default=DEFAULT_PATTERN,
                   help="regex for obfuscated names (default: %(default)s)")
    p.add_argument("--side", choices=["client", "server"], help="override client/server detection")
    p.add_argument("--indent", type=int, default=4, help="spaces per indent level (default 4)")
    p.add_argument("--tabs", action="store_true", help="indent with tabs")
    p.add_argument("--no-verify", action="store_true", help="skip the equivalence check")
    p.add_argument("-q", "--quiet", action="store_true", help="no progress/summary on stderr")
    p.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return p


def collect(inputs):
    """Yield (path, relative path) for every .lua file in the inputs."""
    for item in inputs:
        if os.path.isdir(item):
            for root, _, files in os.walk(item):
                for name in sorted(files):
                    if name.endswith(".lua"):
                        path = os.path.join(root, name)
                        yield path, os.path.relpath(path, item)
        else:
            yield item, os.path.basename(item)


def read_source(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if data.startswith(b"\x1bLua"):
        raise LuaSyntaxError("this is compiled Lua bytecode; decompile it first "
                             "(e.g. with unluac) and run this tool on the decompiled source")
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue


def write(path, text):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def main(argv=None):
    args = build_parser().parse_args(argv)
    files = list(collect(args.inputs))
    if not files:
        print("error: no .lua files found", file=sys.stderr)
        return 2
    many = len(files) > 1 or any(os.path.isdir(i) for i in args.inputs)
    if many and not args.output:
        print("error: use -o FOLDER when processing several files", file=sys.stderr)
        return 2
    indent = "\t" if args.tabs else " " * args.indent
    status = 0
    for path, rel in files:
        try:
            source = read_source(path)
            result = deobfuscate(source, pattern=args.pattern, comments=not args.no_comments,
                                 split=not args.no_split, side=args.side, indent=indent,
                                 check=not args.no_verify, rename_globals=args.rename_globals)
        except LuaSyntaxError as exc:
            print("%s: syntax error: %s" % (path, exc), file=sys.stderr)
            status = 1
            continue
        report = result.report(os.path.basename(path))
        text = report if args.markdown else result.code
        if args.output:
            if many:
                base = os.path.join(args.output, rel)
                target = os.path.splitext(base)[0] + ".md" if args.markdown else base
            else:
                target = args.output
            write(target, text)
        else:
            target = None
            sys.stdout.write(text)
        if args.report is not None:
            if args.report and not many:
                report_path = args.report
            elif target:
                report_path = os.path.splitext(target)[0] + ".report.md"
            else:
                report_path = os.path.splitext(path)[0] + ".report.md"
            write(report_path, report)
        v = result.verification
        if v is not None and not v.ok:
            status = 1
            print("%s: VERIFICATION FAILED - output may not be equivalent:" % path, file=sys.stderr)
            for problem in v.problems:
                print("  " + problem, file=sys.stderr)
            if v.lua_error:
                print("  Lua 5.4: " + v.lua_error, file=sys.stderr)
        if not args.quiet:
            check = "skipped" if v is None else ("OK" if v.ok else "FAILED")
            print("%s: renamed %d variables (%s side), verification %s%s" % (
                path, len(result.renames), result.summary.side, check,
                (" -> " + target) if target else ""), file=sys.stderr)
    return status
