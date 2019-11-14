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
import sys
import os
import random
import time
import logging
import argparse
import importlib
import signal

from modules.shutdown import shutdown
from modules.timekeeper import timekeeper
from modules.settings import settings
from modules.helper import helper
from modules.display import display
from modules.slideshow import slideshow
from modules.colormatch import colormatch
from modules.drivers import drivers
from modules.servicemanager import ServiceManager
from modules.cachemanager import CacheManager
from modules.path import path
from modules.server import WebServer

# Make sure we run from our own directory
os.chdir(os.path.dirname(sys.argv[0]))

parser = argparse.ArgumentParser(description="PhotoFrame - A RaspberryPi based digital photoframe", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--logfile', default=None, help="Log to file instead of stdout")
parser.add_argument('--port', default=7777, type=int, help="Port to listen on")
parser.add_argument('--countdown', default=10, type=int, help="Set seconds to countdown before starting slideshow")
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

class Photoframe:
  def __init__(self, cmdline):
    self.void = open(os.devnull, 'wb')
    random.seed(long(time.clock()))

    self.emulator = cmdline.emulate
    if self.emulator:
      self.enableEmulation()
    if cmdline.basedir is not None:
      self.changeRoot(cmdline.basedir)
    if not path().validate():
      sys.exit(255)

    self.cacheMgr = CacheManager()
    self.settingsMgr = settings()
    self.displayMgr = display(self.emulator)
    # Validate all settings, prepopulate with defaults if needed
    self.validateSettings()

    self.driverMgr = drivers()
    self.serviceMgr = ServiceManager(self.settingsMgr, self.cacheMgr)

    self.colormatch = colormatch(self.settingsMgr.get('colortemp-script'), 2700) # 2700K = Soft white, lowest we'll go
    self.slideshow = slideshow(self.displayMgr, self.settingsMgr, self.colormatch)
    self.timekeeperMgr = timekeeper()
    self.timekeeperMgr.registerListener(self.displayMgr.enable)
    self.powerMgr = shutdown(self.settingsMgr.getUser('shutdown-pin'))

    self.cacheMgr.validate()
    self.cacheMgr.enableCache(self.settingsMgr.getUser('enable-cache') == 1)

    # Tie all the services together as needed
    self.timekeeperMgr.setConfiguration(self.settingsMgr.getUser('display-on'), self.settingsMgr.getUser('display-off'))
    self.timekeeperMgr.setAmbientSensitivity(self.settingsMgr.getUser('autooff-lux'), self.settingsMgr.getUser('autooff-time'))
    self.timekeeperMgr.setPowermode(self.settingsMgr.getUser('powersave'))
    self.colormatch.setUpdateListener(self.timekeeperMgr.sensorListener)

    self.timekeeperMgr.registerListener(self.slideshow.shouldShow)
    self.slideshow.setServiceManager(self.serviceMgr)
    self.slideshow.setCacheManager(self.cacheMgr)
    self.slideshow.setCountdown(cmdline.countdown)

    # Prep the webserver
    self.setupWebserver(cmdline.listen, cmdline.port)

    # Force display to desired user setting
    self.displayMgr.enable(True, True)

  def updating(self, x, y):
    self.slideshow.stop(self.updating_continue)

  def updating_continue(self):
    self.displayMgr.message('Updating software', False)
    self.webServer.stop()
    logging.debug('Entering hover mode, waiting for update to finish')
    while True: # This is to allow our subprocess to run!
      time.sleep(30)

  def _loadRoute(self, module, klass, *vargs):
    module = importlib.import_module('routes.' + module)
    klass = getattr(module, klass)
    route = eval('klass()')
    route.setupex(*vargs)
    self.webServer.registerHandler(route)

  def setupWebserver(self, listen, port):
    test = WebServer(port=port, listen=listen)
    self.webServer = test

    self._loadRoute('settings', 'RouteSettings', self.powerMgr, self.settingsMgr, self.driverMgr, self.timekeeperMgr, self.displayMgr, self.cacheMgr, self.slideshow)
    self._loadRoute('keywords', 'RouteKeywords', self.serviceMgr, self.slideshow)
    self._loadRoute('orientation', 'RouteOrientation', self.cacheMgr)
    self._loadRoute('overscan', 'RouteOverscan', self.cacheMgr)
    self._loadRoute('maintenance', 'RouteMaintenance', self.emulator, self.driverMgr, self.slideshow)
    self._loadRoute('details', 'RouteDetails', self.displayMgr, self.driverMgr, self.colormatch, self.slideshow)
    self._loadRoute('upload', 'RouteUpload', self.settingsMgr, self.driverMgr)
    self._loadRoute('oauthlink', 'RouteOAuthLink', self.serviceMgr, self.slideshow)
    self._loadRoute('service', 'RouteService', self.serviceMgr, self.slideshow)
    self._loadRoute('control', 'RouteControl', self.slideshow)

  def validateSettings(self):
    if not self.settingsMgr.load():
      # First run, grab display settings from current mode
      current = self.displayMgr.current()
      if current is not None:
        logging.info('No display settings, using: %s' % repr(current))
        self.settingsMgr.setUser('tvservice', '%s %s HDMI' % (current['mode'], current['code']))
        self.settingsMgr.save()
      else:
        logging.info('No display attached?')
    if self.settingsMgr.getUser('timezone') == '':
      self.settingsMgr.setUser('timezone', helper.timezoneCurrent())
      self.settingsMgr.save()

    width, height, tvservice = self.displayMgr.setConfiguration(self.settingsMgr.getUser('tvservice'), self.settingsMgr.getUser('display-special'))
    self.settingsMgr.setUser('tvservice', tvservice)
    self.settingsMgr.setUser('width',  width)
    self.settingsMgr.setUser('height', height)
    self.settingsMgr.save()

  def changeRoot(self, newRoot):
    if newRoot is None: return
    newpath = os.path.join(newRoot, '/')
    logging.info('Altering basedir to %s', newpath)
    self.settings().reassignBase(newpath)

  def enableEmulation(self):
    logging.info('Running in emulation mode, settings are stored in /tmp/photoframe/')
    if not os.path.exists('/tmp/photoframe'):
      os.mkdir('/tmp/photoframe')
    path().reassignBase('/tmp/photoframe/')
    path().reassignConfigTxt('extras/config.txt')

  def start(self):
    signal.signal(signal.SIGHUP, lambda x, y: self.updating(x,y))
    self.slideshow.start()
    self.webServer.start()

frame = Photoframe(cmdline)
frame.start()
sys.exit(0)
