"""Add explanatory comments to the de-obfuscated AST and summarise the script.

Comments are placed above the *group* of statements that sets up a call:
decompiled code such as

    L0_1 = AddEventHandler
    L1_1 = "esx:playerLoaded"
    function L2_1(A0_2) ... end
    L0_1(L1_1, L2_1)

is one logical step, so its comment goes above the first line, not the last.
"""

import re

from . import knowledge as K
from . import nodes as N
from .printer import Printer

_TRIVIAL_CALLS = {"Wait", "Citizen.Wait", "print", "tostring", "tonumber", "pairs", "ipairs",
                  "type", "next", "select", "error", "assert", "pcall", "unpack"}
_TRIVIAL_PREFIXES = ("table.", "string.", "math.", "json.", "os.")
_PLACEHOLDER = re.compile(r"\{(\d+)(:raw)?\}")


class Summary:
    def __init__(self):
        self.side = "shared"
        self.frameworks = []
        self.events_handled = []
        self.net_events = []
        self.events_triggered_server = []
        self.events_triggered_client = []
        self.events_triggered_local = []
        self.commands = []
        self.callbacks_registered = []
        self.callbacks_called = []
        self.nui_callbacks = []
        self.exports = []
        self.usable_items = []
        self.threads = 0
        self.globals_defined = []
        self.natives = {}

    def add(self, items, value):
        if value is not None and value not in items:
            items.append(value)


