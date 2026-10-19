"""Run a FiveM script in a fake FiveM runtime (Lua 5.4 via lupa) and return
a trace of every native/global call it makes. Used to compare the original
and de-obfuscated versions of a script: identical behaviour must give an
identical trace."""

try:
    from lupa import lua54
except ImportError:          # pragma: no cover
    lua54 = None

HARNESS = r"""
local source, config, ticks = ...
local log = {}
local handlers, threads, commands, callbacks = {}, {}, {}, {}

local function ser(v)
  local t = type(v)
  if t == "table" then
    local mt = getmetatable(v)
    if mt and mt.__name then return mt.__name end
    if v.__vec then return string.format("vec(%g,%g,%g)", v.x, v.y, v.z) end
    return "<table>"
  elseif t == "function" then return "<function>"
  elseif t == "string" then return string.format("%q", v)
  else return tostring(v) end
end
local function clean(e)
  -- error messages name the variable involved ("local 'L0_1'"): drop that part
  return (tostring(e):gsub("^.-:%d+: ", ""):gsub(" %(.-%)", ""))
end
local function record(name, ...)
  local parts = {}
  for i = 1, select("#", ...) do parts[#parts + 1] = ser((select(i, ...))) end
  log[#log + 1] = name .. "(" .. table.concat(parts, ", ") .. ")"
end

local vecmt = {}
local function vec(x, y, z) return setmetatable({x = x, y = y, z = z or 0.0, __vec = true}, vecmt) end
vecmt.__sub = function(a, b) return vec(a.x - b.x, a.y - b.y, a.z - b.z) end
vecmt.__add = function(a, b) return vec(a.x + b.x, a.y + b.y, a.z + b.z) end
vecmt.__len = function(a) return math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z) end

local magic
local magicmt = {}
function magic(name)
  return setmetatable({}, {
    __name = name,
    __index = function(_, k) return magic(name .. "." .. tostring(k)) end,
    __newindex = function(_, k, v) record(name .. "." .. tostring(k) .. "=", v) end,
    __call = function(self, ...) record(name, ...) return magic(name .. "()") end,
    __lt = function() return false end, __le = function() return false end,
    __len = function() return 0 end,
    __concat = function(a, b) return ser(a) .. ser(b) end,
    __add = function(a) return a end, __sub = function(a) return a end,
  })
end

local env = {}
local fivem = {
  print = function(...) record("print", ...) end,
  pairs = pairs, ipairs = ipairs, next = next, type = type, tostring = tostring,
  tonumber = tonumber, select = select, pcall = pcall, error = error,
  table = table, string = string, math = math, setmetatable = setmetatable,
  vector3 = vec, Config = config, source = 7,
  PlayerPedId = function() record("PlayerPedId") return 42 end,
  GetEntityCoords = function(e) record("GetEntityCoords", e) return vec(1.0, 2.0, 3.0) end,
  IsControlJustReleased = function(g, c) record("IsControlJustReleased", g, c) return c == 38 end,
  IsControlJustPressed = function(g, c) record("IsControlJustPressed", g, c) return c == 38 end,
  Wait = function(ms) record("Wait", ms) coroutine.yield() end,
  AddEventHandler = function(name, fn) record("AddEventHandler", name, fn)
    handlers[name] = handlers[name] or {}; table.insert(handlers[name], fn) end,
  RegisterNetEvent = function(name, fn) record("RegisterNetEvent", name, fn)
    if fn then handlers[name] = handlers[name] or {}; table.insert(handlers[name], fn) end end,
  RegisterServerEvent = function(name) record("RegisterServerEvent", name) end,
  TriggerEvent = function(name, ...) record("TriggerEvent", name, ...)
    for _, fn in ipairs(handlers[name] or {}) do fn(...) end end,
  RegisterCommand = function(name, fn, r) record("RegisterCommand", name, fn, r) commands[name] = fn end,
}
fivem.Citizen = { Wait = fivem.Wait, CreateThread = function(fn) record("CreateThread", fn)
  threads[#threads + 1] = coroutine.create(fn) end }
fivem.CreateThread = fivem.Citizen.CreateThread
fivem.ESX = {
  ShowNotification = function(msg) record("ESX.ShowNotification", msg) end,
  RegisterServerCallback = function(name, fn) record("ESX.RegisterServerCallback", name, fn) callbacks[name] = fn end,
  GetPlayerFromId = function(id) record("ESX.GetPlayerFromId", id) return magic("xPlayer" .. tostring(id)) end,
  GetPlayers = function() record("ESX.GetPlayers") return {7, 8} end,
  RegisterUsableItem = function(name, fn) record("ESX.RegisterUsableItem", name, fn) callbacks["item:" .. name] = fn end,
}
handlers["esx:getSharedObject"] = {function(cb) cb(fivem.ESX) end}
setmetatable(env, {__index = function(_, k)
  local v = fivem[k]
  if v ~= nil then return v end
  return magic(k)
end})

local chunk, err = load(source, "script", "t", env)
if not chunk then error(err) end
chunk()

-- Fire every registered event with deterministic arguments.
local names = {}
for name in pairs(handlers) do
  if name ~= "esx:getSharedObject" then names[#names + 1] = name end
end
local event_args = {playerDropped = {"Exiting"}}
table.sort(names)
for _, name in ipairs(names) do
  for _, fn in ipairs(handlers[name]) do
    local args = event_args[name] or {{job = {name = "police"}, name = "test"}, "second"}
    local ok, e = pcall(fn, table.unpack(args))
    if not ok then record("error", name, clean(e)) end
  end
end
-- Run commands and callbacks.
local cnames = {}
for name in pairs(commands) do cnames[#cnames + 1] = name end
table.sort(cnames)
for _, name in ipairs(cnames) do
  local ok, e = pcall(commands[name], 7, {"arg1", "5"}, name .. " arg1 5")
  if not ok then record("error", name, clean(e)) end
end
local cbnames = {}
for name in pairs(callbacks) do cbnames[#cbnames + 1] = name end
table.sort(cbnames)
for _, name in ipairs(cbnames) do
  local ok, e = pcall(callbacks[name], 7, function(...) record("cb", ...) end, "item_a", 2)
  if not ok then record("error", name, clean(e)) end
end
-- Let every thread run a few ticks.
for _ = 1, ticks do
  for i, co in ipairs(threads) do
    if coroutine.status(co) ~= "dead" then
      local ok, e = coroutine.resume(co)
      if not ok then record("error", "thread" .. i, clean(e)) end
    end
  end
end
return table.concat(log, "\n")
"""


def run_script(source, config_lua="{}", ticks=4):
    runtime = lua54.LuaRuntime(unpack_returned_tuples=True)
    config = runtime.execute("return " + config_lua)
    harness = runtime.compile(HARNESS)
    return harness(source, config, ticks)
