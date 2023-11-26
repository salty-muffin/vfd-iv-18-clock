from micropython import const
import os
import time
import _thread as thread
import machine
from machine import Pin, PWM, I2C, SPI
from mcp7940 import MCP7940
from debouncer import Debouncer

# set overclock frequency
machine.freq(270000000)

# constants
OFF, TIME, DATE, SET_HOUR, SET_MINUTE, SET_DAY, SET_MONTH, SET_YEAR, SET_BRIGHTNESS = (
    const(0),
    const(1),
    const(2),
    const(3),
    const(4),
    const(5),
    const(6),
    const(7),
    const(8),
)

TIME_CHECK_FREQUENCY = const(50)
SWITCH_CHECK_FREQUENCY = const(100)
DISPLAY_FREQUENCY = const(600)

MIN_BRIGHTNESS = 0.5
MAX_BRIGHTNESS = 0.75

TIME_CHECK_INTERVAL = 1 / TIME_CHECK_FREQUENCY * 1000000
SWITCH_CHECK_INTERVAL = 1 / SWITCH_CHECK_FREQUENCY * 1000000
DISPLAY_INTERVAL = 1 / DISPLAY_FREQUENCY * 1000000

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
    "P": const(1 << 16),
}

CHARACTERS = {
    "-": const("G"),
    "0": const("ABCDEF"),
    "1": const("BC"),
    "2": const("ABDEG"),
    "3": const("ABCDG"),
    "4": const("BCFG"),
    "5": const("ACDFG"),
    "6": const("ACDEFG"),
    "7": const("ABC"),
    "8": const("ABCDEFG"),
    "9": const("ABCDFG"),
    ".": const("P"),
}

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
i2c = I2C(0, sda=Pin(20), scl=Pin(21), freq=2000000)
mcp = MCP7940(i2c)
# mcp.time = time.localtime()
mcp.start()
print(mcp.is_battery_backup_enabled())
mcp.battery_backup_enable(1)

# setup MAX6921 shift register
shift = SPI(0, baudrate=1000000, sck=Pin(6), mosi=Pin(7), miso=Pin(4))
load = Pin(8, Pin.OUT, value=1)
blank = Pin(9, Pin.OUT, value=1)


# functions
def set_display(d0, d1, d2, d3, d4, d5, d6, d7, d8):
    global digit_states

    # set each digit
    lock.acquire()
    for index, digit in enumerate([d0, d1, d2, d3, d4, d5, d6, d7, d8]):
        digit_states[index] = MAX6921[f"D{index + 1}"]
        for character in digit:
            for segment in CHARACTERS[character]:
                digit_states[index] |= MAX6921[segment]
    lock.release()

    # turn on boost converter & filament, if off
    boost.duty_u16(int(brightness * 65535))
    filament.on()

    # enable tube outputs, if off
    blank.off()


def set_mode(m):
    global mode

    lock.acquire()
    mode = m
    lock.release()


def turn_off_display():
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
    hour = zfill(str(datetime[3]), 2) if datetime[3] is not None else "--"
    minute = zfill(str(datetime[4]), 2) if datetime[4] is not None else "--"
    second = zfill(str(datetime[5]), 2) if datetime[5] is not None else "--"
    return (second[1], second[0], "-", minute[1], minute[0], "-", hour[1], hour[0], d8)


def date_to_display(datetime, d8=""):
    year = zfill(str(datetime[0]), 4) if datetime[0] is not None else "----"
    month = zfill(str(datetime[1]), 2) if datetime[1] is not None else "--"
    date = zfill(str(datetime[2]), 2) if datetime[2] is not None else "--"
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


def validate_datetime(datetime):
    year = datetime[0]
    month = datetime[1]
    day = datetime[2]

    if (month < 8 and month % 2 == 0 or month >= 8 and month % 2 == 1) and day > 30:
        day = 30
    if MCP7940.is_leap_year(year):
        if day > 29:
            day = 29
    else:
        if day > 28:
            day = 28

    return (
        year,
        month,
        day,
        datetime[3],
        datetime[4],
        datetime[5],
        datetime[6],
        datetime[7],
    )


