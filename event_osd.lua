local s = tonumber(mp.get_opt("slow_motion")) or 1
local outfile = mp.get_opt("outfile") or "__timestamps.txt"

local count = 0
local flash_text = nil
local flash_until = 0

local function update()
    local now = mp.get_time()
    local t = mp.get_property_number("time-pos", 0) / s

    local text = string.format(
        "{\\an7\\pos(15,15)\\fnMenlo\\fs10\\bord0\\shad0\\c&H3D6AFF&}%.6fs",
        t
    )

    if flash_text and now < flash_until then
        text = text .. string.format(
            "\\N{\\fs7}%s",
            flash_text
        )
    end

    mp.set_osd_ass(0, 0, text)
end

local function mark_cut()
    count = count + 1

    local clip = math.floor((count + 1) / 2)
    local label = count % 2 == 1 and ("START CLIP " .. clip) or ("STOP CLIP " .. clip)

    local t = mp.get_property_number("time-pos", 0) / s

    local f = io.open(outfile, "a")
    if f then
        f:write(string.format("%s %.6f\n", label, t))
        f:close()
    end

    flash_text = label
    flash_until = mp.get_time() + 1.0
    update()
end

local function screenshot_mark()
    mp.commandv("no-osd", "screenshot")

    flash_text = "SCREENSHOT"
    flash_until = mp.get_time() + 1.0
    update()
end

mp.add_key_binding("c", "mark_cut", mark_cut)
mp.add_key_binding("s", "screenshot_mark", screenshot_mark)
mp.add_periodic_timer(0.033, update)