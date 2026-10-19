# De-obfuscation report: `client_obfuscated.lua`

## What the script does

This looks like a **client-side** FiveM script built on **ESX**. It reacts to the events `esx:playerLoaded`, `esx:setJob`, `myshop:client:notify`. It sends `myshop:server:openShop`, `myshop:server:reset` to the server. It triggers the local events `esx:getSharedObject`. It registers the chat command(s) `/shopreset`. It starts 2 thread(s) (game loops that run continuously). It defines the global function(s) `DrawText3D`. Main game natives used: `AddTextComponentString`, `ClearDrawOrigin`, `DrawMarker`, `DrawText`, `GetEntityCoords`, `IsControlJustReleased`, `PlayerPedId`, `SetDrawOrigin`, `SetTextEntry`, `SetTextFont`.

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
| 2 | `L0_1` | `value` | local | no usage information available |
| 3 | `L1_1` | `playerData` | local | receives the parameter of the 'esx:playerLoaded' event |
| 4 | `L2_1` | `isPlayerLoaded` | local | set to true when event 'esx:playerLoaded' fires |
| 5 | `L3_1` | `citizen` | local | holds `Citizen` |
| 6 | `L3_1` | `createThread` | local | holds `Citizen.CreateThread` |
| 7 | `L4_1` | `threadFunc` | local | callback registered with `Citizen.CreateThread` |
| 10 | `L0_2` | `esx` | local | holds `ESX` |
| 14 | `L0_2` | `triggerEvent` | local | holds `TriggerEvent` |
| 15 | `L1_2` | `eventName` | local | passed as argument #1 (eventName) to `TriggerEvent` |
| 16 | `L2_2` | `callback` | local | callback registered with `TriggerEvent` for 'esx:getSharedObject' |
| 16 | `A0_3` | `obj` | parameter | parameter of the 'esx:getSharedObject' event |
| 20 | `L0_2` | `citizen` | local | holds `Citizen` |
| 21 | `L0_2` | `wait` | local | holds `Citizen.Wait` |
| 22 | `L1_2` | `waitTime` | local | passed as argument #1 (waitTime) to `Citizen.Wait` |
| 27 | `L3_1` | `drawText3D` | local | stored into global `DrawText3D` |
| 27 | `A0_2` | `x` | parameter | copied into a temporary used as `x` |
| 27 | `A1_2` | `y` | parameter | copied into a temporary used as `y` |
| 27 | `A2_2` | `z` | parameter | copied into a temporary used as `z` |
| 27 | `A3_2` | `text` | parameter | copied into a temporary used as `text` |
| 28 | `L9_2` | `value` | local | no usage information available |
| 28 | `L10_2` | `value2` | local | no usage information available |
| 29 | `L4_2` | `setTextScale` | local | holds `SetTextScale` |
| 30 | `L5_2` | `scaleX` | local | passed as argument #1 (scaleX) to `SetTextScale` |
| 31 | `L6_2` | `scaleY` | local | passed as argument #2 (scaleY) to `SetTextScale` |
| 33 | `L4_2` | `setTextFont` | local | holds `SetTextFont` |
| 34 | `L5_2` | `fontId` | local | passed as argument #1 (fontId) to `SetTextFont` |
| 36 | `L4_2` | `setTextEntry` | local | holds `SetTextEntry` |
| 37 | `L5_2` | `textEntry` | local | passed as argument #1 (textEntry) to `SetTextEntry` |
| 39 | `L4_2` | `addTextComponentString` | local | holds `AddTextComponentString` |
| 40 | `L5_2` | `text2` | local | passed as argument #1 (text) to `AddTextComponentString` |
| 42 | `L4_2` | `setDrawOrigin` | local | holds `SetDrawOrigin` |
| 43 | `L5_2` | `x2` | local | passed as argument #1 (x) to `SetDrawOrigin` |
| 44 | `L6_2` | `y2` | local | passed as argument #2 (y) to `SetDrawOrigin` |
| 45 | `L7_2` | `z2` | local | passed as argument #3 (z) to `SetDrawOrigin` |
| 46 | `L8_2` | `p3` | local | passed as argument #4 (p3) to `SetDrawOrigin` |
| 48 | `L4_2` | `drawText` | local | holds `DrawText` |
| 49 | `L5_2` | `screenX` | local | passed as argument #1 (screenX) to `DrawText` |
| 50 | `L6_2` | `screenY` | local | passed as argument #2 (screenY) to `DrawText` |
| 52 | `L4_2` | `clearDrawOrigin` | local | holds `ClearDrawOrigin` |
| 56 | `L3_1` | `registerNetEvent` | local | holds `RegisterNetEvent` |
| 57 | `L4_1` | `eventName` | local | passed as argument #1 (eventName) to `RegisterNetEvent` |
| 59 | `L3_1` | `addEventHandler` | local | holds `AddEventHandler` |
| 60 | `L4_1` | `eventName` | local | passed as argument #1 (eventName) to `AddEventHandler` |
| 61 | `L5_1` | `onPlayerLoaded` | local | callback registered with `AddEventHandler` for 'esx:playerLoaded' |
| 61 | `A0_2` | `playerData2` | parameter | parameter of the 'esx:playerLoaded' event |
| 66 | `L3_1` | `registerNetEvent` | local | holds `RegisterNetEvent` |
| 67 | `L4_1` | `eventName` | local | passed as argument #1 (eventName) to `RegisterNetEvent` |
| 69 | `L3_1` | `addEventHandler` | local | holds `AddEventHandler` |
| 70 | `L4_1` | `eventName` | local | passed as argument #1 (eventName) to `AddEventHandler` |
| 71 | `L5_1` | `onSetJob` | local | callback registered with `AddEventHandler` for 'esx:setJob' |
| 71 | `A0_2` | `job` | parameter | parameter of the 'esx:setJob' event |
| 75 | `L3_1` | `citizen` | local | holds `Citizen` |
| 76 | `L3_1` | `createThread` | local | holds `Citizen.CreateThread` |
| 77 | `L4_1` | `threadFunc` | local | callback registered with `Citizen.CreateThread` |
| 78 | `L6_2` | `value` | local | no usage information available |
| 78 | `L7_2` | `value2` | local | no usage information available |
| 80 | `L0_2` | `waitTime` | local | copied into a temporary used as `waitTime` |
| 81 | `L1_2` | `playerPedId` | local | holds `PlayerPedId` |
| 82 | `L1_2` | `playerPed` | local | result of `PlayerPedId(...)` |
| 83 | `L2_2` | `getEntityCoords` | local | holds `GetEntityCoords` |
| 84 | `L3_2` | `entity` | local | passed as argument #1 (entity) to `GetEntityCoords` |
| 85 | `L2_2` | `coords2` | local | result of `GetEntityCoords(...)` |
| 86 | `L3_2` | `pairsFn` | local | holds `pairs` |
| 87 | `L4_2` | `config` | local | holds `Config` |
| 88 | `L4_2` | `shops` | local | holds `Config.Shops` |
| 89 | `L3_2` | `iterator` | local | first result of `pairs(...)` |
| 89 | `L4_2` | `state` | local | result #2 of `pairs(...)` |
| 89 | `L5_2` | `initial` | local | result #3 of `pairs(...)` |
| 90 | `L6_2` | `key` | loop variable | key of a `pairs` loop |
| 90 | `L7_2` | `shop` | loop variable | element of `shops` iterated with pairs |
| 91 | `L8_2` | `coords` | local | holds field `.coords` of another value |
| 92 | `L8_2` | `offset` | local | vector difference whose length is taken |
| 93 | `L8_2` | `distance` | local | `#(a - b)` is the distance between two vectors |
| 96 | `L9_2` | `drawMarker` | local | holds `DrawMarker` |
| 97 | `L10_2` | `markerType` | local | passed as argument #1 (markerType) to `DrawMarker` |
| 100 | `L9_2` | `drawText3D` | local | holds `DrawText3D` |
| 101 | `L10_2` | `x` | local | holds field `.x` of another value |
| 103 | `L9_2` | `isControlJustReleased` | local | holds `IsControlJustReleased` |
| 104 | `L10_2` | `inputGroup` | local | passed as argument #1 (inputGroup) to `IsControlJustReleased` |
| 105 | `L9_2` | `released` | local | result of `IsControlJustReleased(...)` |
| 107 | `L9_2` | `triggerServerEvent` | local | holds `TriggerServerEvent` |
| 108 | `L10_2` | `eventName` | local | passed as argument #1 (eventName) to `TriggerServerEvent` |
| 114 | `L3_2` | `citizen` | local | holds `Citizen` |
| 115 | `L3_2` | `wait` | local | holds `Citizen.Wait` |
| 116 | `L4_2` | `waitTime2` | local | passed as argument #1 (waitTime) to `Citizen.Wait` |
| 121 | `L3_1` | `registerNetEvent` | local | holds `RegisterNetEvent` |
| 122 | `L4_1` | `eventName` | local | passed as argument #1 (eventName) to `RegisterNetEvent` |
| 124 | `L3_1` | `addEventHandler` | local | holds `AddEventHandler` |
| 125 | `L4_1` | `eventName` | local | passed as argument #1 (eventName) to `AddEventHandler` |
| 126 | `L5_1` | `onNotify` | local | callback registered with `AddEventHandler` for 'myshop:client:notify' |
| 126 | `A0_2` | `message` | parameter | copied into a temporary used as `message` |
| 128 | `L1_2` | `esx` | local | holds `ESX` |
| 129 | `L1_2` | `showNotification` | local | holds `ESX.ShowNotification` |
| 130 | `L2_2` | `message2` | local | passed as argument #1 (message) to `ESX.ShowNotification` |
| 134 | `L3_1` | `registerCommand` | local | holds `RegisterCommand` |
| 135 | `L4_1` | `commandName` | local | passed as argument #1 (commandName) to `RegisterCommand` |
| 136 | `L5_1` | `shopresetCommand` | local | callback registered with `RegisterCommand` for 'shopreset' |
| 136 | `A0_2` | `src` | parameter | parameter of a command callback (RegisterCommand) |
| 136 | `A1_2` | `args` | parameter | parameter of a command callback (RegisterCommand) |
| 136 | `A2_2` | `rawCommand` | parameter | parameter of a command callback (RegisterCommand) |
| 138 | `L3_2` | `value` | local | no usage information available |
| 140 | `L4_2` | `triggerServerEvent` | local | holds `TriggerServerEvent` |

