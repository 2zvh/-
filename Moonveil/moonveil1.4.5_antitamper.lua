local traceback = debug.traceback
local info      = debug.info
local find      = string.find
local sub       = string.sub
local gmatch    = string.gmatch

local MARKER = "EpDZQySBZuYEl"

local function integrity_check()
    local tb = traceback()

    local at = find(tb, MARKER)
    if not at then
        return false 
    end


    local reported = {}
    for n in gmatch(sub(tb, at), ":(%d*)\n") do
        reported[#reported + 1] = tonumber(n)
    end

    local actual = info(2, "l")


    if reported[1] ~= actual then
        return false
    end

    return true
end

if not integrity_check() then
    return print("ur detected boi.")
end
print("woohoo im safe!!!!")
