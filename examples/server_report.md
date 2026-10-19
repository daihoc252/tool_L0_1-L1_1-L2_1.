# De-obfuscation report: `server_obfuscated.lua`

## What the script does

This looks like a **server-side** FiveM script built on **ESX**. It reacts to the events `myshop:server:openShop`, `playerDropped`. It sends `myshop:client:notify` to clients. It triggers the local events `esx:getSharedObject`. It registers the chat command(s) `/shopreset`. It provides the server callbacks `myshop:buyItem`. It makes the items `shop_voucher` usable.

## How names were inferred

* **Decompiled code reuses variables.** Tools such as *unluac* emit one local
  per VM register (`L0_1`, `A0_2`, ...: `L` = local, `A` = argument, the
  suffix is the function nesting depth) and reuse it for unrelated values.
  A reaching-definitions analysis splits each such variable into independent
  *values* (def-use webs) so every value gets its own name. Once a closure
  (event handler, thread...) can see a variable, all later accesses stay
  one shared variable; in functions using `goto` variables are only
  renamed, never split.
* **Names come from evidence.** Each value collects weighted hints: what
  produced it (`GetEntityCoords(...)` gives `coords`, `"esx:setJob"` passed to
  `AddEventHandler` gives `eventName`, a function registered for that event
  gives `onSetJob`), how it is used (passed as the `entity` argument of a
  native, `:getMoney()` called on it gives `xPlayer`), where it is stored
  (`DrawText3D = L3_1` gives `drawText3D`) and FiveM knowledge (parameters of
  `playerDropped`, `RegisterCommand` handlers, ESX/QBCore callbacks...). The
  strongest hint wins; the "Why" column below quotes it.
* **Renaming is scope-safe.** A new name never equals a global or a
  meaningful local, and two variables share a name only if neither is used
  inside the other's scope. Logic, control flow and every call are unchanged.

## Renamed variables

