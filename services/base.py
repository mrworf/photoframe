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
import OAuth from modules.oauth

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

  STATE_DO_AUTH = 1
  STATE_DO_OAUTH = 2

  STATE_READY = 999

  def __init__(self, id, name, needAuth=False, needOAuth=False):
    # MUST BE CALLED BY THE IMPLEMENTING CLASS!
    self._ID = id
    self._NAME = name

    self._STATE = STATE_UNINITIALIZED
    self._ERROR = None

    self._STATE = [
      '_OAUTH_CONFIG' : None,
      '_OAUTH_CONTEXT' : None,
      '_AUTH_CONFIG' : None,
      '_KEYWORDS' : []
    ]
    self._NEED_AUTH = needAuth
    self._NEED_OAUTH = needOAuth

    self._DIR_BASE = self._prepareFolders()
    self._DIR_MEMORY = os.path.join(self._DIR_BASE, 'memory')
    self._FILE_STATE = os.path.join(self._DIR_BASE, 'state.json')

  def _prepareFolders(self):
    basedir = '/tmp/%s' % self._hash(self._ID)
    if not os.path.exists(basedir):
      os.mkdir(basedir)
    if not os.path.exists(basedir + '/memory'):
      os.mkdir(basedir + '/memory')
    return basedir

  def _hash(self, text):
    return hashlib.sha1(text).hexdigest()

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
    if self._NEED_AUTH and not self.hasAuthentication():
      return STATE_DO_AUTH
    if self._NEED_OAUTH and (not self.hasOAuthConfig or not self.hasOAuth()):
      return STATE_DO_OAUTH

    return STATE_READY

  def getError(self):
    if self._STATE != STATE_ERROR:
      return None
    return self._ERROR

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

  def hasOAuthConfig(self):
    # Returns true/false if we have a config for oauth
    return False

  def hasOAuth(self):
    # Tests if we have a functional OAuth link,
    # returns False if we need to set it up

  def startOAuth(self):
    # Returns a HTTP redirect to begin OAuth or None if
    # oauth isn't configured. Normally not overriden
    pass

  def finishOAuth(self, url):
    # Called when OAuth sequence has completed
    self.saveState()

  ###[ For services which require static auth ]###########################

  def validateAuthentication(self, config):
    # Allow service to validate config, if correct, return None
    # If incorrect, return helpful error message.
    # config is a map with fields and their values
    return 'Not overriden yet but auth is enabled'

  def setAuthentication(self, config):
    # Setup any needed authentication data for this
    # service.
    self._STATE['_AUTH_CONFIG'] = config
    self.saveState()

  def getAuthentication(self):
    return self._STATE['_AUTH_CONFIG']

  def hasAuthentication(self):
    # Checks if it has auth data
    return self._STATE['_AUTH_CONFIG'] != None

  def getAuthenticationFields(self):
    # Returns a key/value map with:
    # "field" => [ "type" => "STR/INT", "name" => "Human readable", "description" => "Longer text" ]
    # Allowing UX to be dynamically created
    return ['username' : ['type':'STR', 'name':'Username', 'description':'Username to use for login']]

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
      return
    self._STATE['_KEYWORDS'].pop(index)

  def needKeywords(self):
    # Some services don't have keywords. Override this to return false
    # to remove the keywords options.
    return True

  def helpKeywords(self):
    return 'Anything you\'d like, we try to find it'

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
    #
    # NOTE! If you need to index anything before you can get the first item, this would
    # also be the place to do it.
    result = ['mimetype' : None, 'error' : 'You haven\'t implemented this yet']
    return result

  ###[ Helpers ]######################################

  def requestUrl(self, url, destination=None, params=None):
    result = ['status':500, 'content' : None]

    if self._oauth is not None:
      # Use OAuth path
      result = self.oauth.request(url, destination, params)
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

  def memoryRemember(self, itemId, keywords=None):
    pass

  def memorySeen(self, itemId, keywords=None):
    pass

  def memoryForget(self, keywords=None):
    pass
