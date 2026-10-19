# lua_deobf: FiveM Lua de-obfuscator

`lua_deobf` turns decompiled or obfuscated FiveM Lua, full of names like `L0_1`,
`L1_1` and `A0_2`, back into readable code. It:

1. **parses** the Lua (5.4 + CfxLua extensions: backtick hashes, `+=`, `?.`, `<const>`),
2. **infers** what each obfuscated variable holds from its context, usage and FiveM knowledge,
3. **renames** it to a descriptive name (`playerPed`, `xPlayer`, `onPlayerLoaded`, `eventName`...),
4. **keeps the logic identical** and **proves it** by re-parsing the output and checking data flow,
5. **adds comments** explaining each section (events, commands, threads, key checks, natives...),
6. **pretty-prints** the result and writes a Markdown report that explains every naming decision.

No dependencies; Python 3.8+. Install `lupa` (optional) to also compile the output with a real Lua 5.4.

## Windows: double-click `deobfuscate.bat`

1. Install Python 3 from https://www.python.org/downloads/ and tick **"Add Python to PATH"** during setup.
2. Run `deobfuscate.bat` in one of these ways:
   * **drag** a folder or a `.lua` file onto `deobfuscate.bat`, or
   * double-click it, then choose **1** to pick a folder in a dialog, or **2** to paste a folder/file path.
3. Results:
   * folder `C:\res\shop` → `C:\res\shop_deobf\` (same subfolders, every `.lua` processed, plus a `.report.md` per file)
   * file `client.lua` → `client_deobf.lua` + `client_deobf.report.md` next to it

   Explorer opens on the result automatically.

## Quick start

```bash
python -m lua_deobf client.lua                      # print de-obfuscated code
python -m lua_deobf client.lua -o client_clean.lua  # write to a file
python -m lua_deobf client.lua --markdown           # report: explanation + rename table + ```lua code
python -m lua_deobf client.lua -o out.lua --report  # code + out.report.md
python -m lua_deobf resource/ -o clean/ --report    # a whole folder
```

Or install it with `pip install .` and use the `lua-deobf` command.

| Option | Meaning |
|---|---|
| `--markdown` | output a Markdown document (purpose, rename table with reasons, verification, code in a ```lua block) |
| `--report [PATH]` | also write that Markdown report next to the output |
| `--no-comments` | rename only, no added comments/header |
| `--no-split` | never split reused temporaries (exactly one new name per old name) |
| `--rename-globals` | also rename obfuscated-looking *globals* (off by default: other files may use them) |
| `--pattern REGEX` | what counts as obfuscated (default `^[A-Za-z]\d+_\d+$`, e.g. `--pattern '^_0x[0-9a-f]+$'`) |
| `--side client\|server` | override the client/server guess (affects e.g. `esx:playerLoaded` parameters) |
| `--indent N` / `--tabs` | output indentation |
| `--no-verify` | skip the equivalence check |

Python API:

```python
from lua_deobf import deobfuscate
result = deobfuscate(open("client.lua").read())
print(result.code)                 # de-obfuscated Lua
for r in result.renames:           # every decision with its reason
    print(r.line, r.old, "->", r.new, ":", r.reason)
print(result.verification.ok)      # True if proven equivalent
print(result.report("client.lua")) # Markdown report
```

## Example

Input (typical *unluac* output, see [`examples/client_obfuscated.lua`](examples/client_obfuscated.lua)):

```lua
L3_1 = Citizen
L3_1 = L3_1.CreateThread
function L4_1()
  local L0_2, L1_2, L2_2, L3_2, L4_2, L5_2, L6_2, L7_2, L8_2, L9_2, L10_2
  while true do
    L0_2 = 500
    L1_2 = PlayerPedId
    L1_2 = L1_2()
    L2_2 = GetEntityCoords
    L3_2 = L1_2
    L2_2 = L2_2(L3_2)
    ...
    for L6_2, L7_2 in L3_2, L4_2, L5_2 do
      L8_2 = L7_2.coords
      L8_2 = L2_2 - L8_2
      L8_2 = #L8_2
      if L8_2 < 10.0 then
```

Output ([`examples/client_deobfuscated.lua`](examples/client_deobfuscated.lua), report in
[`examples/client_report.md`](examples/client_report.md)):

```lua
-- Start a new thread (coroutine)
--   -> uses PlayerPedId, GetEntityCoords, DrawMarker, DrawText3D, IsControlJustReleased; triggers 'myshop:server:openShop'
citizen = Citizen
createThread = citizen.CreateThread
function threadFunc()
    local waitTime, playerPedId, getEntityCoords, entity, config, initial, value, value2, coords, drawMarker, markerType

    -- Main loop: sleeps 0 or 500 ms per iteration (adaptive)
    while true do
        waitTime = 500
        playerPedId = PlayerPedId
        local playerPed = playerPedId()
        getEntityCoords = GetEntityCoords
        entity = playerPed
        local coords2 = getEntityCoords(entity)
        ...
        for key, shop in iterator, state, initial do
            -- If within 10.0 units
            coords = shop.coords
            local offset = coords2 - coords
            local distance = #offset
            if distance < 10.0 then
```

## How variables are named

Decompilers such as *unluac* create one local per Lua VM register: `L` = local,
`A` = argument, and the suffix is the function nesting depth. They reuse that
local for unrelated values. In the input above, `L8_2` is first a table field,
then a vector difference, then a distance. A single name would be misleading, so
the tool works per **value**:

