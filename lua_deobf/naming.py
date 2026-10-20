"""Infer meaningful names for obfuscated locals and rename them safely.

Pipeline
--------
1. ``scope.resolve`` links every name to its declaration.
2. Each obfuscated variable is split into *segments*: its def-use webs.
   Decompilers such as unluac reuse one register variable (``L0_1``) for
   many unrelated values; values that can never flow into each other get
   separate names. This is provably behaviour-preserving, see ``flow.py``.
3. Name *hints* are collected for every segment from how its value is
   produced (``L0_1 = GetPlayerPed(...)`` -> ``playerPed``) and how it is used
   (``SetEntityCoords(L0_1, ...)`` -> ``entity``), each with a weight and a
   human-readable reason.
4. The best hint wins; final names are made unique against every global and
   every other variable whose scope overlaps, so no reference can be
   captured by a different variable.
"""

import bisect
import re

from . import knowledge as K
from . import nodes as N
from .lexer import KEYWORDS, decode_string
from .flow import CAPTURED, analyze
from .scope import Binding, resolve

DEFAULT_PATTERN = r"^[A-Za-z]\d+_\d+$"

LUA_RESERVED = frozenset("""
_G _ENV _VERSION assert collectgarbage dofile error getmetatable ipairs load
loadfile next pairs pcall print rawequal rawget rawlen rawset require select
setmetatable tonumber tostring type xpcall coroutine debug io math os package
string table utf8 self arg unpack
Citizen source exports json msgpack vector2 vector3 vector4 vec vec2 vec3 vec4
quat promise lib Config Wait CreateThread SetTimeout GetHashKey AddEventHandler
RegisterNetEvent TriggerEvent TriggerServerEvent TriggerClientEvent
""".split())

# Lua 5.4 allows 200 active locals per function; stay well below it.
MAX_LOCALS_PER_FUNCTION = 180

_ARITH = {"+", "-", "*", "/", "//", "%", "^"}
_COMPARE = {"==", "~=", "<", ">", "<=", ">="}
_GENERIC_COLLECTIONS = {"list", "tbl", "data", "items", "value", "result", "entries", "args"}


# ---------------------------------------------------------------- name utils

def lower_camel(text):
    """'GetPlayerPed' -> 'getPlayerPed', 'ESX' -> 'esx', 'some_event' -> 'someEvent'."""
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", text) if p]
    if not parts:
        return ""
    first = parts[0]
    m = re.match(r"[A-Z]+", first)
    if m:
        run = m.group(0)
        if len(run) == len(first):
            first = first.lower()
        elif len(run) == 1:
            first = first[0].lower() + first[1:]
        else:
            first = run[:-1].lower() + first[len(run) - 1:]
    out = first + "".join(p[0].upper() + p[1:] for p in parts[1:])
    if out[0].isdigit():
        out = "n" + out
    return out


def pascal(text):
    name = lower_camel(text)
    return name[:1].upper() + name[1:]


def valid_identifier(name):
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name)) and name not in KEYWORDS


def short_event(event):
    """'esx_policejob:server:handcuff' -> 'handcuff'."""
    tail = re.split(r"[:/]", event)[-1]
    return tail or event


def singular(word):
    if not word or word in _GENERIC_COLLECTIONS:
        return "item"
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if re.search(r"(ses|xes|ches|shes)$", word):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word + "Entry"


def last_component(path):
    return re.split(r"[.:]", path)[-1] if path else path


def derive_result_name(func_name):
    """Generic name for a call result when the function is not in the tables."""
    short = last_component(func_name)
    if not short:
        return None, 0
    if short.startswith("Network") and short[7:8].isupper():
        short = short[7:]
    for verb in ("Get", "get", "Create", "Add", "Find", "find", "fetch", "Fetch", "load", "Load"):
        if short.startswith(verb) and short[len(verb):len(verb) + 1].isupper():
            rest = short[len(verb):]
            m = re.match(r"(.+?)(?:From|By|For|At)[A-Z0-9_]", rest)
            if m:
                rest = m.group(1)
            return lower_camel(rest), 6
    for verb in ("Is", "is", "Has", "has", "Does", "does", "Can", "can", "Are", "Was"):
        if short.startswith(verb) and short[len(verb):len(verb) + 1].isupper():
            return lower_camel(short), 6
    return lower_camel(short) + "Result", 3


# ---------------------------------------------------------------- data types

class Hint:
    __slots__ = ("weight", "name", "reason")

    def __init__(self, weight, name, reason):
        self.weight, self.name, self.reason = weight, name, reason


class Segment:
    """One live range of an obfuscated variable."""

    def __init__(self, binding, index):
        self.binding = binding
        self.index = index
        self.refs = []          # Name nodes
        self.defs = []          # (Name node, value) where value is an Expr or tuple
        self.hints = []
        self.deferred = []      # callables producing hints after the first pass
        self.exposed = True     # visible to closures (declared in its own block)
        self.merged_into = None
        self.base = None
        self.name = None
        self.reason = None

    @property
    def effective_defs(self):
        return [d for d in self.defs if d[1] is not None]

    def add(self, weight, name, reason):
        if name and valid_identifier(name):
            self.hints.append(Hint(weight, name, reason))

    def __repr__(self):
        return "Segment(%s#%d)" % (self.binding.name, self.index)


