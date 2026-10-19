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
