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

    self._MEMORY = None
    self._MEMORY_KEY = None

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

  def addKeywords(self, keywords): #shouldn't this be 'addKeyword' (singular)? seems a bit confusing to me, because 'keywords' is a string and not a list!
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
    #  "mimetype" : the filetype you downloaded, for example "image/jpeg"
    #  "error" : None or a human readable text string as to why you failed
    #  "source" : Link to where the item came from or None if not provided
    #
    # NOTE! If you need to index anything before you can get the first item, this would
    # also be the place to do it.
    result = {'mimetype': None, 'error': 'You haven\'t implemented this yet', 'source': None, 'filename': None}
    return result

  ###[ Helpers ]######################################

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
    if len(self._HISTORY) == 0:
      return True
    if keywordindex == self._HISTORY[-1][0] and imageIndex == self._HISTORY[-1][1]:
      return False
    return True

  def memoryRemember(self, itemId, keywords=None, alwaysRemember=True):
    logging.debug("Displaying new image")
    logging.debug(self._NAME)
    logging.debug("keyword: %d; index: %d" % (self.keywordIndex, self.imageIndex))

    self._fetchMemory(keywords)
    h = self.hashString(itemId)
    if h not in self._MEMORY:
      self._MEMORY.append(h)
    
    # only remember if image has changed
    rememberInHistory = alwaysRemember or self._differentThanLastHistory(self.keywordIndex, self.imageIndex)
    if rememberInHistory:
      self._HISTORY.append((self.keywordIndex, self.imageIndex))
    self.imageIndex += 1

    if (len(self._MEMORY) % 20) == 0:
      logging.info('Interim saving of memory every 20 entries')
      with open(os.path.join(self._DIR_MEMORY, '%s.json' % self._MEMORY_KEY), 'w') as f:
        json.dump(self._MEMORY, f)

    return rememberInHistory

  def memorySeen(self, itemId, keywords=None):
    self._fetchMemory(keywords)
    h = self.hashString(itemId)
    return h in self._MEMORY

  def memoryForgetLast(self, keywords=None):
    self._fetchMemory(keywords)
    if len(self._MEMORY) != 0:
      self._MEMORY.pop()
    if len(self._HISTORY) == 0:
      logging.warning("Trying to forget a single memory, but 'self._HISTORY' is empty. This should have never happened!")
    else:
      self.keywordIndex, self.imageIndex = self._HISTORY.pop()

  def memoryForget(self, keywords=None, forgetHistory=False):
    self._fetchMemory(keywords)
    n = os.path.join(self._DIR_MEMORY, '%s.json' % self._MEMORY_KEY)
    if os.path.exists(n):
      os.unlink(n)
    self._MEMORY = []
    if forgetHistory:
      self._HISTORY = []

  def getPreferredImageSize(self, imageSize, displaySize):
    # Calculate the size we need to avoid black borders
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

  def isCorrectOrientation(self, metadata, displaySize):
    if displaySize['force_orientation'] == 0:
      return True

    # NOTE: square images are being treated as portrait-orientation
    image_orientation = 0 if int(metadata["width"]) > int(metadata["height"]) else 1
    display_orientation = 0 if displaySize["width"] > displaySize["height"] else 1

    return image_orientation == display_orientation

  def nextAlbum(self):
    self.imageIndex = 0
    self.keywordIndex += 1
    if self.keywordIndex >= len(self._STATE['_KEYWORDS']):
      self.keywordIndex = 0
      return False
    return True

  def prevAlbum(self):
    self.imageIndex = 0
    self.keywordIndex -= 1
    if self.keywordIndex < 0:
      self.keywordIndex = len(self._STATE['_KEYWORDS']) - 1
      return False
    return True

