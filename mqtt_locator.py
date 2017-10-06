"""A library to plot zipcodes on a map of America"""

from __future__ import print_function

import ConfigParser
import json
import random
import sys
import time

import paho.mqtt.client as mqtt
import pygame
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
        self.size = 20
        self.grow_limit = 5
        self.coordinate = [x_loc, y_loc]

    def is_alive(self):
        """Returns true if we are within lifetime, false otherwise"""
        return (time.time() - self.created_time) < self.life_time

    def life_factor(self):
        """Gets a scaling factor based on life remaining"""
        return (time.time() - self.created_time) / self.life_time

    def draw(self, win):
        """Renders a ping to a display window"""
        radius = int(round(self.life_factor() * self.size))
        if radius < self.grow_limit:
            thickness = radius
        else:
            thickness = self.grow_limit

        pygame.draw.circle(win, self.color, self.coordinate, radius, thickness)

class Map(object):
    """A class to render the map and pings"""
    def __init__(self, config):
        pygame.display.init()
        screen_info = pygame.display.Info()
        self.pings = []
        self.config = config
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.config["host"],
                            int(self.config["port"]),
                            int(self.config["keepalive"]))
        self.background = pygame.image.load("map.PNG")
        self.x_shift = self.background.get_width() / 2.0
        self.y_shift = self.background.get_height() / 2.0
        self.x_scale = self.x_shift / 180.0
        self.y_scale = self.y_shift /  90.0
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
                pygame.FULLSCREEN)
            self.x_offset = (screen_info.current_w - self.background.get_width()) / 2
            self.y_offset = (screen_info.current_h - self.background.get_height()) / 2
        print("{} {}".format(self.x_offset, self.y_offset))
        self.client.loop_start()

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
        self.win.fill((59, 175, 218))
        self.win.blit(self.background, (self.x_offset, self.y_offset))
        for ping in self.pings[:]:
            if ping.is_alive():
                ping.draw(self.win)
            else:
                self.pings.remove(ping)

    def project(self, lon, lat):
        """Convert lat/long to pixel x/y"""
        x_coord = (self.x_scale * lon) + self.x_shift
        y_coord = self.y_shift - (self.y_scale * lat)
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
