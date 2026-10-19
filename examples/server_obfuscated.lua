local L0_1, L1_1, L2_1, L3_1, L4_1, L5_1
L0_1 = nil
L1_1 = TriggerEvent
L2_1 = "esx:getSharedObject"
function L3_1(A0_2)
  L0_1 = A0_2
end
L1_1(L2_1, L3_1)
L1_1 = {}
function L2_1(A0_2, A1_2)
  local L2_2, L3_2, L4_2
  L2_2 = print
  L3_2 = "[myshop] "
  L4_2 = A0_2
  L3_2 = L3_2 .. L4_2 .. " -> " .. A1_2
  L2_2(L3_2)
end
L3_1 = RegisterServerEvent
L4_1 = "myshop:server:openShop"
L3_1(L4_1)
L3_1 = AddEventHandler
L4_1 = "myshop:server:openShop"
function L5_1(A0_2)
  local L1_2, L2_2, L3_2, L4_2, L5_2, L6_2
  L1_2 = source
  L2_2 = L0_1.GetPlayerFromId
  L3_2 = L1_2
  L2_2 = L2_2(L3_2)
  if not L2_2 then
    return
  end
  L3_2 = Config
  L3_2 = L3_2.Shops
  L3_2 = L3_2[A0_2]
  if not L3_2 then
    L4_2 = L2_1
    L5_2 = L1_2
    L6_2 = "tried to open unknown shop"
    L4_2(L5_2, L6_2)
    return
  end
  L4_2 = L2_2.getMoney
  L4_2 = L4_2()
  L5_2 = L1_1
  L5_2[L1_2] = A0_2
  L5_2 = TriggerClientEvent
  L6_2 = "myshop:client:notify"
  L5_2(L6_2, L1_2, "Welcome! You have $" .. L4_2)
end
L3_1(L4_1, L5_1)
L3_1 = L0_1.RegisterServerCallback
L4_1 = "myshop:buyItem"
function L5_1(A0_2, A1_2, A2_2, A3_2)
  local L4_2, L5_2, L6_2, L7_2, L8_2
  L4_2 = L0_1.GetPlayerFromId
  L5_2 = A0_2
  L4_2 = L4_2(L5_2)
  L5_2 = 10
  L6_2 = A3_2
  L5_2 = L5_2 * L6_2
  L6_2 = L4_2.getMoney
  L6_2 = L6_2()
  if L5_2 <= L6_2 then
    L7_2 = L4_2.removeMoney
    L8_2 = L5_2
    L7_2(L8_2)
    L7_2 = L4_2.addInventoryItem
    L8_2 = A2_2
    L7_2(L8_2, A3_2)
    L7_2 = A1_2
    L8_2 = true
    L7_2(L8_2)
  else
    L7_2 = A1_2
    L8_2 = false
    L7_2(L8_2)
  end
end
L3_1(L4_1, L5_1)
L3_1 = L0_1.RegisterUsableItem
L4_1 = "shop_voucher"
function L5_1(A0_2)
  local L1_2, L2_2
  L1_2 = L0_1.GetPlayerFromId
  L2_2 = A0_2
  L1_2 = L1_2(L2_2)
  L2_2 = L1_2.removeInventoryItem
  L2_2("shop_voucher", 1)
  L2_2 = L1_2.addMoney
  L2_2(500)
end
L3_1(L4_1, L5_1)
L3_1 = AddEventHandler
L4_1 = "playerDropped"
function L5_1(A0_2)
  local L1_2, L2_2
  L1_2 = source
  L2_2 = L1_1
  L2_2[L1_2] = nil
  L2_2 = L2_1
  L2_2(L1_2, "left: " .. A0_2)
end
L3_1(L4_1, L5_1)
L3_1 = RegisterCommand
L4_1 = "shopreset"
function L5_1(A0_2, A1_2, A2_2)
  local L3_2, L4_2, L5_2, L6_2, L7_2
  L3_2 = tonumber
  L4_2 = A1_2[1]
  L3_2 = L3_2(L4_2)
  if L3_2 then
    L4_2 = L1_1
    L4_2[L3_2] = nil
  else
    L4_2 = pairs
    L5_2 = L1_1
    L4_2, L5_2, L6_2 = L4_2(L5_2)
    for L7_2 in L4_2, L5_2, L6_2 do
      L1_1[L7_2] = nil
    end
  end
  L4_2 = L2_1
  L5_2 = A0_2
  L6_2 = "reset shops"
  L4_2(L5_2, L6_2)
end
L3_1(L4_1, L5_1, true)
