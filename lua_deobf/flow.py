"""Reaching-definitions analysis over the structured Lua AST.

For every *use* of a local variable it computes the set of *definitions*
(assignments, declarations, parameters, loop variables) whose value may be
read there. Uses that can never see the same definition are independent
values ("webs"), so they may safely get different names: that is what lets
us split decompiler temporaries such as ``L0_1``, which unluac reuses for
unrelated values, into readable variables.

Closures: once a function capturing a variable has been created, the
closure may read or write it at any later time (event handlers, threads).
From that point on (the *exposed* region) every access to the variable is
joined into one web together with the accesses inside the closures, marked
by the ``CAPTURED`` pseudo-definition. Accesses that no closure can observe
(before the first capture) are still split normally.

Functions containing ``goto``/labels are not analysed (their control flow is
no longer structured); their variables are only renamed, never split.
"""

from . import nodes as N

CAPTURED = N.Name("<captured>")


class ReachingDefs:
    def __init__(self, tracked, capture_points):
        self.tracked = tracked              # set of scope.Binding
        self.capture_points = capture_points  # id(Function) -> bindings it captures
        self.reach = {}                     # id(use Name) -> set of definition Names
        self.exposed = set()                # ids of definitions made after a capture
        self.loop_breaks = []

    # ------------------------------------------------------------ state ops
    @staticmethod
    def join(a, b):
        if a is None:
            return None if b is None else dict(b)
        if b is None:
            return dict(a)
        out = dict(a)
        for key, defs in b.items():
            have = out.get(key)
            out[key] = defs if have is None else (have | defs)
        return out

    def define(self, state, name, fresh=False):
        """``fresh``: a new variable instance (declaration, parameter, loop
        variable); closures created earlier captured a previous instance."""
        binding = name.binding
        if state is None or binding not in self.tracked:
            return
        old = state.get(binding)
        if not fresh and old and CAPTURED in old:
            state[binding] = frozenset((name, CAPTURED))
            self.exposed.add(id(name))
        else:
            state[binding] = frozenset((name,))

    def capture(self, state, func):
        if state is None:
            return
        for binding in self.capture_points.get(id(func), ()):
            if binding in self.tracked:
                current = state.get(binding, frozenset())
                # The closure can read the values the variable holds right now.
                self.exposed.update(id(d) for d in current if d is not CAPTURED)
                state[binding] = current | {CAPTURED}

    def use(self, state, name):
        if name.binding not in self.tracked:
            return
        defs = self.reach.setdefault(id(name), set())
        if state is not None:
            current = state.get(name.binding)
            if current:
                defs |= current

    def uses_in(self, state, expr):
        if expr is None:
            return
        stack = [expr]
        while stack:
            node = stack.pop()
            if isinstance(node, N.Function):
                self.capture(state, node)
                continue
            if isinstance(node, N.Name):
                self.use(state, node)
                continue
            stack.extend(node.children())

    # ------------------------------------------------------------ driver
    def run_function(self, func):
        state = {}
        for param in getattr(func, "params", ()):
            self.define(state, param, fresh=True)
        self.block(func.body, state)
        return self

    def block(self, block, state):
        for stmt in block.stmts:
            state = self.stmt(stmt, state)
        return state

    def stmt(self, s, state):
        if isinstance(s, N.Local):
            for expr in s.exprs:
                self.uses_in(state, expr)
            for name in s.names:
                self.define(state, name, fresh=True)
            return state
        if isinstance(s, N.Assign):
            for expr in s.exprs:
                self.uses_in(state, expr)
            for target in s.targets:
                if isinstance(target, N.Name):
                    if s.op != "=":
                        self.use(state, target)
                else:
                    self.uses_in(state, target)
            # `a, a = 1, 2`: Lua does not define which write wins, so every
            # target naming the same variable counts as a reaching definition.
            written = {}
            for target in s.targets:
                if isinstance(target, N.Name) and target.binding in self.tracked:
                    written.setdefault(target.binding, []).append(target)
            if state is not None:
                for binding, targets in written.items():
                    exposed = CAPTURED in state.get(binding, ())
                    if exposed:
                        self.exposed.update(id(t) for t in targets)
                    state[binding] = frozenset(targets + ([CAPTURED] if exposed else []))
            return state
        if isinstance(s, N.CallStmt):
            self.uses_in(state, s.call)
            return state
        if isinstance(s, N.LocalFunction):
            self.define(state, s.name, fresh=True)
            self.capture(state, s.func)
            return state
        if isinstance(s, N.FunctionStmt):
            self.capture(state, s.func)
            if isinstance(s.target, N.Name):
                self.define(state, s.target)
            else:
                self.uses_in(state, s.target)
            return state
        if isinstance(s, N.Do):
            return self.block(s.body, state)
        if isinstance(s, N.If):
            outs = None
            for cond, body in zip(s.conds, s.blocks):
                self.uses_in(state, cond)
                outs = self.join(outs, self.block(body, None if state is None else dict(state)))
            if s.orelse is not None:
                outs = self.join(outs, self.block(s.orelse, None if state is None else dict(state)))
            else:
                outs = self.join(outs, state)
            return outs
        if isinstance(s, N.While):
            return self.loop(state, s.body, before=lambda st: self.uses_in(st, s.cond))
        if isinstance(s, N.NumFor):
            for expr in (s.start, s.stop, s.step):
                self.uses_in(state, expr)
            return self.loop(state, s.body, enter=lambda st: self.define(st, s.var, fresh=True))
        if isinstance(s, N.GenFor):
            for expr in s.exprs:
                self.uses_in(state, expr)
            return self.loop(state, s.body,
                             enter=lambda st: [self.define(st, n, fresh=True) for n in s.names])
        if isinstance(s, N.Repeat):
            return self.repeat(state, s)
        if isinstance(s, N.Return):
            for expr in s.exprs:
                self.uses_in(state, expr)
            return None
        if isinstance(s, N.Break):
            if self.loop_breaks:
                self.loop_breaks[-1].append(state)
            return None
        return state            # Goto / Label (not analysed)

    def loop(self, state, body, before=None, enter=None):
        """while / for loops: the body runs zero or more times."""
        entry = state
        breaks = []
        self.loop_breaks.append(breaks)
        while True:
            if before is not None:
                before(entry)
            if entry is None:
                body_out = None
            else:
                body_state = dict(entry)
                if enter is not None:
                    enter(body_state)
                body_out = self.block(body, body_state)
            new_entry = self.join(state, body_out)
            if new_entry == entry:
                break
            entry = new_entry
            del breaks[:]
        self.loop_breaks.pop()
        out = entry
        for b in breaks:
            out = self.join(out, b)
        return out

    def repeat(self, state, s):
        """repeat ... until: body runs at least once, cond sees body locals."""
        entry = state
        breaks = []
        self.loop_breaks.append(breaks)
        while True:
            body_out = self.block(s.body, None if entry is None else dict(entry))
            self.uses_in(body_out, s.cond)
            new_entry = self.join(state, body_out)
            if new_entry == entry:
                break
            entry = new_entry
            del breaks[:]
        self.loop_breaks.pop()
        out = body_out
        for b in breaks:
            out = self.join(out, b)
        return out


