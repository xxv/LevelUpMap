"""A library to plot zipcodes on a map of America"""

from __future__ import print_function

import pygame
from pygame.locals import *
import json
import logging
import paho.mqtt.client as mqtt
from pprint import pprint
from uszipcode import ZipcodeSearchEngine
import random
import time
import ConfigParser
import sys

class Ping(object):
    """A ping on the map"""

    colors = [
        (0xFF, 0x8D, 0x00),
        (0x1E, 0xBB, 0xF3),
        (0x71, 0xCB, 0x3A)]

    def __init__(self, x, y):
        self.created_time = time.time()
        self.life_time = 1
        self.color = random.choice(Ping.colors)
        self.size = 20
        self.grow_limit = 5
        self.x = x
        self.y = y

    def isAlive(self):
        return (time.time() - self.created_time) < self.life_time

    def lifeFactor(self):
        return (time.time() - self.created_time) / self.life_time

    def draw(self, win):
        radius = int(round(self.lifeFactor() * self.size))
        if (radius < self.grow_limit):
            thickness = radius
        else:
            thickness = self.grow_limit

        pygame.draw.circle(win, self.color, [self.x, self.y], radius, thickness)

def on_connect(client, userdata, flags, rc):
    client.subscribe(self)

class Map(object):
    def __init__(self,mqtt_info):
        pygame.display.init()
        self.pings = []
        self.current_time = time.time()
        self.last_frame_time = time.time()
        self.mqtt_info = mqtt_info
        self.client = mqtt.Client()
        self.client.on_connect = lambda c, d, f, rc: self.on_connect(c,d,f,rc)
        self.client.on_message = lambda c, d, m: self.on_message(c,d,m)
        self.client.connect(self.mqtt_info["host"], int(self.mqtt_info["port"]), int(self.mqtt_info["keepalive"]))
        self.background = pygame.image.load("map.PNG")
        self.x_shift = self.background.get_width() / 2.0
        self.y_shift = self.background.get_height() / 2.0
        self.x_scale = self.x_shift / 180.0
        self.y_scale = self.y_shift /  90.0
        self.screen_size = [self.background.get_width(), self.background.get_height()]
        logging.warning("Scale (" + str(self.x_scale) + "," + str(self.y_scale) + ")")
        logging.warning("Shift (" + str(self.x_shift) + "," + str(self.y_shift) + ")")
        self.zips = None
        self.win = pygame.display.set_mode(self.screen_size, pygame.NOFRAME)
        self.client.loop_start()

    def on_connect(self, client, flags, userdata, rc):
        client.subscribe(self.mqtt_info["topic"])

    def on_message(self, client, userdata, message):
        payload = json.loads(message.payload)
        if payload["postal_code"] == None or payload["postal_code"] == "":
            return
        if (self.zips == None):
            self.zips = ZipcodeSearchEngine()
        zcode = self.zips.by_zipcode(payload["postal_code"])
        if zcode["Longitude"] == None or zcode["Latitude"] == None:
            return
        (x,y) = self.project(zcode["Longitude"], zcode["Latitude"])
        x = int(x)
        y = int(y)
        logging.warning(zcode["City"] + " at " + str(x) + ", " + str(y))
        self.pings.append(Ping(x,y))

    def draw(self):
        self.win.fill((59,175,218))
        self.win.blit(self.background,(0,0))
        for ping in self.pings[:]:
            if ping.isAlive():
                ping.draw(self.win)
            else:
                self.pings.remove(ping)

    def project(self, lon, lat):
        x = (self.x_scale * lon) + self.x_shift
        y = self.y_shift - (self.y_scale * lat)
        return (x, y)

    def quit(self):
        self.client.loop_stop()

def read_config(config_file):
    config = ConfigParser.SafeConfigParser()
    read = config.read(config_file)
    if not read:
        print("Could not read config file {}".format(config_file))
        sys.exit(1)

    return dict(config.items('map'))

def main():
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

        world_map.draw()
        pygame.display.flip()

    world_map.quit()
    pygame.quit()

if __name__ == '__main__':
    main()
