"""A visualization to plot events tagged with zip codes on a map of the US"""

from __future__ import print_function

try:
    from ConfigParser import SafeConfigParser
except ImportError:
    from configparser import SafeConfigParser
from datetime import datetime, timedelta
import json
import math
import sys
import time

import paho.mqtt.client as mqtt
import pygame
import pyganim
import pyproj
from Box2D import b2PolygonShape, b2World
from uszipcode import ZipcodeSearchEngine

from heatmap import Heatmap
from ordertotals import OrderTotals


class FadeText(object):
    """Text that can fade its alpha channel."""
    def __init__(self, font, text, color):
        self._font = font
        self._text = text
        self._color = color
        self._surface = None
        self._surface2 = None
        self._text_width = None

    def draw(self, surface, position, fade):
        if not self._surface:
            self._surface = self._font.render(self._text, True, self._color)
            rect = self._surface.get_rect()
            self._surface.convert_alpha()
            self._surface2 = pygame.surface.Surface(rect.size, pygame.SRCALPHA, 32)
            self._text_width = rect.width

        self._surface2.fill((255, 255, 255, fade))
        self._surface2.blit(self._surface, (0, 0),
                            special_flags=pygame.BLEND_RGBA_MULT)
        # Centered
        text_pos = (position[0] - self._text_width/2, position[1])
        surface.blit(self._surface2, text_pos)

class Ping(object):
    """An event displayed on the map."""

    ORANGE = (0xFF, 0x8D, 0x00)
    BLUE = (0x1E, 0xBB, 0xF3)
    GREEN = (0x71, 0xCB, 0x3A)

    _text_color = (0x55, 0x55, 0x55)
    _text_color_earn = (0x77, 0x77, 0x77)


    def __init__(self, world, x_loc, y_loc, color, text, earn_amount=0):
        self.created_time = time.time()
        self._life_time = 3
        self._position = (x_loc, y_loc)
        self._size = 40
        self._color = color
        self._text = text
        self._rect_surface = None
        self._font = pygame.font.SysFont('Source Sans Pro', 20, bold=True)
        self._earn_font = pygame.font.SysFont('Source Sans Pro', 30, bold=True)
        self._text_widget = FadeText(self._font, text, self._text_color)
        self._body = world.CreateDynamicBody(position=(x_loc, y_loc), fixedRotation=True)
        self._box = self._body.CreatePolygonFixture(box=(self._size, self._size),
                                                    density=1, friction=0.0)
        self._earn_amount = earn_amount
        if earn_amount:
            if earn_amount % 100 == 0:
                earn_text = "${:d}".format(int(earn_amount/100))
            else:
                earn_text = "${:.02f}".format(earn_amount/100.0)

            self._earn_text_widget = FadeText(self._earn_font, earn_text,
                                              self._text_color_earn)
            self._earn_body = world.CreateDynamicBody(position=(x_loc, y_loc - self._size/2),
                                                      fixedRotation=True, linearDamping=0.95)
            self._earn_body.ApplyLinearImpulse((0, -1000), (x_loc, y_loc - 1), wake=True)
        else:
            self._earn_body = None

    @property
    def position(self):
        """Initial coordinates."""
        return self._position

    def is_alive(self):
        """Returns true if we are within lifetime, false otherwise"""
        return (time.time() - self.created_time) < self._life_time

    def life_factor(self):
        """Gets a scaling factor based on life remaining"""
        return (time.time() - self.created_time) / self._life_time

    def draw(self, win):
        """Renders a ping to a display window"""
        pos = self._body.position

        sq_size = self._size
        center_square = (pos[0] - sq_size/2,
                         pos[1] - sq_size/2)
        fade = int(255 * (1 - self.life_factor()))
        alpha = int((1.0 - self.life_factor()) * 255)

        if self._earn_body:
            earn_pos = tuple(map(int, self._earn_body.position))
            self._earn_text_widget.draw(win, earn_pos, int(math.log2(fade + 1) * 32))

        if not self._rect_surface:
            self._rect_surface = pygame.surface.Surface((sq_size, sq_size))
            self._rect_surface.fill(self._color)

        self._rect_surface.set_alpha(alpha)
        win.blit(self._rect_surface, center_square)

        self._text_widget.draw(win, (pos[0], pos[1] + 25), fade)

    def destroy(self, world):
        if self._body:
            world.DestroyBody(self._body)
        if self._earn_body:
            world.DestroyBody(self._earn_body)

    def __repr__(self):
        return "<Ping {}: {:.3f}, {:.3f}>".format(self.created_time,
                                                  *self.position)

