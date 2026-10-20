import os
import random
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lua_deobf import deobfuscate  # noqa: E402
from lua_deobf.lexer import tokenize, decode_string  # noqa: E402
from lua_deobf.naming import lower_camel, singular  # noqa: E402
from lua_deobf.parser import parse  # noqa: E402
from lua_deobf.printer import to_source  # noqa: E402
from lua_deobf.verify import verify  # noqa: E402

try:
    from lupa import lua54
    from fivem_sandbox import run_script
except ImportError:  # pragma: no cover
    lua54 = None

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples")


def read(name):
    with open(os.path.join(EXAMPLES, name), encoding="utf-8") as fh:
        return fh.read()


def names_in(code):
    return set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", re.sub(r"--[^\n]*", "", code)))


class LexerParserTests(unittest.TestCase):
    SOURCE = r'''
local a <const>, b = 1, 0x1F, [==[long ]] str]==]
local t = {1, 2; x = 3, ["y z"] = 4, f = function(...) return ... end}
print "hi" ; (print)("x")
a = - -1 + 2 ^ -3 ^ 2 .. "s\n\"" .. 'q'
local s = `prop_bench`
x += 1; y ..= "q"; z //= 2
if a then b() elseif c then --[[ c ]] d() else e() end
for i = 1, 10, 2 do goto continue ::continue:: end
for k, v in pairs(t) do repeat local z = 1 until z end
function a.b.c:d(e, ...) return self, a?.b end
local function f() end
while true do break end
do return end
'''

    def test_round_trip_is_stable(self):
        once = to_source(parse(self.SOURCE))
        twice = to_source(parse(once))
        self.assertEqual(once, twice)

    def test_round_trip_preserves_program(self):
        result = verify(self.SOURCE, to_source(parse(self.SOURCE)), use_lua=False)
        self.assertTrue(result.ok, result.problems)

    def test_comments_are_kept(self):
        out = to_source(parse("-- hello\nlocal x = 1 -- trailing\nprint(x)\n"))
        self.assertIn("-- hello", out)
        self.assertIn("-- trailing", out)

    def test_ambiguous_call_gets_semicolon(self):
        out = to_source(parse("local a = b;\n(f)()"))
        self.assertIn(";(f)()", out)
        self.assertTrue(verify("local a = b;\n(f)()", out, use_lua=False).ok)

    def test_strings(self):
        self.assertEqual(decode_string(r'"a\tb\65\x41\u{48}"'), "a\tbAAH")
        self.assertEqual(decode_string("[[\nxy]]"), "xy")
        self.assertEqual([t.kind for t in tokenize("`x` 1.5e3 0xAp2")][:3], ["string", "number", "number"])

    def test_syntax_error(self):
        with self.assertRaises(Exception):
            parse("local = 5")


class NameHelperTests(unittest.TestCase):
    def test_lower_camel(self):
        self.assertEqual(lower_camel("GetPlayerPed"), "getPlayerPed")
        self.assertEqual(lower_camel("ESX"), "esx")
        self.assertEqual(lower_camel("QBCore"), "qbCore")
        self.assertEqual(lower_camel("my-event_name"), "myEventName")

    def test_singular(self):
        self.assertEqual(singular("shops"), "shop")
        self.assertEqual(singular("categories"), "category")
        self.assertEqual(singular("boxes"), "box")
        self.assertEqual(singular("list"), "item")


