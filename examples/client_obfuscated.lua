local L0_1, L1_1, L2_1, L3_1, L4_1, L5_1
L0_1 = nil
L1_1 = {}
L2_1 = false
L3_1 = Citizen
L3_1 = L3_1.CreateThread
function L4_1()
  local L0_2, L1_2, L2_2
  while true do
    L0_2 = ESX
    if L0_2 then
      break
    end
    L0_2 = TriggerEvent
    L1_2 = "esx:getSharedObject"
    function L2_2(A0_3)
      ESX = A0_3
    end
    L0_2(L1_2, L2_2)
    L0_2 = Citizen
    L0_2 = L0_2.Wait
    L1_2 = 0
    L0_2(L1_2)
  end
end
L3_1(L4_1)
function L3_1(A0_2, A1_2, A2_2, A3_2)
  local L4_2, L5_2, L6_2, L7_2, L8_2, L9_2, L10_2
  L4_2 = SetTextScale
  L5_2 = 0.35
  L6_2 = 0.35
  L4_2(L5_2, L6_2)
  L4_2 = SetTextFont
  L5_2 = 4
  L4_2(L5_2)
  L4_2 = SetTextEntry
  L5_2 = "STRING"
  L4_2(L5_2)
  L4_2 = AddTextComponentString
  L5_2 = A3_2
  L4_2(L5_2)
  L4_2 = SetDrawOrigin
  L5_2 = A0_2
  L6_2 = A1_2
  L7_2 = A2_2
  L8_2 = 0
  L4_2(L5_2, L6_2, L7_2, L8_2)
  L4_2 = DrawText
  L5_2 = 0.0
  L6_2 = 0.0
  L4_2(L5_2, L6_2)
  L4_2 = ClearDrawOrigin
  L4_2()
end
DrawText3D = L3_1
L3_1 = RegisterNetEvent
L4_1 = "esx:playerLoaded"
L3_1(L4_1)
L3_1 = AddEventHandler
L4_1 = "esx:playerLoaded"
function L5_1(A0_2)
  L1_1 = A0_2
  L2_1 = true
end
L3_1(L4_1, L5_1)
L3_1 = RegisterNetEvent
L4_1 = "esx:setJob"
L3_1(L4_1)
L3_1 = AddEventHandler
L4_1 = "esx:setJob"
function L5_1(A0_2)
  L1_1.job = A0_2
end
L3_1(L4_1, L5_1)
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
    L3_2 = pairs
    L4_2 = Config
    L4_2 = L4_2.Shops
    L3_2, L4_2, L5_2 = L3_2(L4_2)
    for L6_2, L7_2 in L3_2, L4_2, L5_2 do
      L8_2 = L7_2.coords
      L8_2 = L2_2 - L8_2
      L8_2 = #L8_2
      if L8_2 < 10.0 then
        L0_2 = 0
        L9_2 = DrawMarker
        L10_2 = 2
        L9_2(L10_2, L7_2.coords.x, L7_2.coords.y, L7_2.coords.z, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.3, 0.3, 0.3, 255, 255, 0, 200, false, true, 2, false, nil, nil, false)
        if L8_2 < 1.5 then
          L9_2 = DrawText3D
          L10_2 = L7_2.coords.x
          L9_2(L10_2, L7_2.coords.y, L7_2.coords.z, "Press ~g~E~s~ to open the shop")
          L9_2 = IsControlJustReleased
          L10_2 = 0
          L9_2 = L9_2(L10_2, 38)
          if L9_2 then
            L9_2 = TriggerServerEvent
            L10_2 = "myshop:server:openShop"
            L9_2(L10_2, L6_2)
          end
        end
      end
    end
    L3_2 = Citizen
    L3_2 = L3_2.Wait
    L4_2 = L0_2
    L3_2(L4_2)
  end
end
L3_1(L4_1)
L3_1 = RegisterNetEvent
L4_1 = "myshop:client:notify"
L3_1(L4_1)
L3_1 = AddEventHandler
L4_1 = "myshop:client:notify"
function L5_1(A0_2)
  local L1_2, L2_2
  L1_2 = ESX
  L1_2 = L1_2.ShowNotification
  L2_2 = A0_2
  L1_2(L2_2)
end
L3_1(L4_1, L5_1)
L3_1 = RegisterCommand
L4_1 = "shopreset"
function L5_1(A0_2, A1_2, A2_2)
  local L3_2, L4_2
  L3_2 = A1_2[1]
  if L3_2 then
    L4_2 = TriggerServerEvent
    L4_2("myshop:server:reset", L3_2)
  end
end
L3_1(L4_1, L5_1, false)
