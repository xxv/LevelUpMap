from datetime import datetime, timedelta

import pygame

from animated_value import AnimatedAverage, AnimatedValue

class OrderTotals(object):
    _text_color = (0x55, 0x55, 0x55)

    def __init__(self):
        self._font_avg_spend = pygame.font.SysFont('Source Sans Pro', 30, bold=True)
        self._font_day_start_note = pygame.font.SysFont('Source Sans Pro', 25)
        self._avg_spend = AnimatedAverage(count=500)
        self._cum_order_spend_anim = AnimatedValue()
        self._order_count = 0
        self._cum_order_spend = 0
        self._day_start = datetime.now()

    def add(self, payload):
        spend = int(payload['spend_amount'])
        if spend:
            self._avg_spend.add(spend)
        self._maybe_reset_daily_totals()
        self._order_count += 1
        self._cum_order_spend += spend
        self._cum_order_spend_anim.set(self._cum_order_spend)

    def tick(self):
        self._avg_spend.tick()
        self._cum_order_spend_anim.tick()

    def to_snapshot(self):
        snapshot = {}
        snapshot['day_start'] = self._day_start.timestamp()
        snapshot['cumulative_order_spend'] = self._cum_order_spend
        snapshot['order_count'] = self._order_count

        return snapshot

    def load_snapshot(self, payload):
        self._day_start = datetime.fromtimestamp(payload['day_start'])
        self._cum_order_spend = payload['cumulative_order_spend']
        self._order_count = payload['order_count']


    def draw(self, surface, position):
        self._draw_text_stat(surface, position,
                             "Average Order Price: ${:0.02f}",
                             self._avg_spend.get()/100.0, 0)
        self._draw_text_stat(surface, position,
                             "Orders Today Total: ${:0,.02f}",
                             self._cum_order_spend_anim.get()/100.0, 1)
        self._draw_text_stat(surface, position,
                             "Orders Today: {:,}", self._order_count, 2)

        if self._day_start.hour != 0:
            surface.blit(self._font_day_start_note.render(
                "Order totals reset at {}".format(
                    self._day_start.strftime("%Y-%m-%d %H:%M:%S %Z")),
                True, self._text_color), (position[0], position[1] + 3.5 * 40))

    def _draw_text_stat(self, surface, position, text, value, index):
        surface.blit(self._font_avg_spend.render(text.format(value),
                                                 True, self._text_color),
                     (position[0], position[1] + index * 40))

    def _maybe_reset_daily_totals(self):
        now = datetime.now()
        if self._day_start.day != now.day:
            self._cum_order_spend = 0
            self._order_count = 0
            self._day_start = now
