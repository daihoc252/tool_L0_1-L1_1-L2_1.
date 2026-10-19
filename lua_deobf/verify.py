"""Check that the de-obfuscated program behaves exactly like the original.

The output is parsed again and compared with the original program:

1. **Structure** - after erasing local variable names, both programs must
   produce the same canonical token stream (same statements, operators,
   literals, global names, field names and call shapes). Bare ``local x``
   declarations (which only introduce a nil variable) are left out of the
   stream, and ``local x = e`` is treated like ``x = e``; point 2 checks
   that this does not matter.
2. **Data flow** - for every read of a local variable, the set of
   definitions that can reach it (see ``flow.py``) must be the same in both
   programs. Variables captured by closures are not analysed that way;
   for them the renaming must be a one-to-one mapping instead.
3. **Lua** - when the optional ``lupa`` package is installed, the output is
   compiled by a real Lua 5.4 interpreter.
"""

from . import nodes as N
from .flow import CAPTURED, analyze
from .parser import parse
from .scope import resolve

NIL = "nil-declaration"


class Canonical:
    def __init__(self):
        self.tokens = []
        self.refs = []           # every Name, in canonical order
        self.skipped = set()     # ids of names declared by bare `local x`

    def ref(self, name):
        if name.binding is None:
            self.tokens.append(("G", name.name))
        else:
            self.tokens.append(("L",))
        self.refs.append(name)

    def block(self, block):
        self.tokens.append(("BLOCK",))
        for stmt in block.stmts:
            self.stmt(stmt)
        self.tokens.append(("END",))

    def stmt(self, s):
        if isinstance(s, N.Local):
            if not s.exprs and all(a is None for a in s.attribs):
                self.skipped.update(id(n) for n in s.names)
                return
            if any(a is not None for a in s.attribs):
                self.tokens.append(("ATTRIB", tuple(s.attribs)))
            self.tokens.append(("SET", len(s.names), "="))
            for name in s.names:
                self.ref(name)
            self.exprs(s.exprs)
        elif isinstance(s, N.Assign):
            self.tokens.append(("SET", len(s.targets), s.op))
            for target in s.targets:
                self.expr(target)
            self.exprs(s.exprs)
        elif isinstance(s, N.LocalFunction):
            self.tokens.append(("FUNCSET",))
            self.ref(s.name)
            self.expr(s.func)
        elif isinstance(s, N.FunctionStmt) and isinstance(s.target, N.Name) and not s.method:
            self.tokens.append(("FUNCSET",))
            self.ref(s.target)
            self.expr(s.func)
        elif isinstance(s, N.FunctionStmt):
            self.tokens.append(("FUNCPATH", s.method))
            self.expr(s.target)
            self.expr(s.func)
        elif isinstance(s, N.CallStmt):
            self.tokens.append(("CALLSTMT",))
            self.expr(s.call)
        elif isinstance(s, N.Do):
            self.tokens.append(("DO",))
            self.block(s.body)
        elif isinstance(s, N.While):
            self.tokens.append(("WHILE",))
            self.expr(s.cond)
            self.block(s.body)
        elif isinstance(s, N.Repeat):
            self.tokens.append(("REPEAT",))
            self.block(s.body)
            self.expr(s.cond)
        elif isinstance(s, N.If):
            self.tokens.append(("IF", len(s.conds), s.orelse is not None))
            for cond, body in zip(s.conds, s.blocks):
                self.expr(cond)
                self.block(body)
            if s.orelse is not None:
                self.block(s.orelse)
        elif isinstance(s, N.NumFor):
            self.tokens.append(("NUMFOR", s.step is not None))
            self.ref(s.var)
            for expr in (s.start, s.stop, s.step):
                if expr is not None:
                    self.expr(expr)
            self.block(s.body)
        elif isinstance(s, N.GenFor):
            self.tokens.append(("GENFOR", len(s.names)))
            for name in s.names:
                self.ref(name)
            self.exprs(s.exprs)
            self.block(s.body)
        elif isinstance(s, N.Return):
            self.tokens.append(("RETURN",))
            self.exprs(s.exprs)
        elif isinstance(s, N.Break):
            self.tokens.append(("BREAK",))
        elif isinstance(s, N.Goto):
            self.tokens.append(("GOTO", s.label))
        elif isinstance(s, N.Label):
            self.tokens.append(("LABEL", s.label))
        else:
            raise TypeError("unknown statement %r" % s)

    def exprs(self, exprs):
        self.tokens.append(("EXPRS", len(exprs)))
        for e in exprs:
            self.expr(e)

    def expr(self, e):
        if isinstance(e, N.Name):
            self.ref(e)
        elif isinstance(e, N.Const):
            self.tokens.append(("CONST", e.kind, e.raw))
        elif isinstance(e, N.Index):
            self.tokens.append(("INDEX", e.style == "safe"))
            self.expr(e.obj)
            self.expr(e.key)
        elif isinstance(e, N.Call):
            self.tokens.append(("CALL", len(e.args)))
            self.expr(e.func)
            for arg in e.args:
                self.expr(arg)
        elif isinstance(e, N.MethodCall):
            self.tokens.append(("METHOD", e.method, len(e.args)))
            self.expr(e.obj)
            for arg in e.args:
                self.expr(arg)
        elif isinstance(e, N.Function):
            self.tokens.append(("FUNCTION", len(e.params), e.is_vararg))
            for param in e.params:
                self.ref(param)
            self.block(e.body)
        elif isinstance(e, N.Table):
            self.tokens.append(("TABLE", tuple(f.kind for f in e.fields)))
            for field in e.fields:
                if field.kind == "named":
                    self.tokens.append(("KEY", field.key))
                elif field.kind == "expr":
                    self.expr(field.key)
                self.expr(field.value)
        elif isinstance(e, N.BinOp):
            self.tokens.append(("BINOP", e.op))
            self.expr(e.left)
            self.expr(e.right)
        elif isinstance(e, N.UnOp):
            self.tokens.append(("UNOP", e.op))
            self.expr(e.operand)
        elif isinstance(e, N.Paren):
            self.tokens.append(("PAREN",))
            self.expr(e.expr)
        else:
            raise TypeError("unknown expression %r" % e)


