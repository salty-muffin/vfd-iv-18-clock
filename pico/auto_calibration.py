from machine import Pin, I2C
from mcp7940 import MCP7940
import time

# setup led
led = Pin("LED", Pin.OUT, value=0)

# setup rtc
i2c = I2C(0, sda=Pin(20), scl=Pin(21), freq=2000000)
mcp = MCP7940(i2c)


def time_diff_seconds(datetime1, datetime2):
    # now = (2019, 7, 16, 15, 29, 14, 6, 167)  # Sunday 2019/7/16 3:29:14pm (yearday=167)
    # year, month, date, hours, minutes, seconds, weekday, yearday
    diff = [i - j for i, j in zip(datetime1[2:6], datetime2[2:6])]
    return diff[0] * 24 * 60 * 60 + diff[1] * 60 * 60 + diff[2] * 60 + diff[3]


def clamp(i, min, max):
    if i < min:
        return min
    if i > max:
        return max
    return i


trim = 0
resolution = 127

try:
    while True:
        # set the rtc time to computertime:
        mcp.stop()
        start_time = time.localtime()
        local_time = time.localtime()
        mcp.time = time.localtime()
        rtc_time = mcp.time

        # set trim
        mcp.set_trim(trim)

        last_time = local_time

        # start rtc
        mcp.start()

        local_sec = time_diff_seconds(local_time, start_time)
        rtc_sec = time_diff_seconds(rtc_time, start_time)
        print(
            f"START - sec local: {local_sec}, sec rtc: {rtc_sec}, delta (rtc_sec - local_sec): {rtc_sec - local_sec}, trim: {mcp.get_trim()}"
        )

        ppm = 0
        first = True
        offset = 0
        while ppm == 0:
            local_time = time.localtime()

            if time_diff_seconds(local_time, last_time) >= 60:
                last_time = local_time

                local_time = time.localtime()
                rtc_time = mcp.time

                local_sec = time_diff_seconds(local_time, start_time)
                rtc_sec = time_diff_seconds(rtc_time, start_time)
                if first:
                    offset = rtc_sec - local_sec
                    first = False

                ppm = (local_sec - rtc_sec + offset) / local_sec * 1000000
                trimval = ppm * (32768 * 60) / (1000000 * 2)
                print(
                    f"sec local: {local_sec}, sec rtc: {rtc_sec}, delta (rtc_sec - local_sec): {rtc_sec - local_sec}, ppm: {ppm}, trimval: {trimval}, offset: {offset}, trim: {trim}"
                )

            time.sleep_ms(1)

        trim += resolution if ppm > 0 else -resolution
        resolution = clamp(int(resolution / 2), 1, 127)
        if trim < -127 or trim > 127:
            led.on()
            trim = clamp(trim, -127, 127)


except KeyboardInterrupt:
    raise SystemExit
