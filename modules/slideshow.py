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
import time

from modules.helper import helper
from modules.network import RequestNoNetwork

class slideshow:
  SHOWN_IP = False
  EVENTS = ["nextImage", "prevImage", "nextAlbum", "prevAlbum", "settingsChange", "memoryForget", "clearCache", "forgetPreload"]

  def __init__(self, display, settings, colormatch, history):
    self.countdown = 0
    self.thread = None
    self.services = None
    self.display = display
    self.settings = settings
    self.colormatch = colormatch
    self.history = history
    self.cacheMgr = None
    self.void = open(os.devnull, 'wb')
    self.delayer = threading.Event()
    self.cbStopped = None

    self.eventList = []

    self.imageCurrent = None
    self.skipPreloadedImage = False

    self.historyIndex = -1
    self.minimumWait = 1

    self.supportedFormats = helper.getSupportedTypes()

    self.running = True

  def setCountdown(self, seconds):
    if seconds < 1:
      self.countdown = 0
    else:
      self.countdown = seconds

  def getCurrentImage(self):
    return self.imageCurrent.filename, self.imageCurrent.mimetype

  def getColorInformation(self):
    return {
      'temperature':self.colormatch.getTemperature(),
      'lux':self.colormatch.getLux()
      }

  def setServiceManager(self, services):
    self.services = services

  def setCacheManager(self, cacheMgr):
    self.cacheMgr = cacheMgr

  def shouldShow(self, show):
    logging.debug('shouldShow called with %d', show)
    if show:
      logging.debug('Calling start()')
      self.start()
    else:
      logging.debug('Calling stop()')
      self.stop()

  def start(self, blank=False):
    if blank:
      self.display.clear()

    if self.thread is None:
      self.thread = threading.Thread(target=self.presentation)
      self.thread.daemon = True
      self.running = True
      self.imageCurrent = None
      self.thread.start()

  def stop(self, cbStopped=None):
    self.cbStopped = cbStopped
    self.running = False
    self.imageCurrent = None
    self.delayer.set()

  def trigger(self):
    logging.debug('Causing immediate showing of image')
    self.cleanConfig = True
    self.delayer.set()

  def createEvent(self, cmd):
    if cmd not in slideshow.EVENTS:
      logging.warning("Unknown event '%s' received, will not act upon it" % cmd)
      return
    else:
      logging.debug('Event %s added to the queue', cmd)

    self.eventList.append(cmd)
    self.delayer.set()

  def handleEvents(self):
    showNext = True
    isRandom = self.settings.getUser("randomize_images")
    while len(self.eventList) > 0:
      event = self.eventList.pop(0)

      if event == 'memoryForget' or event == 'clearCache':
        if event == 'memoryForget':
          self.services.memoryForgetAll()
        if event == 'clearCache':
          self.cacheMgr.empty()
        if self.imageCurrent:
          self.imageCurrent = None
          self.display.clear()
          showNext = False
      elif event == "nextImage":
        logging.info('nextImage called, historyIndex is %d', self.historyIndex)
      elif event == "prevImage":
        if self.historyIndex == -1:
          # special case, first time, history holds what we're showing, so step twice
          self.historyIndex = min(self.history.getAvailable()-1, self.historyIndex+2)
        else:
          self.historyIndex = min(self.history.getAvailable()-1, self.historyIndex+1)
        logging.info('prevImage called, historyIndex is %d', self.historyIndex)
        showNext = False
      elif event == "nextAlbum":
        # FIX
        self.skipPreloadedImage = True
        self.services.nextAlbum()
        self.delayer.set()
      elif event == "prevAlbum":
        # FIX
        self.skipPreloadedImage = True
        self.services.prevAlbum()
        self.delayer.set()
      elif event == 'forgetPreload':
        self.skipPreloadedImage = True
    return showNext

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

  def waitForNetwork(self):
    self.imageCurrent = None
    helper.waitForNetwork(
      lambda: self.display.message('No internet connection\n\nCheck router, wifi-config.txt or cable'),
      lambda: self.settings.getUser('offline-behavior') != 'wait'
    )
    self.display.setConfigPage('http://%s:%d/' % (helper.getDeviceIp(), 7777))

  def handleErrors(self, result):
    if result is None:
      serviceStates = self.services.getAllServiceStates()
      if len(serviceStates) == 0:
        msg = 'Photoframe isn\'t ready yet\n\nPlease direct your webbrowser to\n\nhttp://%s:7777/\n\nand add one or more photo providers' % helper.getDeviceIp()
      else:
        msg = 'Please direct your webbrowser to\n\nhttp://%s:7777/\n\nto complete the setup process' % helper.getDeviceIp()
        for svcName, state, additionalInfo in serviceStates:
          msg += "\n\n"+svcName+": "
          if state == 'OAUTH':
            msg += "Authorization required"
          elif state == 'CONFIG':
            msg += "Configuration required"
          elif state == 'NEED_KEYWORDS':
            msg += "Add one or more keywords (album names)"
          elif state == 'NO_IMAGES':
            msg += "No images could be found"

          if additionalInfo is not None:
            msg += "\n\n"+additionalInfo

      self.display.message(msg)
      self.imageCurrent = None
      return True

    if result.error is not None:
      logging.debug('%s failed:\n\n%s' % (self.services.getLastUsedServiceName(), result.error))
      self.display.message('%s failed:\n\n%s' % (self.services.getLastUsedServiceName(), result.error))
      self.imageCurrent = None
      return True
    return False

  def _colormatch(self, filenameProcessed):
    if self.colormatch.hasSensor():
      # For Now: Always process original image (no caching of colormatch-adjusted images)
      # 'colormatched_tmp.jpg' will be deleted after the image is displayed
      p, f = os.path.split(filenameProcessed)
      ofile = os.path.join(p, "colormatch_" + f + '.png')
      if self.colormatch.adjust(filenameProcessed, ofile):
        os.unlink(filenameProcessed)
        return ofile
      logging.warning('Unable to adjust image to colormatch, using original')
    return filenameProcessed

  def remember(self, image):
    logging.debug('Commit this to history')
    self.history.add(image)

  def process(self, image):
    logging.debug('Processing %s', image.id)
    imageSizing = self.settings.getUser('imagesizing')

    # Make sure it's oriented correctly
    filename = helper.autoRotate(image.filename)

    # At this point, we have a good image, store it if allowed
    if image.cacheAllow and not image.cacheUsed:
      self.cacheMgr.setCachedImage(filename, image.getCacheId())

    # Frame it
    if imageSizing == 'blur':
      filename = helper.makeFullframe(filename, self.settings.getUser('width'), self.settings.getUser('height'))
    elif imageSizing == 'zoom':
      filename = helper.makeFullframe(filename, self.settings.getUser('width'), self.settings.getUser('height'), zoomOnly=True)
    elif imageSizing == 'auto':
      filename = helper.makeFullframe(filename, self.settings.getUser('width'), self.settings.getUser('height'), autoChoose=True)

    # Color match it
    return self._colormatch(filename)

  def delayNextImage(self, time_process):
    # Delay before we show the image (but take processing into account)
    # This should keep us fairly consistent
    delay = self.settings.getUser('interval')
    if time_process < delay and self.imageCurrent:
      self.delayer.wait(delay - time_process)
    elif not self.imageCurrent:
      self.delayer.wait(self.minimumWait) # Always wait ONE second to avoid busy waiting)
    self.delayer.clear()
    if self.imageCurrent:
      self.minimumWait = 1
    else:
      self.minimumWait = min(self.minimumWait * 2, 16)

  def showPreloadedImage(self, image):
    if not os.path.isfile(image.filename):
      logging.warning("Trying to show image '%s', but file does not exist!" % image.filename)
      self.delayer.set()
      return
    self.display.image(image.filename)
    self.imageCurrent = image

  def presentation(self):
    self.services.getServices(readyOnly=True)

    # Make sure we have network
    if not helper.hasNetwork() and self.settings.getUser('offline-behavior') == 'wait':
      self.waitForNetwork()

    if not slideshow.SHOWN_IP:
      self.startupScreen()

    logging.info('Starting presentation')
    i = 0
    result = None
    lastCfg = self.services.getConfigChange()
    while self.running:
      i += 1
      time_process = time.time()

      if (i % 10) == 0:
        self.cacheMgr.garbageCollect()

      displaySize = {'width': self.settings.getUser('width'), 'height': self.settings.getUser('height'), 'force_orientation': self.settings.getUser('force_orientation')}
      randomize = self.settings.getUser('randomize_images')

      try:
        if self.historyIndex == -1:
          result = self.services.servicePrepareNextItem(self.settings.get('tempfolder'), self.supportedFormats, displaySize, randomize)
          self.remember(result)
        else:
          logging.info('Fetching history image %d of %d', self.historyIndex, self.history.getAvailable())
          result = self.history.getByIndex(self.historyIndex)
          self.historyIndex = max(-1, self.historyIndex-1)
      except RequestNoNetwork:
        offline = self.settings.getUser('offline-behavior')
        if offline == 'wait':
          self.waitForNetwork()
          continue
        elif offline == 'ignore':
          pass

      if not self.handleErrors(result):
        filenameProcessed = self.process(result)
        result = result.copy().setFilename(filenameProcessed)
      else:
        result = None

      time_process = time.time() - time_process
      logging.debug('Took %f seconds to process, next image is %s', time_process, result.filename if result is not None else "None")
      self.delayNextImage(time_process)

      showNextImage = self.handleEvents()

      # Handle changes to config to avoid showing an image which is unexpected
      if self.services.getConfigChange() != lastCfg:
        logging.debug('Services have changed, skip next photo and get fresh one')
        self.skipPreloadedImage = True
        lastCfg = self.services.getConfigChange()

      if self.running and result is not None:
        # Skip this section if we were killed while waiting around
        if showNextImage and not self.skipPreloadedImage:
          self.showPreloadedImage(result)
        else:
          self.imageCurrent = None
          self.skipPreloadedImage = False
        logging.debug('Deleting temp file "%s"' % result.filename)
        os.unlink(result.filename)

    self.thread = None
    logging.info('slideshow has ended')

    # Callback if anyone was listening
    if self.cbStopped is not None:
      logging.debug('Stop required notification, so call them')
      tmp = self.cbStopped
      self.cbStopped = None
      tmp()

#TODO:
#- Once in history, STOP PRELOADING THE IMAGE, IT BREAKS THINGS BADLY
