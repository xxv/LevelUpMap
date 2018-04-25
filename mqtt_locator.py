"""A library to plot zipcodes on a map of America"""

from __future__ import print_function

try:
    from ConfigParser import SafeConfigParser
except ImportError:
    from configparser import SafeConfigParser
from datetime import datetime
import json
import random
import sys
import time

import paho.mqtt.client as mqtt
import pygame
import pyproj
from animated_value import AnimatedAverage, AnimatedValue
from Box2D import b2PolygonShape, b2World

from uszipcode import ZipcodeSearchEngine


class Ping(object):
    """A ping on the map"""

    _text_color = (0x55, 0x55, 0x55)
    colors = [
        (0xFF, 0x8D, 0x00),
        (0x1E, 0xBB, 0xF3),
        (0x71, 0xCB, 0x3A)]

    def __init__(self, world, x_loc, y_loc, text):
        self.created_time = time.time()
        self.life_time = 3
        self.color = random.choice(Ping.colors)
        self.size = 40
        self._text = text
        self._text_surface = None
        self._text_surface2 = None
        self._rect_surface = None
        self._body = world.CreateDynamicBody(position=(x_loc, y_loc), fixedRotation=True)
        self._box = self._body.CreatePolygonFixture(box=(self.size, self.size), density=1, friction=0.0)

    def is_alive(self):
        """Returns true if we are within lifetime, false otherwise"""
        return (time.time() - self.created_time) < self.life_time

    def life_factor(self):
        """Gets a scaling factor based on life remaining"""
        return (time.time() - self.created_time) / self.life_time

    def draw(self, win, font):
        """Renders a ping to a display window"""
        pos = self._body.position

        sq_size = self.size
        center_square = (pos[0] - sq_size/2,
                         pos[1] - sq_size/2)
        alpha = int((1.0 - self.life_factor()) * 255)
        if not self._rect_surface:
            self._rect_surface = pygame.surface.Surface((sq_size, sq_size))
            self._rect_surface.fill(self.color)
        self._rect_surface.set_alpha(alpha)
        win.blit(self._rect_surface, center_square)
        if not self._text_surface:
            self._text_surface = font.render(self._text, True, self._text_color)
            rect = self._text_surface.get_rect()
            self._text_surface.convert_alpha()
            self._text_surface2 = pygame.surface.Surface(rect.size, pygame.SRCALPHA, 32)
            self._text_width = rect.width
        fade = int(255 * (1 - self.life_factor()))
        self._text_surface2.fill((255, 255, 255, fade))
        self._text_surface2.blit(self._text_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        text_pos = (pos[0] - self._text_width/2, pos[1] + 25)
        win.blit(self._text_surface2, text_pos)

    def destroy(self, world):
        if self._body:
            world.DestroyBody(self._body)

    def __repr__(self):
        return "<Ping {}: {:.3f}, {:.3f}>".format(self.created_time,
                                                  *self.coordinate)


class Map(object):
    """A class to render the map and pings"""

    _text_color = (0x55, 0x55, 0x55)
    background_color = (0xe9, 0xe9, 0xe9)

    def __init__(self, config):
        pygame.display.init()
        pygame.font.init()
        self._world = b2World(gravity=(0, 0))
        screen_info = pygame.display.Info()
        pygame.mouse.set_visible(False)
        self.pings = []
        self.config = config
        self._avg_spend = AnimatedAverage(count=500)
        self._order_count = 0
        self._cum_order_spend = 0
        self._cum_order_spend_anim = AnimatedValue()
        self._day_start = datetime.now()
        self._last_frame = 0

        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.config["host"],
                            int(self.config["port"]),
                            int(self.config["keepalive"]))

        self._font = pygame.font.SysFont('Source Sans Pro Semibold', 25)
        self._font_avg_spend = pygame.font.SysFont('Source Sans Pro', 30, bold=True)
        self.background = pygame.image.load(config['map_image'])

        self.proj_in = pyproj.Proj(proj='latlong', datum='WGS84')
        self.proj_map = pyproj.Proj(init=config['map_projection'])

        MANUAL_SCALE_FACTOR = float(self.config['scale_factor'])
        self.x_scale = self.background.get_height()/MANUAL_SCALE_FACTOR
        self.y_scale = self.x_scale
        self.x_shift = self.background.get_width()/2
        self.y_shift = self.background.get_height()/2

        self.zips = None
        if config["fullscreen"].lower() != 'true':
            self.win = pygame.display.set_mode(
                [
                    self.background.get_width(),
                    self.background.get_height()
                ],
                pygame.NOFRAME | pygame.HWSURFACE | pygame.DOUBLEBUF)
            self.x_offset = self.y_offset = 0
        else:
            self.win = pygame.display.set_mode(
                [
                    screen_info.current_w,
                    screen_info.current_h
                ],
                pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF)
            self.x_offset = (screen_info.current_w - self.background.get_width()) / 2
            self.y_offset = (screen_info.current_h - self.background.get_height()) / 2
        self.background = self.background.convert()
        print("{} {}".format(self.x_offset, self.y_offset))
        self.client.loop_start()

    def test(self):
        print("Window size: {}, {}".format(self.background.get_width(), self.background.get_height()))
        print("scale: {}, {}\nshift: {}, {}".format(self.x_scale, self.y_scale, self.x_shift, self.y_shift))
        seattle = [-122.4821474, 47.6129432]
        la = [-118.6919199, 34.0201613]
        bar_harbor = [-68.4103749, 44.3583123]
        miami = [-80.369544, 25.7823404]
        left_coast = [-124.411326, 40.438851]
        cape_flattery = [-124.723378, 48.384951]
        west_quoddy = [-66.952785, 44.816219]
        p_town = [-70.2490474, 42.0622933]
        print("Seattle: {} -> {}".format(seattle, self.project(*seattle)))
        print("LA: {} -> {}".format(la, self.project(*la)))
        print("Bar Harbor: {} -> {}".format(bar_harbor, self.project(*bar_harbor)))
        print("Miami: {} -> {}".format(miami, self.project(*miami)))
        places = [seattle, la, bar_harbor, miami, left_coast, cape_flattery, west_quoddy, p_town]
        for place in places:
            (x_coord, y_coord) = self.project(*place)
            self.pings.append(Ping(self._world, x_coord + self.x_offset, y_coord + self.y_offset, ''))

    def on_connect(self, client, _flags, _userdata, response_code):
        """MQTT Connection callback"""
        print("Connected with result code {}".format(response_code))
        print()
        client.subscribe(self.config["topic"])

    def on_message(self, _client, _userdata, message):
        """MQTT Message received callback"""
        payload = json.loads(message.payload.decode('utf-8'))
        if payload["postal_code"] is None or payload["postal_code"] == "":
            return
        if self.zips is None:
            self.zips = ZipcodeSearchEngine()
        zcode = self.zips.by_zipcode(payload["postal_code"])
        if zcode["Longitude"] is None or zcode["Latitude"] is None:
            return
        merchant_name = payload.get('merchant_name', '')
        (x_coord, y_coord) = self.project(zcode["Longitude"], zcode["Latitude"])
        self.pings.append(Ping(self._world, x_coord + self.x_offset, y_coord + self.y_offset, merchant_name))
        spend = int(payload['spend_amount'])
        if spend:
            self._avg_spend.add(spend)
        self._maybe_reset_daily_totals()
        self._order_count += 1
        self._cum_order_spend += spend
        self._cum_order_spend_anim.set(self._cum_order_spend)

    def _draw_text_stat(self, text, value, index):
        self.win.blit(self._font_avg_spend.render(text.format(value), True, self._text_color), (100, (self.win.get_height() - 180) + index * 40))

    def draw(self):
        """Render the map and it's pings"""
        self._avg_spend.tick()
        self._cum_order_spend_anim.tick()
        frame_time = pygame.time.get_ticks() / 1000
        if self._last_frame:
            frame_delay = frame_time - self._last_frame
        else:
            frame_delay = 1.0/60
        self._world.Step(frame_delay, 6, 2)
        self._last_frame = frame_time
        self.win.fill(Map.background_color)
        self.win.blit(self.background, (self.x_offset, self.y_offset))
        for ping in self.pings[:]:
            if ping.is_alive():
                ping.draw(self.win, self._font)
            else:
                ping.destroy(self._world)
                self.pings.remove(ping)
        self._draw_text_stat("Average Order Price: ${:0.02f}", self._avg_spend.get()/100.0, 0)
        self._draw_text_stat("Orders Today Total: ${:0,.02f}", self._cum_order_spend_anim.get()/100.0, 1)
        self._draw_text_stat("Orders Today: {:,}", self._order_count, 2)

    def project(self, lon, lat):
        """Convert lat/long to pixel x/y"""
        (x_coord_m, y_coord_m) = pyproj.transform(self.proj_in, self.proj_map, lon, lat)
        x_coord = (self.x_scale * x_coord_m) + self.x_shift
        y_coord = -(self.y_scale * y_coord_m) + self.y_shift

        return (int(x_coord), int(y_coord))

    def quit(self):
        """Cleanup"""
        self.client.loop_stop()

    def _maybe_reset_daily_totals(self):
        now = datetime.now()
        if self._day_start.day != now.day:
            self._cum_order_spend = 0
            self._order_count = 0
            self._day_start = now


def read_config(config_file):
    """Global function to read external config file"""
    config = SafeConfigParser()
    read = config.read(config_file)
    if not read:
        print("Could not read config file {}".format(config_file))
        sys.exit(1)

    return dict(config.items('map'))


def main():
    """Script Entry Point"""
    if len(sys.argv) != 2:
        print("Usage: {} CONFIG_FILE".format(sys.argv[0]))
        print()
        sys.exit(1)
    config_file = sys.argv[1]
    done = False
    clock = pygame.time.Clock()
    world_map = Map(read_config(config_file))

    while not done:
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                done = True

        world_map.draw()
        pygame.display.flip()

    world_map.quit()
    pygame.quit()


def main_profiled():
    import cProfile, pstats, StringIO
    pr = cProfile.Profile()
    pr.enable()
    main()
    pr.disable()
    s = StringIO.StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats()
    print(s.getvalue())


if __name__ == '__main__':
    main()
