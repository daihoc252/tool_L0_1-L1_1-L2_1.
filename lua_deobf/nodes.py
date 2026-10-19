"""AST node definitions for the Lua parser.

Every node records ``pos`` (index of its first token) so that scope ranges
can be compared. Parenthesised expressions are kept as ``Paren`` nodes,
which lets the printer reproduce the exact original grouping (parentheses
also truncate multiple results in Lua, so dropping them would change code).
"""


class Node:
    _fields = ()

    def __init__(self, *args, **kwargs):
        for name, value in zip(self._fields, args):
            setattr(self, name, value)
        for name in self._fields[len(args):]:
            setattr(self, name, kwargs.pop(name, None))
        self.pos = kwargs.pop("pos", 0)
        self.line = kwargs.pop("line", 0)
        self.comments = []       # comments printed above a statement
        self.parent = None
        if kwargs:
            raise TypeError("unexpected fields %r" % list(kwargs))

    def children(self):
        for name in self._fields:
            value = getattr(self, name)
            yield from _iter_nodes(value)

    def __repr__(self):
        return "%s(%s)" % (type(self).__name__, ", ".join(
            "%s=%r" % (f, getattr(self, f)) for f in self._fields))


def _iter_nodes(value):
    if isinstance(value, Node):
        yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_nodes(item)


def walk(node):
    """Yield ``node`` and all its descendants in source order."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(list(current.children())))


# ---------------------------------------------------------------- expressions

class Expr(Node):
    pass


class Const(Expr):
    """nil / true / false / number / string / vararg literal (raw text kept)."""
    _fields = ("kind", "raw")


class Name(Expr):
    _fields = ("name",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.binding = None      # scope.Binding, None for globals
        self.func = None         # Function node (or Chunk) the reference is in
        self.is_decl = False
        self.segment = None      # naming.Segment for renamed variables


class Index(Expr):
    """obj.key / obj[key] / obj?.key  (style: 'dot' | 'bracket' | 'safe')."""
    _fields = ("obj", "key", "style")


class Call(Expr):
    _fields = ("func", "args")


class MethodCall(Expr):
    _fields = ("obj", "method", "args")


class Function(Expr):
    _fields = ("params", "is_vararg", "body")


class TableField(Node):
    """kind: 'pos' (value), 'named' (name = value), 'expr' ([key] = value)."""
    _fields = ("kind", "key", "value")


class Table(Expr):
    _fields = ("fields",)


class BinOp(Expr):
    _fields = ("op", "left", "right")


class UnOp(Expr):
    _fields = ("op", "operand")


class Paren(Expr):
    _fields = ("expr",)


# ----------------------------------------------------------------- statements

class Stmt(Node):
    pass


class Block(Node):
    _fields = ("stmts",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.end_pos = 0
        self.trailing_comments = []
        self.repeat_cond = None  # set for repeat-until bodies (cond is in scope)


class Chunk(Node):
    _fields = ("body",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params = []
        self.is_vararg = True
        self.header_comments = []


class Local(Stmt):
    _fields = ("names", "attribs", "exprs")


class Assign(Stmt):
    """targets op exprs, where op is '=' or a CfxLua compound operator."""
    _fields = ("targets", "exprs", "op")


class CallStmt(Stmt):
    _fields = ("call",)


class Do(Stmt):
    _fields = ("body",)


class While(Stmt):
    _fields = ("cond", "body")


class Repeat(Stmt):
    _fields = ("body", "cond")


class If(Stmt):
    """conds[i] guards blocks[i] (if/elseif); orelse is the else Block or None."""
    _fields = ("conds", "blocks", "orelse")

    def children(self):
        for cond, block in zip(self.conds, self.blocks):
            yield cond
            yield block
        if self.orelse is not None:
            yield self.orelse


class NumFor(Stmt):
    _fields = ("var", "start", "stop", "step", "body")


class GenFor(Stmt):
    _fields = ("names", "exprs", "body")


class FunctionStmt(Stmt):
    """function a.b.c(...) / function a.b:c(...); target is Name or Index chain."""
    _fields = ("target", "method", "func")


class LocalFunction(Stmt):
    _fields = ("name", "func")


class Return(Stmt):
    _fields = ("exprs",)


class Break(Stmt):
    _fields = ()


class Goto(Stmt):
    _fields = ("label",)


class Label(Stmt):
    _fields = ("label",)