class Progress(object):
    def __init__(self):
        self._progress_anim = Progress._load_anim('progress{:}.png', range(1, 9), 100)
        self._value = False
        self._dirty = True

    def show(self, value):
        if self._value != value:
            self._dirty = True

        self._value = value

    def draw(self, surface):
        if self._dirty:
            if self._value:
                self._progress_anim.play()
            else:
                self._progress_anim.stop()
            self._dirty = False

        if self._value:
            win_center = surface.get_rect().center
            anim_center = self._progress_anim.getRect().center
            self._progress_anim.blit(surface, (win_center[0] - anim_center[0],
                                                win_center[1] - anim_center[1]))

    @staticmethod
    def _load_anim(filename_format, values, timing):
        return pyganim.PygAnimation([(filename_format.format(i), timing) for i in values])

class FPSCounter(object):
    def __init__(self, clock):
        self._clock = clock
        self._font = pygame.font.SysFont('Source Sans Pro', 25)
        self._update_frequency = 120
        self._update_counter = 0
        self._surface = None
        self._color = pygame.Color(0, 0, 0)

    def draw(self, surface, position):
        self._update_counter += 1
        if not self._surface or self._update_counter > self._update_frequency:
            self._surface = self._font.render("{:0.02f} FPS".format(self._clock.get_fps()),
                                              False, self._color)
            self._update_counter = 0

        surface.blit(self._surface, position)