class Rename:
    """Record of one renaming decision, used by the report."""

    def __init__(self, old, new, kind, line, reason):
        self.old, self.new, self.kind, self.line, self.reason = old, new, kind, line, reason


# ---------------------------------------------------------------- analysis

class Deobfuscator:
    def __init__(self, chunk, pattern=DEFAULT_PATTERN, split=True, side=None, rename_globals=False):
        self.chunk = chunk
        self.rename_globals = rename_globals
        self.pattern = re.compile(pattern)
        self.split_enabled = split
        self.side = side
        self.segments = []
        self.renames = []
        self._func_ctx = {}

    # ------------------------------------------------------------ driver
    def run(self):
        self.bindings, self.globals = resolve(self.chunk)
        self.targets = [b for b in self.bindings if self.pattern.match(b.name)]
        self.target_set = set(self.targets)
        renamed_globals = set()
        if self.rename_globals:
            renamed_globals = {g for g in self.globals if self.pattern.match(g)}
            self.targets.extend(self.global_bindings(renamed_globals))
        self.reserved = set(KEYWORDS) | LUA_RESERVED | (set(self.globals) - renamed_globals)
        self.reserved |= {b.name for b in self.bindings if b not in self.target_set}

        self.build_segments()
        self.calls = [(node, self.call_name(self.desc(node))) for node in N.walk(self.chunk)
                      if isinstance(node, (N.Call, N.MethodCall))]
        if self.side is None:
            self.side = self.detect_side()
        for seg in self.segments:
            self.collect_hints(seg)
        self.choose_all()
        for seg in self.segments:
            for producer in seg.deferred:
                producer(seg)
        self.choose_all()
        self.enforce_local_limit()
        self.allocate()
        self.apply()
        return self

    def global_bindings(self, names):
        """Pseudo-variables for obfuscated globals: one per name, whole file."""
        refs = {}
        for node in N.walk(self.chunk):
            if isinstance(node, N.Name) and node.binding is None and node.name in names:
                refs.setdefault(node.name, []).append(node)
        out = []
        for name, nodes in sorted(refs.items()):
            b = Binding(N.Name(name, pos=0), "global", self.chunk, self.chunk.body)
            b.refs = nodes
            b.scope_start, b.scope_end = 0, self.chunk.body.end_pos
            out.append(b)
        return out

    def detect_side(self):
        client = sum(1 for _, name in self.calls if name in K.CLIENT_HINTS)
        server = sum(1 for _, name in self.calls if name in K.SERVER_HINTS)
        server += sum(1 for name in self.globals if name == "source")
        if client > server:
            return "client"
        if server > client:
            return "server"
        return "shared"

    # ------------------------------------------------------------ segments
    def build_segments(self):
        locals_only = [b for b in self.targets if b.kind != "global"]
        flow = analyze(locals_only) if self.split_enabled else None
        for b in self.targets:
            if flow and b in flow.tracked and b.kind in ("local", "param") and b.attrib is None:
                groups = _webs(b.refs, flow)
            else:
                groups = [list(b.refs)]
            groups.sort(key=lambda refs: min(r.pos for r in refs))
            b.segments = []
            for k, refs in enumerate(groups):
                seg = Segment(b, k)
                seg.exposed = b.kind == "global" or not flow or b not in flow.tracked or \
                    any(flow.is_exposed(r) for r in refs)
                for ref in sorted(refs, key=lambda r: r.pos):
                    ref.segment = seg
                    seg.refs.append(ref)
                b.segments.append(seg)
                self.segments.append(seg)
        for seg in self.segments:
            for ref in seg.refs:
                value = self.def_value(ref)
                if value is not _NOT_A_DEF:
                    seg.defs.append((ref, value))

    def def_value(self, ref):
        """If ``ref`` is written to, return the value written (or None)."""
        p = ref.parent
        if isinstance(p, N.Local) and any(n is ref for n in p.names):
            i = _index_of(p.names, ref)
            return _value_at(p.exprs, i)
        if isinstance(p, N.Assign) and any(t is ref for t in p.targets):
            if p.op != "=":
                return ("compound", p.op)
            return _value_at(p.exprs, _index_of(p.targets, ref))
        if isinstance(p, N.FunctionStmt) and p.target is ref:
            return p.func
        if isinstance(p, N.LocalFunction) and p.name is ref:
            return p.func
        if isinstance(p, N.Function) and any(x is ref for x in p.params):
            return ("param", p, _index_of(p.params, ref))
        if isinstance(p, N.NumFor) and p.var is ref:
            return ("numfor", p)
        if isinstance(p, N.GenFor) and any(x is ref for x in p.names):
            return ("genfor", p, _index_of(p.names, ref))
        return _NOT_A_DEF

    # ------------------------------------------------------------ values
    def desc(self, e, seen=None):
        """Symbolic description of an expression's value (independent of names)."""
        if e is None:
            return ("nil",)
        if isinstance(e, tuple):
            if e[0] == "multi":
                return ("multi", self.desc(e[1], seen), e[2])
            return e
        if isinstance(e, N.Const):
            if e.kind == "string":
                if e.raw[:1] == "`":
                    return ("hash", e.raw[1:-1])     # CfxLua compile-time joaat hash
                return ("str", decode_string(e.raw))
            if e.kind == "number":
                return ("num", e.raw)
            if e.kind == "vararg":
                return ("vararg",)
            return ("const", e.kind)
        if isinstance(e, N.Name):
            seg = e.segment
            if e.binding is None:
                return ("path", e.name)
            if seg is None:
                return ("path", e.name)       # meaningful (non-obfuscated) local
            defs = seg.effective_defs
            if len(defs) > 1:
                # `local ESX = nil` + one real assignment: describe the real value
                # (only used for naming/comments, never to change code).
                real = [d for d in defs if not (isinstance(d[1], N.Const) and d[1].kind == "nil")]
                defs = real if len(real) == 1 else defs
            seen = seen or frozenset()
            if len(defs) == 1 and seg not in seen:
                return self.desc(defs[0][1], seen | {seg})
            return ("local", seg)
        if isinstance(e, N.Paren):
            return self.desc(e.expr, seen)
        if isinstance(e, N.Index):
            obj = self.desc(e.obj, seen)
            key = self.desc(e.key, seen)
            if key[0] == "str":
                alias = self.alias(obj)
                if alias:
                    return ("path", alias + "." + key[1])
                return ("field", obj, key[1])
            return ("index", obj, key)
        if isinstance(e, N.Call):
            return ("call", self.desc(e.func, seen), e)
        if isinstance(e, N.MethodCall):
            return ("mcall", self.desc(e.obj, seen), e.method, e)
        if isinstance(e, N.Function):
            return ("func", e)
        if isinstance(e, N.Table):
            return ("table", e)
        if isinstance(e, N.BinOp):
            return ("binop", e.op, e)
        if isinstance(e, N.UnOp):
            return ("unop", e.op, e)
        return ("?",)

    def alias(self, d):
        """A dotted path naming the value, when it is a well-known object."""
        kind = d[0]
        if kind == "path":
            return d[1]
        if kind == "mcall":
            if d[2] == "getSharedObject":
                return "ESX"
            if d[2] == "GetCoreObject":
                return "QBCore"
        if kind == "param":
            ctx = self.func_context(d[1])
            if ctx and ctx.get("event") in K.SHARED_OBJECT_EVENTS and d[2] == 0:
                return K.SHARED_OBJECT_EVENTS[ctx["event"]]
        return None

    def callee_name(self, d):
        """Readable dotted name of a called value ('ESX.GetPlayerFromId')."""
        kind = d[0]
        if kind == "path":
            return d[1]
        if kind == "field":
            base = self.alias(d[1])
            return base + "." + d[2] if base else d[2]
        alias = self.alias(d)
        return alias

    def call_name(self, d):
        """Function name of a ('call', ...) or ('mcall', ...) description."""
        if d[0] == "call":
            return self.callee_name(d[1])
        if d[0] == "mcall":
            base = self.alias(d[1])
            return (base + ":" + d[2]) if base else d[2]
        return None

    def literal(self, e):
        """Return the decoded value of a string/number literal (through temps)."""
        d = self.desc(e)
        if d[0] in ("str", "num"):
            return d[1]
        return None

    # ------------------------------------------------------------ handlers
    def func_context(self, func):
        """Find how a function value is used: registered as an event handler,
        command, thread...  Returns a dict or None."""
        key = id(func)
        if key in self._func_ctx:
            return self._func_ctx[key]
        self._func_ctx[key] = None
        ctx = None
        sites = []
        p = func.parent
        if isinstance(p, (N.Call, N.MethodCall)) and any(a is func for a in p.args):
            sites.append((p, _index_of(p.args, func)))
        else:
            holder = _def_holder(func)
            if holder is not None and holder.segment is not None:
                for ref in holder.segment.refs:
                    rp = ref.parent
                    if isinstance(rp, (N.Call, N.MethodCall)) and any(a is ref for a in rp.args):
                        sites.append((rp, _index_of(rp.args, ref)))
        for call, index in sites:
            name = self.call_name(self.desc(call))
            reg = K.lookup(K.HANDLER_REGISTRARS, name)
            if reg is None or reg[1] != index:
                continue
            name_index, _, kind = reg
            ctx = {"kind": kind, "registrar": name, "call": call}
            if name_index is not None and name_index < len(call.args):
                value = self.literal(call.args[name_index])
                if value is not None:
                    ctx["name"] = value
                    if kind in ("event", "trigger"):
                        ctx["event"] = value
            break
        self._func_ctx[key] = ctx
        return ctx

    def param_names_for(self, ctx):
        if ctx is None:
            return None, None
        event = ctx.get("event")
        if event is not None:
            if self.side == "server" and event in K.SERVER_EVENT_PARAMS:
                return K.SERVER_EVENT_PARAMS[event], "parameter of the '%s' event" % event
            if event in K.EVENT_PARAMS:
                return K.EVENT_PARAMS[event], "parameter of the '%s' event" % event
        names = K.HANDLER_PARAMS.get(ctx["kind"])
        if names:
            return names, "parameter of a %s callback (%s)" % (ctx["kind"].replace("_", " "), ctx["registrar"])
        return None, None

    # ------------------------------------------------------------ hints
    def collect_hints(self, seg):
        for ref, value in seg.defs:
            self.def_hints(seg, ref, value)
        for ref in seg.refs:
            if not ref.is_decl and self.def_value(ref) is _NOT_A_DEF:
                self.use_hints(seg, ref)

    def def_hints(self, seg, ref, value):
        if value is None:
            return
        if isinstance(value, tuple):
            kind = value[0]
            if kind == "param":
                self.param_hints(seg, value[1], value[2])
                return
            if kind == "numfor":
                depth = sum(1 for a in _ancestors(value[1]) if isinstance(a, N.NumFor))
                seg.add(6, "ijklmn"[min(depth, 5)], "counter of a numeric for-loop")
                return
            if kind == "genfor":
                self.genfor_hints(seg, value[1], value[2])
                return
            if kind == "compound":
                seg.add(1, "total" if value[1] in ("+=", "-=") else "value",
                        "updated with compound operator %s" % value[1])
                return
        # A plain copy (`a = b`) only weakly inherits the source's meaning.
        self.value_hints(seg, self.desc(value), 0.6 if isinstance(value, N.Name) and value.binding is not None else 1.0, value)
        if isinstance(value, N.Const) and value.kind == "true" and isinstance(ref.func, N.Function):
            ctx = self.func_context(ref.func)
            if ctx and ctx.get("event"):
                seg.add(3, "is" + pascal(short_event(ctx["event"])),
                        "set to true when event '%s' fires" % ctx["event"])

    def value_hints(self, seg, d, scale, expr=None, depth=0):
        kind = d[0]
        if depth > 6:
            return          # self-referencing values such as `x = c and x`

        def add(weight, name, reason):
            seg.add(weight * scale, name, reason)

        if kind == "path":
            path = d[1]
            if path == "source":
                add(9, "src", "copy of the global `source` (id of the player who triggered the event)")
            else:
                name = lower_camel(last_component(path))
                if name == path:
                    name += "Fn" if _is_called(seg) else "Value"
                add(5, name, "holds `%s`" % path)
        elif kind == "field":
            add(5, lower_camel(d[2]), "holds field `.%s` of another value" % d[2])
        elif kind == "index":
            obj = d[1]
            base = None
            if obj[0] == "path":
                base = lower_camel(last_component(obj[1]))
            elif obj[0] == "field":
                base = lower_camel(obj[2])
            if base and singular(base) != base + "Entry":
                add(5, singular(base), "element of `%s` looked up by key" % base)
            elif base:
                add(2, base + "Entry", "element of `%s` looked up by key" % base)
        elif kind in ("call", "mcall"):
            name = self.call_name(d)
            alias = self.alias(d)
            if alias:
                add(10, alias, "framework object returned by `%s`" % name)
                return
            if name is None:
                return
            result = K.lookup(K.CALL_RESULT_NAMES, name)
            multi = K.lookup(K.MULTI_RESULT_NAMES, name)
            if multi:
                add(9, multi[0], "first result of `%s(...)`" % name)
            elif result:
                add(10, result, "result of `%s(...)`" % name)
            else:
                guess, weight = derive_result_name(name)
                add(weight, guess, "result of `%s(...)`" % name)
        elif kind == "multi":
            inner = d[1]
            name = self.call_name(inner) if inner[0] in ("call", "mcall") else None
            multi = K.lookup(K.MULTI_RESULT_NAMES, name) if name else None
            if multi and d[2] < len(multi):
                add(9, multi[d[2]], "result #%d of `%s(...)`" % (d[2] + 1, name))
            elif name:
                add(3, "result%d" % (d[2] + 1), "result #%d of `%s(...)`" % (d[2] + 1, name))
            else:
                add(2, "value%d" % (d[2] + 1), "extra value of a multiple assignment")
        elif kind == "str":
            if ":" in d[1] and " " not in d[1]:
                add(2, "eventName", "string that looks like an event name ('%s')" % d[1])
            else:
                add(1, "text", "string literal")
        elif kind == "num":
            add(0.5, "value", "numeric literal")
        elif kind == "hash":
            add(4, "hash", "backtick string: compile-time hash of '%s'" % d[1])
        elif kind == "const":
            if d[1] in ("true", "false"):
                add(1, "flag", "boolean literal")
        elif kind == "vararg":
            add(2, "args", "the function's varargs")
        elif kind == "table":
            add(1, "data", "table constructor")
        elif kind == "func":
            self.function_hints(seg, d[1], add)
        elif kind == "binop":
            op, node = d[1], d[2]
            if op == "..":
                add(2, "text", "string concatenation")
            elif op == "-":
                add(1.2, "difference", "subtraction")
            elif op in _ARITH:
                add(1, "result", "arithmetic expression")
            elif op in _COMPARE:
                add(1.5, "condition", "comparison")
            elif op in ("and", "or"):
                self.value_hints(seg, self.desc(node.right), scale * 0.8, depth=depth + 1)
                if op == "or":
                    self.value_hints(seg, self.desc(node.left), scale * 0.8, depth=depth + 1)
        elif kind == "unop":
            op, node = d[1], d[2]
            operand = self.desc(node.operand)
            if op == "#" and operand[0] == "binop" and operand[1] == "-":
                add(9, "distance", "`#(a - b)` is the distance between two vectors")
            elif op == "#":
                add(4, "count", "length operator `#`")
            elif op == "not":
                add(1.5, "condition", "boolean negation")
        elif kind == "param":
            alias = self.alias(d)
            if alias:
                add(9, alias, "receives the framework object from '%s'" % self.func_context(d[1])["event"])
                return
            names, reason = self.param_names_for(self.func_context(d[1]))
            if names and d[2] < len(names):
                add(6, names[d[2]], "receives the " + reason)
        elif kind == "local":
            other = d[1]
            seg.deferred.append(lambda s, other=other: s.add(
                3 * scale, other.base, "copy of `%s`" % other.base))

    def function_hints(self, seg, func, add):
        ctx = self.func_context(func)
        if ctx is None:
            add(1, "func", "function value")
            guess = self.name_from_body(func)
            if guess:
                add(2.5, guess[0], guess[1])
            return
        kind, name = ctx["kind"], ctx.get("name")
        reason = "callback registered with `%s`" % ctx["registrar"]
        if name:
            reason += " for '%s'" % name
        specific = None
        if name and isinstance(name, str):
            if kind == "event":
                specific = "on" + pascal(short_event(name))
            elif kind == "command":
                specific = lower_camel(name) + "Command"
            elif kind == "nui":
                specific = "nui" + pascal(name)
            elif kind == "server_callback":
                specific = lower_camel(short_event(name)) + "Callback"
            elif kind == "client_callback":
                specific = "on" + pascal(short_event(name)) + "Result"
            elif kind == "usable_item":
                specific = "use" + pascal(name)
            elif kind == "export":
                specific = lower_camel(name)
        if specific and valid_identifier(specific):
            add(9, specific, reason)
        add(8, K.HANDLER_FUNC_NAMES.get(kind, "callback"), reason)

    def name_from_body(self, func):
        """Guess a helper function's name from the calls it makes."""
        calls = []
        for node in N.walk(func.body):
            if isinstance(node, (N.Call, N.MethodCall)):
                name = self.call_name(self.desc(node))
                if name and name not in ("Wait", "Citizen.Wait", "tostring", "tonumber", "pairs", "ipairs"):
                    calls.append(name)
        names = set(calls)
        if not names:
            return None
        if names <= {"print", "string.format"}:
            return "log", "only prints to the console"
        if names & {"SetDrawOrigin", "World3dToScreen2d", "GetScreenCoordFromWorldCoord"} and \
                names & {"DrawText", "EndTextCommandDisplayText"}:
            return "drawText3D", "draws text at a 3D world position"
        if names & {"DrawText", "EndTextCommandDisplayText"}:
            return "drawText", "draws text on screen"
        if names & {"SetNotificationTextEntry", "BeginTextCommandThefeedPost", "ESX.ShowNotification",
                    "QBCore.Functions.Notify", "lib.notify"}:
            return "showNotification", "shows a notification"
        if names & {"BeginTextCommandDisplayHelp", "DisplayHelpTextThisFrame", "ESX.ShowHelpNotification"}:
            return "showHelpText", "shows a help text"
        if names & {"RequestModel"} and names & {"HasModelLoaded"}:
            return "loadModel", "requests a model and waits for it to load"
        if names & {"RequestAnimDict"} and names & {"HasAnimDictLoaded"}:
            return "loadAnimDict", "requests an animation dictionary and waits for it"
        triggers = [n for n in calls if n in ("TriggerServerEvent", "TriggerClientEvent", "TriggerEvent")]
        if len(names) == 1 and triggers:
            for node in N.walk(func.body):
                if isinstance(node, N.Call) and node.args and \
                        self.call_name(self.desc(node)) == triggers[0]:
                    event = self.literal(node.args[0])
                    if event:
                        return "trigger" + pascal(short_event(event)), "only triggers '%s'" % event
        return None

    def param_hints(self, seg, func, index):
        ctx = self.func_context(func)
        names, reason = self.param_names_for(ctx)
        if names and index < len(names):
            seg.add(9, names[index], reason)
        seg.add(0.2, "arg%d" % (index + 1), "parameter #%d" % (index + 1))

    def genfor_hints(self, seg, stmt, index):
        iterator = None
        coll = None
        d = self.desc(stmt.exprs[0]) if stmt.exprs else ("?",)
        if d[0] == "multi" and d[2] == 0:
            d = d[1]
        if d[0] == "call" and d[2].args:
            iterator = self.callee_name(d[1])
            coll = d[2].args[0]
        if iterator in ("pairs", "ipairs"):
            key_name = "i" if iterator == "ipairs" else "key"
            if index == 0:
                seg.add(5, key_name, "key of a `%s` loop" % iterator)
                return
            if index == 1:
                seg.add(3, "value" if iterator == "pairs" else "item", "value of a `%s` loop" % iterator)

                def element_hint(s, coll=coll, iterator=iterator):
                    base = self.value_base(coll)
                    if base:
                        s.add(6, singular(base), "element of `%s` iterated with %s" % (base, iterator))
                seg.deferred.append(element_hint)
                return
        seg.add(2, ("key", "value")[index] if index < 2 else "value%d" % (index + 1),
                "variable of a generic for-loop")

    def value_base(self, expr):
        """Readable base name of a collection expression (for loop elements)."""
        if isinstance(expr, N.Name):
            if expr.segment is not None:
                return expr.segment.base
            return expr.name
        probe = Segment(None, 0)
        self.value_hints(probe, self.desc(expr), 1.0, expr)
        if not probe.hints:
            return None
        return max(probe.hints, key=lambda h: h.weight).name

    def use_hints(self, seg, ref):
        p = ref.parent
        if isinstance(p, N.Call) and p.func is ref:
            seg.add(3, "callback", "called as a function")
            return
        if isinstance(p, (N.Call, N.MethodCall)) and any(a is ref for a in p.args):
            index = _index_of(p.args, ref)
            name = self.call_name(self.desc(p))
            roles = K.lookup(K.ARG_ROLES, name)
            if roles:
                role = None
                if index < len(roles) and roles[index] != "...":
                    role = roles[index]
                if role:
                    weight = 4 if role in ("x", "y", "z", "w") else 8
                    seg.add(weight, role, "passed as argument #%d (%s) to `%s`" % (index + 1, role, name))
                    return
            if name and index == 0 and K.is_native_name(name):
                entity = K.first_arg_entity(name)
                if entity:
                    seg.add(5, entity, "first argument of native `%s`" % name)
            return
        if isinstance(p, N.MethodCall) and p.obj is ref:
            if p.method in K.ESX_PLAYER_METHODS:
                seg.add(7, "xPlayer", "ESX player method `:%s()` is called on it" % p.method)
            return
        if isinstance(p, N.Index) and p.obj is ref:
            key = self.desc(p.key)
            if key[0] != "str":
                seg.add(1, "tbl", "indexed like a table")
                return
            key = key[1]
            if key in K.QB_PLAYER_KEYS:
                seg.add(6, "Player", "QBCore player field `.%s` is used" % key)
            elif key in K.ESX_PLAYER_METHODS and isinstance(p.parent, N.Call) and p.parent.func is p:
                seg.add(7, "xPlayer", "ESX player method `.%s()` is called on it" % key)
            elif key in ("x", "y", "z", "xyz", "xy"):
                seg.add(4, "coords", "vector component `.%s` is used" % key)
            else:
                seg.add(1, "data", "field `.%s` is read" % key)
            return
        if isinstance(p, N.Index) and p.key is ref:
            seg.add(2, "key", "used as a table key")
            return
        if isinstance(p, N.Assign) and any(e is ref for e in p.exprs):
            i = _index_of(p.exprs, ref)
            if i < len(p.targets):
                self.target_hint(seg, p.targets[i])
            return
        if isinstance(p, N.Local) and any(e is ref for e in p.exprs):
            i = _index_of(p.exprs, ref)
            if i < len(p.names):
                self.target_hint(seg, p.names[i])
            return
        if isinstance(p, N.TableField) and p.value is ref and p.kind == "named":
            seg.add(5, lower_camel(p.key), "stored in table field `%s`" % p.key)
            return
        if isinstance(p, N.BinOp):
            if p.op == "..":
                seg.add(1, "text", "used in string concatenation")
            elif p.op in _ARITH:
                seg.add(1, "num", "used in arithmetic")
            return
        if isinstance(p, N.UnOp) and p.op == "#":
            if any(self.desc(v)[:2] == ("binop", "-") for _, v in seg.effective_defs):
                seg.add(5, "offset", "vector difference whose length is taken")
            else:
                seg.add(3, "list", "length operator `#` applied to it")
            return
        if isinstance(p, N.NumFor) and p.stop is ref:
            seg.add(3, "count", "upper bound of a for-loop")

    def target_hint(self, seg, target):
        if isinstance(target, N.Name):
            if target.binding is None:
                name = lower_camel(target.name)
                if name == target.name:
                    name += "Fn" if seg_is_function(seg) else "Value"
                seg.add(7, name, "stored into global `%s`" % target.name)
            elif target.segment is None:
                seg.add(6, target.name, "stored into local `%s`" % target.name)
            else:
                # Copied into another temporary: borrow that one's name later.
                other = target.segment

                def copy_hint(s, other=other):
                    best = max((h.weight for h in other.hints if h.name == other.base), default=0)
                    if best >= 4:
                        s.add(best * 0.7, other.base, "copied into a temporary used as `%s`" % other.base)
                seg.deferred.append(copy_hint)
        elif isinstance(target, N.Index):
            key = self.desc(target.key)
            if key[0] == "str":
                seg.add(6, lower_camel(key[1]), "stored into field `.%s`" % key[1])

    # ------------------------------------------------------------ choosing
    def choose_all(self):
        for seg in self.segments:
            self.choose(seg)
        # A declaration whose own value is never read (`local L0_1` followed by
        # `L0_1 = ...`) takes the name of the next value stored in the variable.
        for b in self.targets:
            segs = b.segments
            if len(segs) > 1 and len(segs[0].refs) == 1 and segs[0].refs[0] is b.decl:
                segs[0].merged_into = segs[1]
                segs[0].base, segs[0].reason = segs[1].base, segs[1].reason

    def choose(self, seg):
        scores = {}
        best_reason = {}
        for hint in seg.hints:
            entry = scores.setdefault(hint.name, [0.0, 0.0])
            if hint.weight > entry[0]:
                entry[0] = hint.weight
                best_reason[hint.name] = hint.reason
            entry[1] += hint.weight
        if scores:
            name = max(scores, key=lambda n: (scores[n][0] + 0.05 * scores[n][1], -len(n)))
            seg.base, seg.reason = name, best_reason[name]
        else:
            fallback = "arg" if seg.binding.kind == "param" else "value"
            seg.base, seg.reason = fallback, "no usage information available"

    def enforce_local_limit(self):
        """Undo splitting where Lua's limit of 200 active locals could be hit.

        New names are counted as if declared at the top of the variable's
        own block, which over-estimates how many locals are alive at once."""
        funcs = {}
        for b in self.bindings:
            funcs.setdefault(id(b.func), (b.func, []))[1].append(b)
        for func, bindings in funcs.values():
            split = [b for b in bindings if b in self.target_set and len(b.segments) > 1]
            if not split:
                continue
            extra = {b: len({s.base for s in b.segments}) - 1 for b in split}
            for b in sorted(split, key=lambda x: -extra[x]):
                if _max_active_locals(func, bindings, extra) <= MAX_LOCALS_PER_FUNCTION:
                    break
                extra[b] = 0
                self.unsplit(b)

    def unsplit(self, b):
        merged = Segment(b, 0)
        merged.exposed = True
        for seg in b.segments:
            self.segments.remove(seg)
            merged.refs.extend(seg.refs)
            merged.defs.extend(seg.defs)
            merged.hints.extend(seg.hints)
        for ref in merged.refs:
            ref.segment = merged
        b.segments = [merged]
        self.segments.append(merged)
        self.choose(merged)

    # ------------------------------------------------------------ allocation
    def allocate(self):
        """Give every (variable, base name) group a final, collision-free name.

        A name may be reused only by groups whose scopes do not overlap, and
        never equals a global or a meaningful (non-obfuscated) local, so a
        renamed reference can never be captured by another variable."""
        groups = []
        for b in self.targets:
            by_base = {}
            for seg in b.segments:
                by_base.setdefault(seg.base, []).append(seg)
            for base, segs in by_base.items():
                refs = [r for seg in segs for r in seg.refs]
                if b.kind == "global":
                    start, end = b.scope_start, b.scope_end
                elif any(r is b.decl for r in refs):
                    start, end = b.decl.parent.pos, b.scope_end
                else:
                    exposed = any(seg.exposed for seg in segs)
                    block, index, _ = _declaration_point(refs, b.block, exposed)
                    start = block.stmts[index].pos if index < len(block.stmts) else block.end_pos
                    end = block.end_pos
                groups.append((start, end, base, segs))
        used = {}   # name -> [(start, end, sorted ref positions, binding)]

        def any_within(positions, start, end):
            k = bisect.bisect_left(positions, start)
            return k < len(positions) and positions[k] <= end

        def free(name, start, end, positions, binding):
            # Scopes are block-structured, so two ranges are nested or disjoint.
            # An inner declaration may shadow an outer one with the same name
            # as long as the outer variable is never referenced inside it.
            if name in self.reserved:
                return False
            for s2, e2, pos2, b2 in used.get(name, ()):
                if b2 is binding:
                    return False
                if e2 < start or s2 > end:
                    continue
                if s2 <= start and end <= e2:
                    if any_within(pos2, start, end):
                        return False
                elif start <= s2 and e2 <= end:
                    if any_within(positions, s2, e2):
                        return False
                else:
                    return False
            return True

        for start, end, base, segs in sorted(groups, key=lambda g: (g[0], -g[1])):
            binding = segs[0].binding
            positions = sorted(r.pos for seg in segs for r in seg.refs)
            candidate, n = base, 1
            while not free(candidate, start, end, positions, binding):
                n += 1
                candidate = "%s%d" % (base, n)
            used.setdefault(candidate, []).append((start, end, positions, binding))
            for seg in segs:
                seg.name = candidate

    # ------------------------------------------------------------ rewriting
    def apply(self):
        for seg in self.segments:
            for ref in seg.refs:
                ref.name = seg.name
        inserts = {}     # id(block) -> (block, {stmt index: [names]})
        converts = []    # (block, stmt index)
        for b in self.targets:
            by_name = {}
            exposed = set()
            for seg in b.segments:
                by_name.setdefault(seg.name, []).extend(seg.refs)
                if seg.exposed:
                    exposed.add(seg.name)
            for name, refs in by_name.items():
                if b.kind == "global" or any(r is b.decl for r in refs):
                    continue          # declared by the original declaration
                block, index, first_refs = _declaration_point(refs, b.block, name in exposed)
                stmt = block.stmts[index] if index < len(block.stmts) else None
                target = _boundary_target(stmt) if stmt is not None else None
                if target is not None and len(first_refs) == 1 and first_refs[0] is target:
                    converts.append((block, index))
                else:
                    inserts.setdefault(id(block), (block, {}))[1].setdefault(index, []).append(
                        (name, b, refs[0].segment))
            for seg in b.segments:
                if seg.merged_into is None:
                    line = seg.refs[0].line if seg.refs else b.decl.line
                    self.renames.append(Rename(b.name, seg.name, b.kind, line, seg.reason))
        for block, index in converts:
            block.stmts[index] = _to_local(block.stmts[index])
        for block, positions in inserts.values():
            for index in sorted(positions, reverse=True):
                entries = positions[index]
                pos = block.stmts[index].pos if index < len(block.stmts) else block.end_pos
                decl = N.Local([N.Name(n, pos=pos) for n, _, _ in entries], [None] * len(entries), [],
                               pos=pos)
                decl.parent = block
                for name, (_, binding, segment) in zip(decl.names, entries):
                    name.parent = decl
                    name.binding, name.segment, name.is_decl = binding, segment, True
                block.stmts.insert(index, decl)
        self.renames.sort(key=lambda r: r.line)


