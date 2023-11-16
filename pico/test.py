import time
from machine import Pin, PWM, SoftI2C
import mcp7940

# setup led
led = Pin("LED", Pin.OUT)

# setup switches
switches = [
    Pin(26, Pin.IN, Pin.PULL_UP),
    Pin(27, Pin.IN, Pin.PULL_UP),
    Pin(28, Pin.IN, Pin.PULL_UP),
]
switch_states = [1, 1, 1]

# setup boost converter control
boost = PWM(Pin(17, Pin.OUT), freq=625000, duty_u16=int(0.6 * 65535))  # 60 - 76 %

# setup rtc
i2c = SoftI2C(sda=Pin(21), scl=Pin(20))
mcp = mcp7940.MCP7940(i2c)

print(mcp.time)
mcp.start()

led.off()

try:
    while True:
        print(mcp.time)
        time.sleep_ms(1000)
except KeyboardInterrupt:
    print("exiting...")
    raise SystemExit
