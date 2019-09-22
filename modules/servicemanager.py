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
import time
import shutil
import os
import logging
import json
import re
import importlib

from modules.helper import helper
from modules.path import path

class ServiceManager:
  def __init__(self, settings, cacheMgr):
    self._SETTINGS = settings
    self._CACHEMGR = cacheMgr

    svc_folder = os.path.join(path.CONFIGFOLDER, 'services')
    if not os.path.exists(svc_folder):
      os.mkdir(svc_folder)

    self._BASEDIR = svc_folder
    self._SVC_INDEX = {} # Holds all detected services
    self._SERVICES = {}
    self._CONFIGFILE = os.path.join(self._BASEDIR, 'services.json')

    self.nextService = False
    self.prevService = False
    self.forceService = None
    self.lastUsedService = None

    # Logs services that appear to have no images or only images that have already been displayed
    # memoryForget will be called when all images of every services have been displayed 
    self._OUT_OF_IMAGES = []

    # Logs the sequence in which services are being used
    # useful for displaying previous images
    self._HISTORY = []

    self._detectServices()

    self._load()

    # Translate old config into new
    self._migrate()

  def _instantiate(self, module, klass):
      module = importlib.import_module('services.' + module)
      my_class = getattr(module, klass)
      return my_class

  def _detectServices(self):
    for item in os.listdir('services'):
      if os.path.isfile('services/' + item) and item.startswith('svc_') and item.endswith('.py'):
        with open('services/' + item, 'r') as f:
          for line in f:
            line = line.strip()
            if line.startswith('class ') and line.endswith('(BaseService):'):
              m = re.search('class +([^\(]+)\(', line)
              if m is not None:
                klass = self._instantiate(item[0:-3], m.group(1))
                logging.info('Loading service %s from %s', klass.__name__, item)
                self._SVC_INDEX[m.group(1)] = {'id' : klass.SERVICE_ID, 'name' : klass.SERVICE_NAME, 'module' : item[0:-3], 'class' : m.group(1), 'deprecated' : klass.SERVICE_DEPRECATED}
              break

  def _deletefolder(self, folder):
    try:
      shutil.rmtree(folder)
    except:
      logging.exception('Failed to delete "%s"', folder)

  def _resolveService(self, id):
    for svc in self._SVC_INDEX:
      if self._SVC_INDEX[svc]['id'] == id:
        return svc

    return None

  def listServices(self):
    result = []
    # Make sure it retains the ID sort order
    for key, value in sorted(self._SVC_INDEX.iteritems(), key=lambda (k,v): (v['id'],k)):
      result.append(self._SVC_INDEX[key])
    return result;

  def _save(self):
    data = []
    for k in self._SERVICES:
      svc = self._SERVICES[k]
      data.append({'type' : svc['service'].SERVICE_ID, 'id' : svc['id'], 'name' : svc['name']})
    with open(self._CONFIGFILE, 'w') as f:
      json.dump(data, f)

  def _load(self):
    if not os.path.exists(self._CONFIGFILE):
      return
    try:
      with open(self._CONFIGFILE, 'r') as f:
        data = json.load(f)
    except:
      logging.error('%s is corrupt, skipping' % self._CONFIGFILE)
      os.unlink(self._CONFIGFILE)
      return

    # Instantiate the services
    for entry in data:
      svcname = self._resolveService(entry['type'])
      if svcname is None:
        logging.error('Cannot resolve service type %d, skipping', entry['type'])
        continue
      klass = self._instantiate(self._SVC_INDEX[svcname]['module'], self._SVC_INDEX[svcname]['class'])
      if klass:
        svc = eval("klass(self._BASEDIR, entry['id'], entry['name'])")
        svc.setCacheManager(self._CACHEMGR)
        self._SERVICES[svc.getId()] = {'service' : svc, 'id' : svc.getId(), 'name' : svc.getName()}

  def _hash(self, text):
    return hashlib.sha1(text).hexdigest()

  def addService(self, type, name):
    svcname = self._resolveService(type)
    if svcname is None:
      return None

    genid = self._hash("%s-%f-%d" % (name, time.time(), len(self._SERVICES)))
    klass = self._instantiate(self._SVC_INDEX[svcname]['module'], self._SVC_INDEX[svcname]['class'])
    if klass:
      svc = eval("klass(self._BASEDIR, genid, name)")
      svc.setCacheManager(self._CACHEMGR)
      self._SERVICES[genid] = {'service' : svc, 'id' : svc.getId(), 'name' : svc.getName()}
      self._save()
      return genid
    return None

  def renameService(self, id, newName):
    if id not in self._SERVICES:
      return False
    self._SERVICES[id]['service'].setName(newName)
    self._SERVICES[id]['name'] = newName
    self._save()
    return True

  def deleteService(self, id):
    if id not in self._SERVICES:
      return

    self._HISTORY = filter(lambda h: h != self._SERVICES[id]['service'], self._HISTORY)
    del self._SERVICES[id]
    self._deletefolder(os.path.join(self._BASEDIR, id))
    self._save()

  def oauthCallback(self, request):
    state = request.args.get('state').split('-')
    if len(state) < 3:
      logging.error('Invalid callback, need correct state to redirect to OAuth session')
      return False

    if state[2] not in self._SERVICES:
      return False
    svc = self._SERVICES[state[2]]['service']
    svc.finishOAuth(request.url)
    return True

  def oauthConfig(self, service, data):
    if service not in self._SERVICES:
      return False
    svc = self._SERVICES[service]['service']
    return svc.setOAuthConfig(data)

  def oauthStart(self, service):
    if service not in self._SERVICES:
      return None
    svc = self._SERVICES[service]['service']
    return svc.startOAuth()

  def getServiceConfigurationFields(self, service):
    if service not in self._SERVICES:
      return {}
    svc = self._SERVICES[service]['service']
    if not svc.hasConfiguration():
      return {}
    return svc.getConfigurationFields()

  def getServiceConfiguration(self, service):
    if service not in self._SERVICES:
      return {}
    svc = self._SERVICES[service]['service']
    if not svc.hasConfiguration():
      return {}
    return svc.getConfiguration()

  def setServiceConfiguration(self, service, config):
    if service not in self._SERVICES:
      return False
    svc = self._SERVICES[service]['service']
    if not svc.hasConfiguration():
      return False
    if not svc.validateConfiguration(config):
      return False
    svc.setConfiguration(config)
    return True

  def getServiceKeywords(self, service):
    if service not in self._SERVICES:
      return None
    svc = self._SERVICES[service]['service']
    if not svc.needKeywords():
      return None
    return svc.getKeywords()

  def addServiceKeywords(self, service, keywords):
    if service not in self._SERVICES:
      return {'error' : 'No such service'}
    svc = self._SERVICES[service]['service']
    if not svc.needKeywords():
      return {'error' : 'Service does not use keywords'}
    if svc in self._OUT_OF_IMAGES:
      self._OUT_OF_IMAGES.remove(svc)
    return svc.addKeywords(keywords)

  def removeServiceKeywords(self, service, index):
    if service not in self._SERVICES:
      logging.error('removeServiceKeywords: No such service')
      return False
    svc = self._SERVICES[service]['service']
    if not svc.needKeywords():
      logging.error('removeServiceKeywords: Does not use keywords')
      return False
    return svc.removeKeywords(index)

  def sourceServiceKeywords(self, service, index):
    if service not in self._SERVICES:
      return None
    svc = self._SERVICES[service]['service']
    if not svc.hasKeywordSourceUrl():
      logging.error('Service does not support sourceUrl')
      return None
    return svc.getKeywordSourceUrl(index)

  def helpServiceKeywords(self, service):
    if service not in self._SERVICES:
      return False
    svc = self._SERVICES[service]['service']
    if not svc.needKeywords():
      return None
    return svc.helpKeywords()

  def getServiceState(self, id):
    if id not in self._SERVICES:
      return None

    svc = self._SERVICES[id]['service']
    # Find out if service is ready
    state = svc.updateState()
    if state == svc.STATE_DO_OAUTH:
      return 'OAUTH'
    elif state == svc.STATE_DO_CONFIG:
      return 'CONFIG'
    elif state == svc.STATE_NEED_KEYWORDS:
      return 'NEED_KEYWORDS'
    elif state == svc.STATE_NO_IMAGES:
      return 'NO_IMAGES'
    elif state == svc.STATE_READY:
      return 'READY'
    return 'ERROR'

  def getAllServiceStates(self):
    serviceStates = []
    for id in self._SERVICES:
      svc = self._SERVICES[id]['service']
      name = svc.getName()
      state = self.getServiceState(id)
      additionalInfo = svc.explainState()
      serviceStates.append((name, state, additionalInfo))
    return serviceStates

  def _migrate(self):
    if os.path.exists(path.CONFIGFOLDER + '/oauth.json'):
      logging.info('Migrating old setup to new service layout')
      from services.svc_picasaweb import PicasaWeb

      id = self.addService(PicasaWeb.SERVICE_ID, 'PicasaWeb')
      svc = self._SERVICES[id]['service']

      # Migrate the oauth configuration
      with open(path.CONFIGFOLDER + '/oauth.json') as f:
        data = json.load(f)
      if 'web' in data: # if someone added it via command-line
        data = data['web']
      svc.setOAuthConfig(data)
      svc.migrateOAuthToken(self._SETTINGS.get('oauth_token'))

      os.unlink(path.CONFIGFOLDER + '/oauth.json')
      self._SETTINGS.set('oauth_token', '')

      # Migrate keywords
      keywords = self._SETTINGS.getUser('keywords')
      for keyword in keywords:
        svc.addKeywords(keyword)

      # Blank out the old keywords since they were migrated
      self._SETTINGS.delete('keywords')
      self._SETTINGS.delete('keywords', userField=True)
      self._SETTINGS.save()

  def getLastUsedServiceName(self):
    if self.lastUsedService is None:
      return ""
    return self.lastUsedService.getName()

  def getServices(self, readyOnly=False):
    result = []
    for k in self._SERVICES:
      if readyOnly and self.getServiceState(k) != 'READY':
        continue
      svc = self._SERVICES[k]
      result.append({
        'name' : svc['service'].getName(),
        'service' : svc['service'].SERVICE_ID,
        'id' : k,
        'state' : self.getServiceState(k),
        'useKeywords' : svc['service'].needKeywords(),
        'hasSourceUrl' : svc['service'].hasKeywordSourceUrl(),
        'messages' : svc['service'].getMessages(),
      })
    return result

  def _getOffsetService(self, availableServices, lastService, offset):
    # Just a helper function to figure out what the next/previous service is
    for i, _svc in enumerate(availableServices):
      if self._SERVICES[_svc['id']]['service'] == lastService:
        key = availableServices[(i+offset) % len(availableServices)]['id']
        return self._SERVICES[key]['service']
    return lastService

  def selectRandomService(self, services):
    # select service at random but weighted by the number of images each service provides
    numImages = [self._SERVICES[s['id']]['service'].getNumImages() for s in services]
    totalImages = sum(numImages)
    if totalImages == 0:
      return 0
    i = helper.getWeightedRandomIndex(numImages)
    return services[i]['id']

  def chooseService(self, randomize, lastService=None):
    availableServices = self.getServices(readyOnly=True)
    if len(availableServices) == 0:
      return None

    if lastService is None:
      if len(self._HISTORY) != 0:
        lastService = self._HISTORY[-1]
      elif self.lastUsedService != None:
        lastService = self.lastUsedService
    # if lastService is not ready anymore!
    if lastService not in [self._SERVICES[s['id']]['service'] for s in availableServices]:
      lastService = None

    if self.forceService is not None:
      svc = self.forceService
    elif randomize:
      availableServices = [s for s in availableServices if self._SERVICES[s['id']]['service'] not in self._OUT_OF_IMAGES]
      logging.debug("# of available services %d"%len(availableServices))
      if len(availableServices) == 0:
        self.memoryForget()
        availableServices = self.getServices(readyOnly=True)

      key = self.selectRandomService(availableServices)
      svc = self._SERVICES[key]['service']
    else:
      if lastService == None:
        key = availableServices[0]['id']
        svc = self._SERVICES[key]['service']
        svc.resetIndices()
      else:
        if self.nextService:
          svc = self._getOffsetService(availableServices, lastService, 1)
          svc.resetIndices()
        elif self.prevService:
          svc = self._getOffsetService(availableServices, lastService, -1)
          svc.resetToLastAlbum()
        else:
          svc = lastService
      
    self.forceService = None
    self.nextService = False
    self.prevService = False
    return svc

  def servicePrepareNextItem(self, destinationDir, supportedMimeTypes, displaySize, randomize):
    svc = self.chooseService(randomize)
    if svc is None:
      return None
    result = svc.prepareNextItem(destinationDir, supportedMimeTypes, displaySize, randomize)
    if result.error is not None:
      # If we end up here, two things can have happened
      # 1. All images have been shown for this service
      # 2. No image or data was able to download from this service
      # Retry, but use next service instead
      # If all services are out of images
      # Try forgetting all data and do another run (see 'chooseService')
      state = svc.updateState()
      if state == svc.STATE_READY and randomize and svc not in self._OUT_OF_IMAGES:
        self._OUT_OF_IMAGES.append(svc)
        logging.info("%s is probably out of images!" % svc.getName())

      self.nextService = True
      svc = self.chooseService(randomize, lastService=svc)
      if svc is None:
        return None
      result = svc.prepareNextItem(destinationDir, supportedMimeTypes, displaySize, randomize)

      if result.error is not None:
        logging.error('Service returned: ' + result.error)
        state = svc.updateState()
        if state == svc.STATE_READY and randomize and svc not in self._OUT_OF_IMAGES:
          self._OUT_OF_IMAGES.append(svc)
          logging.info("%s is probably out of images!" % svc.getName())

    self.lastUsedService = svc
    return result

  def hasKeywords(self):
    # Check any and all services to see if any is ready and if they have keywords
    for k in self._SERVICES:
      if self.getServiceState(k) != 'READY':
        continue
      words = self.getServiceKeywords(k)
      if words is not None and len(words) > 0:
        return True
    return False

  def hasReadyServices(self):
    for k in self._SERVICES:
      if self.getServiceState(k) != 'READY':
        continue
      return True
    return False

  def memoryRemember(self, imageId):
    svc = self.lastUsedService
    # only remember service in _HISTORY if image has changed. 
    # alwaysRemember is True if the current service is different to the service of the previous image 
    alwaysRemember = (len(self._HISTORY) == 0) or (svc != self._HISTORY[-1])
    if svc.memoryRemember(imageId, alwaysRemember=alwaysRemember):
      self._HISTORY.append(svc)

  def memoryForget(self, forgetHistory=False):
    logging.info("Photoframe's memory was reset. Already displayed images will be shown again!")
    for key in self._SERVICES:
      svc = self._SERVICES[key]["service"]
      svc.memoryForget(forgetHistory=forgetHistory)
      for file in os.listdir(svc.getStoragePath()):
        os.unlink(os.path.join(svc.getStoragePath(), file))
    self._OUT_OF_IMAGES = []
    if forgetHistory:
      self._HISTORY = []

  def nextImage(self):
    #No need to change anything; all done in slideshow.py
    pass

  def prevImage(self):
    if len(self._HISTORY) <= 1:
      return False

    # delete last two memories, because the currentImage and the previous need to be forgotten
    currentService = self._HISTORY.pop()
    currentService.memoryForgetLast()
    if currentService in self._OUT_OF_IMAGES:
      self._OUT_OF_IMAGES.remove(currentService)

    previousService = self._HISTORY.pop()
    previousService.memoryForgetLast()
    if previousService in self._OUT_OF_IMAGES:
      self._OUT_OF_IMAGES.remove(previousService)

    # skip all previous images of services that are not ready
    while previousService.updateState() != previousService.STATE_READY:
      if len(self._HISTORY) == 0:
        previousService = None
        break
      previousService = self._HISTORY.pop()
      previousService.memoryForgetLast()
      if previousService in self._OUT_OF_IMAGES:
        self._OUT_OF_IMAGES.remove(previousService)

    self.forceService = previousService
    return True

  def nextAlbum(self):
    if len(self._HISTORY) == 0:
      return False
    lastService = self._HISTORY[-1]
    if not lastService.nextAlbum():
      self.nextService = True
    return True

  def prevAlbum(self):
    if len(self._HISTORY) == 0:
      return False
    lastService = self._HISTORY[-1]
    if not lastService.prevAlbum():
      self.prevService = True
    return True

