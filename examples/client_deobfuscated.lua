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
