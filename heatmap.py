import numpy as np
import pygame

class Heatmap(object):
    def __init__(self, size):
        self.surface = pygame.Surface(size, pygame.SRCALPHA, 32)
        #self.surface = None
        self._data = np.zeros(size, dtype=np.int16)
        self._norm = None
        self._dirty = True

    def add(self, position):
        print(position)
        self._data[position] += 1
        self._dirty = True

    def gray(self, im):
        w, h = im.shape
        ret = np.empty((w, h, 4), dtype=np.uint8)
        #ret[:, :, 3] = ret[:, :, 1] = ret[:, :, 0] = im
        ret[:, :, 3] = im
        return ret

    def render(self):
        if self._dirty:
            d_max = 1
            if d_max > 0:
                self._norm = (255 * self._data / d_max).astype(np.int8)
                np.clip(self._norm, 0, 255)
            else:
                self._norm = self._data
            pixel_data = pygame.surfarray.pixels_alpha(self.surface)
            pixel_data[:] = self._norm
            #self.surface = pygame.surfarray.make_surface(self.gray(self._norm))
            self._dirty = False

        return self.surface