def update_display():
    global digit, last_display_update, last_mode, last_digit_states

    try:
        while True:
            current_ticks = time.ticks_us()

            if time.ticks_diff(current_ticks, last_display_update) > DISPLAY_INTERVAL:
                last_display_update = current_ticks

                if lock.acquire(0):
                    current_mode = mode
                    last_mode = mode

                    current_digit_states = digit_states
                    last_digit_states = digit_states

                    lock.release()
                else:
                    current_mode = last_mode
                    current_digit_states = last_digit_states

                if current_mode != OFF:
                    blank.on()
                    load.off()
                    shift.write(current_digit_states[digit].to_bytes(3, "big"))
                    load.on()
                    blank.off()
                    digit += 1

                    # iterate through digits
                    if digit >= len(current_digit_states):
                        digit = 0
    except:
        thread.exit()


# global variables
clock_time = mcp.time
last_time = clock_time
set_time = list(clock_time)

mode = TIME
last_mode = mode

digit = 0  # 0 - 8
digit_states = [0] * 9
last_digit_states = digit_states

brightness = 0.6  # 50 - 76 %
if "brightness.txt" in os.listdir():
    with open("brightness.txt") as file:
        brightness = float(file.read())
else:
    print("no brightness file was found. using default brightness of 0.6")

last_time_check = time.ticks_us()
last_switch_check = time.ticks_us()
last_display_update = time.ticks_us()

# create a global lock
lock = thread.allocate_lock()

# start display update thread
update_display_thread = thread.start_new_thread(update_display, ())

