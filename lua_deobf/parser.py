"""Recursive-descent parser for Lua 5.4 / CfxLua producing ``nodes`` ASTs."""

from .lexer import LuaSyntaxError, tokenize
from . import nodes as N

# Binary operator priorities (left, right), taken from lparser.c of Lua 5.4.
BINARY_PRIORITY = {
    "or": (1, 1), "and": (2, 2),
    "<": (3, 3), ">": (3, 3), "<=": (3, 3), ">=": (3, 3), "~=": (3, 3), "==": (3, 3),
    "|": (4, 4), "~": (5, 5), "&": (6, 6), "<<": (7, 7), ">>": (7, 7),
    "..": (9, 8),
    "+": (10, 10), "-": (10, 10),
    "*": (11, 11), "/": (11, 11), "//": (11, 11), "%": (11, 11),
    "^": (14, 13),
}
UNARY_PRIORITY = 12
UNARY_OPS = ("not", "-", "#", "~")
COMPOUND_OPS = ("+=", "-=", "*=", "/=", "%=", "^=", "..=", "|=", "&=", "<<=", ">>=", "//=")
BLOCK_END = ("end", "else", "elseif", "until")


class Parser:
    def __init__(self, source):
        self.tokens = tokenize(source)
        self.i = 0
        self.pending_comments = []

    # ------------------------------------------------------------ utilities
    @property
    def tok(self):
        return self.tokens[self.i]

    def peek(self, offset=1):
        return self.tokens[min(self.i + offset, len(self.tokens) - 1)]

    def advance(self):
        tok = self.tokens[self.i]
        if tok.comments:
            self.pending_comments.extend(tok.comments)
            tok.comments = []
        if tok.kind != "eof":
            self.i += 1
        return tok

    def take_comments(self):
        comments = self.pending_comments + self.tok.comments
        self.pending_comments = []
        self.tok.comments = []
        return comments

    def error(self, message):
        tok = self.tok
        near = tok.value if tok.kind != "eof" else "<eof>"
        raise LuaSyntaxError("%s near %r" % (message, near), tok.line)

    def check_op(self, value):
        return self.tok.kind == "op" and self.tok.value == value

    def check_kw(self, value):
        return self.tok.kind == "keyword" and self.tok.value == value

    def accept_op(self, value):
        if self.check_op(value):
            return self.advance()
        return None

    def accept_kw(self, value):
        if self.check_kw(value):
            return self.advance()
        return None

    def expect_op(self, value):
        if not self.check_op(value):
            self.error("'%s' expected" % value)
        return self.advance()

    def expect_kw(self, value):
        if not self.check_kw(value):
            self.error("'%s' expected" % value)
        return self.advance()

    def expect_name(self):
        if self.tok.kind != "name":
            self.error("<name> expected")
        return self.advance()

    def make_name(self, tok):
        return N.Name(tok.value, pos=tok.index, line=tok.line)

    # ------------------------------------------------------------ blocks
    def parse_chunk(self):
        body = self.parse_block()
        if self.tok.kind != "eof":
            self.error("'<eof>' expected")
        return N.Chunk(body, pos=0, line=1)

    def block_follows(self, with_until=True):
        tok = self.tok
        if tok.kind == "eof":
            return True
        if tok.kind == "keyword" and tok.value in BLOCK_END:
            return with_until or tok.value != "until"
        return False

    def parse_block(self):
        block = N.Block([], pos=self.tok.index, line=self.tok.line)
        while not self.block_follows():
            if self.check_kw("return"):
                block.stmts.append(self.parse_return())
                break
            comments = self.take_comments()
            if self.accept_op(";"):
                self.pending_comments = comments + self.pending_comments
                continue
            stmt = self.parse_statement()
            stmt.comments = comments + stmt.comments
            block.stmts.append(stmt)
        block.trailing_comments = self.take_comments()
        block.end_pos = self.tok.index
        return block

    def parse_return(self):
        comments = self.take_comments()
        tok = self.advance()
        exprs = []
        if not self.block_follows() and not self.check_op(";"):
            exprs = self.parse_exprlist()
        self.accept_op(";")
        if not self.block_follows():
            self.error("'end' expected")
        stmt = N.Return(exprs, pos=tok.index, line=tok.line)
        stmt.comments = comments
        return stmt

    # ------------------------------------------------------------ statements
    def parse_statement(self):
        tok = self.tok
        pos, line = tok.index, tok.line
        if tok.kind == "keyword":
            kw = tok.value
            if kw == "if":
                return self.parse_if()
            if kw == "while":
                self.advance()
                cond = self.parse_expr()
                self.expect_kw("do")
                body = self.parse_block()
                self.expect_kw("end")
                return N.While(cond, body, pos=pos, line=line)
            if kw == "do":
                self.advance()
                body = self.parse_block()
                self.expect_kw("end")
                return N.Do(body, pos=pos, line=line)
            if kw == "for":
                return self.parse_for()
            if kw == "repeat":
                self.advance()
                body = self.parse_block()
                self.expect_kw("until")
                cond = self.parse_expr()
                body.repeat_cond = cond
                return N.Repeat(body, cond, pos=pos, line=line)
            if kw == "function":
                return self.parse_function_stmt()
            if kw == "local":
                self.advance()
                if self.accept_kw("function"):
                    name = self.make_name(self.expect_name())
                    func = self.parse_funcbody(pos, line)
                    return N.LocalFunction(name, func, pos=pos, line=line)
                return self.parse_local(pos, line)
            if kw == "return":
                self.error("unexpected 'return'")
            if kw == "break":
                self.advance()
                return N.Break(pos=pos, line=line)
            if kw == "goto":
                self.advance()
                return N.Goto(self.expect_name().value, pos=pos, line=line)
        if self.accept_op("::"):
            label = self.expect_name().value
            self.expect_op("::")
            return N.Label(label, pos=pos, line=line)
        return self.parse_expr_statement()

    def parse_if(self):
        tok = self.advance()
        conds, blocks = [], []
        cond = self.parse_expr()
        self.expect_kw("then")
        conds.append(cond)
        blocks.append(self.parse_block())
        orelse = None
        while True:
            if self.accept_kw("elseif"):
                conds.append(self.parse_expr())
                self.expect_kw("then")
                blocks.append(self.parse_block())
            elif self.accept_kw("else"):
                orelse = self.parse_block()
                self.expect_kw("end")
                break
            else:
                self.expect_kw("end")
                break
        return N.If(conds, blocks, orelse, pos=tok.index, line=tok.line)

    def parse_for(self):
        tok = self.advance()
        first = self.make_name(self.expect_name())
        if self.accept_op("="):
            start = self.parse_expr()
            self.expect_op(",")
            stop = self.parse_expr()
            step = self.parse_expr() if self.accept_op(",") else None
            self.expect_kw("do")
            body = self.parse_block()
            self.expect_kw("end")
            return N.NumFor(first, start, stop, step, body, pos=tok.index, line=tok.line)
        names = [first]
        while self.accept_op(","):
            names.append(self.make_name(self.expect_name()))
        self.expect_kw("in")
        exprs = self.parse_exprlist()
        self.expect_kw("do")
        body = self.parse_block()
        self.expect_kw("end")
        return N.GenFor(names, exprs, body, pos=tok.index, line=tok.line)

    def parse_function_stmt(self):
        tok = self.advance()
        name_tok = self.expect_name()
        target = self.make_name(name_tok)
        method = None
        while self.check_op(".") or self.check_op(":"):
            sep = self.advance().value
            key_tok = self.expect_name()
            if sep == ":":
                method = key_tok.value
                break
            key = N.Const("string", '"%s"' % key_tok.value, pos=key_tok.index, line=key_tok.line)
            target = N.Index(target, key, "dot", pos=target.pos, line=target.line)
        func = self.parse_funcbody(tok.index, tok.line)
        return N.FunctionStmt(target, method, func, pos=tok.index, line=tok.line)

    def parse_local(self, pos, line):
        names, attribs = [], []
        while True:
            names.append(self.make_name(self.expect_name()))
            attrib = None
            if self.accept_op("<"):
                attrib = self.expect_name().value
                if self.check_op(">="):
                    # `local x <const>= 1`: split the '>=' token into '>' '='.
                    self.tok.value = "="
                else:
                    self.expect_op(">")
            attribs.append(attrib)
            if not self.accept_op(","):
                break
        exprs = self.parse_exprlist() if self.accept_op("=") else []
        return N.Local(names, attribs, exprs, pos=pos, line=line)

    def parse_expr_statement(self):
        tok = self.tok
        expr = self.parse_suffixed()
        if self.check_op("=") or self.check_op(","):
            targets = [expr]
            while self.accept_op(","):
                targets.append(self.parse_suffixed())
            self.expect_op("=")
            for target in targets:
                if not isinstance(target, (N.Name, N.Index)):
                    self.error("syntax error (cannot assign)")
            exprs = self.parse_exprlist()
            return N.Assign(targets, exprs, "=", pos=tok.index, line=tok.line)
        if self.tok.kind == "op" and self.tok.value in COMPOUND_OPS:
            op = self.advance().value
            if not isinstance(expr, (N.Name, N.Index)):
                self.error("syntax error (cannot assign)")
            value = self.parse_expr()
            return N.Assign([expr], [value], op, pos=tok.index, line=tok.line)
        if not isinstance(expr, (N.Call, N.MethodCall)):
            self.error("syntax error")
        return N.CallStmt(expr, pos=tok.index, line=tok.line)

    # ------------------------------------------------------------ expressions
    def parse_exprlist(self):
        exprs = [self.parse_expr()]
        while self.accept_op(","):
            exprs.append(self.parse_expr())
        return exprs

    def parse_expr(self, limit=0):
        tok = self.tok
        if (tok.kind == "op" and tok.value in ("-", "#", "~")) or tok.is_kw("not"):
            self.advance()
            operand = self.parse_expr(UNARY_PRIORITY)
            left = N.UnOp(tok.value, operand, pos=tok.index, line=tok.line)
        else:
            left = self.parse_simple()
        while True:
            op_tok = self.tok
            if op_tok.kind not in ("op", "keyword"):
                break
            prio = BINARY_PRIORITY.get(op_tok.value)
            if prio is None or prio[0] <= limit:
                break
            self.advance()
            right = self.parse_expr(prio[1])
            left = N.BinOp(op_tok.value, left, right, pos=left.pos, line=left.line)
        return left

    def parse_simple(self):
        tok = self.tok
        pos, line = tok.index, tok.line
        if tok.kind == "number":
            self.advance()
            return N.Const("number", tok.value, pos=pos, line=line)
        if tok.kind == "string":
            self.advance()
            return N.Const("string", tok.value, pos=pos, line=line)
        if tok.kind == "keyword":
            if tok.value in ("nil", "true", "false"):
                self.advance()
                return N.Const(tok.value, tok.value, pos=pos, line=line)
            if tok.value == "function":
                self.advance()
                return self.parse_funcbody(pos, line)
        if tok.is_op("..."):
            self.advance()
            return N.Const("vararg", "...", pos=pos, line=line)
        if tok.is_op("{"):
            return self.parse_table()
        return self.parse_suffixed()

    def parse_primary(self):
        tok = self.tok
        if tok.kind == "name":
            self.advance()
            return self.make_name(tok)
        if tok.is_op("("):
            self.advance()
            expr = self.parse_expr()
            self.expect_op(")")
            return N.Paren(expr, pos=tok.index, line=tok.line)
        self.error("unexpected symbol")

    def parse_suffixed(self):
        expr = self.parse_primary()
        while True:
            tok = self.tok
            if tok.is_op(".") or tok.is_op("?."):
                self.advance()
                key_tok = self.expect_name()
                key = N.Const("string", '"%s"' % key_tok.value, pos=key_tok.index, line=key_tok.line)
                expr = N.Index(expr, key, "dot" if tok.value == "." else "safe",
                               pos=expr.pos, line=expr.line)
            elif tok.is_op("["):
                self.advance()
                key = self.parse_expr()
                self.expect_op("]")
                expr = N.Index(expr, key, "bracket", pos=expr.pos, line=expr.line)
            elif tok.is_op(":"):
                self.advance()
                method = self.expect_name().value
                args = self.parse_args()
                expr = N.MethodCall(expr, method, args, pos=expr.pos, line=expr.line)
            elif tok.is_op("(") or tok.is_op("{") or tok.kind == "string":
                args = self.parse_args()
                expr = N.Call(expr, args, pos=expr.pos, line=expr.line)
            else:
                return expr

    def parse_args(self):
        tok = self.tok
        if tok.kind == "string":
            self.advance()
            return [N.Const("string", tok.value, pos=tok.index, line=tok.line)]
        if tok.is_op("{"):
            return [self.parse_table()]
        self.expect_op("(")
        args = []
        if not self.check_op(")"):
            args = self.parse_exprlist()
        self.expect_op(")")
        return args

    def parse_table(self):
        tok = self.expect_op("{")
        fields = []
        while not self.check_op("}"):
            ftok = self.tok
            if ftok.is_op("["):
                self.advance()
                key = self.parse_expr()
                self.expect_op("]")
                self.expect_op("=")
                field = N.TableField("expr", key, self.parse_expr(), pos=ftok.index, line=ftok.line)
            elif ftok.kind == "name" and self.peek().is_op("="):
                self.advance()
                self.advance()
                field = N.TableField("named", ftok.value, self.parse_expr(), pos=ftok.index, line=ftok.line)
            else:
                field = N.TableField("pos", None, self.parse_expr(), pos=ftok.index, line=ftok.line)
            fields.append(field)
            if not (self.accept_op(",") or self.accept_op(";")):
                break
        self.expect_op("}")
        return N.Table(fields, pos=tok.index, line=tok.line)

    def parse_funcbody(self, pos, line):
        self.expect_op("(")
        params, is_vararg = [], False
        if not self.check_op(")"):
            while True:
                if self.accept_op("..."):
                    is_vararg = True
                    break
                params.append(self.make_name(self.expect_name()))
                if not self.accept_op(","):
                    break
        self.expect_op(")")
        body = self.parse_block()
        self.expect_kw("end")
        return N.Function(params, is_vararg, body, pos=pos, line=line)


def parse(source):
    """Parse Lua source text into a ``nodes.Chunk``."""
    return Parser(source).parse_chunk()
