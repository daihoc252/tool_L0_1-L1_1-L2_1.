"""Lexical scope resolution.

Links every ``Name`` reference to the ``Binding`` (local variable) it refers
to, or to ``None`` for globals, following Lua's scoping rules exactly:

* ``local x = <expr>``         x is visible *after* the statement
* ``local function f``         f is visible inside its own body
* function parameters          visible in the function body
* for-loop variables           visible in the loop body
* repeat ... until cond        cond sees the body's locals
"""

from . import nodes as N


class Binding:
    """One declared local variable (a parameter, for variable, local...)."""

    _counter = 0

    def __init__(self, name_node, kind, func, block, stmt=None):
        Binding._counter += 1
        self.id = Binding._counter
        self.name = name_node.name
        self.decl = name_node
        self.kind = kind          # 'local' | 'localfunc' | 'param' | 'for' | 'self'
        self.func = func          # Function / Chunk owning the variable
        self.block = block        # Block in which the variable is in scope
        self.stmt = stmt          # declaring statement (Local / LocalFunction / loop)
        self.attrib = None
        self.refs = []            # all Name nodes bound to this variable (incl. decl)
        self.scope_start = name_node.pos
        self.scope_end = block.end_pos if block is not None else name_node.pos

    def __repr__(self):
        return "Binding(%s#%d, %s)" % (self.name, self.id, self.kind)


class Resolver:
    def __init__(self):
        self.scopes = []
        self.func = None
        self.bindings = []
        self.globals = set()

    def resolve(self, chunk):
        self.func = chunk
        self.visit_block(chunk.body)
        return self.bindings

    # ------------------------------------------------------------ helpers
    def declare(self, name_node, kind, block, stmt=None):
        binding = Binding(name_node, kind, self.func, block, stmt)
        name_node.binding = binding
        name_node.func = self.func
        name_node.is_decl = True
        binding.refs.append(name_node)
        self.scopes[-1][binding.name] = binding
        self.bindings.append(binding)
        return binding

    def lookup(self, name_node):
        name_node.func = self.func
        for scope in reversed(self.scopes):
            binding = scope.get(name_node.name)
            if binding is not None:
                name_node.binding = binding
                binding.refs.append(name_node)
                return
        name_node.binding = None
        self.globals.add(name_node.name)

    # ------------------------------------------------------------ blocks
    def visit_block(self, block, declare=None):
        """Visit a block in a new scope; ``declare`` pre-binds names in it."""
        self.scopes.append({})
        if declare:
            declare(block)
        for stmt in block.stmts:
            self.visit_stmt(stmt, block)
        if block.repeat_cond is not None:
            self.visit_expr(block.repeat_cond)
        self.scopes.pop()

    def visit_function(self, func, self_name=None):
        outer = self.func
        self.func = func

        def declare(block):
            if self_name is not None:
                self.declare(self_name, "self", block)
            for param in func.params:
                self.declare(param, "param", block)

        self.visit_block(func.body, declare)
        self.func = outer

    # ------------------------------------------------------------ statements
    def visit_stmt(self, s, block):
        if isinstance(s, N.Local):
            for expr in s.exprs:
                self.visit_expr(expr)
            for name, attrib in zip(s.names, s.attribs):
                self.declare(name, "local", block, s).attrib = attrib
        elif isinstance(s, N.LocalFunction):
            self.declare(s.name, "localfunc", block, s)
            self.visit_function(s.func)
        elif isinstance(s, N.Assign):
            for expr in s.exprs:
                self.visit_expr(expr)
            for target in s.targets:
                self.visit_expr(target)
        elif isinstance(s, N.CallStmt):
            self.visit_expr(s.call)
        elif isinstance(s, N.Do):
            self.visit_block(s.body)
        elif isinstance(s, N.While):
            self.visit_expr(s.cond)
            self.visit_block(s.body)
        elif isinstance(s, N.Repeat):
            self.visit_block(s.body)
        elif isinstance(s, N.If):
            for cond, body in zip(s.conds, s.blocks):
                self.visit_expr(cond)
                self.visit_block(body)
            if s.orelse is not None:
                self.visit_block(s.orelse)
        elif isinstance(s, N.NumFor):
            for expr in (s.start, s.stop, s.step):
                if expr is not None:
                    self.visit_expr(expr)
            self.visit_block(s.body, lambda b: self.declare(s.var, "for", b, s))
        elif isinstance(s, N.GenFor):
            for expr in s.exprs:
                self.visit_expr(expr)
            self.visit_block(s.body, lambda b: [self.declare(n, "for", b, s) for n in s.names])
        elif isinstance(s, N.FunctionStmt):
            self.visit_expr(s.target)
            if s.method:
                implicit_self = N.Name("self", pos=s.func.pos, line=s.func.line)
                s.func.implicit_self = implicit_self
                self.visit_function(s.func, implicit_self)
            else:
                self.visit_function(s.func)
        elif isinstance(s, N.Return):
            for expr in s.exprs:
                self.visit_expr(expr)
        # Break / Goto / Label have no names to resolve.

    # ------------------------------------------------------------ expressions
    def visit_expr(self, e):
        if isinstance(e, N.Name):
            self.lookup(e)
        elif isinstance(e, N.Function):
            self.visit_function(e)
        elif isinstance(e, N.Index):
            self.visit_expr(e.obj)
            self.visit_expr(e.key)
        elif isinstance(e, N.Call):
            self.visit_expr(e.func)
            for arg in e.args:
                self.visit_expr(arg)
        elif isinstance(e, N.MethodCall):
            self.visit_expr(e.obj)
            for arg in e.args:
                self.visit_expr(arg)
        elif isinstance(e, N.Table):
            for field in e.fields:
                if field.kind == "expr":
                    self.visit_expr(field.key)
                self.visit_expr(field.value)
        elif isinstance(e, N.BinOp):
            self.visit_expr(e.left)
            self.visit_expr(e.right)
        elif isinstance(e, N.UnOp):
            self.visit_expr(e.operand)
        elif isinstance(e, N.Paren):
            self.visit_expr(e.expr)


def set_parents(node):
    for child in node.children():
        child.parent = node
        set_parents(child)


def resolve(chunk):
    """Resolve all names in ``chunk``; returns (bindings, global_names)."""
    set_parents(chunk)
    resolver = Resolver()
    bindings = resolver.resolve(chunk)
    return bindings, resolver.globals