_NOT_A_DEF = object()


def _max_active_locals(func, bindings, extra):
    own = {}
    for b in bindings:
        own[id(b.block)] = own.get(id(b.block), 0) + 1 + extra.get(b, 0)
    best = 0
    stack = [(func.body, 0)]
    while stack:
        block, inherited = stack.pop()
        total = inherited + own.get(id(block), 0)
        best = max(best, total)
        nodes = list(block.children())
        while nodes:
            node = nodes.pop()
            if isinstance(node, N.Block):
                stack.append((node, total))
            elif not isinstance(node, N.Function):
                nodes.extend(node.children())
    return best


def _is_called(seg):
    return any(isinstance(r.parent, N.Call) and r.parent.func is r for r in seg.refs)


def seg_is_function(seg):
    return any(isinstance(v, N.Function) for _, v in seg.defs)


def _boundary_target(stmt):
    """The Name unconditionally (re)assigned by ``stmt``, if it is that simple."""
    if isinstance(stmt, N.Assign) and stmt.op == "=" and len(stmt.targets) == 1 \
            and isinstance(stmt.targets[0], N.Name):
        return stmt.targets[0]
    if isinstance(stmt, N.FunctionStmt) and stmt.method is None and isinstance(stmt.target, N.Name):
        return stmt.target
    return None


