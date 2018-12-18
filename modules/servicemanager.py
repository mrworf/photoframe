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
import random
import shutil
import os
import logging
import json

# Any added service here also needs corresponding
# entry in _resolveService
from services.svc_picasaweb import PicasaWeb
from services.svc_googlephotos import GooglePhotos

class ServiceManager:
  def __init__(self, settings):
    self._SETTINGS = settings
    svc_folder = os.path.join(settings.CONFIGFOLDER, 'services')
    if not os.path.exists(svc_folder):
      os.mkdir(svc_folder)

    self._BASEDIR = svc_folder
    self._SERVICES = {}
    self._CONFIGFILE = os.path.join(self._BASEDIR, 'services.json')
    self._load()

    # Translate old config into new
    self._migrate()

  def _deletefolder(self, folder):
    try:
      shutil.rmtree(folder)
    except:
      logging.exception('Failed to delete "%s"', folder)

  def _resolveService(self, id):
    if PicasaWeb.SERVICE_ID == id:
      return 'PicasaWeb'
    if GooglePhotos.SERVICE_ID == id:
      return 'GooglePhotos'
    return None

  def listServices(self):
    result = []
    result.append({'name' : PicasaWeb.SERVICE_NAME, 'id' : PicasaWeb.SERVICE_ID})
    result.append({'name' : GooglePhotos.SERVICE_NAME, 'id' : GooglePhotos.SERVICE_ID})
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

    # Instanciate the services
    for entry in data:
      svcname = self._resolveService(entry['type'])
      if svcname is None:
        logging.error('Cannot resolve service type %d, skipping', entry['type'])
        continue
      svc = eval("%s(self._BASEDIR, entry['id'], entry['name'])" % svcname)
      self._SERVICES[svc.getId()] = {'service' : svc, 'id' : svc.getId(), 'name' : svc.getName()}

  def _hash(self, text):
    return hashlib.sha1(text).hexdigest()

  def addService(self, type, name):
    svcname = self._resolveService(type)
    if svcname is None:
      return None

    genid = self._hash("%s-%f-%d" % (name, time.time(), len(self._SERVICES)))
    svc = eval("%s(self._BASEDIR, genid, name)" % svcname)
    self._SERVICES[genid] = {'service' : svc, 'id' : svc.getId(), 'name' : svc.getName()}
    self._save()
    return genid

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

    del self._SERVICES[id]
    self._deletefolder(os.path.join(self._BASEDIR, id))
    self._save()

  def handleOAuthCallback(self, request):
    state = request.args.get('state').split('-')
    if len(state) < 3:
      logging.error('Invalid callback, need correct state to redirect to OAuth session')
      return False

    if state[2] not in self._SERVICES:
      return False
    svc = self._SERVICES[state[2]]['service']
    svc.finishOAuth(request.url)
    return True

  def handleOAuthStart(self, service):
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

  def getServiceState(self, id):
    if id not in self._SERVICES:
      return None

    svc = self._SERVICES[id]['service']
    # Find out if service is ready
    state = svc.updateState()
    if state == svc.STATE_DO_OAUTH:
      return 'OAUTH'
    if state == svc.STATE_DO_CONFIG:
      return 'CONFIG'
    if state == svc.STATE_READY:
      return 'READY'
    return 'ERROR'

  def _migrate(self):
    if os.path.exists(self._SETTINGS.CONFIGFOLDER + '/oauth.json'):
      logging.info('Migrating old setup to new service layout')
      id = self.addService(PicasaWeb.SERVICE_ID, 'PicasaWeb')
      svc = self._SERVICES[id]['service']

      # Migrate the oauth configuration
      with open(self._SETTINGS.CONFIGFOLDER + '/oauth.json') as f:
        data = json.load(f)
      if 'web' in data: # if someone added it via command-line
        data = data['web']
      svc.setOAuthConfig(data)
      svc.migrateOAuthToken(self._SETTINGS.get('oauth_token'))

      os.unlink(self._SETTINGS.CONFIGFOLDER + '/oauth.json')
      self._SETTINGS.set('oauth_token', '')

      # Migrate keywords
      keywords = self._SETTINGS.getUser('keywords')
      for keyword in keywords:
        svc.addKeywords(keyword)

      # Blank out the old keywords since they were migrated
      self._SETTINGS.set('keywords', '')
      self._SETTINGS.save()

  def getServices(self):
    result = []
    for k in self._SERVICES:
      svc = self._SERVICES[k]
      result.append({'name' : svc['service'].getName(), 'service' : svc['service'].SERVICE_ID, 'id' : k, 'state' : self.getServiceState(k)})
    return result

  def servicePrepareNextItem(self, id, destinationFile, supportedMimeTypes, displaySize):
    if id not in self._SERVICES:
      return {'error' : 'Service not available', 'mime' : None, 'source' : None}

    svc = self._SERVICES[id]['service']
    return svc.prepareNextItem(destinationFile, supportedMimeTypes, displaySize)