* **Live-range splitting.** A reaching-definitions analysis (`flow.py`) finds which
  assignments each read can see. Reads and writes that can never exchange a value
  form separate *webs*, and each web gets its own name and its own `local`
  declaration, placed so that every read sees exactly the values it saw before.
  Once a closure such as an event handler or thread can see a variable, all later
  accesses stay one shared variable, declared where the original was. In functions
  that use `goto`, variables are renamed only, never split.
* **Weighted hints.** Each web collects evidence, and the strongest hint wins.
  The report's "Why" column quotes it.
  * *Producer*: `GetEntityCoords(...)` gives `coords`. `ESX.GetPlayerFromId(...)` gives `xPlayer`. `#(a - b)` gives `distance`. `source` gives `src`. `exports.es_extended:getSharedObject()` gives `ESX`. Any other `GetX`/`IsX`/`CreateX` call gives `x`/`isX`.
  * *Consumer*: the argument's role in roughly 180 known functions (e.g. `TaskWarpPedIntoVehicle(ped, vehicle, seatIndex)`). The first argument of a `SetVehicle*`, `SetPed*` or `SetEntity*` native gives `vehicle`, `ped` or `entity`. Calling `:getMoney()` on a value gives `xPlayer`. Reading `.PlayerData` gives `Player`.
  * *Destination*: `DrawText3D = L3_1` gives `drawText3D`. `Config.X = v` gives `x`. `{ coords = v }` gives `coords`. A value copied into a temporary borrows that temporary's name.
  * *FiveM context*: handler parameters for known events (`playerDropped(reason)`, `playerConnecting(playerName, setKickReason, deferrals)`, `esx:setJob(job, lastJob)`...). Command handlers get `(src, args, rawCommand)`. ESX/QBCore/ox_lib callbacks get `(src, cb, ...)`. Handlers are named after their event or command (`onPlayerLoaded`, `shopresetCommand`). `pairs(Config.Shops)` loops get `key, shop`, and numeric loops get `i`, `j`, `k`.
* **Scope-safe allocation.** A new name never equals a global, a Lua/FiveM builtin
  or a meaningful local. Two variables share a name only if neither is referenced
  inside the other's scope, so shadowing can never redirect a reference. Clashes
  get a numeric suffix (`coords2`).

## Why the logic is guaranteed unchanged

Every run re-parses its own output and checks it against the original
(`verify.py`):

1. **Same program shape.** With local names erased, both programs produce the same
   canonical stream of statements, operators, literals, globals, fields and calls.
2. **Same data flow.** Every read of a local sees exactly the same set of
   definitions as before. Accesses visible to closures stay grouped exactly as
   before.
3. **Real Lua.** With `lupa` installed, the output must compile in Lua 5.4.

If any check fails, the CLI prints `VERIFICATION FAILED` and exits with status 1.

The test suite (`python -m unittest discover tests`) also **runs** the code. The
examples run inside a mocked FiveM runtime (events, threads, commands, ESX), and
the original and de-obfuscated call traces must be identical. A fuzzer generates
300 random register-reusing programs (branches, loops, `break`, `repeat`, multiple
assignment, closures that read or write registers and are called later) and
compares their output under Lua 5.4. The fuzzer is not just for show: it caught
a real bug during development (`a, a = f()` assigns right-to-left in Lua 5.4).

## Comments that are added

* A **header** with the guessed side (client/server), framework (ESX, QBCore,
  ox_lib, oxmysql...), events handled and triggered, commands, callbacks, NUI
  callbacks, exports, usable items, threads and globals defined.
* Above each logical step (the whole group of temp assignments that prepares a
  call), what it does:
  * events: `-- Handle event 'esx:playerLoaded'`, `-- Send event 'x' to the server`
  * commands, callbacks, NUI, exports, timers
  * around 100 natives: `-- Teleport entity`, `-- Draw marker (type 2)`
  * conditions: `-- If key E (control 38) was just released`, `-- If within 1.5 units`
  * loops: `-- Main loop: runs every frame`
  * functions: their signature plus a summary of the natives they use and the events they trigger
* The original comments are kept.

## Limitations

* Names are inferred, so they can be generic (`value`, `data`) when the code gives
  no clue, or occasionally wrong in meaning. Logic is never affected. Every choice
  is listed with its reason in the report.
* The input must be Lua source. For compiled bytecode (`\x1bLua` header), decompile
  it first, e.g. with *unluac*.
* Code that reads locals through `debug.getlocal`, or that relies on a runtime error
  message naming a variable, can observe names. That is unavoidable for any renamer.

## Project layout

```
lua_deobf/
  lexer.py      tokenizer (Lua 5.4 + CfxLua)
  parser.py     recursive-descent parser -> nodes.py AST (parentheses kept)
  printer.py    pretty printer (round-trip exact)
  scope.py      binds every name to its declaration
  flow.py       reaching definitions, closure capture model
  naming.py     webs, hints, name choice, safe allocation, rewriting
  knowledge.py  FiveM natives, ESX/QBCore/ox APIs, event signatures, control keys
  annotate.py   comments and script summary
  verify.py     equivalence checker
  report.py     Markdown report
  cli.py        command line
examples/       obfuscated inputs, de-obfuscated outputs, reports
tests/          unit tests, FiveM sandbox trace comparison, fuzzer
```
