import sys

sys.stdout.reconfigure(encoding="utf-8")

LUAU_TEMPLATE = r"""
-- if junkie, just execute the keysystem ui, get a key, and paste it, then execute it fully.
local OUT_STRINGS = "luraph_strings_dump.txt"
local OUT_PROTOS  = "luraph_chunks_dump.tsv"
local POLL_TRIES, POLL_GAP = 25, 3
local SLICE = 2500

local warn = warn or print
local getgc = getgc or get_gc_objects or (debug and debug.getgc)
local writefile = writefile or write_file
if not getgc or not writefile then warn("[dump] need getgc + writefile"); return end

pcall(function()
    local genv = (getgenv and getgenv()) or _G
    genv.SCRIPT_KEY = SCRIPT_KEY
    genv.script_key = SCRIPT_KEY
end)

local function fromhex(h) return (h:gsub("..", function(c) return string.char(tonumber(c, 16)) end)) end
local SRC = fromhex(_LPH_SRC)
local function spawn(fn) if task and task.spawn then return task.spawn(fn) else coroutine.resume(coroutine.create(fn)) end end
local function wait_(t) if task and task.wait then return task.wait(t) elseif wait then return wait(t) end end

spawn(function()
    local f, err = loadstring(SRC, "=luraph")
    if not f then warn("[dump] loadstring failed: " .. tostring(err)); return end
    local ok, e = pcall(f)
    warn("[dump] script returned ok=" .. tostring(ok) .. " " .. tostring(e))
end)

local function vAL(v)
    local k = type(v)
    if k == "string" then return "str:" .. (v:gsub(".", function(ch) return string.format("%02x", string.byte(ch)) end))
    elseif k == "number" then return "num:" .. tostring(v)
    elseif k == "boolean" then return "bool:" .. tostring(v)
    elseif k == "nil" then return "nil:"
    elseif k == "table" then return "table:" end
    return k .. ":"
end
local function numlist(v) return type(v) == "table" and type(rawget(v, 1)) == "number" end
local function isProtoAt(t, cf)
    if type(t) ~= "table" or not numlist(rawget(t, cf)) then return false end
    local a = 0
    for f = 1, 11 do if f ~= cf and type(rawget(t, f)) == "table" then a = a + 1 end end
    return a >= 3
end
local function readable(s)
    local n = #s; if n < 3 or n > 200 then return false end
    local p = 0; for i = 1, n do local b = string.byte(s, i); if b >= 32 and b < 127 then p = p + 1 end end
    return p / n >= 0.85
end

local function dump_now(objs)
    local votes = { [3] = 0, [4] = 0 }
    local n = 0
    for _, o in pairs(objs) do
        n = n + 1
        if isProtoAt(o, 3) then votes[3] = votes[3] + 1 end
        if isProtoAt(o, 4) then votes[4] = votes[4] + 1 end
        if n % SLICE == 0 then wait_() end
    end
    local CF = (votes[4] > votes[3]) and 4 or 3
    if votes[CF] == 0 then return false, votes end
    local function isProto(t) return isProtoAt(t, CF) end

    local protos, pseen, strs, sseen = {}, {}, {}, {}
    local function addstr(s) if type(s) == "string" and readable(s) and not sseen[s] then sseen[s] = true; strs[#strs + 1] = s end end
    n = 0
    for _, o in pairs(objs) do
        n = n + 1
        local t = type(o)
        if t == "string" then addstr(o)
        elseif t == "table" then
            if isProto(o) and not pseen[o] then pseen[o] = true; protos[#protos + 1] = o end
            pcall(function() for k, v in pairs(o) do if type(k) == "string" then addstr(k) end; if type(v) == "string" then addstr(v) end end end)
        end
        if n % SLICE == 0 then wait_() end
    end

    table.sort(strs)
    writefile(OUT_STRINGS, table.concat(strs, "\n"))

    local index = {}; for i, S in ipairs(protos) do index[S] = i end
    local function tarr(S, k) local v = rawget(S, k); return type(v) == "table" and v or {} end
    local FIELDS = {}; for f = 1, 11 do if f ~= CF then FIELDS[#FIELDS + 1] = f end end
    local out = { "CODEFIELD\t" .. CF, "ROOTS\t" .. #protos }
    for i = 1, #protos do out[#out + 1] = "ROOT\t" .. i .. "\t" .. i end
    for id = 1, #protos do
        local S = protos[id]
        local ok = pcall(function()
            local code = tarr(S, CF)
            out[#out + 1] = "PROTO\t" .. id .. "\t" .. #code .. "\t" .. tostring(rawget(S, 2))
            for i = 1, #code do
                local row = { "I", i, tostring(code[i]) }; local refs = {}
                for _, f in ipairs(FIELDS) do
                    local v = tarr(S, f)[i]; row[#row + 1] = "f" .. f .. "=" .. vAL(v)
                    if isProto(v) then refs[#refs + 1] = tostring(index[v] or "?") end
                end
                row[#row + 1] = table.concat(refs, ","); out[#out + 1] = table.concat(row, "\t")
            end
            out[#out + 1] = "ENDPROTO"
        end)
        if not ok then out[#out + 1] = "PROTO\t" .. id .. "\t0\t?"; out[#out + 1] = "ENDPROTO" end
        if id % 50 == 0 then wait_() end
    end
    writefile(OUT_PROTOS, table.concat(out, "\n"))
    warn(string.format("[dump] DONE: %d protos, %d strings (code-field [%d]) -> %s + %s",
        #protos, #strs, CF, OUT_PROTOS, OUT_STRINGS))
    return true, votes
end

spawn(function()
    for attempt = 1, POLL_TRIES do
        wait_(POLL_GAP)
        local objs = getgc(true)
        if type(objs) ~= "table" then objs = getgc() end
        if type(objs) == "table" then
            local ok, votes = dump_now(objs)
            warn(string.format("[dump] poll %d/%d  protos[3]=%d [4]=%d", attempt, POLL_TRIES, votes[3], votes[4]))
            if ok then return end
        end
    end
    warn("[dump] no protos found")
end)
"""


def build(src_path, out_path, key):
    src = open(src_path, "rb").read()
    luau = LUAU_TEMPLATE.replace("%SCRIPT_KEY%", key or "__PUT_YOUR_KEY_HERE__")
    full = 'local _LPH_SRC = "' + src.hex() + '"\n' + luau
    open(out_path, "w", encoding="utf-8").write(full)
    print("[*] source: {0} ({1} bytes)".format(src_path, len(src)))
    print("[*] wrote {0} ({1} KB)".format(out_path, len(full) // 1024))
    if not key:
        print("[*] edit the SCRIPT_KEY line in {0}, or pass it as arg 3".format(out_path))
    print("[*] run {0} in your executor".format(out_path))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python make_dump.py <script>.lua [out.luau] [SCRIPT_KEY]")
        sys.exit(1)
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "dump.luau"
    key = sys.argv[3] if len(sys.argv) > 3 else None
    build(src, out, key)
