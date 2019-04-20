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

from modules.oauth import OAuth
from modules.helper import helper

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
  STATE_ERROR = -1
  STATE_UNINITIALIZED = 0

  STATE_DO_CONFIG = 1
  STATE_DO_OAUTH = 2
  STATE_NEED_KEYWORDS = 3
  STATE_NO_IMAGES = 4
  STATE_NOT_CONNECTED = 5

  STATE_READY = 999

  def __init__(self, configDir, id, name, needConfig=False, needOAuth=False):
    # MUST BE CALLED BY THE IMPLEMENTING CLASS!
    self._ID = id
    self._NAME = name
    self._OAUTH = None

    self._STATE = BaseService.STATE_UNINITIALIZED
    self._ERROR = None

    self._STATE = {
      '_OAUTH_CONFIG' : None,
      '_OAUTH_CONTEXT' : None,
      '_CONFIG' : None,
      '_KEYWORDS' : [],
      '_EXTRAS' : None
    }
    self._NEED_CONFIG = needConfig
    self._NEED_OAUTH = needOAuth

    self._DIR_BASE = self._prepareFolders(configDir)
    self._DIR_MEMORY = os.path.join(self._DIR_BASE, 'memory')
    self._DIR_PRIVATE = os.path.join(self._DIR_BASE, 'private')
    self._FILE_STATE = os.path.join(self._DIR_BASE, 'state.json')

    # MEMORY stores unique image ids of already displayed images
    # it prevents an image from being shown multiple times, before ALL images have been displayed
    # From time to time, memory is saved to disk as a backup. 
    self._MEMORY = None
    self._MEMORY_KEY = None

    # HISTORY stores (keywordId, imageId)-pairs
    # That way it can be useful to determine any previously displayed image
    # Unlike memory, the history is only stored in RAM
    self._HISTORY = []

    self.resetIndices()

    self.loadState()
    self.preSetup()

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
      return BaseService.STATE_DO_CONFIG
    if self._NEED_OAUTH and (not self.hasOAuthConfig or not self.hasOAuth()):
      return BaseService.STATE_DO_OAUTH
    if self.needKeywords() and len(self.getKeywords()) == 0:
      return BaseService.STATE_NEED_KEYWORDS

    return BaseService.STATE_READY

  ###[ Allows loading/saving of service state ]###########################

  def loadState(self):
    # Load any stored state data from storage
    # Normally you don't override this
    if os.path.exists(self._FILE_STATE):
      with open(self._FILE_STATE, 'r') as f:
        self._STATE.update( json.load(f) )

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

  def getMessages(self):
    # override this if you wish to show a message associated with
    # the provider's instance. Return None to hide
    # Format: [{'level' : 'INFO', 'message' : None, 'link' : None}]
    if self.needKeywords() and len(self.getKeywords()) == 0:
      return [
        {
          'level': 'INFO',
          'message' : 'Please add one or more items in order to show photos from this provider (see help button)',
          'link': None
        }
      ]
    return []

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

  def resetIndices(self):
    self.keywordIndex = 0
    self.imageIndex = 0

  def resetToLastAlbum(self):
    self.keywordIndex = max(0, len(self.getKeywords())-1)
    self.imageIndex = 0

  def validateKeywords(self, keywords):  # shouldn't this be 'validateKeyword' (singular)?
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

  def hasKeywordSourceUrl(self):
    # Override to provide source url support
    return False

  def removeKeywords(self, index):
    if index < 0 or index > (len(self._STATE['_KEYWORDS'])-1):
      logging.error('removeKeywords: Out of range %d' % index)
      return False
    self._STATE['_KEYWORDS'].pop(index)
    self.saveState()
    return True

  def needKeywords(self):
    # Some services don't have keywords. Override this to return false
    # to remove the keywords options.
    return True

  def helpKeywords(self):
    return 'Has not been defined'

  def getRandomKeywordIndex(self):
    if len(self._STATE['_KEYWORDS']) == 0:
      return 0
    return random.SystemRandom().randint(0,len(self._STATE['_KEYWORDS'])-1)

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
    #  "id" : a unique - preferably not-changing - ID to identify the same image in future requests, e.g. hash(imageUrl)
    #  "mimetype" : the filetype you downloaded, for example "image/jpeg"
    #  "error" : None or a human readable text string as to why you failed
    #  "source" : Link to where the item came from or None if not provided
    #
    # NOTE! If you need to index anything before you can get the first item, this would
    # also be the place to do it.
    #
    # If your service uses keywords (as albums) you probably only need to implement 'getImagesFor' and 'addUrlParams'

    if self.needKeywords():
      result = self.selectImageFromAlbum(destinationFile, supportedMimeTypes, displaySize, randomize)
      if result is None:
        result = {'id': None, 'mimetype': None, 'source': None, 'error': 'No (new) images could be found!'}
    else:
      result = {'id': None, 'mimetype': None, 'source': None, 'error': 'You haven\'t implemented this yet!'}

    return result

  def getImagesFor(self, keyword):
    # TODO explanation
    # id, mimetype, url, size, filename, sources

    return None

  def addUrlParams(self, url, recommendedSize, displaySize):
    # If the service provider allows 'width' / 'height' parameters 
    # override this function and place them inside the url.
    # If the recommendedSize is None (due to unknown imageSize) 
    # use the displaySize instead (better than nothing, but image quality might suffer a little bit)

    return url

  ###[ Helpers ]######################################

  def selectImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize, randomize):
    # chooses an album and selects an image from that album --> return {'id':, 'mimetype':, 'error':, 'source':}
    # if no (new) images can be found --> return None

    keywordList = list(self.getKeywords())
    keywordCount = len(keywordList)
    if keywordCount == 0:
      return {'id': None, 'mimetype': None, 'source': None, 'error': 'No albums have been specified'}

    if randomize:
      index = self.getRandomKeywordIndex()
    else:
      index = self.keywordIndex

    # if current keywordList[index] does not contain any new images --> just run through all albums
    for i in range(0, keywordCount):
      if not randomize and (index + i) >= keywordCount:
        # (non-random image order): return if the last album is exceeded --> serviceManager should use next service
        break
      self.keywordIndex = (index + i) % keywordCount
      keyword = keywordList[self.keywordIndex]
      
      # a provider-specific implementation for 'getImagesFor' is obligatory!
      images = self.getImagesFor(keyword)
      if images is None:
        return {'id': None, 'mimetype': None, 'source': None, 'error': 'You haven\'t implemented "getImagesFor" yet'}
      elif len(images) == 0:
        self.imageIndex = 0
        continue
      elif any(key not in images[0].keys() for key in ['id', 'url', 'mimetype', 'source', 'filename']):
        return {'id': None, 'mimetype': None, 'source': None, 'error': 'You haven\'t implemented "getImagesFor" correctly (some keys are missing)'}

      image = self.selectImage(images, supportedMimeTypes, displaySize, randomize)
      if image is None:
        self.imageIndex = 0
        continue

      filename = os.path.join(destinationDir, image['id'])
      if self.useCachedImage(filename):
        if image['mimetype'] is None:
          image['mimetype'] = helper.getMimeType(filename)
        return {'id': image['id'], 'mimetype': image['mimetype'], 'source': image['source'], 'error': None}

      # you should implement 'addUrlParams' if the provider allows 'width' / 'height' parameters!
      recommendedSize = self.calcRecommendedSize(image['size'], displaySize)
      url = self.addUrlParams(image['url'], recommendedSize, displaySize)

      result = self.requestUrl(url, destination=filename)
      if result['status'] == 200:
        if image['mimetype'] is None:
          image['mimetype'] = result['mimetype']
        return {'id': image['id'], 'mimetype': image['mimetype'], 'source': image['source'], 'error': None}
      else:
        return {'id': None, 'mimetype': None, 'source': None, 'error': "%d: Unable to download image!" % result['status']}

    self.resetIndices()
    return None

  def selectImage(self, images, supportedMimeTypes, displaySize, randomize):
    imageCount = len(images)
    if randomize:
      index = random.SystemRandom().randint(0, imageCount-1)
    else:
      index = self.imageIndex

    for i in range(0, imageCount):
      if not randomize and (index + i) >= imageCount:
        break

      self.imageIndex = (index + i) % imageCount
      image = images[self.imageIndex]

      orgFilename = image['filename'] if image['filename'] is not None else image['id']
      if randomize and self.memorySeen(image['id']):
        logging.debug("Skipping already displayed image '%s'!" % orgFilename)
        continue
      if not self.isCorrectOrientation(image['size'], displaySize):
        logging.debug("Skipping image '%s' due to wrong orientation!" % orgFilename)
        continue
      if image['mimetype'] is not None and image['mimetype'] not in supportedMimeTypes:
        # Make sure we don't get a video, unsupported for now (gif is usually bad too)
        logging.debug('Unsupported media: %s' % (image['mimetype']))
        continue

      return image
    return None

  def useCachedImage(self, filename):
    if helper.getImageSize(filename) is not None:
      logging.debug("using cached image: '%s'"%filename)
      return True
    elif os.path.isfile(filename):
      logging.debug("Deleting currupted (cached) image: %s" % filename)
      os.unlink(filename)
    return False

  def requestUrl(self, url, destination=None, params=None, data=None, usePost=False):
    result = {'status':500, 'content' : None}

    if self._OAUTH is not None:
      # Use OAuth path
      result = self._OAUTH.request(url, destination, params, data=data, usePost=usePost)
    else:
      if usePost:
        r = requests.post(url, params=params, json=data)
      else:
        r = requests.get(url, params=params)

      result['status'] = r.status_code
      result['mimetype'] = None
      result['headers'] = r.headers

      if 'Content-Type' in r.headers:
        result['mimetype'] = r.headers['Content-Type']

      if destination is None:
        result['content'] = r.content
      else:
        result['content'] = None
        with open(destination, 'wb') as f:
          for chunk in r.iter_content(chunk_size=1024):
            f.write(chunk)
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
    return hashlib.sha1(text.encode('ascii', 'ignore')).hexdigest()

  ###[ Memory management ]=======================================================

  def _fetchMemory(self, key):
    if key is None:
      key = ''
    h = self.hashString(key)
    if self._MEMORY_KEY == h:
      return
    # Save work and swap
    if self._MEMORY is not None and len(self._MEMORY) > 0:
      with open(os.path.join(self._DIR_MEMORY, '%s.json' % self._MEMORY_KEY), 'w') as f:
        json.dump(self._MEMORY, f)
    if os.path.exists(os.path.join(self._DIR_MEMORY, '%s.json' % h)):
      with open(os.path.join(self._DIR_MEMORY, '%s.json' % h), 'r') as f:
        self._MEMORY = json.load(f)
    else:
      self._MEMORY = []
    self._MEMORY_KEY = h

  def _differentThanLastHistory(self, keywordindex, imageIndex):
    # just a little helper function to compare indices with the indices of the previously displayed image
    if len(self._HISTORY) == 0:
      return True
    if keywordindex == self._HISTORY[-1][0] and imageIndex == self._HISTORY[-1][1]:
      return False
    return True

  def memoryRemember(self, itemId, keywords=None, alwaysRemember=True):
    # some debug info about the service of the currently displayed image
    logging.debug("Displaying new image")
    logging.debug(self._NAME)
    logging.debug("keyword: %d; index: %d" % (self.keywordIndex, self.imageIndex))

    # The MEMORY makes sure that this image won't be shown again until memoryForget is called
    self._fetchMemory(keywords)
    h = self.hashString(itemId)
    if h not in self._MEMORY:
      self._MEMORY.append(h)
    # save memory
    if (len(self._MEMORY) % 20) == 0:
      logging.info('Interim saving of memory every 20 entries')
      with open(os.path.join(self._DIR_MEMORY, '%s.json' % self._MEMORY_KEY), 'w') as f:
        json.dump(self._MEMORY, f)
    
    # annoying behaviour fix: only remember current image in history if the image has actually changed
    rememberInHistory = alwaysRemember or self._differentThanLastHistory(self.keywordIndex, self.imageIndex)
    if rememberInHistory:
      # The HISTORY makes it possible to show previously displayed images
      self._HISTORY.append((self.keywordIndex, self.imageIndex))

    # (non-random image order only): on 'prepareNextItem' --> make sure to preload the following image
    self.imageIndex += 1

    return rememberInHistory

  def memorySeen(self, itemId, keywords=None):
    self._fetchMemory(keywords)
    h = self.hashString(itemId)
    return h in self._MEMORY

  def memoryForgetLast(self, keywords=None):
    # remove the currently displayed image from memory as well as history
    # implications: 
    # - the image will be treated as never seen before (random image order)
    # - the same image will be preloaded again during 'prepareNextItem' (non-random image order)
    self._fetchMemory(keywords)
    if len(self._MEMORY) != 0:
      self._MEMORY.pop()
    if len(self._HISTORY) != 0:
      self.keywordIndex, self.imageIndex = self._HISTORY.pop()
    else:
      logging.warning("Trying to forget a single memory, but 'self._HISTORY' is empty. This should have never happened!")

  def memoryForget(self, keywords=None, forgetHistory=False):
    self._fetchMemory(keywords)
    n = os.path.join(self._DIR_MEMORY, '%s.json' % self._MEMORY_KEY)
    if os.path.exists(n):
      os.unlink(n)
    self._MEMORY = []
    if forgetHistory:
      self._HISTORY = []

  ###[ Slideshow controls ]=======================================================

  def nextAlbum(self):
    # skip to the next album
    # return False if service is out of albums to tell the serviceManager that it should use the next Service instead
    self.imageIndex = 0
    self.keywordIndex += 1
    if self.keywordIndex >= len(self._STATE['_KEYWORDS']):
      self.keywordIndex = 0
      return False
    return True

  def prevAlbum(self):
    # skip to the previous album
    # return False if service is already on its first album to tell the serviceManager that it should use the previous Service instead
    self.imageIndex = 0
    self.keywordIndex -= 1
    if self.keywordIndex < 0:
      self.keywordIndex = len(self._STATE['_KEYWORDS']) - 1
      return False
    return True

