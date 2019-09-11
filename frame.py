#!/usr/bin/env python
#
# This file is part of photoframe (https://github.com/mrworf/photoframe).
#
# photoframe is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# photoframe is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with photoframe.  If not, see <http://www.gnu.org/licenses/>.
#
import json
import sys
import os
import random
import hashlib
import datetime
import time
import math
import subprocess
import logging
import socket
import threading
import argparse
import shutil
import traceback
import re

from modules.remember import remember
from modules.shutdown import shutdown
from modules.timekeeper import timekeeper
from modules.settings import settings
from modules.helper import helper
from modules.display import display
from modules.oauth import OAuth
from modules.slideshow import slideshow
from modules.colormatch import colormatch
from modules.drivers import drivers
from modules.servicemanager import ServiceManager
from modules.sysconfig import sysconfig
from modules.cachemanager import CacheManager
from modules.path import path
import modules.debug as debug
from modules.server import WebServer

parser = argparse.ArgumentParser(description="PhotoFrame - A RaspberryPi based digital photoframe", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--logfile', default=None, help="Log to file instead of stdout")
parser.add_argument('--port', default=7777, type=int, help="Port to listen on")
parser.add_argument('--listen', default="0.0.0.0", help="Address to listen on")
parser.add_argument('--debug', action='store_true', default=False, help='Enable loads more logging')
parser.add_argument('--basedir', default=None, help='Change the root folder of photoframe')
parser.add_argument('--emulate', action='store_true', help='Run as an app without root access or framebuffer')
parser.add_argument('--size', default='1280x720', help='Set the resolution to be used when emulating the framebuffer')
cmdline = parser.parse_args()

if cmdline.debug:
  logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
else:
  logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if cmdline.emulate:
  logging.info('Running in emulation mode, settings are stored in /tmp/photoframe/')
  if not os.path.exists('/tmp/photoframe'):
    os.mkdir('/tmp/photoframe')
  path().reassignBase('/tmp/photoframe/')
  path().reassignConfigTxt('extras/config.txt')

if cmdline.basedir is not None:
  newpath = cmdline.basedir + '/'
  logging.info('Altering basedir to %s', newpath)
  settings().reassignBase(newpath)

void = open(os.devnull, 'wb')

# Supercritical, since we store all photoframe files in a subdirectory, make sure to create it
if not path().validate():
  sys.exit(255)

settings = settings()
drivers = drivers()

m = re.search('([0-9]+)x([0-9]+)', cmdline.size)
if m is None:
    logging.error('--size has to be WIDTHxHEIGHT')
    sys.exit(1)

display = display(cmdline.emulate, int(m.group(1)), int(m.group(2)))

if not settings.load():
  # First run, grab display settings from current mode
  current = display.current()
  if current is not None:
    logging.info('No display settings, using: %s' % repr(current))
    settings.setUser('tvservice', '%s %s HDMI' % (current['mode'], current['code']))
    settings.save()
  else:
    logging.info('No display attached?')
if settings.getUser('timezone') == '':
  settings.setUser('timezone', helper.timezoneCurrent())
  settings.save()

width, height, tvservice = display.setConfiguration(settings.getUser('tvservice'), settings.getUser('display-special'))
settings.setUser('tvservice', tvservice)
settings.setUser('width',  width)
settings.setUser('height', height)
settings.save()

# Force display to desired user setting
display.enable(True, True)

# Load services
services = ServiceManager(settings)

# Spin until we have internet, check every 10s
if not helper.hasNetwork():
  helper.waitForNetwork(lambda: display.message('No internet\n\nCheck wifi-config.txt or cable'))

# Let the display know the URL to use
display.setConfigPage('http://%s:%d/' % (settings.get('local-ip'), 7777))

# Prep random
random.seed(long(time.clock()))
colormatch = colormatch(settings.get('colortemp-script'), 2700) # 2700K = Soft white, lowest we'll go
slideshow = slideshow(display, settings, colormatch)
timekeeper = timekeeper(display.enable, slideshow.start)
slideshow.setQueryPower(timekeeper.getDisplayOn)
slideshow.setServiceManager(services)

timekeeper.setConfiguration(settings.getUser('display-on'), settings.getUser('display-off'))
timekeeper.setAmbientSensitivity(settings.getUser('autooff-lux'), settings.getUser('autooff-time'))
timekeeper.setPowermode(settings.getUser('powersave'))
colormatch.setUpdateListener(timekeeper.sensorListener)

powermanagement = shutdown(settings.getUser('shutdown-pin'))

test = WebServer(port=cmdline.port, listen=cmdline.listen)

from routes.settings import RouteSettings
from routes.keywords import RouteKeywords
from routes.orientation import RouteOrientation
from routes.overscan import RouteOverscan
from routes.maintenance import RouteMaintenance
from routes.details import RouteDetails
from routes.upload import RouteUpload
from routes.oauthlink import RouteOAuthLink
from routes.service import RouteService
from routes.control import RouteControl

route = RouteSettings()
route.setupex(powermanagement, settings, drivers, timekeeper, display, CacheManager, slideshow)
test.registerHandler(route)

route = RouteKeywords()
route.setupex(services, slideshow)
test.registerHandler(route)

route = RouteOrientation()
route.setupex(CacheManager)
test.registerHandler(route)

route = RouteOverscan()
route.setupex(CacheManager)
test.registerHandler(route)

route = RouteMaintenance()
route.setupex(cmdline.emulate, drivers, slideshow)
test.registerHandler(route)

route = RouteDetails()
route.setupex(display, drivers, colormatch, slideshow)
test.registerHandler(route)

route = RouteUpload()
route.setupex(settings, drivers)
test.registerHandler(route)

route = RouteOAuthLink()
route.setupex(services, slideshow)
test.registerHandler(route)

route = RouteService()
route.setupex(services, slideshow)
test.registerHandler(route)

route = RouteControl()
route.setupex(slideshow)
test.registerHandler(route)

test.start();
#if __name__ == "__main__":
# This allows us to use a plain HTTP callback
#  os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
#  app.secret_key = os.urandom(24)
#  slideshow.start()
#  app.run(debug=False, port=cmdline.port, host=cmdline.listen )

sys.exit(0)
