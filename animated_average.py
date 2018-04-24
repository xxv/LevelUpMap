class AnimatedAverage(object):
    """Computes the average of the last N values, cross-fading between new results

    In order to create a smooth animation between computed averages, call
    tick() on a regular interval. The results from get() will cross-fade
    between the previously-computed average and the new average on each tick().
    Add a new value to the list with add()."""
    _values = []
    _previous = 0
    _average = 0
    _animation_speed = None
    _ticks_ago = 0

    def __init__(self, count=100, animation_speed=50):
        self._animation_speed = animation_speed
        self._count = count

    def add(self, new_value):
        """Add a new value; drop old values"""
        self._previous = self.get()
        self._values.append(new_value)
        self._average = self._compute_average()

        if len(self._values) > self._count:
            del(self._values[0])
        self._ticks_ago = 0

    def get(self):
        fade = 1.0-(float(self._animation_speed - self._ticks_ago) / self._animation_speed)
        value = (self._average - self._previous) * fade + self._previous

        return value

    def tick(self):
        self._ticks_ago = min(self._animation_speed, self._ticks_ago + 1)

    def _compute_average(self):
        if len(self._values) > 0:
            return sum(self._values)/len(self._values)
        else:
            return 0
