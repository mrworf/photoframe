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
import threading
import logging
import os
import random
import datetime
import hashlib
import time
import json
import math
import re
import subprocess

from modules.remember import remember
from modules.helper import helper

class slideshow:
  SHOWN_IP = False

  def __init__(self, display, settings, colormatch):
    self.queryPowerFunc = None
    self.thread = None
    self.display = display
    self.settings = settings
    self.colormatch = colormatch
    self.imageCurrent = None
    self.imageMime = None
    self.services = None
    self.void = open(os.devnull, 'wb')

  def getCurrentImage(self):
    return self.imageCurrent, self.imageMime

  def getColorInformation(self):
    return {
      'temperature':self.colormatch.getTemperature(),
      'lux':self.colormatch.getLux()
      }

  def setServiceManager(self, services):
    self.services = services

  def setQueryPower(self, func):
    self.queryPowerFunc = func

  def start(self, blank=False):
    if blank:
      self.display.clear()

    if self.thread is None:
      self.thread = threading.Thread(target=self.presentation)
      self.thread.daemon = True
      self.thread.start()

  def presentation(self):

    if not slideshow.SHOWN_IP:
      slideshow.SHOWN_IP = True
      # Once we have IP, show for 10s
      cd = 10
      while (cd > 0):
        self.display.message('Starting in %d seconds\n\nFrame configuration\n\nhttp://%s:7777' % (cd, self.settings.get('local-ip')))
        cd -= 1
        time.sleep(1)
      self.display.clear()


    logging.info('Starting presentation')
    delay = 0
    useService = 0

    while True:
      # Avoid showing images if the display is off
      if self.queryPowerFunc is not None and self.queryPowerFunc() is False:
        logging.info("Display is off, exit quietly")
        break

      # For now, just pick the first service
      time_process = time.time()

      services = self.services.getServices(readyOnly=True)
      if len(services) > 0:
        # Very simple round-robin
        if useService >= len(services):
          useService = 0
        svc = services[useService]['id']

        filename = os.path.join(self.settings.get('tempfolder'), 'image')
        result = self.services.servicePrepareNextItem(svc, filename, ['image/jpeg'], {'width' : self.settings.getUser('width'), 'height' : self.settings.getUser('height')})
        if result['error'] is not None:
          self.display.message('%s failed:\n\n%s' % (services[useService]['name'], result['error']))
        else:
          self.imageMime = result['mimetype']
          self.imageCurrent = filename

          if self.settings.getUser('imagesizing') == 'blur':
            helper.makeFullframe(filename, self.settings.getUser('width'), self.settings.getUser('height'))
          elif self.settings.getUser('imagesizing') == 'zoom':
            helper.makeFullframe(filename, self.settings.getUser('width'), self.settings.getUser('height'), zoomOnly=True)
          if self.colormatch.hasSensor():
            if not self.colormatch.adjust(filename):
              logging.warning('Unable to adjust image to colormatch, using original')
        useService += 1
      else:
        self.display.message('Photoframe isn\'t ready yet\n\nPlease direct your webbrowser to\n\nhttp://%s:7777/\n\nand add one or more photo providers' % self.settings.get('local-ip'))

      time_process = time.time() - time_process

      # Delay before we show the image (but take processing into account)
      # This should keep us fairly consistent
      if time_process < delay:
        time.sleep(delay - time_process)

      if self.imageCurrent is not None and os.path.exists(self.imageCurrent):
        self.display.image(self.imageCurrent)
        os.remove(self.imageCurrent)

      delay = self.settings.getUser('interval')
    self.thread = None