class Map(object):
    """A class to render the map and pings"""

    _text_color = (0x55, 0x55, 0x55)
    background_color = (0xcc, 0xcc, 0xcc)

    def __init__(self, config, clock):
        self._clock = clock
        pygame.display.init()
        pygame.font.init()
        self._world = b2World(gravity=(0, 0))
        self.pings = []
        self.config = config
        self._debug_enable = False
        self._last_frame = 0
        self._event_topic = config['event_topic']
        self._my_topic = config['topic']
        self._stats = {}
        self._stats_last_update = None
        self._stats_stale = timedelta(seconds=10)
        self._loading = False
        self._heatmap_show = False
        self._heatmap_location = 0

        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.config["host"],
                            int(self.config["port"]),
                            int(self.config["keepalive"]))

        self._legend_font = pygame.font.SysFont('Source Sans Pro', 25)
        self._legend_surface = None
        self._mask = pygame.image.load(config['map_image_mask'])

        self.proj_in = pyproj.Proj(proj='latlong', datum='WGS84')
        self.proj_map = pyproj.Proj(init=config['map_projection'])

        manual_scale_factor = float(self.config['scale_factor'])
        self.x_scale = self._mask.get_height()/manual_scale_factor
        self.y_scale = self.x_scale
        self.x_shift = self._mask.get_width()/2
        self.y_shift = self._mask.get_height()/2

        self.zips = None

        pygame.mouse.set_visible(False)
        screen_info = pygame.display.Info()

        if config["fullscreen"].lower() != 'true':
            self.win = pygame.display.set_mode(
                [
                    self._mask.get_width(),
                    self._mask.get_height()
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
            self.x_offset = (screen_info.current_w - self._mask.get_width()) / 2
            self.y_offset = (screen_info.current_h - self._mask.get_height()) / 2
        self._mask = self._mask.convert_alpha()
        print("{} {}".format(self.x_offset, self.y_offset))

        self._heatmap = Heatmap(self._mask.get_size(), (0x00, 0x00, 0x00), (0xff, 0xff, 0xff))
        self._order_totals = OrderTotals()
        self._progress = Progress()
        self._fps_counter = FPSCounter(self._clock)

        self.client.loop_start()

    def test(self):
        print("Window size: {}, {}".format(self._mask.get_width(), self._mask.get_height()))
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
        places = [seattle, la, bar_harbor, miami, left_coast, cape_flattery,
                  west_quoddy, p_town]
        for place in places:
            (x_coord, y_coord) = self.project(*place)
            self.pings.append(Ping(self._world,
                                   x_coord + self.x_offset,
                                   y_coord + self.y_offset,
                                   (0, 0, 0), ''))

    def on_connect(self, client, _flags, _userdata, response_code):
        """MQTT Connection callback"""
        print("Connected with result code {}".format(response_code))
        print()
        client.subscribe(self._event_topic)
        client.subscribe(self._my_topic + '/#')
        client.subscribe('dataclip_mqtt/#')

    def on_message(self, _client, _userdata, message):
        """MQTT Message received callback"""

        if message.topic == self._event_topic:
            self.on_event(json.loads(message.payload.decode('utf-8')))
        elif message.topic == 'dataclip_mqtt/stats':
            self.on_stats(json.loads(message.payload.decode('utf-8')))
        elif message.topic.startswith(self._my_topic):
            subpath = message.topic[len(self._my_topic) + 1:]
            self.on_map_message(subpath, json.loads(message.payload.decode('utf-8')))

    def on_event(self, payload):
        """Called when on event comes in that should be displayed."""
        ping = self._to_ping(payload)
        if not ping:
            return
        self.pings.append(ping)
        self._order_totals.add(payload)
        self._heatmap.add(ping.position)

    def on_stats(self, stats):
        """Called when a stats broadcast comes in."""
        self._stats_last_update = datetime.now()
        self._stats = stats

    def on_map_message(self, path, payload):
        """Called when a map configuration message arrives."""
        try:
            if path == 'heatmap/enable':
                self._heatmap_show = bool(payload)
            elif path == 'heatmap/location_id':
                self._heatmap_location = int(payload)
            elif path == 'heatmap/snapshot':
                self._heatmap.load_snapshot(payload)
            elif path == 'snapshot':
                self._order_totals.load_snapshot(payload)
            elif path == 'debug':
                self._debug_enable = bool(payload)
        except ValueError as e:
            print("Error parsing message '{}' to sub-path '{}': {}".format(payload, path, e))

    def _to_ping(self, payload):
        if payload["postal_code"] is None or payload["postal_code"] == "":
            return None
        if self.zips is None:
            self.zips = ZipcodeSearchEngine()
        zcode = self.zips.by_zipcode(payload["postal_code"])
        if zcode["Longitude"] is None or zcode["Latitude"] is None:
            return None
        merchant_name = payload.get('merchant_name', '')

        if payload.get('user_order_app_name', None) == 'LevelUp':
            color = Ping.ORANGE
        elif payload.get('ready_time', None):
            color = Ping.GREEN
        else:
            color = Ping.BLUE

        (x_coord, y_coord) = self.project(zcode["Longitude"], zcode["Latitude"])
        earn = int(payload.get('earn_amount', 0))

        return Ping(self._world,
                    x_coord + self.x_offset,
                    y_coord + self.y_offset,
                    color, merchant_name, earn)

    def _render_legend_item(self, color, text):
        text_offset = (30, -8)
        rect_size = 20
        text_surface = self._legend_font.render(text, True, self._text_color)
        text_size = text_surface.get_rect().size
        surface = pygame.surface.Surface((text_size[0] + text_offset[0],
                                          text_size[1] + text_offset[1]),
                                         pygame.SRCALPHA, 32)
        surface.blit(text_surface, text_offset)
        pygame.draw.rect(surface, color, (0, 0, rect_size, rect_size), 0)

        return surface

    def _draw_legend(self, position):
        if not self._legend_surface:
            surface = pygame.Surface((500, 500), pygame.SRCALPHA, 32)
            surface.blit(self._render_legend_item(Ping.ORANGE, "LevelUp app"), (0, 0))
            surface.blit(self._render_legend_item(Ping.GREEN, "order ahead"), (0, 30))
            surface.blit(self._render_legend_item(Ping.BLUE, "in-store orders"), (0, 60))
            self._legend_surface = surface
        self.win.blit(self._legend_surface, position)

    def _draw_debug_stats(self):
        height = 8
        source = self._stats.get('source', {})

        buffer_size = self._stats.get('buffer_size', 0)

        before = source.get('events_before_window', 0)
        in_win = source.get('events_in_window', 0)
        after = source.get('events_after_window', 0)

        surface = pygame.surface.Surface((self.win.get_width(),
                                         height * 6), pygame.SRCALPHA, 32)
        pygame.draw.rect(surface, (180, 180, 180),
                         ((0, 0), (before, height)))
        pygame.draw.rect(surface, (90, 90, 90),
                         ((before, 0), (before + in_win, height)))
        pygame.draw.rect(surface, (10, 10, 10),
                         ((before + in_win, 0), (before + in_win + after, height)))

        pygame.draw.rect(surface, (90, 90, 90),
                         ((before, height), (before + buffer_size, height*2)))

        self._fps_counter.draw(surface, (0, height * 2))

        self.win.blit(surface, (0, 0))


    def _tick(self):
        self._order_totals.tick()

        self._world.Step(self._clock.get_time()/1000.0, 6, 2)

    def _draw_pings(self):
        for ping in self.pings[:]:
            if ping.is_alive():
                ping.draw(self.win)
            else:
                ping.destroy(self._world)
                self.pings.remove(ping)

    def draw(self):
        """Render the map and it's pings"""

        self._tick()
        self.win.fill(Map.background_color)

        if self._heatmap_show:
            self.win.blit(self._heatmap.render(), (0, 0))
        self.win.blit(self._mask, (self.x_offset, self.y_offset))

        self._draw_pings()
        self._order_totals.draw(self.win, (100, (self.win.get_height() - 180)))

        self._draw_legend((self._mask.get_width() - 250, self._mask.get_height() - 150))

        if self._debug_enable:
            self._draw_debug_stats()

        self._update_progress()
        self._progress.draw(self.win)

    def _update_progress(self):
        buffer_size = self._stats.get('buffer_size', 0)

        stats_stale = not self._stats_last_update or (
            datetime.now() > (self._stats_last_update + self._stats_stale))

        loading = buffer_size == 0 or stats_stale

        self._progress.show(loading)

    def project(self, lon, lat):
        """Convert lat/long to pixel x/y"""
        (x_coord_m, y_coord_m) = pyproj.transform(self.proj_in, self.proj_map, lon, lat)
        x_coord = (self.x_scale * x_coord_m) + self.x_shift
        y_coord = -(self.y_scale * y_coord_m) + self.y_shift

        return (int(x_coord), int(y_coord))

    def _snapshot(self):
        self.client.publish(self._my_topic + '/heatmap/snapshot',
                            json.dumps(self._heatmap.snapshot()).encode('utf-8'), retain=True)
        self.client.publish(self._my_topic + '/snapshot',
                            json.dumps(self._order_totals.to_snapshot()).encode('utf-8'),
                            retain=True)

    def quit(self):
        """Cleanup"""
        self._snapshot()
        self.client.loop_stop()


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
    world_map = Map(read_config(config_file), clock)

    try:
        while not done:
            clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    done = True
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    done = True

            world_map.draw()
            pygame.display.flip()
    except KeyboardInterrupt:
        done = True

    world_map.quit()
    pygame.quit()


def main_profiled():
    import cProfile, pstats, io
    pr = cProfile.Profile()
    pr.enable()
    main()
    pr.disable()
    s = io.StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats()
    print(s.getvalue())


if __name__ == '__main__':
    main()
