"""Pretty printer that turns a ``nodes`` AST back into formatted Lua source.

The printer never adds or removes parentheses (``Paren`` nodes are kept by
the parser), and literals are re-emitted from their raw source text, so the
printed program parses back into exactly the same tree.
"""

import re

from . import nodes as N

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
INLINE_TABLE_LIMIT = 90


def string_key(expr):
    """Return the identifier if ``expr`` is a string constant usable as .key."""
    if isinstance(expr, N.Const) and expr.kind == "string" and expr.raw[:1] in "\"'":
        body = expr.raw[1:-1]
        if _IDENT_RE.match(body):
            from .lexer import KEYWORDS
            if body not in KEYWORDS:
                return body
    return None


class Printer:
    def __init__(self, indent="    "):
        self.indent_unit = indent

    def ind(self, level):
        return self.indent_unit * level

    # ------------------------------------------------------------ program
    def chunk(self, chunk):
        lines = []
        for comment in chunk.header_comments:
            lines.extend(comment.split("\n"))
        if chunk.header_comments and chunk.body.stmts:
            lines.append("")
        lines.extend(self.block(chunk.body, 0))
        return "\n".join(lines).rstrip() + "\n"

    def block(self, block, level):
        lines = []
        pad = self.ind(level)
        for i, stmt in enumerate(block.stmts):
            if i > 0 and getattr(stmt, "blank_before", False):
                lines.append("")
            for comment in stmt.comments:
                lines.extend(pad + part if j == 0 else part
                             for j, part in enumerate(comment.split("\n")))
            text = self.stmt(stmt, level)
            if text.startswith("("):
                text = ";" + text      # keep `a = b` / `(f)()` from merging
            lines.append(pad + text)
        for comment in block.trailing_comments:
            lines.extend(pad + part if j == 0 else part
                         for j, part in enumerate(comment.split("\n")))
        return lines

    def body(self, block, level):
        """Render an indented block followed by a newline (or nothing if empty)."""
        lines = self.block(block, level)
        if not lines:
            return "\n"
        return "\n" + "\n".join(lines) + "\n"

    # ------------------------------------------------------------ statements
    def stmt(self, s, level):
        method = getattr(self, "stmt_" + type(s).__name__)
        return method(s, level)

    def stmt_Local(self, s, level):
        names = []
        for name, attrib in zip(s.names, s.attribs):
            names.append(name.name + (" <%s>" % attrib if attrib else ""))
        text = "local " + ", ".join(names)
        if s.exprs:
            text += " = " + self.exprlist(s.exprs, level)
        return text

    def stmt_Assign(self, s, level):
        targets = ", ".join(self.expr(t, level) for t in s.targets)
        return "%s %s %s" % (targets, s.op, self.exprlist(s.exprs, level))

    def stmt_CallStmt(self, s, level):
        return self.expr(s.call, level)

    def stmt_Do(self, s, level):
        return "do" + self.body(s.body, level + 1) + self.ind(level) + "end"

    def stmt_While(self, s, level):
        return ("while %s do" % self.expr(s.cond, level) + self.body(s.body, level + 1)
                + self.ind(level) + "end")

    def stmt_Repeat(self, s, level):
        return ("repeat" + self.body(s.body, level + 1) + self.ind(level)
                + "until " + self.expr(s.cond, level))

    def stmt_If(self, s, level):
        out = []
        for i, (cond, block) in enumerate(zip(s.conds, s.blocks)):
            keyword = "if" if i == 0 else self.ind(level) + "elseif"
            out.append("%s %s then" % (keyword, self.expr(cond, level)) + self.body(block, level + 1))
        if s.orelse is not None:
            out.append(self.ind(level) + "else" + self.body(s.orelse, level + 1))
        return "".join(out) + self.ind(level) + "end"

    def stmt_NumFor(self, s, level):
        parts = [self.expr(s.start, level), self.expr(s.stop, level)]
        if s.step is not None:
            parts.append(self.expr(s.step, level))
        return ("for %s = %s do" % (s.var.name, ", ".join(parts)) + self.body(s.body, level + 1)
                + self.ind(level) + "end")

    def stmt_GenFor(self, s, level):
        return ("for %s in %s do" % (", ".join(n.name for n in s.names), self.exprlist(s.exprs, level))
                + self.body(s.body, level + 1) + self.ind(level) + "end")

    def stmt_FunctionStmt(self, s, level):
        name = self.funcname(s.target)
        if s.method:
            name += ":" + s.method
        return "function " + name + self.funcbody(s.func, level)

    def funcname(self, target):
        if isinstance(target, N.Name):
            return target.name
        return self.funcname(target.obj) + "." + string_key(target.key)

    def stmt_LocalFunction(self, s, level):
        return "local function " + s.name.name + self.funcbody(s.func, level)

    def stmt_Return(self, s, level):
        if not s.exprs:
            return "return"
        return "return " + self.exprlist(s.exprs, level)

    def stmt_Break(self, s, level):
        return "break"

    def stmt_Goto(self, s, level):
        return "goto " + s.label

    def stmt_Label(self, s, level):
        return "::%s::" % s.label

    # ------------------------------------------------------------ expressions
    def exprlist(self, exprs, level):
        return ", ".join(self.expr(e, level) for e in exprs)

    def expr(self, e, level):
        method = getattr(self, "expr_" + type(e).__name__)
        return method(e, level)

    def expr_Const(self, e, level):
        return e.raw

    def expr_Name(self, e, level):
        return e.name

    def expr_Index(self, e, level):
        obj = self.expr(e.obj, level)
        if e.style in ("dot", "safe"):
            key = string_key(e.key)
            if key is not None:
                return obj + ("." if e.style == "dot" else "?.") + key
        return "%s[%s]" % (obj, self.expr(e.key, level))

    def expr_Call(self, e, level):
        return "%s(%s)" % (self.expr(e.func, level), self.exprlist(e.args, level))

    def expr_MethodCall(self, e, level):
        return "%s:%s(%s)" % (self.expr(e.obj, level), e.method, self.exprlist(e.args, level))

    def expr_Function(self, e, level):
        return "function" + self.funcbody(e, level)

    def funcbody(self, func, level):
        params = [p.name for p in func.params]
        if func.is_vararg:
            params.append("...")
        return "(%s)" % ", ".join(params) + self.body(func.body, level + 1) + self.ind(level) + "end"

    def expr_Table(self, e, level):
        if not e.fields:
            return "{}"
        inline = [self.field(f, level + 1) for f in e.fields]
        joined = ", ".join(inline)
        if "\n" not in joined and len(joined) <= INLINE_TABLE_LIMIT:
            return "{" + joined + "}"
        pad = self.ind(level + 1)
        return "{\n" + ",\n".join(pad + f for f in inline) + "\n" + self.ind(level) + "}"

    def field(self, f, level):
        value = self.expr(f.value, level)
        if f.kind == "pos":
            return value
        if f.kind == "named":
            return "%s = %s" % (f.key, value)
        return "[%s] = %s" % (self.expr(f.key, level), value)

    def expr_BinOp(self, e, level):
        return "%s %s %s" % (self.expr(e.left, level), e.op, self.expr(e.right, level))

    def expr_UnOp(self, e, level):
        operand = self.expr(e.operand, level)
        if e.op == "not":
            return "not " + operand
        if e.op == "-" and operand.startswith("-"):
            return "- " + operand          # avoid producing a `--` comment
        return e.op + operand

    def expr_Paren(self, e, level):
        return "(%s)" % self.expr(e.expr, level)


def to_source(chunk, indent="    "):
    return Printer(indent).chunk(chunk)
