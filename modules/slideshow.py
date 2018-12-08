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
  def __init__(self, display, settings, oauth, colormatch):
    self.queryPowerFunc = None
    self.thread = None
    self.display = display
    self.settings = settings
    self.oauth = oauth
    self.colormatch = colormatch
    self.imageCurrent = None
    self.imageMime = None
    self.void = open(os.devnull, 'wb')

  def getCurrentImage(self):
    return self.imageCurrent, self.imageMime

  def getColorInformation(self):
    return {
      'temperature':self.colormatch.getTemperature(),
      'lux':self.colormatch.getLux()
      }

  def setQueryPower(self, func):
    self.queryPowerFunc = func

  def start(self, blank=False):
    if blank:
      self.display.clear()

    if self.settings.get('oauth_token') is None:
      self.display.message('Photoalbum isn\'t ready yet\n\nPlease direct your webbrowser to\n\nhttp://%s:7777/' % self.settings.get('local-ip'))
      logging.info('You need to link your photoalbum first')
    elif self.thread is None:
      self.thread = threading.Thread(target=self.presentation)
      self.thread.daemon = True
      self.thread.start()

  def presentation(self):
    logging.info('Starting presentation')
    seen = []
    delay = 0
    while True:
      # Avoid showing images if the display is off
      if self.queryPowerFunc is not None and self.queryPowerFunc() is False:
        logging.info("Display is off, exit quietly")
        break

      imgs = cache = memory = None
      index = self.settings.getKeyword()
      tries = 20
      time_process = time.time()
      while tries > 0:
        tries -= 1
        if len(seen) == self.settings.countKeywords():
          # We've viewed all images, reset
          logging.info('All images we have keywords for have been seen, restart')
          logging.info('Seen holds: %s', repr(seen))
          logging.info('Settings.countKeywords() = %d', self.settings.countKeywords())

          for saw in seen:
            r = remember(saw, 0)
            r.debug()
            r.forget()
          r = remember('/tmp/overallmemory.json', 0)
          r.debug()
          r.forget()
          if self.settings.getUser('refresh-content') == 0:
            logging.info('Make sure we refresh all images now')
            for saw in seen:
              os.remove(saw)
          seen = []


        keyword = self.settings.getKeyword(index)
        imgs, cache = self.getImages(keyword)
        if imgs is None:
          # Try again!
          continue

        # If we've seen all images for this keyword, skip to next
        if cache in seen:
          index += 1
          if index == self.settings.countKeywords():
            index = 0
          continue

        memory = remember(cache, len(imgs['feed']['entry']))

        if not imgs or memory.seenAll():
          if not imgs:
            logging.error('Failed to load image list for keyword %s' % keyword)
          elif memory.seenAll():
            seen.append(cache)
            logging.debug('All images for keyword %s has been shown' % keyword)
          continue

        # Now, lets make sure we didn't see this before
        uri, mime, title, ts = self.pickImage(imgs, memory)
        if uri == '':
          logging.warning('No image was returned from pickImage')
          continue # Do another one (well, it means we exhausted available images for this keyword)

        # Avoid having duplicated because of overlap from keywords
        memory = remember('/tmp/overallmemory.json', 0)
        if memory.seen(uri):
          continue
        else:
          memory.saw(uri)

        ext = helper.getExtension(mime)
        if ext is not None:
          filename = os.path.join(self.settings.get('tempfolder'), 'image.%s' % ext)
          if self.downloadImage(uri, filename):
            self.imageCurrent = filename
            self.imageMime = mime
            break
          else:
            logging.warning('Failed to download image, trying another one')
        else:
          logging.warning('Mime type %s isn\'t supported' % mime)

      time_process = time.time() - time_process

      # Delay before we show the image (but take processing into account)
      # This should keep us fairly consistent
      if time_process < delay:
        time.sleep(delay - time_process)
      if tries == 0:
        self.display.message('Issues showing images\n\nCheck network and settings')
      else:
        self.display.image(self.imageCurrent)
        os.remove(self.imageCurrent)

      delay = self.settings.getUser('interval')
    self.thread = None

  def pickImage(self, images, memory):
    ext = ['jpg','png','dng','jpeg','gif','bmp']
    count = len(images['feed']['entry'])

    i = random.SystemRandom().randint(0,count-1)
    while not memory.seenAll():
      proposed = images['feed']['entry'][i]['content']['src']
      if not memory.seen(proposed):
        memory.saw(proposed)
        entry = images['feed']['entry'][i]
        # Make sure we don't get a video, unsupported for now (gif is usually bad too)
        if 'image' in entry['content']['type'] and 'gphoto$videostatus' not in entry:
          break
        elif 'gphoto$videostatus' in entry:
          logging.debug('Image is thumbnail for videofile')
        else:
          logging.warning('Unsupported media: %s (video = %s)' % (entry['content']['type'], repr('gphoto$videostatus' in entry)))
      else:
        i += 1
        if i == count:
          i = 0

    if memory.seenAll():
      logging.error('Failed to find any image, abort')
      return ('', '', '', 0)

    title = entry['title']['$t']
    parts = title.lower().split('.')
    if len(parts) > 0 and parts[len(parts)-1] in ext:
      # Title isn't title, it's a filename
      title = ""
    uri = entry['content']['src']
    timestamp = datetime.datetime.fromtimestamp((float)(entry['gphoto$timestamp']['$t']) / 1000)
    mime = entry['content']['type']

    # Due to google's unwillingness to return what I own, we need to hack the URI
    uri = uri.replace('/s1600/', '/s%s/' % self.settings.getUser('width'), 1)

    return (uri, mime, title, timestamp)

  def getImages(self, keyword):
    # Create filename from keyword
    filename = hashlib.new('sha1')
    filename.update(repr(keyword))
    filename = filename.hexdigest() + ".json"
    filename = os.path.join(self.settings.get('tempfolder'), filename)

    if os.path.exists(filename) and self.settings.getUser('refresh-content') > 0: # Check age!
      age = math.floor( (time.time() - os.path.getctime(filename)) / 3600)
      if age >= self.settings.getUser('refresh-content'):
        logging.debug('File too old, %dh > %dh, refreshing' % (age, self.settings.getUser('refresh-content')))
        os.remove(filename)
        # Make sure we don't remember since we're refreshing
        memory = remember(filename, 0)
        memory.forget()

    if not os.path.exists(filename):
      # check if keyword is album
      url = 'https://photoslibrary.googleapis.com/v1/albums'
      data = self.oauth.request(url)
      albumid = None
      for i in range(len(data['albums'])):
        if data['albums'][i]['title'] == keyword:
          albumid = data['albums'][i][id]
      
      # fallback to all pictures if album not available
      if albumid is not None:
        params = {
          'albumId' : albumid,
          'pageSize' : self.settings.get('no_of_pic'),
        }
      else:
        params = {
          'pageSize' : self.settings.get('no_of_pic'),
          'filters': {
            'mediaTypeFilter': {
              'mediaTypes': [
                'PHOTO'
              ]
            }
          }
        }
      # Request albums      
      url = 'https://photoslibrary.googleapis.com/v1/mediaItems:search'
      logging.debug('Downloading image list for %s...' % keyword)
      data = self.oauth.request(url, params=params,post=True)
    
      if data.status_code != 200:
        logging.warning('Requesting photo failed with status code %d (%s)', data.status_code, data.reason)
        return None, filename
      with open(filename, 'w') as f:
        f.write(data.content)
    images = None
    try:
      with open(filename) as f:
        images = json.load(f)['mediaItems']
      logging.debug('Loaded %d images into list' % len(images))
      return images, filename
    except:
      logging.exception('Failed to load images')
      os.remove(filename)
      return None, filename

  def downloadImage(self, uri, dest):
    logging.debug('Downloading %s...' % uri)
    filename, ext = os.path.splitext(dest)
    temp = "%s-org%s" % (filename, ext)
    if self.oauth.request(uri, destination=temp):
      helper.makeFullframe(temp, self.settings.getUser('width'), self.settings.getUser('height'))
      if self.colormatch.hasSensor():
        if not self.colormatch.adjust(temp, dest):
          logging.warning('Unable to adjust image to colormatch, using original')
          os.rename(temp, dest)
        else:
          os.remove(temp)
      else:
        os.rename(temp, dest)
      return True
    else:
      return False