def has_goto(func):
    """True if the function body (not nested functions) uses goto/labels."""
    stack = [func.body]
    while stack:
        node = stack.pop()
        if isinstance(node, (N.Goto, N.Label)):
            return True
        for child in node.children():
            if not isinstance(child, N.Function):
                stack.append(child)
    return False


def capture_function(ref, binding):
    """The closure, created in the binding's own function, that contains ``ref``."""
    node, closure = ref, None
    while node is not None and node is not binding.func:
        if isinstance(node, N.Function):
            closure = node
        node = node.parent
    return closure


class FlowResult:
    def __init__(self):
        self.reach = {}          # id(use) -> set of definition Names (may contain CAPTURED)
        self.tracked = set()     # bindings analysed
        self.exposed = set()     # ids of refs that closures can observe

    def is_exposed(self, ref):
        return id(ref) in self.exposed or CAPTURED in self.reach.get(id(ref), ())


def analyze(bindings):
    """Analyse every function that owns one of ``bindings``."""
    by_func = {}
    capture_points = {}
    result = FlowResult()
    for b in bindings:
        if b.kind == "self":
            continue
        by_func.setdefault(id(b.func), (b.func, set()))[1].add(b)
        for ref in b.refs:
            if ref.func is not b.func:
                result.exposed.add(id(ref))
                closure = capture_function(ref, b)
                capture_points.setdefault(id(closure), set()).add(b)
    for func, group in by_func.values():
        if has_goto(func):
            continue
        flow = ReachingDefs(group, capture_points).run_function(func)
        result.reach.update(flow.reach)
        result.exposed |= flow.exposed
        result.tracked |= group
    return result
