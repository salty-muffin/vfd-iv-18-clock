import time
from machine import Pin


class Debouncer:
    def __init__(self, pin, delay_ms=50):
        self._pin = pin
        self._delay_ms = delay_ms
        self._state = self._pin.value()
        self._last_change = 0
        self._changed = False

    def set_delay_ms(self, delay_ms):
        self._delay_ms = delay_ms

    def update(self):
        value = self._pin.value()
        if value != self._state:
            if not self._changed:
                self._last_change = time.ticks_ms()
                self._changed = True
            elif time.ticks_ms() - self._last_change > self._delay_ms:
                self._state = value
                self._changed = False
        elif self._changed:
            self._changed = False

    def value(self):
        return self._state