class NamingTests(unittest.TestCase):
    def dob(self, source, **kw):
        result = deobfuscate(source, comments=False, **kw)
        self.assertTrue(result.verification.ok, result.verification.problems)
        return result.code

    def test_native_results(self):
        code = self.dob("""
local L0_1, L1_1, L2_1
L0_1 = PlayerPedId
L0_1 = L0_1()
L1_1 = GetEntityCoords
L2_1 = L0_1
L1_1 = L1_1(L2_1)
print(L0_1, L1_1)
""")
        self.assertIn("local playerPed = playerPedId()", code)
        self.assertIn("coords = getEntityCoords(entity)", code)

    def test_event_handler_and_params(self):
        code = self.dob("""
local L0_1, L1_1, L2_1
L0_1 = AddEventHandler
L1_1 = "playerDropped"
function L2_1(A0_2)
  print(A0_2)
end
L0_1(L1_1, L2_1)
""")
        self.assertIn("function onPlayerDropped(reason)", code)
        self.assertIn("eventName = \"playerDropped\"", code)

    def test_command_handler(self):
        code = self.dob("""
RegisterCommand("heal", function(A0_2, A1_2, A2_2)
  local L3_2 = A1_2[1]
  print(A0_2, L3_2, A2_2)
end, false)
""")
        self.assertIn("function(src, args, rawCommand)", code)

    def test_esx_server_player(self):
        code = self.dob("""
local L0_1 = exports.es_extended:getSharedObject()
RegisterNetEvent("shop:buy", function(A0_2)
  local L1_2 = source
  local L2_2 = L0_1.GetPlayerFromId(L1_2)
  L2_2.removeMoney(A0_2)
end)
""")
        self.assertIn("local ESX = exports.es_extended:getSharedObject()", code)
        self.assertIn("local src = source", code)
        self.assertIn("local xPlayer = ESX.GetPlayerFromId(src)", code)
        self.assertIn("xPlayer.removeMoney(amount)", code)

    def test_loop_variables(self):
        code = self.dob("""
for L0_1, L1_1 in pairs(Config.Shops) do print(L0_1, L1_1) end
for L0_1, L1_1 in ipairs(GetActivePlayers()) do print(L1_1) end
for L0_1 = 1, 10 do for L1_1 = 1, 2 do print(L0_1 * L1_1) end end
""")
        self.assertIn("for key, shop in pairs(Config.Shops) do", code)
        self.assertIn("for i, activePlayer in ipairs(GetActivePlayers()) do", code)
        self.assertIn("for i = 1, 10 do", code)
        self.assertIn("for j = 1, 2 do", code)

    def test_reused_register_is_split(self):
        code = self.dob("""
local L0_1
L0_1 = GetPlayerPed
L0_1 = L0_1(-1)
print(L0_1)
L0_1 = "esx:test"
TriggerServerEvent(L0_1)
""")
        self.assertIn("local getPlayerPed", code)
        self.assertIn("local playerPed = getPlayerPed(-1)", code)
        self.assertIn("local eventName = \"esx:test\"", code)

    def test_no_split_mode(self):
        code = self.dob("""
local L0_1
L0_1 = GetPlayerPed
L0_1 = L0_1(-1)
print(L0_1)
""", split=False)
        self.assertEqual(code.count("local "), 1)
        self.assertNotIn("L0_1", code)

    def test_captured_variable_not_split(self):
        source = """
local L0_1 = 1
local function L1_1() return L0_1 end
L0_1 = GetGameTimer()
print(L1_1())
"""
        code = self.dob(source)
        self.assertEqual(len(re.findall(r"\blocal\b", code)), 2)

    def test_never_shadows_globals_or_named_locals(self):
        code = self.dob("""
local coords = 5
local L0_1 = GetEntityCoords(PlayerPedId())
print(coords, L0_1, playerPed)
""")
        self.assertIn("local coords2 = GetEntityCoords", code)

    def test_globals_left_alone_by_default(self):
        source = "L0_1 = 5\nprint(L0_1)\n"
        self.assertIn("L0_1", self.dob(source))
        renamed = self.dob(source, rename_globals=True)
        self.assertNotIn("L0_1", renamed)

    def test_self_referencing_value(self):
        code = self.dob("local L0_1 = nil\nwhile c do\n  L0_1 = x and L0_1\nend\nprint(L0_1)\n")
        self.assertNotIn("L0_1", code)

    def test_custom_pattern(self):
        code = self.dob("local _0x1a2b = GetPlayerPed(-1)\nprint(_0x1a2b)\n", pattern=r"^_0x[0-9a-f]+$")
        self.assertIn("local playerPed = GetPlayerPed(-1)", code)


