import time
from machine import Pin, Timer, PWM, SoftI2C
import mcp7940
from debouncer import Debouncer

# constants
TIME, DATE, OFF = 0, 1, 2

# setup timers
switch_timer = Timer()
mcp_timer = Timer()

# setup led
led = Pin("LED", Pin.OUT)

# setup switches
switches = [
    Debouncer(Pin(26, Pin.IN, Pin.PULL_UP), delay_ms=50),
    Debouncer(Pin(27, Pin.IN, Pin.PULL_UP), delay_ms=50),
    Debouncer(Pin(28, Pin.IN, Pin.PULL_UP), delay_ms=50),
]
switch_states = [1, 1, 1]

# setup boost converter control
boost = PWM(Pin(17, Pin.OUT), freq=625000, duty_u16=int(0.6 * 65535))  # 60 - 76 %

# setup rtc
i2c = SoftI2C(sda=Pin(21), scl=Pin(20))
mcp = mcp7940.MCP7940(i2c)

mcp.start()

# set led
led.off()


# functions
def update_display(c0, c1, c2, c3, c4, c5, c6, c7, c8, c9):
    print(c0 + c1 + c2 + c3 + c4 + c5 + c6 + c7 + c8 + c9)


def turn_off_display():
    pass


def zfill(s, l):
    while len(s) < l:
        s = "0" + s
    return s


def time_to_display(datetime, c0=""):
    hour = zfill(str(datetime[3]), 2)
    minute = zfill(str(datetime[4]), 2)
    second = zfill(str(datetime[5]), 2)
    return (
        c0,
        "",
        hour[0],
        hour[1],
        "-",
        minute[0],
        minute[1],
        "-",
        second[0],
        second[1],
    )


def date_to_display(datetime, c0=""):
    year = zfill(str(datetime[0]), 4)
    month = zfill(str(datetime[1]), 2)
    date = zfill(str(datetime[1]), 2)
    return (
        c0,
        "",
        year[0],
        year[1],
        year[2],
        year[3] + ".",
        month[0],
        month[1] + ".",
        date[0],
        date[1],
    )


# global variables
clock_time = mcp.time
last_time = clock_time
mode = TIME


try:
    # define timed executions
    def update_switches(_):
        global switches
        for switch in switches:
            switch.update()

    def check_time(_):
        global mcp, clock_time, last_time
        clock_time = mcp.time

    switch_timer.init(period=1, mode=Timer.PERIODIC, callback=update_switches)
    mcp_timer.init(period=10, mode=Timer.PERIODIC, callback=check_time)

    # main loop
    while True:
        # mode selector
        values = [switches[i].value() for i in range(3)]
        # switch 1
        if not values[1] and switch_states[1]:
            # time / date
            print("pressed switch 2")
            if mode == TIME:
                mode = DATE
                update_display(*date_to_display(clock_time))
            elif mode == DATE:
                mode = TIME
                update_display(*time_to_display(clock_time))

        # switch 2
        if not values[2] and switch_states[2]:
            # on / off
            print("pressed switch 3")
            if mode == TIME or mode == DATE:
                mode = OFF
                turn_off_display()
            elif mode == OFF:
                mode = TIME

        # set switch states (so they only trigger once per press)
        for i in range(3):
            switch_states[i] = values[i]

        # update display
        if clock_time != last_time:
            last_time = clock_time
            if mode == TIME:
                update_display(*time_to_display(clock_time))
            elif mode == DATE:
                update_display(*date_to_display(clock_time))


except KeyboardInterrupt:
    print("exiting...")
    switch_timer.deinit()
    mcp_timer.deinit()
    raise SystemExit