def _webs(refs, flow):
    """Group the references of one variable into def-use webs (union-find).
    Everything closures can observe is joined through the CAPTURED node."""
    parent = {id(r): id(r) for r in refs}
    parent[id(CAPTURED)] = id(CAPTURED)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for ref in refs:
        if flow.is_exposed(ref):
            parent[find(id(ref))] = find(id(CAPTURED))
        for d in flow.reach.get(id(ref), ()):
            if id(d) in parent:
                parent[find(id(ref))] = find(id(d))
    groups = {}
    for ref in refs:
        groups.setdefault(find(id(ref)), []).append(ref)
    return list(groups.values())


def _block_chain(ref, scope_block):
    """[(block, top statement index), ...] from ``scope_block`` down to ``ref``."""
    chain = []
    node = ref
    while True:
        parent = node.parent
        if parent is None:
            raise ValueError("reference outside its scope block")
        if isinstance(parent, N.Block):
            chain.append((parent, _index_of(parent.stmts, node)))
            if parent is scope_block:
                break
        elif isinstance(parent, N.Repeat) and parent.cond is node:
            chain.append((parent.body, len(parent.body.stmts)))
            if parent.body is scope_block:
                break
        node = parent
    chain.reverse()
    return chain


def _declaration_point(refs, scope_block, top_level=False):
    """Innermost block containing all ``refs`` and the index of the first
    statement in it that mentions one of them.

    Declaring the variable right there is safe: every read of these refs
    sees only definitions from the same web (see flow.py); a definition
    reaching from outside that block or from a previous loop iteration
    would belong to the web and pull the common block further out.

    ``top_level``: a value closures can see must live exactly as long as the
    original variable, so it is declared in the variable's own block (inside
    a loop body every iteration would create a new instance)."""
    chains = [(_block_chain(r, scope_block), r) for r in refs]
    depth = 1
    while not top_level and all(len(chain) > depth for chain, _ in chains) and \
            len({id(chain[depth][0]) for chain, _ in chains}) == 1:
        depth += 1
    level = depth - 1
    block = chains[0][0][level][0]
    index = min(chain[level][1] for chain, _ in chains)
    first_refs = [r for chain, r in chains if chain[level][1] == index]
    return block, index, first_refs


