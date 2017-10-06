# LevelUpMap
A python MQTT Data mapping script.

## Installation
Depends on SDL and Sqlite3.
`apt-get install libsdl-dev sqlite3 libsqlite3-dev`

You can use PIP to install the requirements file.
`pip install -r requirements.txt`

## Configuration
The MQTT Server and graphics settings are given in map.config.
map.config and map.png should be in the working directory.

## Running
`python mqtt_locator.py map.config`
