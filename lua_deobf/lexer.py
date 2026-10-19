"""Tokenizer for Lua 5.4 with the CfxLua (FiveM) extensions.

Supported extras on top of stock Lua 5.4:
  * backtick hash strings:   `prop_bench_01a`
  * compound assignment:     a += 1, s ..= "x", n //= 2, ...
  * safe navigation:         a?.b
  * C-style comments are NOT supported (they are not valid CfxLua either).

Comments are not emitted as tokens; they are attached to the token that
follows them (``Token.comments``) so the parser can keep them.
"""

import re

KEYWORDS = frozenset("""
and break do else elseif end false for function goto if in local nil not or
repeat return then true until while
""".split())

# Longest operators first so the scanner is greedy.
OPERATORS = sorted("""
... ..= .. == ~= <= >= << >> // :: += -= *= /= %= ^= |= &= <<= >>= //= ?.
+ - * / % ^ # & ~ | < > = ( ) { } [ ] ; : , .
""".split(), key=len, reverse=True)

_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_HEX_RE = re.compile(r"0[xX](?:[0-9a-fA-F]*\.?[0-9a-fA-F]*)(?:[pP][+-]?[0-9]+)?")
_DEC_RE = re.compile(r"(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_LONG_OPEN_RE = re.compile(r"\[(=*)\[")


class LuaSyntaxError(Exception):
    def __init__(self, message, line=None):
        if line is not None:
            message = "line %d: %s" % (line, message)
        super().__init__(message)
        self.line = line


class Token:
    __slots__ = ("kind", "value", "line", "index", "comments")

    def __init__(self, kind, value, line):
        self.kind = kind        # 'name' | 'keyword' | 'number' | 'string' | 'op' | 'eof'
        self.value = value      # raw source text of the token
        self.line = line
        self.index = 0          # position in the token stream (set by tokenize)
        self.comments = []      # raw comment texts that precede this token

    def is_op(self, value):
        return self.kind == "op" and self.value == value

    def is_kw(self, value):
        return self.kind == "keyword" and self.value == value

    def __repr__(self):
        return "Token(%s, %r, line %d)" % (self.kind, self.value, self.line)


def _read_long_bracket(src, pos, line):
    """Read a [==[ ... ]==] long bracket starting at ``pos``.

    Returns (end_position, newline_count)."""
    m = _LONG_OPEN_RE.match(src, pos)
    if not m:
        return None
    close = "]" + m.group(1) + "]"
    end = src.find(close, m.end())
    if end < 0:
        raise LuaSyntaxError("unfinished long string/comment", line)
    end += len(close)
    return end, src.count("\n", pos, end)


def _read_quoted(src, pos, line):
    quote = src[pos]
    i = pos + 1
    n = len(src)
    while i < n:
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if c == quote:
            return i + 1
        if c == "\n" and quote != "`":
            raise LuaSyntaxError("unfinished string", line)
        i += 1
    raise LuaSyntaxError("unfinished string", line)


def tokenize(src):
    """Turn Lua source into a list of tokens ending with an 'eof' token."""
    tokens = []
    comments = []
    pos = 0
    line = 1
    n = len(src)

    # A shebang line is kept as a comment so it survives a round trip.
    if src.startswith("#"):
        end = src.find("\n")
        end = n if end < 0 else end
        comments.append(src[:end])
        pos = end

    while True:
        # Skip whitespace and collect comments.
        while pos < n:
            c = src[pos]
            if c == "\n":
                line += 1
                pos += 1
            elif c in " \t\r\f\v":
                pos += 1
            elif src.startswith("--", pos):
                long = _read_long_bracket(src, pos + 2, line)
                if long:
                    end, newlines = long
                    comments.append(src[pos:end])
                    line += newlines
                    pos = end
                else:
                    end = src.find("\n", pos)
                    end = n if end < 0 else end
                    comments.append(src[pos:end].rstrip())
                    pos = end
            else:
                break

        if pos >= n:
            tok = Token("eof", "", line)
            tok.comments = comments
            tokens.append(tok)
            break

        c = src[pos]
        start_line = line
        if c.isalpha() or c == "_":
            m = _NAME_RE.match(src, pos)
            word = m.group(0)
            tok = Token("keyword" if word in KEYWORDS else "name", word, line)
            pos = m.end()
        elif c.isdigit() or (c == "." and pos + 1 < n and src[pos + 1].isdigit()):
            m = _HEX_RE.match(src, pos) if src.startswith(("0x", "0X"), pos) else None
            if not m:
                m = _DEC_RE.match(src, pos)
            text = m.group(0)
            end = m.end()
            # Reject things such as 3x or 1.2.3 the same way Lua does.
            if end < n and (src[end].isalnum() or src[end] == "_" or
                            (src[end] == "." and not src.startswith("..", end))):
                raise LuaSyntaxError("malformed number near %r" % src[pos:end + 1], line)
            tok = Token("number", text, line)
            pos = end
        elif c in "\"'`":
            end = _read_quoted(src, pos, line)
            text = src[pos:end]
            line += text.count("\n")
            tok = Token("string", text, start_line)
            pos = end
        elif c == "[" and _LONG_OPEN_RE.match(src, pos):
            end, newlines = _read_long_bracket(src, pos, line)
            tok = Token("string", src[pos:end], line)
            line += newlines
            pos = end
        else:
            for op in OPERATORS:
                if src.startswith(op, pos):
                    break
            else:
                raise LuaSyntaxError("unexpected symbol %r" % c, line)
            tok = Token("op", op, line)
            pos += len(op)

        tok.comments = comments
        comments = []
        tok.index = len(tokens)
        tokens.append(tok)

    tokens[-1].index = len(tokens) - 1
    return tokens


_SIMPLE_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b",
                   "f": "\f", "v": "\v", "\\": "\\", '"': '"', "'": "'",
                   "\n": "\n", "`": "`"}


def decode_string(raw):
    """Best-effort decoding of a Lua string literal's raw text to its value.

    Only used for analysis (event names, etc.); the printer always re-emits
    the original raw text, so imperfect decoding can never change code."""
    if raw.startswith("["):
        m = _LONG_OPEN_RE.match(raw)
        body = raw[m.end():len(raw) - len(m.group(0))]
        return body[1:] if body.startswith("\n") else body
    body = raw[1:-1]
    if "\\" not in body:
        return body
    out = []
    i = 0
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        nxt = body[i + 1] if i + 1 < len(body) else ""
        if nxt in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[nxt])
            i += 2
        elif nxt == "x":
            out.append(chr(int(body[i + 2:i + 4], 16)))
            i += 4
        elif nxt == "z":
            i += 2
            while i < len(body) and body[i].isspace():
                i += 1
        elif nxt.isdigit():
            m = re.match(r"[0-9]{1,3}", body[i + 1:])
            out.append(chr(int(m.group(0))))
            i += 1 + len(m.group(0))
        elif nxt == "u":
            m = re.match(r"u\{([0-9a-fA-F]+)\}", body[i + 1:])
            out.append(chr(int(m.group(1), 16)) if m else "u")
            i += 1 + (len(m.group(0)) if m else 1)
        else:
            out.append(nxt)
            i += 2
    return "".join(out)
