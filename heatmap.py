import base64
from datetime import datetime, timedelta
import gzip

import numpy as np
import pygame

class Heatmap(object):
    def __init__(self, size, color, background=None, scale_factor=8):
        self._scale_factor = scale_factor
        self._scaled_surface = pygame.Surface(size, pygame.SRCALPHA, 32)
        if background:
            self._bg_surface = pygame.Surface(size, pygame.SRCALPHA, 32)
        else:
            self._bg_surface = None
        self._surface = None
        self._scaled_size = (int(size[0]/scale_factor), int(size[1]/scale_factor))
        self._boxes = pygame.Surface(self._scaled_size, pygame.SRCALPHA, 32)
        self._boxes.fill(color)
        self._data = np.zeros(self._scaled_size, dtype=np.int32)
        self._norm = None
        self._dirty = True
        self._last_update = None
        self._bgcolor = background
        self._update_frequency = timedelta(seconds=1)

    def add(self, position):
        scaled_pos = (int(position[0]/self._scale_factor),
                      int(position[1]/self._scale_factor))
        self._data[scaled_pos] += 1
        self._dirty = True

    def render(self):
        now = datetime.now()
        if self._dirty and (
                not self._last_update or (
                    now > (self._last_update + self._update_frequency))):
            d_max = self._data.max()
            if d_max > 0:
                self._norm = np.log(self._data + np.ones(self._data.shape))
                d_max = self._norm.max()
                self._norm = (255 * (self._norm / d_max)).astype(np.int8)
            else:
                self._norm = self._data
            pixel_data = pygame.surfarray.pixels_alpha(self._boxes)
            pixel_data[:] = self._norm
            pygame.transform.scale(self._boxes, self._scaled_surface.get_size(), self._scaled_surface)
            if self._bg_surface:
                self._bg_surface.fill(self._bgcolor)
                self._bg_surface.blit(self._scaled_surface, (0, 0))
                self._surface = self._bg_surface
            else:
                self._surface = self._scaled_surface
            self._dirty = False
            self._last_update = now

        return self._surface

    def snapshot(self):
        try:
            data = self._data.tobytes()
        except AttributeError:
            data = self._data.tostring()
        return base64.b64encode(gzip.compress(data)).decode('ascii')

    def load_snapshot(self, data):
        try:
            loaded = gzip.decompress(base64.b64decode(data))
            self._data = np.frombuffer(loaded, dtype=np.int32).copy()
            self._data.resize(self._scaled_size)
        except (ValueError, TypeError) as e:
            print("Could not load retained snapshot: {}".format(e))
            self._data = np.zeros(self._scaled_size, dtype=np.int32)
