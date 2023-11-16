import time
from machine import Pin


class Debouncer:
    def __init__(self, pin, delay_ms=50):
        self._pin = pin
        self._delay_ms = delay_ms
        self._state = self._pin.value()
        self._last_change = time.ticks_ms()

    def set_delay_ms(self, delay_ms):
        self._delay_ms = delay_ms

    def update(self):
        if self._pin.value() != self._state:
            self._last_change = time.ticks_ms()

    def value(self):
        return self._state
