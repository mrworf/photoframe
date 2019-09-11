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
import shutil
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
from modules.cachemanager import CacheManager
from modules.path import path

class slideshow:
  SHOWN_IP = False
  EVENTS = ["nextImage", "prevImage", "nextAlbum", "prevAlbum", "settingsChange", "memoryForget", "clearCache"]

  def __init__(self, display, settings, colormatch):
    self.countdown = 0
    self.queryPowerFunc = None
    self.thread = None
    self.services = None
    self.display = display
    self.settings = settings
    self.colormatch = colormatch
    self.void = open(os.devnull, 'wb')
    self.delayer = threading.Event()

    self.imageCurrent = None
    self.imageMime = None
    self.imageOnScreen = False
    self.cleanConfig = False
    self.doControl = None
    self.doClearCache = False
    self.doMemoryForget = False
    self.ignoreRandomize = False
    self.skipPreloadedImage = False

    self.supportedFormats = [
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/bmp'
        # HEIF to be added once I get ImageMagick running with support
    ]

  def setCountdown(self, seconds):
    if seconds < 1:
      self.countdown = 0
    else:
      self.countdown = seconds

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

  def trigger(self):
    logging.debug('Causing immediate showing of image')
    self.cleanConfig = True
    self.delayer.set()

  def createEvent(self, cmd):
    if cmd not in slideshow.EVENTS:
      logging.warning("Unknown event '%s' detected!"%cmd)
      return 

    if cmd == "settingsChange":
      self.skipPreloadedImage = True
    elif cmd == "memoryForget":
      self.cleanConfig = True
      self.doMemoryForget = True
    elif cmd == "clearCache":
      self.cleanConfig = True
      self.doClearCache = True
    else:
      self.doControl = cmd
      if self.settings.getUser("randomize_images"):
        if cmd == "nextAlbum":
          self.doControl = "nextImage"
        elif cmd == "prevAlbum":
          self.doControl = "prevImage"

    self.delayer.set()

  def handleEvents(self):
    if self.cleanConfig:
      logging.info('Change of configuration, flush data and restart')
      # We need to expunge any pending image now
      # so we get fresh data to show the user
      if self.doMemoryForget:
        self.services.memoryForget(forgetHistory=True)
        self.doMemoryForget = False
      if self.doClearCache:
        CacheManager.empty(path.CACHEFOLDER)
        self.doClearCache = False
      if self.imageCurrent:
        self.imageCurrent = None
        self.skipPreloadedImage = True
        self.imageOnScreen = False
        self.display.clear()
      self.cleanConfig = False

    if self.doControl == "nextImage":
      #just skip delay and show the next (preloaded) image
      pass
    elif self.doControl == "prevImage":
      self.skipPreloadedImage = True
      self.ignoreRandomize = True
      if self.services.prevImage():
        self.delayer.set()
    elif self.doControl == "nextAlbum":
      self.skipPreloadedImage = True
      self.services.nextAlbum()
      self.delayer.set()
    elif self.doControl == "prevAlbum":
      self.skipPreloadedImage = True
      self.services.prevAlbum()
      self.delayer.set()
    self.doControl = None

  def startupScreen(self):
    slideshow.SHOWN_IP = True
    # Once we have IP, show for 10s
    cd = self.countdown
    while (cd > 0):
      time_process = time.time()
      self.display.message('Starting in %d' % (cd))
      cd -= 1
      time_process = time.time() - time_process
      if time_process < 1.0:
        time.sleep(1.0 - time_process)
    self.display.clear()

  def handleErrors(self, result):
    if result is None:
      serviceStates = self.services.getAllServiceStates()
      if len(serviceStates) == 0:
        msg = 'Photoframe isn\'t ready yet\n\nPlease direct your webbrowser to\n\nhttp://%s:7777/\n\nand add one or more photo providers' % self.settings.get('local-ip')
      else:
        msg = 'Please direct your webbrowser to\n\nhttp://%s:7777/\n\nto complete the setup process:' % self.settings.get('local-ip')
        for svcName, state, additionalInfo in serviceStates:
          msg += "\n\n'"+svcName+"' --> "
          if state == 'OAUTH':
            msg += "Authorization required!"
          elif state == 'CONFIG':
            msg += "Configuration required!"
          elif state == 'NEED_KEYWORDS':
            msg += "Add one or more keywords (album names)!"
          elif state == 'NO_IMAGES':
            msg += "No images could be found!"
          
          if additionalInfo is not None:
            msg += "\n"+additionalInfo
          
      self.display.message(msg)
      self.imageOnScreen = False
      return True

    if result.error is not None:
      logging.debug('%s failed:\n\n%s' % (self.services.getLastUsedServiceName(), result.error))
      self.display.message('%s failed:\n\n%s' % (self.services.getLastUsedServiceName(), result.error))
      self.imageOnScreen = False
      return True
    return False

  def _colormatch(self, filenameProcessed):
    if self.colormatch.hasSensor():
      # For Now: Always process original image (no caching of colormatch-adjusted images)
      # 'colormatched_tmp.jpg' will be deleted after the image is displayed
      filenameTemp = os.path.join(self.settings.get('tempfolder'), "colormatched_tmp.jpg")
      if self.colormatch.adjust(filenameProcessed, filenameTemp):
        return filenameTemp
      logging.warning('Unable to adjust image to colormatch, using original')
    return filenameProcessed

  def process(self, filename):
    imageSizing = self.settings.getUser('imagesizing')
    if imageSizing == None or imageSizing == "none":
      return self._colormatch(filename)
    if imageSizing == 'blur':
      filenameProcessed = helper.makeFullframe(filename, self.settings.getUser('width'), self.settings.getUser('height'))
    elif imageSizing == 'zoom':
      filenameProcessed = helper.makeFullframe(filename, self.settings.getUser('width'), self.settings.getUser('height'), zoomOnly=True)
    elif imageSizing == 'auto':
      filenameProcessed = helper.makeFullframe(filename, self.settings.getUser('width'), self.settings.getUser('height'), autoChoose=True)
    return self._colormatch(filenameProcessed)

  def delayNextImage(self, time_process):
    # Delay before we show the image (but take processing into account)
    # This should keep us fairly consistent
    delay = self.settings.getUser('interval')
    if time_process < delay and self.imageOnScreen:
      self.delayer.wait(delay - time_process)
    elif not self.imageOnScreen:
      self.delayer.wait(1) # Always wait ONE second to avoid busy waiting)
    self.delayer.clear()

  def showPreloadedImage(self, filename, mimetype, imageId):
    if not self.skipPreloadedImage:
      if not os.path.isfile(filename):
        logging.warning("Trying to show image '%s', but file does not exist!"%filename)
        self.delayer.set()
        return
      self.display.image(filename)
      self.imageCurrent = filename
      self.imageMime = mimetype
      self.imageOnScreen = True
      self.services.memoryRemember(imageId)
      if "colormatched_tmp.jpg" in filename:
        os.unlink(filename)
    
    self.skipPreloadedImage = False

  def presentation(self):
    cacheFolder = path.CACHEFOLDER
    lessImportantDirs = ["blurred", "zoomed"]
    CacheManager.createDirs(cacheFolder, subDirs=lessImportantDirs)
    CacheManager.garbageCollect(cacheFolder, lessImportantDirs)

    self.services.getServices(readyOnly=True)

    if not slideshow.SHOWN_IP:
      self.startupScreen()

    logging.info('Starting presentation')
    i = 0
    while True:
      i += 1
      time_process = time.time()

      # Avoid showing images if the display is off
      if self.queryPowerFunc is not None and self.queryPowerFunc() is False:
        logging.info("Display is off, exit quietly")
        break
      
      if (i % 100) == 0:
        CacheManager.garbageCollect(cacheFolder, lessImportantDirs)
  
      displaySize = {'width': self.settings.getUser('width'), 'height': self.settings.getUser('height'), 'force_orientation': self.settings.getUser('force_orientation')}
      randomize = (not self.ignoreRandomize) and bool(self.settings.getUser('randomize_images'))
      self.ignoreRandomize = False

      result = self.services.servicePrepareNextItem(cacheFolder, self.supportedFormats, displaySize, randomize)
      if self.handleErrors(result):
        continue

      filenameOriginal = os.path.join(cacheFolder, result.id)
      filenameProcessed = self.process(filenameOriginal)
      if filenameProcessed is None:
        continue

      time_process = time.time() - time_process
      self.delayNextImage(time_process)
      self.handleEvents()
      self.showPreloadedImage(filenameProcessed, result.mimetype, result.id)

    self.thread = None
