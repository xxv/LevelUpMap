import numpy as np
import pygame

class Heatmap(object):
    def __init__(self, size, color, scale_factor=8):
        self._scale_factor = scale_factor
        self.surface = pygame.Surface(size, pygame.SRCALPHA, 32)
        scaled_size = (int(size[0]/scale_factor), int(size[1]/scale_factor))
        self._boxes = pygame.Surface(scaled_size, pygame.SRCALPHA, 32)
        self._boxes.fill(color)
        self._data = np.zeros(scaled_size, dtype=np.int16)
        self._norm = None
        self._dirty = True

    def add(self, position):
        scaled_pos = (int(position[0]/self._scale_factor),
                      int(position[1]/self._scale_factor))
        self._data[scaled_pos] += 1
        self._dirty = True

    def render(self):
        if self._dirty:
            d_max = self._data.max()
            if d_max > 0:
                self._norm = np.log(self._data + np.ones(self._data.shape))
                d_max = self._norm.max()
                self._norm = (255 * (self._norm / d_max)).astype(np.int8)
            else:
                self._norm = self._data
            pixel_data = pygame.surfarray.pixels_alpha(self._boxes)
            pixel_data[:] = self._norm
            pygame.transform.scale(self._boxes, self.surface.get_size(), self.surface)
            self._dirty = False

        return self.surface
