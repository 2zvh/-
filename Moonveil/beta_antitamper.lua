local MARKER = "l_dmscXnKJjpMhNEzT"

local game, Enum, debug = game, Enum, debug
local pcall, type, find = pcall, type, string.find

local function probe(fn)
    local ok, err = pcall(fn)
    if type(err) ~= "string" then
        return false
    end
    local at = find(err, MARKER)
    return at ~= nil
end

local function integrity_check()
    if type(game) ~= "userdata" then return false end
    if type(Enum) ~= "userdata" then return false end

    for _ = 1, 7 do
        if not probe(function()
            error(MARKER)
        end) then
            return false
        end
    end

    return true
end

if not integrity_check() then
    return
end