def canonical(chunk):
    c = Canonical()
    c.block(chunk.body)
    return c


class VerificationResult:
    def __init__(self):
        self.problems = []
        self.lua_checked = False
        self.lua_error = None
        self.locals_checked = 0
        self.uses_checked = 0

    @property
    def ok(self):
        return not self.problems and self.lua_error is None

    def fail(self, message):
        if len(self.problems) < 20:
            self.problems.append(message)


def verify(original_source, output_source, use_lua=True, global_renames=None):
    """``global_renames`` maps intentionally renamed globals (old -> new)."""
    result = VerificationResult()
    original = parse(original_source)
    try:
        output = parse(output_source)
    except Exception as exc:      # pragma: no cover - would be a printer bug
        result.fail("output does not parse: %s" % exc)
        return result
    bindings_o, _ = resolve(original)
    bindings_n, _ = resolve(output)
    co, cn = canonical(original), canonical(output)

    if len(co.tokens) != len(cn.tokens):
        result.fail("program structure differs (%d vs %d tokens)" % (len(co.tokens), len(cn.tokens)))
        return result
    renames = global_renames or {}
    for i, (a, b) in enumerate(zip(co.tokens, cn.tokens)):
        if a[0] == "G" and a[1] in renames:
            a = ("G", renames[a[1]])
        if a != b:
            result.fail("program structure differs at token %d: %r vs %r" % (i, a, b))
            return result

    index_o = {id(r): i for i, r in enumerate(co.refs)}
    index_n = {id(r): i for i, r in enumerate(cn.refs)}
    flow_o = analyze(bindings_o)
    flow_n = analyze(bindings_n)
    tracked_o, tracked_n = flow_o.tracked, flow_n.tracked

    def reaching(flow, index, ref):
        return {"captured" if d is CAPTURED else index.get(id(d), NIL)
                for d in flow.reach.get(id(ref), ())}

    pairs_fwd, pairs_back = {}, {}
    exposed_o, exposed_n = {}, {}
    for i, (ro, rn) in enumerate(zip(co.refs, cn.refs)):
        bo, bn = ro.binding, rn.binding
        if bo is None or bn is None:
            continue          # globals were compared by name in the token stream
        result.locals_checked += 1
        if bo in tracked_o and bn in tracked_n:
            eo, en = flow_o.is_exposed(ro), flow_n.is_exposed(rn)
            if eo != en:
                result.fail("line %d: `%s` (now `%s`) changed whether closures can see it"
                            % (ro.line, ro.name, rn.name))
            elif eo:
                # Accesses visible to closures must stay one shared variable.
                exposed_o.setdefault(bo, set()).add(i)
                exposed_n.setdefault(bn, set()).add(i)
            elif id(ro) in flow_o.reach or id(rn) in flow_n.reach:
                result.uses_checked += 1
                if reaching(flow_o, index_o, ro) != reaching(flow_n, index_n, rn):
                    result.fail("line %d: `%s` (now `%s`) may read a different value"
                                % (ro.line, ro.name, rn.name))
            continue
        if (bo in tracked_o) != (bn in tracked_n):
            result.fail("line %d: `%s` (now `%s`) changed how it is captured"
                        % (ro.line, ro.name, rn.name))
            continue
        if pairs_fwd.setdefault(bo, bn) is not bn or pairs_back.setdefault(bn, bo) is not bo:
            result.fail("line %d: `%s` (now `%s`) refers to a different variable"
                        % (ro.line, ro.name, rn.name))

    groups_o = {frozenset(v) for v in exposed_o.values()}
    groups_n = {frozenset(v) for v in exposed_n.values()}
    if groups_o != groups_n:
        result.fail("variables shared with closures were split or merged differently")

    if use_lua:
        result.lua_checked, result.lua_error = lua_compile(original_source, output_source)
    return result


def lua_compile(original_source, output_source):
    """Compile the output with real Lua 5.4 (via lupa) when possible.

    Returns (checked, error). CfxLua-only syntax (backtick strings, +=) is
    not understood by stock Lua, so if the original does not compile either
    the check is skipped."""
    try:
        from lupa import lua54
    except ImportError:
        try:
            import lupa as lua54        # older lupa: single runtime
        except ImportError:
            return False, None
    runtime = lua54.LuaRuntime()
    check = runtime.eval("function(src) local f, err = load(src, 'chunk', 't', {}) return err end")
    if check(original_source) is not None:
        return False, None
    error = check(output_source)
    return True, error