class CommentTests(unittest.TestCase):
    def test_comments_and_header(self):
        result = deobfuscate(read("client_obfuscated.lua"))
        code = result.code
        self.assertIn("-- Script side : client", code)
        self.assertIn("-- Framework   : ESX", code)
        self.assertIn("-- Handle event 'esx:playerLoaded'", code)
        self.assertIn("-- Send event 'myshop:server:openShop' to the server", code)
        self.assertIn("-- If key E (control 38) was just released", code)
        self.assertIn("-- Register chat command /shopreset", code)
        self.assertIn("-- Main loop: runs every frame", code)

    def test_report(self):
        result = deobfuscate(read("server_obfuscated.lua"))
        report = result.report("server_obfuscated.lua")
        self.assertIn("```lua", report)
        self.assertIn("| Line | Original | New name | Kind | Why |", report)
        self.assertIn("server-side", report)


class VerifierTests(unittest.TestCase):
    def test_detects_capture(self):
        original = "local L0_1 = 1\nlocal L1_1 = 2\nprint(L0_1, L1_1)\n"
        broken = "local a = 1\nlocal a = 2\nprint(a, a)\n"
        self.assertFalse(verify(original, broken, use_lua=False).ok)

    def test_detects_global_leak(self):
        original = "local L0_1 = 1\nprint(L0_1)\n"
        broken = "local a = 1\nprint(b)\n"
        self.assertFalse(verify(original, broken, use_lua=False).ok)

    def test_detects_wrong_split(self):
        original = "local L0_1 = 1\nif c then L0_1 = 2 end\nprint(L0_1)\n"
        broken = "local a = 1\nif c then local b = 2 end\nprint(a)\n"
        self.assertFalse(verify(original, broken, use_lua=False).ok)

    def test_examples_verify(self):
        for name in sorted(os.listdir(EXAMPLES)):
            if name.endswith("_obfuscated.lua"):
                with self.subTest(name=name):
                    result = deobfuscate(read(name))
                    self.assertTrue(result.verification.ok, result.verification.problems)
                    self.assertFalse(re.search(r"\b[LA]\d+_\d+\b", re.sub(r"--[^\n]*", "", result.code)))


@unittest.skipIf(lua54 is None, "lupa (Lua 5.4) not installed")
class BehaviourTests(unittest.TestCase):
    """Run original and de-obfuscated code; the observable behaviour must match."""

    CONFIG = '{Shops = {a = {coords = {x = 1.0, y = 2.0, z = 3.5}}}}'

    def compare(self, source):
        result = deobfuscate(source)
        before = run_script(source, self.CONFIG)
        after = run_script(result.code, self.CONFIG)
        self.assertEqual(before, after)
        self.assertTrue(len(before.splitlines()) > 5)
        return before

    def test_client_example(self):
        self.compare(read("client_obfuscated.lua"))

    def test_server_example(self):
        self.compare(read("server_obfuscated.lua"))


