from micropython import const
import time
from machine import Pin, Timer, PWM, SoftI2C, SPI
import mcp7940
from debouncer import Debouncer

# constants
TIME, DATE, OFF = const(0), const(1), const(2)

MAX6921 = {
    "D1": const(1 << 7),
    "D2": const(1 << 0),
    "D3": const(1 << 6),
    "D4": const(1 << 1),
    "D5": const(1 << 5),
    "D6": const(1 << 2),
    "D7": const(1 << 3),
    "D8": const(1 << 4),
    "D9": const(1 << 8),
    "A": const(1 << 9),
    "B": const(1 << 11),
    "C": const(1 << 14),
    "D": const(1 << 15),
    "E": const(1 << 13),
    "F": const(1 << 12),
    "G": const(1 << 10),
    "DP": const(1 << 16),
}
# setup timers
switch_timer = Timer()
mcp_timer = Timer()
display_timer = Timer()

# setup led
led = Pin("LED", Pin.OUT, value=0)

# setup filament
filament = Pin(18, Pin.OUT, value=0)

# setup switches
switches = [
    Debouncer(Pin(26, Pin.IN, Pin.PULL_UP), delay_ms=50),
    Debouncer(Pin(27, Pin.IN, Pin.PULL_UP), delay_ms=50),
    Debouncer(Pin(28, Pin.IN, Pin.PULL_UP), delay_ms=50),
]
switch_states = [1, 1, 1]

# setup boost converter control
boost = PWM(Pin(17, Pin.OUT), freq=625000, duty_u16=0)

# setup rtc
i2c = SoftI2C(sda=Pin(21), scl=Pin(20))
mcp = mcp7940.MCP7940(i2c)
mcp.start()

# setup MAX6921 shift register
shift = SPI(0, baudrate=1000000, sck=Pin(6), mosi=Pin(7), miso=Pin(4))
load = Pin(8, Pin.OUT, value=1)
blank = Pin(9, Pin.OUT)

# set time
mcp.time = time.localtime()

# global variables
clock_time = mcp.time
last_time = clock_time
mode = TIME
digit = 0  # 0 - 8
digit_states = [0] * 9
brightness = 0.6  # 60 - 76 %


# functions
def set_display(d0, d1, d2, d3, d4, d5, d6, d7, d8):
    global brightness, boost, digit_states, filament

    # debug
    print(d8 + d7 + d6 + d5 + d4 + d3 + d2 + d1 + d0)

    # set each digit
    for index, digit in enumerate([d0, d1, d2, d3, d4, d5, d6, d7, d8]):
        segments = []
        if digit:
            if digit[0] == "-":
                segments = ["G"]
            elif digit[0] == "0":
                segments = ["A", "B", "C", "D", "E", "F"]
            elif digit[0] == "1":
                segments = ["B", "C"]
            elif digit[0] == "2":
                segments = ["A", "B", "D", "E", "G"]
            elif digit[0] == "3":
                segments = ["A", "B", "C", "D", "G"]
            elif digit[0] == "4":
                segments = ["B", "C", "F", "G"]
            elif digit[0] == "5":
                segments = ["A", "C", "D", "F", "G"]
            elif digit[0] == "6":
                segments = ["A", "C", "D", "E", "F", "G"]
            elif digit[0] == "7":
                segments = ["A", "B", "C"]
            elif digit[0] == "8":
                segments = ["A", "B", "C", "D", "E", "F", "G"]
            elif digit[0] == "9":
                segments = ["A", "B", "C", "D", "F", "G"]
            if "." in digit:
                segments.append("DP")

        digit_states[index] = MAX6921[f"D{index + 1}"]
        for segment in segments:
            digit_states[index] |= MAX6921[segment]

    # turn on boost converter & filament, if off
    boost.duty_u16(int(brightness * 65535))
    filament.on()

    # enable tube outputs, if off
    blank.off()


def turn_off_display():
    global boost, blank, filament
    # debug
    print("off")

    # turn off boost converter
    boost.duty_u16(0)

    # set all tube outputs low
    blank.on()

    # turn off filament
    filament.off()


def zfill(s, l):
    while len(s) < l:
        s = "0" + s
    return s


def time_to_display(datetime, d8=""):
    hour = zfill(str(datetime[3]), 2)
    minute = zfill(str(datetime[4]), 2)
    second = zfill(str(datetime[5]), 2)
    return (second[1], second[0], "-", minute[1], minute[0], "-", hour[1], hour[0], d8)


def date_to_display(datetime, d8=""):
    year = zfill(str(datetime[0]), 4)
    month = zfill(str(datetime[1]), 2)
    date = zfill(str(datetime[2]), 2)
    return (
        year[3],
        year[2],
        year[1],
        year[0],
        month[1] + ".",
        month[0],
        date[1] + ".",
        date[0],
        d8,
    )


# define timed executions
def check_time(_):
    global mcp, clock_time, last_time
    clock_time = mcp.time


def update_display(_):
    global load, shift, digit, digit_states

    # send out data to the vfd controller
    load.off()
    shift.write(digit_states[digit].to_bytes(3, "big"))
    load.on()
    digit += 1

    # iterate through digits
    if digit >= len(digit_states):
        digit = 0


def update_switches(_):
    global switches
    for switch in switches:
        switch.update()


# setup times executions
mcp_timer.init(period=10, mode=Timer.PERIODIC, callback=check_time)
switch_timer.init(period=1, mode=Timer.PERIODIC, callback=update_switches)
# display_timer.init(period=10, mode=Timer.PERIODIC, callback=update_display)

try:
    boost.duty_u16(int(brightness * 65535))
    # main loop
    while True:
        set_display(*date_to_display(clock_time))
        time.sleep(1)

        load.off()
        shift.write(digit_states[0].to_bytes(3, "big"))
        load.on()

        time.sleep(1000)


except KeyboardInterrupt:
    print("exiting...")

    boost.duty_u16(0)

    switch_timer.deinit()
    mcp_timer.deinit()
    # display_timer.deinit()

    raise SystemExit

except Exception as ex:
    boost.duty_u16(0)

    switch_timer.deinit()
    mcp_timer.deinit()
    # display_timer.deinit()

    raise ex
