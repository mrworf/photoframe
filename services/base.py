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
import hashlib
import os
import json
import random
import logging
import requests
import time
import uuid

from modules.oauth import OAuth
from modules.helper import helper
from modules.network import RequestResult
from modules.network import RequestNoNetwork
from modules.network import RequestInvalidToken
from modules.network import RequestExpiredToken
from modules.images import ImageHolder

from modules.memory import MemoryManager

# This is the base implementation of a service. It provides all the
# basic features like OAuth and Authentication as well as state and
# all other goodies. Most calls will not be overriden unless specified.
#
# Inherit from this class to create a new service.
#
# Do not access items prefixed with underscore since they should be
# considered internal to this class and may change.
#
# Use the exposed functions as needed to get the data you want.
#
class BaseService:
  REFRESH_DELAY = 60*60 # Number of seconds before we refresh the index in case no photos
  SERVICE_DEPRECATED = False

  STATE_ERROR = -1
  STATE_UNINITIALIZED = 0

  STATE_DO_CONFIG = 1
  STATE_DO_OAUTH = 2
  STATE_NEED_KEYWORDS = 3
  STATE_NO_IMAGES = 4

  STATE_READY = 999

  def __init__(self, configDir, id, name, needConfig=False, needOAuth=False):
    # MUST BE CALLED BY THE IMPLEMENTING CLASS!
    self._ID = id
    self._NAME = name
    self._OAUTH = None
    self._CACHEMGR = None

    self._CURRENT_STATE = BaseService.STATE_UNINITIALIZED
    self._ERROR = None

    # NUM_IMAGES keeps track of how many images are being provided by each keyword
    # As for now, unsupported images (mimetype, orientation) and already displayed images are NOT excluded due to simplicity,
    # but it should still serve as a rough estimate to ensure that every image has a similar chance of being shown in "random_image_mode"!
    # NEXT_SCAN is used to determine when a keyword should be re-indexed. This used in the case number of photos are zero to avoid hammering
    # services.
    self._STATE = {
        '_OAUTH_CONFIG' : None,
        '_OAUTH_CONTEXT' : None,
        '_CONFIG' : None,
        '_KEYWORDS' : [],
        '_NUM_IMAGES' : {},
        '_NEXT_SCAN' : {},
        '_EXTRAS' : None,
        '_INDEX_IMAGE' : 0,
        '_INDEX_KEYWORD' : 0
    }
    self._NEED_CONFIG = needConfig
    self._NEED_OAUTH = needOAuth

    self._DIR_BASE = self._prepareFolders(configDir)
    self._DIR_PRIVATE = os.path.join(self._DIR_BASE, 'private')
    self._FILE_STATE = os.path.join(self._DIR_BASE, 'state.json')

    self.memory = MemoryManager(os.path.join(self._DIR_BASE, 'memory'))

    self.loadState()
    self.preSetup()

  def setCacheManager(self, cacheMgr):
    self._CACHEMGR = cacheMgr

  def _prepareFolders(self, configDir):
    basedir = os.path.join(configDir, self._ID)
    if not os.path.exists(basedir):
      os.mkdir(basedir)
    if not os.path.exists(basedir + '/memory'):
      os.mkdir(basedir + '/memory')
    if not os.path.exists(basedir + '/private'):
      os.mkdir(basedir + '/private')
    return basedir

  ###[ Used by service to do any kind of house keeping ]###########################

  def preSetup(self):
    # If you need to do anything before initializing, override this
    # NOTE! No auth or oauth has been done at this point, only state has been loaded
    pass

  def postSetup(self):
    # If you need to do anything right after initializing, override this
    # NOTE! At this point, any auth and/or oauth will have been performed. State is not saved after this call
    pass

  ###[ Used by photoframe to determinte what to do next ]###########################

  def updateState(self):
    # Determines what the user needs to do next to configure this service
    # if this doesn't return ready, caller must take appropiate action
    if self._NEED_OAUTH and self._OAUTH is None:
      self._OAUTH = OAuth(self._setOAuthToken, self._getOAuthToken, self.getOAuthScope(), self._ID)
      if self._STATE['_OAUTH_CONFIG'] is not None:
        self._OAUTH.setOAuth(self._STATE['_OAUTH_CONFIG'])
        self.postSetup()

    if self._NEED_CONFIG and not self.hasConfiguration():
      self._CURRENT_STATE = BaseService.STATE_DO_CONFIG
    elif self._NEED_OAUTH and (not self.hasOAuthConfig or not self.hasOAuth()):
      self._CURRENT_STATE = BaseService.STATE_DO_OAUTH
    elif self.needKeywords() and len(self.getKeywords()) == 0:
      self._CURRENT_STATE = BaseService.STATE_NEED_KEYWORDS
    elif self.getImagesTotal() == 0:
      self._CURRENT_STATE = BaseService.STATE_NO_IMAGES
    else:
      self._CURRENT_STATE = BaseService.STATE_READY

    return self._CURRENT_STATE

  ###[ Allows loading/saving of service state ]###########################

  def loadState(self):
    # Load any stored state data from storage
    # Normally you don't override this
      if os.path.exists(self._FILE_STATE):
        try:
          with open(self._FILE_STATE, 'r') as f:
            self._STATE.update( json.load(f) )
        except:
          logging.exception('Unable to load state for service')
          os.unlink(self._FILE_STATE)

  def saveState(self):
    # Stores the state data under the unique ID for
    # this service provider's instance
    # normally you don't override this
    with open(self._FILE_STATE, 'w') as f:
      json.dump(self._STATE, f)

  ###[ Get info about instance ]###########################

  def getName(self):
    # Retrieves the name of this instance
    return self._NAME

  def setName(self, newName):
    self._NAME = newName

  def getId(self):
    return self._ID

  def getImagesTotal(self):
    # return the total number of images provided by this service
    sum = 0
    if self.needKeywords():
      for keyword in self.getKeywords():
        if keyword not in self._STATE["_NUM_IMAGES"] or keyword not in self._STATE['_NEXT_SCAN'] or self._STATE['_NEXT_SCAN'][keyword] < time.time():
          logging.debug('Keywords either not scanned or we need to scan now')
          self._getImagesFor(keyword) # Will make sure to get images
          self._STATE['_NEXT_SCAN'][keyword] = time.time() + self.REFRESH_DELAY
        sum = sum + self._STATE["_NUM_IMAGES"][keyword]  
    return sum

  def getImagesSeen(self):
    count = 0
    if self.needKeywords():
      for keyword in self.getKeywords():
        count += self.memory.count(keyword)
    return count

  def getImagesRemaining(self):
    return self.getImagesTotal() - self.getImagesSeen()

  def getMessages(self):
    # override this if you wish to show a message associated with
    # the provider's instance. Return None to hide
    # Format: [{'level' : 'INFO', 'message' : None, 'link' : None}]
    msgs = []
    if self._CURRENT_STATE in [self.STATE_NEED_KEYWORDS]: # , self.STATE_NO_IMAGES]:
      msgs.append(
          {
              'level': 'INFO',
              'message' : 'Please add one or more items in order to show photos from this provider (see help button)',
              'link': None
          }
      )
    if 0 in self._STATE["_NUM_IMAGES"].values():
      # Find first keyword with zero (unicode issue)
      removeme = []
      for keyword in self._STATE["_KEYWORDS"]:
        if self._STATE["_NUM_IMAGES"][keyword] == 0:
          removeme.append(keyword)
      msgs.append(
          {
              'level': 'WARNING',
              'message': 'The following keyword(s) do not yield any photos: %s' % ', '.join(map(u'"{0}"'.format, removeme)),
              'link': None
          }
      )
    return msgs

  def explainState(self):
    # override this if you wish to show additional on-screen information for a specific state
    # return String
    return None

  ###[ All the OAuth functionality ]###########################

  def getOAuthScope(self):
    # *Override* to define any needed OAuth scope
    # must return array of string(s)
    return None

  def setOAuthConfig(self, config):
    # Provides OAuth config data for linking.
    # Without this information, OAuth cannot be done.
    # If config is invalid, returns False
    self._STATE['_OAUTH_CONFIG'] = config
    if self._OAUTH is not None:
      self._OAUTH.setOAuth(self._STATE['_OAUTH_CONFIG'])
      self.postSetup()

    self.saveState()
    return True

  def helpOAuthConfig(self):
    return 'Should explain what kind of content to provide'

  def hasOAuthConfig(self):
    # Returns true/false if we have a config for oauth
    return self._STATE['_OAUTH_CONFIG'] is not None

  def hasOAuth(self):
    # Tests if we have a functional OAuth link,
    # returns False if we need to set it up
    return self._STATE['_OAUTH_CONTEXT'] is not None

  def invalidateOAuth(self):
    # Removes previously negotiated OAuth
    self._STATE['_OAUTH_CONFIG'] = None
    self._STATE['_OAUTH_CONTEXT'] = None
    self.saveState()

  def startOAuth(self):
    # Returns a HTTP redirect to begin OAuth or None if
    # oauth isn't configured. Normally not overriden
    return self._OAUTH.initiate()

  def finishOAuth(self, url):
    # Called when OAuth sequence has completed
    self._OAUTH.complete(url)
    self.saveState()

  def _setOAuthToken(self, token):
    self._STATE['_OAUTH_CONTEXT'] = token
    self.saveState()

  def _getOAuthToken(self):
    return self._STATE['_OAUTH_CONTEXT']

  def migrateOAuthToken(self, token):
    if self._STATE['_OAUTH_CONTEXT'] is not None:
      logging.error('Cannot migrate token, already have one!')
      return
    logging.debug('Setting token to %s' % repr(token))
    self._STATE['_OAUTH_CONTEXT'] = token
    self.saveState()

  ###[ For services which require static auth ]###########################

  def validateConfiguration(self, config):
    # Allow service to validate config, if correct, return None
    # If incorrect, return helpful error message.
    # config is a map with fields and their values
    return 'Not overriden yet but config is enabled'

  def setConfiguration(self, config):
    # Setup any needed authentication data for this
    # service.
    self._STATE['_CONFIG'] = config
    self.saveState()

  def getConfiguration(self):
    return self._STATE['_CONFIG']

  def hasConfiguration(self):
    # Checks if it has auth data
    return self._STATE['_CONFIG'] != None

  def getConfigurationFields(self):
    # Returns a key/value map with:
    # "field" => [ "type" => "STR/INT", "name" => "Human readable", "description" => "Longer text" ]
    # Allowing UX to be dynamically created
    # Supported field types are: STR, INT, PW (password means it will obscure it on input)
    return {'username' : {'type':'STR', 'name':'Username', 'description':'Username to use for login'}}

  ###[ Keyword management ]###########################

  def validateKeywords(self, keywords):
    # Quick check, don't allow duplicates!
    if keywords in self.getKeywords():
      logging.error('Keyword is already in list')
      return {'error': 'Keyword already in list', 'keywords': keywords}

    return {'error':None, 'keywords': keywords}

  def addKeywords(self, keywords):
    # This is how the user will configure it, this adds a new set of keywords to this
    # service module. Return none on success, string with error on failure
    keywords = keywords.strip()

    if not self.needKeywords():
      return {'error' : 'Doesn\'t use keywords', 'keywords' : keywords}
    if keywords == '':
      return {'error' : 'Keyword string cannot be empty', 'kewords' : keywords}

    tst = self.validateKeywords(keywords)
    if tst['error'] is None:
      keywords = tst['keywords']
      self._STATE['_KEYWORDS'].append(keywords)
      self.saveState()
    return tst

  def getKeywords(self):
    # Returns an array of all keywords
    return self._STATE['_KEYWORDS']

  def getKeywordSourceUrl(self, index):
    # Override to provide a source link
    return None

  def getKeywordDetails(self, index):
    # Override so we can tell more
    # Format of data is:
    # ('short': short, 'long' : ["line1", "line2", ...]) where short is a string and long is a string array
    return None

  def hasKeywordDetails(self):
    # Override so we can tell more
    return False

  def hasKeywordSourceUrl(self):
    # Override to provide source url support
    return False

  def removeKeywords(self, index):
    if index < 0 or index > (len(self._STATE['_KEYWORDS'])-1):
      logging.error('removeKeywords: Out of range %d' % index)
      return False
    kw = self._STATE['_KEYWORDS'].pop(index)
    if kw in self._STATE['_NUM_IMAGES']:
      del self._STATE['_NUM_IMAGES'][kw]
    self.saveState()
    # Also kill the memory of this keyword
    self.memory.forget(kw)
    return True

  def needKeywords(self):
    # Some services don't have keywords. Override this to return false
    # to remove the keywords options.
    return True

  def helpKeywords(self):
    return 'Has not been defined'

  def getRandomKeywordIndex(self):
    # select keyword index at random but weighted by the number of images of each album
    totalImages = self.getImagesTotal()
    if totalImages == 0:
      return 0
    numImages = [self._STATE['_NUM_IMAGES'][kw] for kw in self._STATE['_NUM_IMAGES']]
    return helper.getWeightedRandomIndex(numImages)

  def getKeywordLink(self, index):
    if index < 0 or index > (len(self._STATE['_KEYWORDS'])-1):
      logging.error('removeKeywords: Out of range %d' % index)
      return

  ###[ Extras - Allows easy access to config ]#################

  def getExtras(self):
    return self._STATE['_EXTRAS']

  def setExtras(self, data):
    self._STATE['_EXTRAS'] = data
    self.saveState()

  ###[ Actual hard work ]###########################

  def prepareNextItem(self, destinationFile, supportedMimeTypes, displaySize, randomize):
    # This call requires the service to download the next item it
    # would like to show. The destinationFile has to be used as where to save it
    # and you are only allowed to provide content listed in the supportedMimeTypes.
    # displaySize holds the keys width & height to provide a hint for the service to avoid downloading HUGE files
    # Return for this function is a key/value map with the following MANDATORY
    # fields:
    #  "id" : a unique - preferably not-changing - ID to identify the same image in future requests, e.g. hashString(imageUrl)
    #  "mimetype" : the filetype you downloaded, for example "image/jpeg"
    #  "error" : None or a human readable text string as to why you failed
    #  "source" : Link to where the item came from or None if not provided
    #
    # NOTE! If you need to index anything before you can get the first item, this would
    # also be the place to do it.
    #
    # If your service uses keywords (as albums) 'selectImageFromAlbum' of the baseService class should do most of the work for you
    # You will probably only need to implement 'getImagesFor' and 'addUrlParams'

    if self.needKeywords():
      if len(self.getKeywords()) == 0:
        return ImageHolder().setError('No albums have been specified')

      if randomize:
        result = self.selectRandomImageFromAlbum(destinationFile, supportedMimeTypes, displaySize)
      else:
        result = self.selectNextImageFromAlbum(destinationFile, supportedMimeTypes, displaySize)
      if result is None:
        result = ImageHolder().setError('No (new) images could be found')
    else:
      result = ImageHolder().setError('prepareNextItem() not implemented')

    return result

  def _getImagesFor(self, keyword):
    images = self.getImagesFor(keyword)
    if images is None:
      logging.warning('Function returned None, this is used sometimes when a temporary error happens. Still logged')

    if images is not None and len(images) > 0:
      self._STATE["_NUM_IMAGES"][keyword] = len(images)
      # Change next time for refresh (postpone if you will)
      self._STATE['_NEXT_SCAN'][keyword] = time.time() + self.REFRESH_DELAY
    else:
      self._STATE["_NUM_IMAGES"][keyword] = 0
    return images

  def getImagesFor(self, keyword):
    # You need to override this function if your service needs keywords and
    # you want to use 'selectImageFromAlbum' of the baseService class
    # This function should collect data about all images matching a specific keyword
    # Return for this function is a list of multiple key/value maps each containing the following MANDATORY fields:
    # "id":       a unique - preferably not-changing - ID to identify the same image in future requests, e.g. hashString(imageUrl)
    # "url":      Link to the actual image file
    # "sources":  Link to where the item came from or None if not provided
    # "mimetype": the filetype of the image, for example "image/jpeg"
    #             can be None, but you should catch unsupported mimetypes after the image has downloaded (example: svc_simpleurl.py)
    # "size":     a key/value map containing "width" and "height" of the image
    #             can be None, but the service won't be able to determine a recommendedImageSize for 'addUrlParams'
    # "filename": the original filename of the image or None if unknown (only used for debugging purposes)
    # "error":    If present, will generate an error shown to the user with the text within this key as the message

    return [ ImageHolder().setError('getImagesFor() not implemented') ]

  def _clearImagesFor(self, keyword):
    self._STATE["_NUM_IMAGES"].pop(keyword, None)
    self._STATE['_NEXT_SCAN'].pop(keyword, None)
    self.memory.forget(keyword)
    self.clearImagesFor(keyword)

  def clearImagesFor(self, keyword):
    # You can hook this function to do any additional needed cleanup
    # keyword is the item for which you need to clear the images for
    pass

  def freshnessImagesFor(self, keyword):
    # You need to implement this function if you intend to support refresh of content
    # keyword is the item for which you need to clear the images for. Should return age of content in hours
    return 0

  def getContentUrl(self, image, hints):
    # Allows a content provider to do extra operations as needed to
    # extract the correct URL.
    #
    # image is an image object
    #
    # hints is a map holding various hints to be used by the content provider.
    # "size" holds "width" and "height" of the ideal image dimensions based on display size
    # "display" holds "width" and "height" of the physical display
    #
    # By default, if you don't override this, it will simply use the image.url as the return
    return image.url

  ###[ Helpers ]######################################

  def selectRandomImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize):
    # chooses an album and selects an image from that album. Returns an image object or None
    # if no images are available.

    keywords = self.getKeywords()
    index = self.getRandomKeywordIndex()

    # if current keywordList[index] does not contain any new images --> just run through all albums
    for i in range(0, len(keywords)):
      self.setIndex(keyword = (index + i) % len(keywords))
      keyword = keywords[self.getIndexKeyword()]

      # a provider-specific implementation for 'getImagesFor' is obligatory!
      # We use a wrapper to clear things up
      images = self._getImagesFor(keyword)
      if images is None or len(images) == 0:
        self.setIndex(0)
        continue
      elif images[0].error is not None:
        # Something went wrong, only return first image since it holds the error
        return images[0]
      self.saveState()

      image = self.selectRandomImage(keyword, images, supportedMimeTypes, displaySize)
      if image is None:
        self.setIndex(0)
        continue

      return self.fetchImage(image, destinationDir, supportedMimeTypes, displaySize)
    return None

  def generateFilename(self):
    return str(uuid.uuid4())

  def fetchImage(self, image, destinationDir, supportedMimeTypes, displaySize):
    filename = os.path.join(destinationDir, self.generateFilename())

    if image.cacheAllow:
      # Look it up in the cache mgr
      if self._CACHEMGR is None:
        logging.error('CacheManager is not available')
      else:
        cacheFile = self._CACHEMGR.getCachedImage(image.getCacheId(), filename)
        if cacheFile:
          image.setFilename(cacheFile)
          image.cacheUsed = True

    if not image.cacheUsed:
      recommendedSize = self.calcRecommendedSize(image.dimensions, displaySize)
      if recommendedSize is None:
        recommendedSize = displaySize
      url = self.getContentUrl(image, {'size' : recommendedSize, 'display' : displaySize})
      if url is None:
        return ImageHolder().setError('Unable to download image, no URL')

      try:
        result = self.requestUrl(url, destination=filename)
      except (RequestResult.RequestExpiredToken, RequestInvalidToken):
        logging.exception('Cannot fetch due to token issues')
        result = RequestResult().setResult(RequestResult.OAUTH_INVALID)
        self._OAUTH = None
      except requests.exceptions.RequestException:
        logging.exception('request to download image failed')
        result = RequestResult().setResult(RequestResult.NO_NETWORK)

      if not result.isSuccess():
        return ImageHolder().setError('%d: Unable to download image!' % result.httpcode)
      else:
        image.setFilename(filename)
    if image.filename is not None:
      image.setMimetype(helper.getMimetype(image.filename))
    return image

  def selectNextImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize):
    # chooses an album and selects an image from that album. Returns an image object or None
    # if no images are available.

    keywordList = self.getKeywords()
    keywordCount = len(keywordList)
    index = self.getIndexKeyword()

    # if current keywordList[index] does not contain any new images --> just run through all albums
    for i in range(0, keywordCount):
      if (index + i) >= keywordCount:
        # (non-random image order): return if the last album is exceeded --> serviceManager should use next service
        break
      self.setIndex(keyword = (index + i) % keywordCount)
      keyword = keywordList[self.getIndexKeyword()]

      # a provider-specific implementation for 'getImagesFor' is obligatory!
      # We use a wrapper to clear things up
      images = self._getImagesFor(keyword)
      if images is None or len(images) == 0:
        self.setIndex(0)
        continue
      elif images[0].error is not None:
        # Something went wrong, only return first image since it holds the error
        return images[0]
      self.saveState()

      image = self.selectNextImage(keyword, images, supportedMimeTypes, displaySize)
      if image is None:
        self.setIndex(0)
        continue

      return self.fetchImage(image, destinationDir, supportedMimeTypes, displaySize)
    return None

  def selectRandomImage(self, keywords, images, supportedMimeTypes, displaySize):
    imageCount = len(images)
    index = random.SystemRandom().randint(0, imageCount-1)

    logging.debug('There are %d images total' % imageCount)
    for i in range(0, imageCount):
      image = images[(index + i) % imageCount]

      orgFilename = image.filename if image.filename is not None else image.id
      if self.memory.seen(image.id, keywords):
        logging.debug("Skipping already displayed image '%s'!" % orgFilename)
        continue

      # No matter what, we need to track that we considered this image
      self.memory.remember(image.id, keywords)

      if not self.isCorrectOrientation(image.dimensions, displaySize):
        logging.debug("Skipping image '%s' due to wrong orientation!" % orgFilename)
        continue
      if image.mimetype is not None and image.mimetype not in supportedMimeTypes:
        # Make sure we don't get a video, unsupported for now (gif is usually bad too)
        logging.debug('Skipping unsupported media: %s' % (image.mimetype))
        continue

      self.setIndex((index + i) % imageCount)
      return image
    return None

  def selectNextImage(self, keywords, images, supportedMimeTypes, displaySize):
    imageCount = len(images)
    index = self.getIndexImage()

    for i in range(index, imageCount):
      image = images[i]

      orgFilename = image.filename if image.filename is not None else image.id
      if self.memory.seen(image.id, keywords):
        logging.debug("Skipping already displayed image '%s'!" % orgFilename)
        continue

      # No matter what, we need to track that we considered this image
      self.memory.remember(image.id, keywords)

      if not self.isCorrectOrientation(image.dimensions, displaySize):
        logging.debug("Skipping image '%s' due to wrong orientation!" % orgFilename)
        continue
      if image.mimetype is not None and image.mimetype not in supportedMimeTypes:
        # Make sure we don't get a video, unsupported for now (gif is usually bad too)
        logging.debug('Skipping unsupported media: %s' % (image.mimetype))
        continue

      self.setIndex(i)
      return image
    return None

  def requestUrl(self, url, destination=None, params=None, data=None, usePost=False):
    result = RequestResult()

    if self._OAUTH is not None:
      # Use OAuth path
      try:
        result = self._OAUTH.request(url, destination, params, data=data, usePost=usePost)
      except (RequestExpiredToken, RequestInvalidToken):
        logging.exception('Cannot fetch due to token issues')
        result = RequestResult().setResult(RequestResult.OAUTH_INVALID)
        self.invalidateOAuth()
      except requests.exceptions.RequestException:
        logging.exception('request to download image failed')
        result = RequestResult().setResult(RequestResult.NO_NETWORK)
    else:
      tries = 0
      while tries < 5:
        try:
          if usePost:
            r = requests.post(url, params=params, json=data, timeout=180)
          else:
            r = requests.get(url, params=params, timeout=180)
          break
        except:
          logging.exception('Issues downloading')
        time.sleep(tries / 10) # Back off 10, 20, ... depending on tries
        tries += 1
        logging.warning('Retrying again, attempt #%d', tries)

      if tries == 5:
        logging.error('Failed to download due to network issues')
        raise RequestNoNetwork

      if r:
        result.setHTTPCode(r.status_code).setHeaders(r.headers).setResult(RequestResult.SUCCESS)

        if destination is None:
          result.setContent(r.content)
        else:
          with open(destination, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
              f.write(chunk)
          result.setFilename(destination)
    return result

  def calcRecommendedSize(self, imageSize, displaySize):
    # The recommended image size is basically the displaySize extended along one side to match the aspect ratio of your image
    # e.g. displaySize: 1920x1080, imageSize: 4000x3000 --> recImageSize: 1920x1440
    # If possible every request url should contain the recommended width/height as parameters to reduce image file sizes.
    # That way the image provider does most of the scaling (instead of the rather slow raspberryPi),
    # the image only needs to be cropped (zoomOnly) or downscaled a little bit (blur / do nothing) during post-processing.

    if imageSize is None or "width" not in imageSize or "height" not in imageSize:
      return None

    oar = float(imageSize['width'])/float(imageSize['height'])
    dar = float(displaySize['width'])/float(displaySize['height'])

    newImageSize = {}
    if imageSize['width'] > displaySize['width'] and imageSize['height'] > displaySize['height']:
      if oar <= dar:
        newImageSize['width'] = displaySize['width']
        newImageSize['height'] = int(float(displaySize['width']) / oar)
      else:
        newImageSize['width'] = int(float(displaySize['height']) * oar)
        newImageSize['height'] = displaySize['height']
    else:
      newImageSize['width'] = imageSize['width']
      newImageSize['height'] = imageSize['height']

    return newImageSize

  def isCorrectOrientation(self, imageSize, displaySize):
    if displaySize['force_orientation'] == 0:
      return True
    if imageSize is None or "width" not in imageSize or "height" not in imageSize:
      # always show image if size is unknown!
      return True

    # NOTE: square images are being treated as portrait-orientation
    image_orientation = 0 if int(imageSize["width"]) > int(imageSize["height"]) else 1
    display_orientation = 0 if displaySize["width"] > displaySize["height"] else 1

    return image_orientation == display_orientation

  def getStoragePath(self):
    return self._DIR_PRIVATE

  def hashString(self, text):
    if type(text) is not unicode:
      # make sure it's unicode
      a = text.decode('ascii', errors='replace')
    else:
      a = text
    a = a.encode('utf-8', errors='replace')
    return hashlib.sha1(a).hexdigest()

  def createImageHolder(self):
    return ImageHolder()

  def setIndex(self, image = None, keyword = None, addImage = 0, addKeyword = 0):
    wrapped = False
    if addImage != 0:
      self._STATE['_INDEX_IMAGE'] += addImage
    elif image is not None:
      self._STATE['_INDEX_IMAGE'] = image
    if addKeyword != 0:
      self._STATE['_INDEX_KEYWORD'] += addKeyword
    elif keyword is not None:
      self._STATE['_INDEX_KEYWORD'] = keyword

    # Sanity
    if self._STATE['_INDEX_KEYWORD'] > len(self._STATE['_KEYWORDS']):
      if addKeyword != 0:
        self._STATE['_INDEX_KEYWORD'] = 0 # Wraps when adding
        wrapped = True
      else:
        self._STATE['_INDEX_KEYWORD'] = len(self._STATE['_KEYWORDS'])-1
    elif self._STATE['_INDEX_KEYWORD'] < 0:
      if addKeyword != 0:
        self._STATE['_INDEX_KEYWORD'] = len(self._STATE['_KEYWORDS'])-1 # Wraps when adding
        wrapped = True
      else:
        self._STATE['_INDEX_KEYWORD'] = 0
    return wrapped

  def getIndexImage(self):
    return self._STATE['_INDEX_IMAGE']

  def getIndexKeyword(self):
    return self._STATE['_INDEX_KEYWORD']

  ###[ Slideshow controls ]=======================================================

  def nextAlbum(self):
    # skip to the next album
    # return False if service is out of albums to tell the serviceManager that it should use the next Service instead
    return not self.setIndex(0, addKeyword=1)

  def prevAlbum(self):
    # skip to the previous album
    # return False if service is already on its first album to tell the serviceManager that it should use the previous Service instead
    return not self.setIndex(0, addKeyword=-1)
