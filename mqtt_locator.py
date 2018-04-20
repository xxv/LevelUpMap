"""A library to plot zipcodes on a map of America"""

from __future__ import print_function

import ConfigParser
import json
import random
import sys
import time

import paho.mqtt.client as mqtt
import pygame
import pyproj
from uszipcode import ZipcodeSearchEngine


class Ping(object):
    """A ping on the map"""

    colors = [
        (0xFF, 0x8D, 0x00),
        (0x1E, 0xBB, 0xF3),
        (0x71, 0xCB, 0x3A)]

    def __init__(self, x_loc, y_loc):
        self.created_time = time.time()
        self.life_time = 1
        self.color = random.choice(Ping.colors)
        self.size = 40
        self.coordinate = [x_loc, y_loc]

    def is_alive(self):
        """Returns true if we are within lifetime, false otherwise"""
        return (time.time() - self.created_time) < self.life_time

    def life_factor(self):
        """Gets a scaling factor based on life remaining"""
        return (time.time() - self.created_time) / self.life_time

    def draw(self, win):
        """Renders a ping to a display window"""
        radius = int(round((1-self.life_factor()) * self.size))
        thickness = 2
        if thickness > radius:
            thickness = radius
        pygame.draw.rect(win, self.color, (self.coordinate[0] - radius/2, self.coordinate[1] - radius/2, radius, radius), 0)

    def __repr__(self):
        return "<Ping {}: {:.3f}, {:.3f}>".format(self.created_time, self.coordinate[0], self.coordinate[1])


class Map(object):
    """A class to render the map and pings"""

    background_color = (0, 0, 0)

    def __init__(self, config):
        pygame.display.init()
        screen_info = pygame.display.Info()
        pygame.mouse.set_visible(False)
        self.pings = []
        self.config = config

        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.config["host"],
                            int(self.config["port"]),
                            int(self.config["keepalive"]))

        self.background = pygame.image.load(self.config['map_image'])

        self.proj_in = pyproj.Proj(proj='latlong', datum='WGS84')
        self.proj_map = pyproj.Proj(init='esri:102003')

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
                pygame.NOFRAME)
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
            self.pings.append(Ping(x_coord + self.x_offset, y_coord + self.y_offset))

    def on_connect(self, client, _flags, _userdata, response_code):
        """MQTT Connection callback"""
        print("Connected with result code {}".format(response_code))
        print()
        client.subscribe(self.config["topic"])

    def on_message(self, _client, _userdata, message):
        """MQTT Message recieved callback"""
        payload = json.loads(message.payload)
        if payload["postal_code"] is None or payload["postal_code"] == "":
            return
        if self.zips is None:
            self.zips = ZipcodeSearchEngine()
        zcode = self.zips.by_zipcode(payload["postal_code"])
        if zcode["Longitude"] is None or zcode["Latitude"] is None:
            return
        (x_coord, y_coord) = self.project(zcode["Longitude"], zcode["Latitude"])
        self.pings.append(Ping(x_coord + self.x_offset, y_coord + self.y_offset))

    def draw(self):
        """Render the map and it's pings"""
        self.win.fill(Map.background_color)
        self.win.blit(self.background, (self.x_offset, self.y_offset))
        for ping in self.pings[:]:
            if ping.is_alive():
                ping.draw(self.win)
            else:
                self.pings.remove(ping)

    def project(self, lon, lat):
        """Convert lat/long to pixel x/y"""
        (x_coord_m, y_coord_m) = pyproj.transform(self.proj_in, self.proj_map, lon, lat)
        x_coord = (self.x_scale * x_coord_m) + self.x_shift
        y_coord = -(self.y_scale * y_coord_m) + self.y_shift

        return (int(x_coord), int(y_coord))

    def quit(self):
        """Cleanup"""
        self.client.loop_stop()


def read_config(config_file):
    """Global function to read external config file"""
    config = ConfigParser.SafeConfigParser()
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


if __name__ == '__main__':
    main()
