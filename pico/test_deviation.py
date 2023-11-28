from machine import Pin, PWM, I2C, SPI
from mcp7940 import MCP7940
import time

FILENAME = "calibration.txt"

# setup rtc
i2c = I2C(0, sda=Pin(20), scl=Pin(21), freq=2000000)
mcp = MCP7940(i2c)


def time_diff_seconds(datetime1, datetime2):
    # now = (2019, 7, 16, 15, 29, 14, 6, 167)  # Sunday 2019/7/16 3:29:14pm (yearday=167)
    # year, month, date, hours, minutes, seconds, weekday, yearday
    diff = [i - j for i, j in zip(datetime1[2:6], datetime2[2:6])]
    return diff[0] * 24 * 60 * 60 + diff[1] * 60 * 60 + diff[2] * 60 + diff[3]


# set the rtc time to computertime:
start_time = time.localtime()
local_time = time.localtime()
mcp.time = time.localtime()
rtc_time = mcp.time
mcp.start()

last_time = local_time

local_sec = time_diff_seconds(local_time, start_time)
rtc_sec = time_diff_seconds(rtc_time, start_time)
printout = f"START - sec rtc: {local_sec}, sec local: {rtc_sec}, delta (rtc_sec - local_sec): {rtc_sec - local_sec}"
print(printout)
with open(FILENAME, "w") as file:
    file.write(f"{printout}\n")
try:
    while True:
        local_time = time.localtime()

        if time_diff_seconds(local_time, last_time) >= 60:
            last_time = local_time

            local_time = time.localtime()
            rtc_time = mcp.time

            local_sec = time_diff_seconds(local_time, start_time)
            rtc_sec = time_diff_seconds(rtc_time, start_time)
            ppm = (rtc_sec - local_sec) / local_sec * 1000000
            trimval = ppm * (32768 * 60) / (1000000 * 2)
            printout = f"sec rtc: {local_sec}, sec local: {rtc_sec}, delta (rtc_sec - local_sec): {rtc_sec - local_sec}, ppm: {ppm}, trimval: {trimval}"
            print(printout)
            with open(FILENAME, "a") as file:
                file.write(f"{printout}\n")

        time.sleep_ms(1)
except KeyboardInterrupt:
    raise SystemExit
