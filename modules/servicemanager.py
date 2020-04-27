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
from services.base import BaseService

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

    # Logs services that appear to have no images or only images that have already been displayed
    # memoryForgetAll will be called when all images of every services have been displayed
    self._OUT_OF_IMAGES = []

    # Logs the sequence in which services are being used
    # useful for displaying previous images
    self._HISTORY = []

    # Tracks current service showing the image
    self.currentService = None

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

  def detailsServiceKeywords(self, service, index):
    if service not in self._SERVICES:
      return None
    svc = self._SERVICES[service]['service']
    if not svc.hasKeywordDetails():
      logging.error('Service does not support keyword details')
      return None
    return svc.getKeywordDetails(index)

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
    return svc.updateState()

  def getServiceStateText(self, id):
    state = self.getServiceState(id)
    if state == BaseService.STATE_DO_OAUTH:
      return 'OAUTH'
    elif state == BaseService.STATE_DO_CONFIG:
      return 'CONFIG'
    elif state == BaseService.STATE_NEED_KEYWORDS:
      return 'NEED_KEYWORDS'
    elif state == BaseService.STATE_NO_IMAGES:
      return 'NO_IMAGES'
    elif state == BaseService.STATE_READY:
      return 'READY'
    return 'ERROR'

  def getAllServiceStates(self):
    serviceStates = []
    for id in self._SERVICES:
      svc = self._SERVICES[id]['service']
      name = svc.getName()
      state = self.getServiceStateText(id)
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
    if self.currentService is None:
      return ""
    return self._SERVICES[self.currentService]['service'].getName()

  def getServices(self, readyOnly=False):
    result = []
    for k in self._SERVICES:
      if readyOnly and self.getServiceState(k) != BaseService.STATE_READY:
        continue
      svc = self._SERVICES[k]
      result.append({
        'name' : svc['service'].getName(),
        'service' : svc['service'].SERVICE_ID,
        'id' : k,
        'state' : self.getServiceStateText(k),
        'useKeywords' : svc['service'].needKeywords(),
        'hasSourceUrl' : svc['service'].hasKeywordSourceUrl(),
        'hasDetails' : svc['service'].hasKeywordDetails(),
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
    numImages = [self._SERVICES[s['id']]['service'].getImagesTotal() for s in services]
    totalImages = sum(numImages)
    if totalImages == 0:
      return 0
    i = helper.getWeightedRandomIndex(numImages)
    return services[i]['id']

  def chooseService(self, randomize, retry=False):
    result = None
    availableServices = self.getServices(readyOnly=True)
    if len(availableServices) == 0:
      return None

    if randomize:
      availableServices = [s for s in availableServices if self._SERVICES[s['id']]['service'].getImagesRemaining() > 0]
      if len(availableServices) > 0:
        logging.debug('Found %d services with images' % len(availableServices))
        key = self.selectRandomService(availableServices)
        result = self._SERVICES[key]['service']
    else:
        offset = 0
        # Find where to start
        for s in range(0, len(availableServices)):
          if availableServices[s]['id'] == self.currentService:
            offset = s
            break
        # Next, pick the service which has photos
        for s in range(0, len(availableServices)):
          index = (offset + s) % len(availableServices)
          svc = self._SERVICES[availableServices[index]['id']]['service']
          if svc.getImagesRemaining() > 0:
            result = svc
            break

    # Oh snap, out of images, reset memory and try again
    if result is None and not retry:
      logging.info('All images have been shown, resetting counters')
      self.memoryForgetAll()
      return self.chooseService(randomize, retry=True) # Avoid calling us forever
    else:
      logging.debug('Picked %s which has %d images left to show', result.getName(), result.getImagesRemaining())
    return result

  def expireStaleKeywords(self):
    maxage = self._SETTINGS.getUser('refresh')
    for key in self._SERVICES:
      svc = self._SERVICES[key]["service"]
      for k in svc.getKeywords():
        if svc.freshnessImagesFor(k) < maxage:
          continue
        logging.info('Expire is set to %dh, expiring %s which was %d hours old', maxage, k, svc.freshnessImagesFor(k))
        svc._clearImagesFor(k)

  def getTotalImageCount(self):
    services = self.getServices(readyOnly=True)
    return sum([self._SERVICES[s['id']]['service'].getImagesTotal() for s in services])

  def servicePrepareNextItem(self, destinationDir, supportedMimeTypes, displaySize, randomize):
    # We should expire any old index if setting is active
    if self._SETTINGS.getUser('refresh') > 0:
      self.expireStaleKeywords()

    svc = self.chooseService(randomize)
    if svc is None:
      return None
    result = svc.prepareNextItem(destinationDir, supportedMimeTypes, displaySize, randomize)
    if result is None:
      logging.warning('prepareNextItem for %s came back with None', svc.getName())
    elif result.error is not None:
      logging.warning('prepareNextItem for %s came back with an error: %s', svc.getName(), result.error)
    return result

  def hasKeywords(self):
    # Check any and all services to see if any is ready and if they have keywords
    for k in self._SERVICES:
      if self.getServiceStateText(k) != 'READY':
        continue
      words = self.getServiceKeywords(k)
      if words is not None and len(words) > 0:
        return True
    return False

  def hasReadyServices(self):
    for k in self._SERVICES:
      if self.getServiceStateText(k) != 'READY':
        continue
      return True
    return False

  def memoryForgetAll(self):
    logging.info("Photoframe's memory was reset. Already displayed images will be shown again!")
    for key in self._SERVICES:
      svc = self._SERVICES[key]["service"]
      for k in svc.getKeywords():
        logging.info('%s was %d hours old when we refreshed' % (k, svc.freshnessImagesFor(k)))
        svc._clearImagesFor(k)

  def nextImage(self):
    #No need to change anything; all done in slideshow.py
    pass

  def prevImage(self):
    return False

  def nextAlbum(self):
    return False

  def prevAlbum(self):
    return False