| Line | Original | New name | Kind | Why |
|---:|---|---|---|---|
| 2 | `L0_1` | `ESX` | local | receives the framework object from 'esx:getSharedObject' |
| 3 | `L1_1` | `triggerEvent` | local | holds `TriggerEvent` |
| 4 | `L2_1` | `eventName` | local | passed as argument #1 (eventName) to `TriggerEvent` |
| 5 | `L3_1` | `callback` | local | callback registered with `TriggerEvent` for 'esx:getSharedObject' |
| 5 | `A0_2` | `obj` | parameter | parameter of the 'esx:getSharedObject' event |
| 9 | `L1_1` | `tbl` | local | indexed like a table |
| 10 | `L2_1` | `log` | local | only prints to the console |
| 10 | `A0_2` | `arg1` | parameter | parameter #1 |
| 10 | `A1_2` | `text` | parameter | used in string concatenation |
| 12 | `L2_2` | `printFn` | local | holds `print` |
| 13 | `L3_2` | `text2` | local | string literal |
| 14 | `L4_2` | `text3` | local | used in string concatenation |
| 15 | `L3_2` | `text2` | local | string concatenation |
| 18 | `L3_1` | `registerServerEvent` | local | holds `RegisterServerEvent` |
| 19 | `L4_1` | `eventName2` | local | passed as argument #1 (eventName) to `RegisterServerEvent` |
| 21 | `L3_1` | `addEventHandler` | local | holds `AddEventHandler` |
| 22 | `L4_1` | `eventName2` | local | passed as argument #1 (eventName) to `AddEventHandler` |
| 23 | `L5_1` | `onOpenShop` | local | callback registered with `AddEventHandler` for 'myshop:server:openShop' |
| 23 | `A0_2` | `key` | parameter | used as a table key |
| 25 | `L1_2` | `src` | local | copy of the global `source` (id of the player who triggered the event) |
| 26 | `L2_2` | `getPlayerFromId` | local | holds `ESX.GetPlayerFromId` |
| 27 | `L3_2` | `playerId` | local | passed as argument #1 (playerId) to `ESX.GetPlayerFromId` |
| 28 | `L2_2` | `xPlayer` | local | result of `ESX.GetPlayerFromId(...)` |
| 32 | `L3_2` | `config` | local | holds `Config` |
| 33 | `L3_2` | `shops` | local | holds `Config.Shops` |
| 34 | `L3_2` | `shop` | local | element of `shops` looked up by key |
| 36 | `L4_2` | `callback` | local | called as a function |
| 37 | `L5_2` | `src2` | local | copy of the global `source` (id of the player who triggered the event) |
| 38 | `L6_2` | `text` | local | string literal |
| 42 | `L4_2` | `getMoney` | local | holds field `.getMoney` of another value |
| 43 | `L4_2` | `money` | local | result of `getMoney(...)` |
| 44 | `L5_2` | `tbl2` | local | indexed like a table |
| 46 | `L5_2` | `triggerClientEvent` | local | holds `TriggerClientEvent` |
| 47 | `L6_2` | `eventName` | local | passed as argument #1 (eventName) to `TriggerClientEvent` |
| 51 | `L3_1` | `registerServerCallback` | local | holds `ESX.RegisterServerCallback` |
| 52 | `L4_1` | `callbackName` | local | passed as argument #1 (callbackName) to `ESX.RegisterServerCallback` |
| 53 | `L5_1` | `buyItemCallback` | local | callback registered with `ESX.RegisterServerCallback` for 'myshop:buyItem' |
| 53 | `A0_2` | `src` | parameter | parameter of a server callback callback (ESX.RegisterServerCallback) |
| 53 | `A1_2` | `cb` | parameter | parameter of a server callback callback (ESX.RegisterServerCallback) |
| 53 | `A2_2` | `itemName` | parameter | copied into a temporary used as `itemName` |
| 53 | `A3_2` | `count` | parameter | passed as argument #2 (count) to `addInventoryItem` |
| 55 | `L4_2` | `getPlayerFromId` | local | holds `ESX.GetPlayerFromId` |
| 56 | `L5_2` | `playerId` | local | passed as argument #1 (playerId) to `ESX.GetPlayerFromId` |
| 57 | `L4_2` | `xPlayer` | local | result of `ESX.GetPlayerFromId(...)` |
| 58 | `L5_2` | `num2` | local | used in arithmetic |
| 59 | `L6_2` | `num` | local | used in arithmetic |
| 60 | `L5_2` | `amount2` | local | copied into a temporary used as `amount` |
| 61 | `L6_2` | `getMoney` | local | holds field `.getMoney` of another value |
| 62 | `L6_2` | `money` | local | result of `getMoney(...)` |
| 64 | `L7_2` | `removeMoney` | local | holds field `.removeMoney` of another value |
| 65 | `L8_2` | `amount` | local | passed as argument #1 (amount) to `removeMoney` |
| 67 | `L7_2` | `addInventoryItem` | local | holds field `.addInventoryItem` of another value |
| 68 | `L8_2` | `itemName2` | local | passed as argument #1 (itemName) to `addInventoryItem` |
| 70 | `L7_2` | `cb2` | local | receives the parameter of a server callback callback (ESX.RegisterServerCallback) |
| 71 | `L8_2` | `flag` | local | boolean literal |
| 74 | `L7_2` | `cb2` | local | receives the parameter of a server callback callback (ESX.RegisterServerCallback) |
| 75 | `L8_2` | `flag` | local | boolean literal |
| 80 | `L3_1` | `registerUsableItem` | local | holds `ESX.RegisterUsableItem` |
| 81 | `L4_1` | `itemName` | local | passed as argument #1 (itemName) to `ESX.RegisterUsableItem` |
| 82 | `L5_1` | `useShopVoucher` | local | callback registered with `ESX.RegisterUsableItem` for 'shop_voucher' |
| 82 | `A0_2` | `src` | parameter | parameter of a usable item callback (ESX.RegisterUsableItem) |
| 84 | `L1_2` | `getPlayerFromId` | local | holds `ESX.GetPlayerFromId` |
| 85 | `L2_2` | `playerId` | local | passed as argument #1 (playerId) to `ESX.GetPlayerFromId` |
| 86 | `L1_2` | `xPlayer` | local | result of `ESX.GetPlayerFromId(...)` |
| 87 | `L2_2` | `removeInventoryItem` | local | holds field `.removeInventoryItem` of another value |
| 89 | `L2_2` | `addMoney` | local | holds field `.addMoney` of another value |
| 93 | `L3_1` | `addEventHandler` | local | holds `AddEventHandler` |
| 94 | `L4_1` | `eventName2` | local | passed as argument #1 (eventName) to `AddEventHandler` |
| 95 | `L5_1` | `onPlayerDropped` | local | callback registered with `AddEventHandler` for 'playerDropped' |
| 95 | `A0_2` | `reason` | parameter | parameter of the 'playerDropped' event |
| 97 | `L1_2` | `src` | local | copy of the global `source` (id of the player who triggered the event) |
| 98 | `L2_2` | `tbl2` | local | indexed like a table |
| 100 | `L2_2` | `callback` | local | called as a function |
| 104 | `L3_1` | `registerCommand` | local | holds `RegisterCommand` |
| 105 | `L4_1` | `commandName` | local | passed as argument #1 (commandName) to `RegisterCommand` |
| 106 | `L5_1` | `shopresetCommand` | local | callback registered with `RegisterCommand` for 'shopreset' |
| 106 | `A0_2` | `src` | parameter | parameter of a command callback (RegisterCommand) |
| 106 | `A1_2` | `args` | parameter | parameter of a command callback (RegisterCommand) |
| 106 | `A2_2` | `rawCommand` | parameter | parameter of a command callback (RegisterCommand) |
| 107 | `L7_2` | `value` | local | no usage information available |
| 108 | `L3_2` | `tonumberFn` | local | holds `tonumber` |
| 109 | `L4_2` | `text` | local | passed as argument #1 (text) to `tonumber` |
| 110 | `L3_2` | `num` | local | result of `tonumber(...)` |
| 112 | `L4_2` | `tbl2` | local | indexed like a table |
| 115 | `L4_2` | `pairsFn` | local | holds `pairs` |
| 116 | `L5_2` | `data` | local | table constructor |
| 117 | `L4_2` | `iterator` | local | first result of `pairs(...)` |
| 117 | `L5_2` | `state` | local | result #2 of `pairs(...)` |
| 117 | `L6_2` | `initial` | local | result #3 of `pairs(...)` |
| 118 | `L7_2` | `key` | loop variable | key of a `pairs` loop |
| 122 | `L4_2` | `callback` | local | called as a function |
| 123 | `L5_2` | `src2` | local | receives the parameter of a command callback (RegisterCommand) |
| 124 | `L6_2` | `text` | local | string literal |