## Verification

Passed: the output has the same structure as the original, and each of the 101 local-variable reads sees exactly the same definitions as before.
The output also compiles with Lua 5.4.

## De-obfuscated code

```lua
-- ======================================================================
-- De-obfuscated with lua_deobf (variable names inferred from usage).
-- Script side : client (guessed from the natives/APIs it uses)
-- Framework   : ESX
-- Handles     : 'esx:playerLoaded', 'esx:setJob', 'myshop:client:notify'
-- To server   : 'myshop:server:openShop', 'myshop:server:reset'
-- Local events: 'esx:getSharedObject'
-- Commands    : /shopreset
-- Threads     : 2
-- Globals     : DrawText3D
-- Renamed     : 44 obfuscated variables -> 102 named values
-- ======================================================================

local value, playerData, isPlayerLoaded, citizen, threadFunc, onPlayerLoaded
value = nil
playerData = {}
isPlayerLoaded = false

-- Start a new thread (coroutine)
--   -> triggers 'esx:getSharedObject'
citizen = Citizen
local createThread = citizen.CreateThread
function threadFunc()
    local esx, eventName, callback

    -- Main loop: runs every frame
    while true do
        esx = ESX
        if esx then
            break
        end

        -- Trigger local event 'esx:getSharedObject'
        local triggerEvent = TriggerEvent
        eventName = "esx:getSharedObject"
        function callback(obj)
            ESX = obj
        end

        triggerEvent(eventName, callback)
        local citizen = Citizen
        local wait = citizen.Wait
        local waitTime = 0
        wait(waitTime)
    end
end

createThread(threadFunc)

-- drawText3D(x, y, z, text)
--   -> uses SetTextScale, SetTextFont, SetTextEntry, AddTextComponentString, SetDrawOrigin, DrawText (+1 more)
local function drawText3D(x, y, z, text)
    local setTextScale, scaleX, scaleY, z2, p3, value, value2
    setTextScale = SetTextScale
    scaleX = 0.35
    scaleY = 0.35
    setTextScale(scaleX, scaleY)
    local setTextFont = SetTextFont
    local fontId = 4
    setTextFont(fontId)
    local setTextEntry = SetTextEntry
    local textEntry = "STRING"
    setTextEntry(textEntry)
    local addTextComponentString = AddTextComponentString
    local text2 = text
    addTextComponentString(text2)
    local setDrawOrigin = SetDrawOrigin
    local x2 = x
    local y2 = y
    z2 = z
    p3 = 0
    setDrawOrigin(x2, y2, z2, p3)

    -- Draw text on screen
    local drawText = DrawText
    local screenX = 0.0
    local screenY = 0.0
    drawText(screenX, screenY)
    local clearDrawOrigin = ClearDrawOrigin
    clearDrawOrigin()
end

DrawText3D = drawText3D

-- Register network event 'esx:playerLoaded' (can be triggered remotely)
local registerNetEvent = RegisterNetEvent
local eventName = "esx:playerLoaded"
registerNetEvent(eventName)

-- Handle event 'esx:playerLoaded'
local addEventHandler = AddEventHandler
eventName = "esx:playerLoaded"
function onPlayerLoaded(playerData2)
    playerData = playerData2
    isPlayerLoaded = true
end

addEventHandler(eventName, onPlayerLoaded)

-- Register network event 'esx:setJob' (can be triggered remotely)
registerNetEvent = RegisterNetEvent
eventName = "esx:setJob"
registerNetEvent(eventName)

-- Handle event 'esx:setJob'
addEventHandler = AddEventHandler
eventName = "esx:setJob"
local function onSetJob(job)
    playerData.job = job
end

addEventHandler(eventName, onSetJob)

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
        local pairsFn = pairs
        config = Config
        local shops = config.Shops
        local iterator, state
        iterator, state, initial = pairsFn(shops)
        for key, shop in iterator, state, initial do
            -- If within 10.0 units
            coords = shop.coords
            local offset = coords2 - coords
            local distance = #offset
            if distance < 10.0 then
                waitTime = 0

                -- Draw marker (type 2)
                drawMarker = DrawMarker
                markerType = 2
                drawMarker(markerType, shop.coords.x, shop.coords.y, shop.coords.z, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.3, 0.3, 0.3, 255, 255, 0, 200, false, true, 2, false, nil, nil, false)

                -- If within 1.5 units
                if distance < 1.5 then
                    local drawText3D = DrawText3D
                    local x = shop.coords.x
                    drawText3D(x, shop.coords.y, shop.coords.z, "Press ~g~E~s~ to open the shop")

                    -- If key E (control 38) was just released
                    local isControlJustReleased = IsControlJustReleased
                    local inputGroup = 0
                    local released = isControlJustReleased(inputGroup, 38)
                    if released then
                        -- Send event 'myshop:server:openShop' to the server
                        local triggerServerEvent = TriggerServerEvent
                        local eventName = "myshop:server:openShop"
                        triggerServerEvent(eventName, key)
                    end
                end
            end
        end

        local citizen = Citizen
        local wait = citizen.Wait
        local waitTime2 = waitTime
        wait(waitTime2)
    end
end

createThread(threadFunc)

-- Register network event 'myshop:client:notify' (can be triggered remotely)
registerNetEvent = RegisterNetEvent
eventName = "myshop:client:notify"
registerNetEvent(eventName)

-- Handle event 'myshop:client:notify'
--   -> uses ESX.ShowNotification
addEventHandler = AddEventHandler
eventName = "myshop:client:notify"
local function onNotify(message)
    -- Show a notification
    local esx, message2
    esx = ESX
    local showNotification = esx.ShowNotification
    message2 = message
    showNotification(message2)
end

addEventHandler(eventName, onNotify)

-- Register chat command /shopreset
--   -> triggers 'myshop:server:reset'
local registerCommand = RegisterCommand
local commandName = "shopreset"
local function shopresetCommand(src, args, rawCommand)
    local value, triggerServerEvent
    value = args[1]
    if value then
        -- Send event 'myshop:server:reset' to the server
        triggerServerEvent = TriggerServerEvent
        triggerServerEvent("myshop:server:reset", value)
    end
end

registerCommand(commandName, shopresetCommand, false)
```