class Fuzzer:
    """Random unluac-style programs that aggressively reuse register locals."""

    def __init__(self, seed):
        self.r = random.Random(seed)
        self.depth = 0

    def reg(self, level=1):
        return "L%d_%d" % (self.r.randrange(5), level)

    def expr(self, level):
        choice = self.r.randrange(6)
        if choice == 0:
            return str(self.r.randrange(10))
        if choice == 1:
            return self.reg(level)
        if choice == 2:
            return "%s + %s" % (self.reg(level), self.r.randrange(5))
        if choice == 3:
            return "(%s or 0) * 2" % self.reg(level)
        if choice == 4:
            return "f(%s)" % self.reg(level)
        return "#\"%s\"" % ("x" * self.r.randrange(4))

    def stmts(self, n, level, in_loop=False):
        out = []
        for _ in range(n):
            out.append(self.stmt(level, in_loop))
        return "\n".join(out)

    def stmt(self, level, in_loop):
        r = self.r.randrange(16 if self.depth < 3 else 6)
        reg = self.reg(level)
        if r == 13:
            return "fns[#fns + 1] = function() return %s end" % self.reg(level)
        if r == 14:
            return "fns[#fns + 1] = function() %s = (%s or 0) + 10 end" % (reg, reg)
        if r == 15:
            return "callall()"
        if r <= 2:
            return "%s = %s" % (reg, self.expr(level))
        if r == 3:
            return "out(%s, %s)" % (self.reg(level), self.reg(level))
        if r == 4:
            return "%s, %s = g(%s)" % (reg, self.reg(level), self.reg(level))
        if r == 5:
            return "if %s > 3 and %s then break end" % (self.reg(level), self.reg(level)) if in_loop \
                else "out(%s)" % reg
        self.depth += 1
        try:
            if r in (6, 7):
                text = "if (%s or 0) > %d then\n%s\nelse\n%s\nend" % (
                    self.reg(level), self.r.randrange(6), self.stmts(2, level, in_loop),
                    self.stmts(2, level, in_loop))
            elif r == 8:
                text = "for A%d_%d = 1, %d do\n%s\nend" % (
                    self.r.randrange(3), level, self.r.randrange(1, 4), self.stmts(3, level, True))
            elif r == 9:
                text = "do\nlocal %s = %s\n%s\nend" % (reg, self.expr(level), self.stmts(2, level, in_loop))
            elif r == 10:
                text = "while (%s or 0) < %d do\nguard()\n%s = (%s or 0) + 1\n%s\nend" % (
                    reg, self.r.randrange(2, 6), reg, reg, self.stmts(2, level, True))
            elif r == 11:
                text = "out((function() return %s end)())" % self.reg(level)
            else:
                text = "repeat\nguard()\n%s\n%s = (%s or 0) + 1\nuntil (%s or 0) > 2" % (
                    self.stmts(2, level, True), reg, reg, reg)
        finally:
            self.depth -= 1
        return text

    def program(self):
        header = "local L0_1, L1_1, L2_1, L3_1, L4_1 = 0, 1, nil, 3, 4\n"
        return header + self.stmts(12, 1) + "\ncallall()\nout(L0_1, L1_1, L2_1, L3_1, L4_1)\n"


@unittest.skipIf(lua54 is None, "lupa (Lua 5.4) not installed")
class FuzzTests(unittest.TestCase):
    PRELUDE = """
local trace = {}
local env = {}
env.out = function(...) local t = table.pack(...) for i = 1, t.n do t[i] = tostring(t[i]) end
  trace[#trace + 1] = table.concat(t, ",", 1, t.n) end
env.f = function(x) return (x or 0) % 7 end
env.fns = {}
env.callall = function() for _, fn in ipairs(env.fns) do env.out("fn", fn()) end end
env.g = function(x) return x, (x or 0) + 1 end
local steps = 0
env.guard = function() steps = steps + 1 if steps > 200 then error("loop limit") end end
local fn = assert(load(..., "p", "t", env))
local ok, err = pcall(fn)
-- error messages name the variable involved ("local 'L0_1'"), drop that part
trace[#trace + 1] = ok and "ok" or ("err:" .. tostring(err):gsub("^.-:%d+: ", ""):gsub(" %(.-%)", ""))
return table.concat(trace, "\\n")
"""

    def run_lua(self, source):
        runtime = lua54.LuaRuntime()
        return runtime.compile(self.PRELUDE)(source)

    def test_random_programs(self):
        for seed in range(300):
            source = Fuzzer(seed).program()
            with self.subTest(seed=seed):
                result = deobfuscate(source)
                self.assertTrue(result.verification.ok, result.verification.problems)
                self.assertEqual(self.run_lua(source), self.run_lua(result.code))


if __name__ == "__main__":
    unittest.main()