def _index_of(items, node):
    for i, item in enumerate(items):
        if item is node:
            return i
    raise ValueError("node not found")


def _value_at(exprs, i):
    if i < len(exprs):
        return exprs[i]
    if exprs:
        last = exprs[-1]
        if isinstance(last, (N.Call, N.MethodCall)) or (isinstance(last, N.Const) and last.kind == "vararg"):
            return ("multi", last, i - len(exprs) + 1)
    return None


def _def_holder(func):
    """The Name a function expression is assigned to, if any."""
    p = func.parent
    if isinstance(p, (N.FunctionStmt,)) and isinstance(p.target, N.Name):
        return p.target
    if isinstance(p, N.LocalFunction):
        return p.name
    if isinstance(p, N.Local) and any(e is func for e in p.exprs):
        i = _index_of(p.exprs, func)
        return p.names[i] if i < len(p.names) else None
    if isinstance(p, N.Assign) and any(e is func for e in p.exprs):
        i = _index_of(p.exprs, func)
        target = p.targets[i] if i < len(p.targets) else None
        return target if isinstance(target, N.Name) else None
    return None


def _ancestors(node):
    node = node.parent
    while node is not None and not isinstance(node, (N.Function, N.Chunk)):
        yield node
        node = node.parent


def _to_local(stmt):
    """Turn the boundary statement into a declaration of the new name."""
    if isinstance(stmt, N.Assign):
        new = N.Local(stmt.targets, [None], stmt.exprs, pos=stmt.pos, line=stmt.line)
    else:
        new = N.LocalFunction(stmt.target, stmt.func, pos=stmt.pos, line=stmt.line)
    new.comments = stmt.comments
    new.parent = stmt.parent
    for child in new.children():
        child.parent = new
    return new