class Annotator:
    def __init__(self, deob, indent="    "):
        self.d = deob
        self.printer = Printer(indent)
        self.summary = Summary()

    # ------------------------------------------------------------ driver
    def run(self, chunk):
        self.summarize(chunk)
        for node in N.walk(chunk):
            if isinstance(node, N.Block):
                self.annotate_block(node)
        return self.summary

    # ------------------------------------------------------------ rendering
    def render(self, expr, limit=40):
        text = self.printer.expr(expr, 0).replace("\n", " ")
        return text if len(text) <= limit else text[:limit - 3] + "..."

    def render_arg(self, func_name, call, index, raw=False):
        if index >= len(call.args):
            return "?"
        arg = call.args[index]
        value = self.d.literal(arg)
        if value is not None:
            d = self.d.desc(arg)
            if "Control" in (func_name or "") and index == 1 and d[0] == "num":
                return key_label(value)
            if d[0] == "num" and value in ("-1",) and "Client" in (func_name or ""):
                return "-1 (all players)"
            if d[0] == "str" and not raw:
                return "'%s'" % value
            return value
        return self.render(arg)

    def fill(self, template, func_name, call):
        return _PLACEHOLDER.sub(
            lambda m: self.render_arg(func_name, call, int(m.group(1)), bool(m.group(2))), template)

    # ------------------------------------------------------------ comments
    def annotate_block(self, block):
        stmts = block.stmts
        claimed = set()
        plans = []
        # Calls first so a handler definition joins its registration's group.
        for j, stmt in enumerate(stmts):
            text = self.call_comment(stmt) or self.loop_comment(stmt) or self.if_comment(stmt)
            if text:
                plans.append((j, text))
        for j, stmt in enumerate(stmts):
            text = self.function_comment(stmt)
            if text:
                plans.append((j, text))
        placed = []
        for j, text in plans:
            if j in claimed:
                continue
            start = self.group_start(stmts, j, claimed)
            for k in range(start, j + 1):
                claimed.add(k)
            placed.append((start, text))
        for start, text in placed:
            stmt = stmts[start]
            stmt.comments = stmt.comments + ["-- " + line for line in text.split("\n")]
            if start > 0:
                stmt.blank_before = True
        # Separate multi-line definitions from what follows.
        for j, stmt in enumerate(stmts[1:], start=1):
            prev = stmts[j - 1]
            if isinstance(prev, (N.FunctionStmt, N.LocalFunction, N.While, N.NumFor, N.GenFor)) \
                    and not stmt.comments:
                stmt.blank_before = True

    def group_start(self, stmts, j, claimed):
        """Walk back over statements that only prepare values used by stmt j."""
        needed = self.bindings_in(self.head_of(stmts[j]))
        start = j
        for i in range(j - 1, -1, -1):
            if i in claimed or not needed:
                break
            stmt = stmts[i]
            defined = self.defined_bindings(stmt)
            if defined is None or not (defined & needed):
                break
            if isinstance(stmt, (N.Local, N.Assign)):
                for expr in stmt.exprs:
                    needed |= self.bindings_in(expr)
            start = i
        return start

    def head_of(self, stmt):
        if isinstance(stmt, N.If):
            return stmt.conds
        if isinstance(stmt, N.While):
            return [stmt.cond]
        if isinstance(stmt, (N.NumFor,)):
            return [stmt.start, stmt.stop, stmt.step]
        if isinstance(stmt, N.GenFor):
            return stmt.exprs
        if isinstance(stmt, N.CallStmt):
            return [stmt.call]
        if isinstance(stmt, (N.Local, N.Assign)):
            return stmt.exprs + [t for t in getattr(stmt, "targets", []) if isinstance(t, N.Index)]
        return []

    def bindings_in(self, exprs):
        if not isinstance(exprs, list):
            exprs = [exprs]
        found = set()
        stack = [e for e in exprs if e is not None]
        while stack:
            node = stack.pop()
            if isinstance(node, N.Function):
                continue
            if isinstance(node, N.Name) and node.binding is not None:
                found.add(_var_key(node))
            stack.extend(node.children())
        return found

    def defined_bindings(self, stmt):
        if isinstance(stmt, N.Local):
            return {_var_key(n) for n in stmt.names}
        if isinstance(stmt, N.Assign) and all(isinstance(t, N.Name) and t.binding is not None
                                              for t in stmt.targets):
            return {_var_key(t) for t in stmt.targets}
        if isinstance(stmt, N.LocalFunction):
            return {_var_key(stmt.name)}
        if isinstance(stmt, N.FunctionStmt) and isinstance(stmt.target, N.Name) \
                and stmt.target.binding is not None:
            return {_var_key(stmt.target)}
        return None

    def statement_call(self, stmt):
        if isinstance(stmt, N.CallStmt):
            return stmt.call
        if isinstance(stmt, (N.Local, N.Assign)) and len(stmt.exprs) == 1 \
                and isinstance(stmt.exprs[0], (N.Call, N.MethodCall)):
            return stmt.exprs[0]
        return None

    def call_comment(self, stmt):
        call = self.statement_call(stmt)
        if call is None:
            return None
        name = self.d.call_name(self.d.desc(call))
        template = K.lookup(K.CALL_COMMENTS, name)
        if not template:
            return None
        text = self.fill(template, name, call)
        func = self.handler_arg(name, call)
        if func is not None:
            summary = self.describe_function(func)
            if summary:
                text += "\n" + summary
        return text

    def handler_arg(self, name, call):
        reg = K.lookup(K.HANDLER_REGISTRARS, name)
        if reg is None or reg[1] >= len(call.args):
            return None
        d = self.d.desc(call.args[reg[1]])
        return d[1] if d[0] == "func" else None

    def loop_comment(self, stmt):
        if not isinstance(stmt, N.While):
            return None
        cond = stmt.cond
        forever = isinstance(cond, N.Const) and cond.kind == "true"
        waits = []
        for node in _walk_no_functions(stmt.body):
            if isinstance(node, N.Call):
                name = self.d.call_name(self.d.desc(node))
                if name in ("Wait", "Citizen.Wait") and node.args:
                    values = self.possible_literals(node.args[0])
                    waits.extend(values if values else ["?"])
        if not forever:
            return None
        if not waits:
            return "Loop forever"
        known = sorted({w for w in waits if w != "?"}, key=_num)
        if "?" in waits and not known:
            return "Main loop (sleep time varies at runtime)"
        if "?" in waits:
            return "Main loop (sleeps a variable time, e.g. %s ms)" % " / ".join(known)
        if len(known) == 1:
            return "Main loop: runs every %s ms" % known[0] if known[0] != "0" \
                else "Main loop: runs every frame"
        return "Main loop: sleeps %s ms per iteration (adaptive)" % " or ".join(known)

    def possible_literals(self, expr, depth=0):
        """All literal values an expression can have, following temporaries."""
        value = self.d.literal(expr)
        if value is not None:
            return [value]
        if depth > 6 or not isinstance(expr, N.Name) or expr.segment is None:
            return None
        values = []
        for _, v in expr.segment.effective_defs:
            if not isinstance(v, N.Expr):
                return None
            found = self.possible_literals(v, depth + 1)
            if found is None:
                return None
            values.extend(x for x in found if x not in values)
        return values or None

    def if_comment(self, stmt):
        if not isinstance(stmt, N.If):
            return None
        text = self.describe_condition(stmt.conds[0])
        return "If " + text if text else None

    def describe_condition(self, cond):
        negate = False
        while True:
            if isinstance(cond, N.Paren):
                cond = cond.expr
            elif isinstance(cond, N.UnOp) and cond.op == "not":
                negate = not negate
                cond = cond.operand
            else:
                break
        d = self.d.desc(cond)
        if d[0] in ("call", "mcall"):
            name = self.d.call_name(d)
            template = K.lookup(K.CONDITION_COMMENTS, name)
            if template:
                text = self.fill(template, name, d[-1])
                return ("NOT: " if negate else "") + text
        if isinstance(cond, N.BinOp) and cond.op in ("<", "<=") and not negate:
            left = self.d.desc(cond.left)
            limit = self.d.literal(cond.right)
            is_distance = (left[0] == "unop" and left[1] == "#") or (
                left[0] in ("call",) and self.d.call_name(left) in ("GetDistanceBetweenCoords", "Vdist"))
            if is_distance and limit is not None:
                return "within %s units" % limit
        return None

    def function_comment(self, stmt):
        func = None
        name = None
        if isinstance(stmt, N.FunctionStmt):
            func, name = stmt.func, self.printer.funcname(stmt.target)
            if stmt.method:
                name += ":" + stmt.method
        elif isinstance(stmt, N.LocalFunction):
            func, name = stmt.func, stmt.name.name
        elif isinstance(stmt, (N.Local, N.Assign)) and len(stmt.exprs) == 1 \
                and isinstance(stmt.exprs[0], N.Function):
            func = stmt.exprs[0]
            target = stmt.names[0] if isinstance(stmt, N.Local) else stmt.targets[0]
            name = self.render(target)
        if func is None:
            return None
        params = [p.name for p in func.params] + (["..."] if func.is_vararg else [])
        text = "%s(%s)" % (name, ", ".join(params))
        summary = self.describe_function(func)
        return text + ("\n" + summary if summary else "")

    def describe_function(self, func):
        calls, events = [], []
        for node in _walk_no_functions(func.body):
            if isinstance(node, (N.Call, N.MethodCall)):
                name = self.d.call_name(self.d.desc(node))
                if not name or name in _TRIVIAL_CALLS or name.startswith(_TRIVIAL_PREFIXES):
                    continue
                if name in ("TriggerServerEvent", "TriggerClientEvent", "TriggerEvent") and node.args:
                    event = self.d.literal(node.args[0])
                    if event is not None and event not in events:
                        events.append(event)
                    continue
                if name not in calls:
                    calls.append(name)
        parts = []
        if calls:
            shown = calls[:6]
            more = len(calls) - len(shown)
            parts.append("uses " + ", ".join(shown) + (" (+%d more)" % more if more else ""))
        if events:
            parts.append("triggers " + ", ".join("'%s'" % e for e in events[:4]))
        if not parts:
            return None
        return "  -> " + "; ".join(parts)

    # ------------------------------------------------------------ summary
    def summarize(self, chunk):
        s = self.summary
        d = self.d
        s.side = d.side
        globals_used = d.globals
        if "ESX" in globals_used or any(n and n.startswith("ESX.") for _, n in d.calls):
            s.add(s.frameworks, "ESX")
        if "QBCore" in globals_used or any(n and n.startswith("QBCore.") for _, n in d.calls):
            s.add(s.frameworks, "QBCore")
        if "vRP" in globals_used:
            s.add(s.frameworks, "vRP")
        if "lib" in globals_used:
            s.add(s.frameworks, "ox_lib")
        if "MySQL" in globals_used:
            s.add(s.frameworks, "oxmysql / mysql-async")
        for call, name in d.calls:
            if not name:
                continue
            short = name.replace(":", ".")
            if K.is_native_name(name):
                s.natives[name] = s.natives.get(name, 0) + 1
            first = d.literal(call.args[0]) if call.args else None
            if name == "AddEventHandler":
                s.add(s.events_handled, first)
            elif name in ("RegisterNetEvent", "RegisterServerEvent"):
                s.add(s.net_events, first)
                if len(call.args) > 1:
                    s.add(s.events_handled, first)
            elif name in ("TriggerServerEvent", "TriggerLatentServerEvent"):
                s.add(s.events_triggered_server, first)
            elif name in ("TriggerClientEvent", "TriggerLatentClientEvent"):
                s.add(s.events_triggered_client, first)
            elif name == "TriggerEvent":
                s.add(s.events_triggered_local, first)
            elif name in ("RegisterCommand", "QBCore.Commands.Add"):
                s.add(s.commands, first)
            elif name in ("ESX.RegisterServerCallback", "QBCore.Functions.CreateCallback",
                          "lib.callback.register"):
                s.add(s.callbacks_registered, first)
            elif name in ("ESX.TriggerServerCallback", "QBCore.Functions.TriggerCallback",
                          "lib.callback", "lib.callback.await"):
                s.add(s.callbacks_called, first)
            elif name == "RegisterNUICallback":
                s.add(s.nui_callbacks, first)
            elif name == "exports":
                s.add(s.exports, first)
            elif name in ("ESX.RegisterUsableItem", "QBCore.Functions.CreateUseableItem"):
                s.add(s.usable_items, first)
            elif short in ("CreateThread", "Citizen.CreateThread", "Citizen.CreateThreadNow"):
                s.threads += 1
        for node in N.walk(chunk):
            target = None
            if isinstance(node, N.Assign):
                for t, v in zip(node.targets, node.exprs):
                    if isinstance(t, N.Name) and t.binding is None and d.desc(v)[0] == "func":
                        s.add(s.globals_defined, t.name)
            elif isinstance(node, N.FunctionStmt):
                target = node.target
                while isinstance(target, N.Index):
                    target = target.obj
                if isinstance(target, N.Name) and target.binding is None:
                    s.add(s.globals_defined, self.printer.funcname(node.target)
                          + (":" + node.method if node.method else ""))

    def header_lines(self, renames):
        s = self.summary
        lines = ["=" * 70,
                 "De-obfuscated with lua_deobf (variable names inferred from usage).",
                 "Script side : %s (guessed from the natives/APIs it uses)" % s.side]
        if s.frameworks:
            lines.append("Framework   : " + ", ".join(s.frameworks))

        def listing(label, items, fmt="%s"):
            items = [fmt % i for i in items if i is not None]
            if items:
                lines.append("%-12s: %s" % (label, ", ".join(items)))

        listing("Handles", s.events_handled, "'%s'")
        listing("Net events", [e for e in s.net_events if e not in s.events_handled], "'%s'")
        listing("To server", s.events_triggered_server, "'%s'")
        listing("To clients", s.events_triggered_client, "'%s'")
        listing("Local events", s.events_triggered_local, "'%s'")
        listing("Commands", s.commands, "/%s")
        listing("Callbacks", s.callbacks_registered, "'%s'")
        listing("Calls back", s.callbacks_called, "'%s'")
        listing("NUI", s.nui_callbacks, "'%s'")
        listing("Exports", s.exports, "'%s'")
        listing("Items", s.usable_items, "'%s'")
        if s.threads:
            lines.append("Threads     : %d" % s.threads)
        listing("Globals", s.globals_defined)
        originals = len({id(seg.binding) for seg in self.d.segments})
        lines.append("Renamed     : %d obfuscated variables -> %d named values" % (originals, len(renames)))
        lines.append("=" * 70)
        return ["-- " + line for line in lines]


def key_label(value):
    try:
        number = int(float(value))
    except ValueError:
        return value
    key = K.CONTROL_KEYS.get(number)
    return "%s (control %s)" % (key, value) if key else "control %s" % value


def _num(text):
    try:
        return float(text)
    except ValueError:
        return float("inf")


def _var_key(name):
    """Identify a variable: split temporaries are told apart by their new name."""
    return (name.binding, name.name)


def _walk_no_functions(node):
    """Source-order walk that does not enter nested functions."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(c for c in reversed(list(current.children())) if not isinstance(c, N.Function))