try:
    # set display to show time in the beginning
    set_display(*time_to_display(clock_time))

    # main loop
    while True:
        start_ticks_us = time.ticks_us()

        # get current ticks
        current_ticks = time.ticks_us()

        # update time & set display accordingly
        if time.ticks_diff(current_ticks, last_time_check) >= TIME_CHECK_INTERVAL:
            # debug
            last_time_check = current_ticks

            clock_time = mcp.time

            if clock_time != last_time:
                last_time = clock_time
                if mode == TIME:
                    set_display(*time_to_display(clock_time))
                elif mode == DATE:
                    set_display(*date_to_display(clock_time))

        # update debounced switches
        if time.ticks_diff(current_ticks, last_switch_check) >= SWITCH_CHECK_INTERVAL:
            last_switch_check = current_ticks

            for switch in switches:
                switch.update()

            # mode selector
            values = [switches[i].value() for i in range(3)]

            # switch 1 (high)
            if not values[0] and switch_states[0]:
                # set time / date / brighness
                if mode == TIME or mode == DATE:
                    set_mode(SET_HOUR)
                    set_time = list(clock_time)
                    set_time[5] = 0
                    set_display(
                        *time_to_display((None, None, None, set_time[3], None, 0), ".")
                    )
                elif mode == SET_HOUR:
                    set_mode(SET_MINUTE)
                    set_display(
                        *time_to_display((None, None, None, None, set_time[4], 0), ".")
                    )
                elif mode == SET_MINUTE:
                    set_mode(SET_DAY)
                    clock_time = tuple(set_time)
                    mcp.time = clock_time
                    last_time = clock_time
                    mcp.start()
                    set_display(
                        *date_to_display(
                            (None, None, set_time[2], None, None, None), "."
                        )
                    )
                elif mode == SET_DAY:
                    set_mode(SET_MONTH)
                    set_display(
                        *date_to_display(
                            (None, set_time[1], None, None, None, None), "."
                        )
                    )
                elif mode == SET_MONTH:
                    set_mode(SET_YEAR)
                    set_display(
                        *date_to_display(
                            (set_time[0], None, None, None, None, None), "."
                        )
                    )
                elif mode == SET_YEAR:
                    set_mode(SET_BRIGHTNESS)
                    set_display(
                        *time_to_display(
                            (None, None, None, None, None, int(brightness * 100)), "."
                        )
                    )
                elif mode == SET_BRIGHTNESS:
                    set_mode(TIME)
                    set_time[3:6] = clock_time[3:6]
                    clock_time = validate_datetime(set_time)
                    mcp.time = clock_time
                    last_time = clock_time
                    with open("brightness.txt", "w") as file:
                        file.write(str(brightness))
                    mcp.start()
                    set_display(*time_to_display(set_time))

            # switch 2 (middle)
            if not values[1] and switch_states[1]:
                # time / date
                if mode == TIME:
                    set_mode(DATE)
                    set_display(*date_to_display(clock_time))
                elif mode == DATE:
                    set_mode(TIME)
                    set_display(*time_to_display(clock_time))
                elif mode == SET_HOUR:
                    set_time[3] += 1
                    if set_time[3] > 23:
                        set_time[3] = 0
                    set_display(
                        *time_to_display((None, None, None, set_time[3], None, 0), ".")
                    )
                elif mode == SET_MINUTE:
                    set_time[4] += 1
                    if set_time[4] > 59:
                        set_time[4] = 0
                    set_display(
                        *time_to_display((None, None, None, None, set_time[4], 0), ".")
                    )
                elif mode == SET_DAY:
                    set_time[2] += 1
                    if set_time[2] > 31:
                        set_time[2] = 1
                    set_display(
                        *date_to_display(
                            (None, None, set_time[2], None, None, None), "."
                        )
                    )
                elif mode == SET_MONTH:
                    set_time[1] += 1
                    if set_time[1] > 12:
                        set_time[1] = 1
                    set_display(
                        *date_to_display(
                            (None, set_time[1], None, None, None, None), "."
                        )
                    )
                elif mode == SET_YEAR:
                    set_time[0] += 1
                    if set_time[0] > 2500:
                        set_time[0] = 2500
                    set_display(
                        *date_to_display(
                            (set_time[0], None, None, None, None, None), "."
                        )
                    )
                elif mode == SET_BRIGHTNESS:
                    brightness += 0.01
                    if brightness > MAX_BRIGHTNESS:
                        brightness = MAX_BRIGHTNESS
                    set_display(
                        *time_to_display(
                            (None, None, None, None, None, int(brightness * 100), ".")
                        )
                    )

            # switch 3 (low)
            if not values[2] and switch_states[2]:
                # on / off
                if mode == TIME or mode == DATE:
                    set_mode(OFF)
                    turn_off_display()
                elif mode == OFF:
                    set_mode(TIME)
                    set_display(*time_to_display(clock_time))
                elif mode == SET_HOUR:
                    set_time[3] -= 1
                    if set_time[3] < 0:
                        set_time[3] = 23
                    set_display(
                        *time_to_display((None, None, None, set_time[3], None, 0), ".")
                    )
                elif mode == SET_MINUTE:
                    set_time[4] -= 1
                    if set_time[4] < 0:
                        set_time[4] = 59
                    set_display(
                        *time_to_display((None, None, None, None, set_time[4], 0), ".")
                    )
                elif mode == SET_DAY:
                    set_time[2] -= 1
                    if set_time[2] < 1:
                        set_time[2] = 31
                    set_display(
                        *date_to_display(
                            (None, None, set_time[2], None, None, None), "."
                        )
                    )
                elif mode == SET_MONTH:
                    set_time[1] -= 1
                    if set_time[1] < 1:
                        set_time[1] = 12
                    set_display(
                        *date_to_display(
                            (None, set_time[1], None, None, None, None), "."
                        )
                    )
                elif mode == SET_YEAR:
                    set_time[0] -= 1
                    if set_time[0] < 1972:
                        set_time[0] = 1972
                    set_display(
                        *date_to_display(
                            (set_time[0], None, None, None, None, None), "."
                        )
                    )
                elif mode == SET_BRIGHTNESS:
                    brightness -= 0.01
                    if brightness < MIN_BRIGHTNESS:
                        brightness = MIN_BRIGHTNESS
                    set_display(
                        *time_to_display(
                            (None, None, None, None, None, int(brightness * 100), ".")
                        )
                    )

            # set switch states (so they only trigger once per press)
            for i in range(3):
                switch_states[i] = values[i]


except (KeyboardInterrupt, SystemExit):
    print("exiting...")

    boost.duty_u16(0)

    filament.off()

except Exception as ex:
    boost.duty_u16(0)

    filament.off()

    raise ex