## Verification

Passed: the output has the same structure as the original, and each of the 101 local-variable reads sees exactly the same definitions as before.
The output also compiles with Lua 5.4.

## De-obfuscated code

```lua
-- ======================================================================
-- De-obfuscated with lua_deobf (variable names inferred from usage).
-- Script side : server (guessed from the natives/APIs it uses)
-- Framework   : ESX
-- Handles     : 'myshop:server:openShop', 'playerDropped'
-- To clients  : 'myshop:client:notify'
-- Local events: 'esx:getSharedObject'
-- Commands    : /shopreset
-- Callbacks   : 'myshop:buyItem'
-- Items       : 'shop_voucher'
-- Renamed     : 43 obfuscated variables -> 93 named values
-- ======================================================================

local ESX, triggerEvent, eventName, callback, eventName2, onOpenShop
ESX = nil

-- Trigger local event 'esx:getSharedObject'
triggerEvent = TriggerEvent
eventName = "esx:getSharedObject"
function callback(obj)
    ESX = obj
end

triggerEvent(eventName, callback)
local tbl = {}

-- log(arg1, text)
local function log(arg1, text)
    -- Print to console
    local printFn, text2, text3
    printFn = print
    text2 = "[myshop] "
    text3 = arg1
    text2 = text2 .. text3 .. " -> " .. text
    printFn(text2)
end

-- Register server event 'myshop:server:openShop' (can be triggered by clients)
local registerServerEvent = RegisterServerEvent
eventName2 = "myshop:server:openShop"
registerServerEvent(eventName2)

-- Handle event 'myshop:server:openShop'
--   -> uses ESX.GetPlayerFromId, getMoney; triggers 'myshop:client:notify'
local addEventHandler = AddEventHandler
eventName2 = "myshop:server:openShop"
function onOpenShop(key)
    local src, getPlayerFromId, playerId, callback, src2, text
    src = source
    getPlayerFromId = ESX.GetPlayerFromId
    playerId = src
    local xPlayer = getPlayerFromId(playerId)
    if not xPlayer then
        return
    end
    local config = Config
    local shops = config.Shops
    local shop = shops[key]
    if not shop then
        callback = log
        src2 = src
        text = "tried to open unknown shop"
        callback(src2, text)
        return
    end
    local getMoney = xPlayer.getMoney
    local money = getMoney()
    local tbl2 = tbl
    tbl2[src] = key

    -- Send event 'myshop:client:notify' to client src
    local triggerClientEvent = TriggerClientEvent
    local eventName = "myshop:client:notify"
    triggerClientEvent(eventName, src, "Welcome! You have $" .. money)
end

addEventHandler(eventName2, onOpenShop)

-- Register ESX server callback 'myshop:buyItem'
--   -> uses ESX.GetPlayerFromId, getMoney, removeMoney, addInventoryItem
local registerServerCallback = ESX.RegisterServerCallback
local callbackName = "myshop:buyItem"
local function buyItemCallback(src, cb, itemName, count)
    local getPlayerFromId, playerId, num, removeMoney, amount
    getPlayerFromId = ESX.GetPlayerFromId
    playerId = src
    local xPlayer = getPlayerFromId(playerId)
    local num2 = 10
    num = count
    local amount2 = num2 * num
    local getMoney = xPlayer.getMoney
    local money = getMoney()
    local cb2, flag
    if amount2 <= money then
        -- Take money from player
        removeMoney = xPlayer.removeMoney
        amount = amount2
        removeMoney(amount)

        -- Give item itemName2 to player
        local addInventoryItem = xPlayer.addInventoryItem
        local itemName2 = itemName
        addInventoryItem(itemName2, count)
        cb2 = cb
        flag = true
        cb2(flag)
    else
        cb2 = cb
        flag = false
        cb2(flag)
    end
end

registerServerCallback(callbackName, buyItemCallback)

-- Make item 'shop_voucher' usable
--   -> uses ESX.GetPlayerFromId, removeInventoryItem, addMoney
local registerUsableItem = ESX.RegisterUsableItem
local itemName = "shop_voucher"
local function useShopVoucher(src)
    -- Remove item 'shop_voucher' from player
    local getPlayerFromId, playerId
    getPlayerFromId = ESX.GetPlayerFromId
    playerId = src
    local xPlayer = getPlayerFromId(playerId)
    local removeInventoryItem = xPlayer.removeInventoryItem
    removeInventoryItem("shop_voucher", 1)

    -- Give money to player
    local addMoney = xPlayer.addMoney
    addMoney(500)
end

registerUsableItem(itemName, useShopVoucher)

-- Handle event 'playerDropped'
addEventHandler = AddEventHandler
eventName2 = "playerDropped"
local function onPlayerDropped(reason)
    local src, tbl2
    src = source
    tbl2 = tbl
    tbl2[src] = nil
    local callback = log
    callback(src, "left: " .. reason)
end

addEventHandler(eventName2, onPlayerDropped)

-- Register chat command /shopreset
local registerCommand = RegisterCommand
local commandName = "shopreset"
local function shopresetCommand(src, args, rawCommand)
    local tonumberFn, text, data, initial, value
    tonumberFn = tonumber
    text = args[1]
    local num = tonumberFn(text)
    if num then
        local tbl2 = tbl
        tbl2[num] = nil
    else
        local pairsFn = pairs
        data = tbl
        local iterator, state
        iterator, state, initial = pairsFn(data)
        for key in iterator, state, initial do
            tbl[key] = nil
        end
    end
    local callback = log
    local src2 = src
    local text = "reset shops"
    callback(src2, text)
end

registerCommand(commandName, shopresetCommand, true)
```
