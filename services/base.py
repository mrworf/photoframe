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
      '_KEYWORDS' : []
    }
    self._NEED_CONFIG = needConfig
    self._NEED_OAUTH = needOAuth

    self._DIR_BASE = self._prepareFolders(configDir)
    self._DIR_MEMORY = os.path.join(self._DIR_BASE, 'memory')
    self._DIR_PRIVATE = os.path.join(self._DIR_BASE, 'private')
    self._FILE_STATE = os.path.join(self._DIR_BASE, 'state.json')

    self._MEMORY = None
    self._MEMORY_KEY = None

    self.loadState()

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

    if self._NEED_CONFIG and not self.hasConfiguration():
      return BaseService.STATE_DO_CONFIG
    if self._NEED_OAUTH and (not self.hasOAuthConfig or not self.hasOAuth()):
      return BaseService.STATE_DO_OAUTH

    return BaseService.STATE_READY

  ###[ Allows loading/saving of service state ]###########################

  def loadState(self):
    # Load any stored state data from storage
    # Normally you don't override this
    if os.path.exists(self._FILE_STATE):
      with open(self._FILE_STATE, 'r') as f:
        self._STATE = json.load(f)

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

  def validateKeywords(self, keywords):
    # Allows a service to validate the provided keywords
    # if they are OK, it should return None, if not, it should return helpful error message
    # This call should return asap
    return None

  def addKeywords(self, keywords):
    # This is how the user will configure it, this adds a new set of keywords to this
    # service module. DO NOT OVERRIDE OR USE THIS TO DO PROCESSING
    if not self.needKeywords():
      return
    self._STATE['_KEYWORDS'].append(keywords)
    self.saveState()

  def getKeywords(self):
    # Returns an array of all keywords
    return self._STATE['_KEYWORDS']

  def removeKeywords(self, index):
    if index < 0 or index > (len(self._STATE['_KEYWORDS'])-1):
      logging.error('removeKeywords: Out of range %d' % index)
      return
    self._STATE['_KEYWORDS'].pop(index)
    self.saveState()

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

  ###[ Actual hard work ]###########################

  def prepareNextItem(self, destinationFile, supportedMimeTypes, displaySize):
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
    result = {'mimetype' : None, 'error' : 'You haven\'t implemented this yet', 'source':None}
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
      if destination is None:
        result['content'] = r.content
      else:
        with open(destination, 'wb') as f:
          for chunk in r.iter_content(chunk_size=1024):
            f.write(chunk)
    return result

  def _fetchMemory(self, key):
    if key is None:
      key = ''
    h =  self.hashString(key)
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

  def memoryRemember(self, itemId, keywords=None):
    self._fetchMemory(keywords)
    h = self.hashString(itemId)
    if h in self._MEMORY:
      return
    self._MEMORY.append(h)

    if (len(self._MEMORY) % 20) == 0:
      logging.info('Interim saving of memory every 20 entries')
      with open(os.path.join(self._DIR_MEMORY, '%s.json' % self._MEMORY_KEY), 'w') as f:
        json.dump(self._MEMORY, f)

  def memorySeen(self, itemId, keywords=None):
    self._fetchMemory(keywords)
    h = self.hashString(itemId)
    return h in self._MEMORY

  def memoryForget(self, keywords=None):
    self._fetchMemory(keywords)
    n = os.path.join(self._DIR_MEMORY, '%s.json' % self._MEMORY_KEY)
    if os.path.exists(n):
      os.unlink(n)
    self._MEMORY = []

  def getStoragePath(self):
    return self._DIR_PRIVATE

  def hashString(self, text):
    return hashlib.sha1(text).hexdigest()

