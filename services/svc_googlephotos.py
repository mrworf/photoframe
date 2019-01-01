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
from base import BaseService
import random
import os
import json
import logging

class GooglePhotos(BaseService):
  SERVICE_NAME = 'GooglePhotos'
  SERVICE_ID = 2

  def __init__(self, configDir, id, name):
    BaseService.__init__(self, configDir, id, name, needConfig=False, needOAuth=True)

  def getOAuthScope(self):
    return ['https://www.googleapis.com/auth/photoslibrary.readonly']

  def helpOAuthConfig(self):
    return 'Please upload client.json from the Google API Console'

  def helpKeywords(self):
    return 'Currently, each entry represents the name of an album (case-insensitive). If you want the latest photos, simply write "latest" as album'

  def hasKeywordSourceUrl(self):
    return True

  def postSetup(self):
    extras = self.getExtras()
    keywords = self.getKeywords()

    if extras is None and keywords is not None and len(keywords) > 0:
      logging.info('Migrating to new format with preresolved album ids')
      extras = {}
      for key in keywords:
        if key.lower() == 'latest':
          continue
        albumId = self.translateKeywordToId(key)
        if albumId is None:
          logging.error('Existing keyword cannot be resolved')
        else:
          extras[key] = albumId
      self.setExtras(extras)

  def getKeywordSourceUrl(self, index):
    keys = self.getKeywords()
    if index < 0 or index >= len(keys):
      return 'Out of range, index = %d' % index
    keywords = keys[index]
    extras = self.getExtras()
    if keywords not in extras:
      return 'No such keyword'
    return extras[keywords]['sourceUrl']

  def removeKeywords(self, index):
    # Override since we need to delete our private data
    keys = self.getKeywords()
    if index < 0 or index >= len(keys):
      return
    keywords = keys[index]
    filename = os.path.join(self.getStoragePath(), self.hashString(keywords) + '.json')
    if os.path.exists(filename):
      os.unlink(filename)
    BaseService.removeKeywords(self, index)
    # Remove any extras
    extras = self.getExtras()
    if extras is not None and keywords in extras:
      del extras[keywords]
      self.setExtras(extras)

  def validateKeywords(self, keywords):
    # Remove quotes around keyword
    if keywords[0] == '"' and keywords[-1] == '"':
      keywords = keywords[1:-1]
    return {'error':None, 'keywords':keywords}

  def addKeywords(self, keywords):
    result = BaseService.addKeywords(self, keywords)
    if result['error'] is None:
      # No error in input, result album now
      if result['keywords'].upper().lower().strip() != 'latest':
        albumId = self.translateKeywordToId(result['keywords'])
        if albumId is None:
          result['error'] = 'No such album "%s"' % result['keywords']
          # Delete the newly added keyword
          self.removeKeywords(len(self.getKeywords())-1)
        else:
          extras = self.getExtras()
          if extras is None:
            extras = {}
          extras[result['keywords']] = albumId
          self.setExtras(extras)
    return result

  def prepareNextItem(self, destinationFile, supportedMimeTypes, displaySize):
    result = self.fetchImage(destinationFile, supportedMimeTypes, displaySize)
    if result['error'] is not None:
      # If we end up here, two things can have happened
      # 1. All images have been shown
      # 2. No image or data was able to download
      # Try forgetting all data and do another run
      self.memoryForget()
      for file in os.listdir(self.getStoragePath()):
        os.unlink(os.path.join(self.getStoragePath(), file))
      result = self.fetchImage(destinationFile, supportedMimeTypes, displaySize)
    return result

  def fetchImage(self, destinationFile, supportedMimeTypes, displaySize):
    # First, pick which keyword to use
    keywordList = list(self.getKeywords())
    offset = 0

    # Make sure we always have a default
    if len(keywordList) == 0:
      keywordList.append('')
    else:
      offset = self.getRandomKeywordIndex()

    total = len(keywordList)
    for i in range(0, total):
      index = (i + offset) % total
      keyword = keywordList[index]
      images = self.getImagesFor(keyword)
      if images is None:
        continue

      mimeType, imageUrl, sourceUrl = self.getUrlFromImages(supportedMimeTypes, displaySize, images)
      if imageUrl is None:
        continue
      result = self.requestUrl(imageUrl, destination=destinationFile)
      if result['status'] == 200:
        return {'mimetype' : mimeType, 'error' : None, 'source': sourceUrl}

    # Don't assume spelling by default, make sure API is enabled first!
    if not self.isGooglePhotosEnabled():
      return {'mimetype' : None, 'error' : '"Photos Library API" is not enabled on\nhttps://console.developers.google.com\n\nCheck the Photoframe Wiki for details', 'source': None}
    else:
      return {'mimetype' : None, 'error' : 'No images could be found,\nCheck spelling or make sure you have added albums', 'source': None}

  def isGooglePhotosEnabled(self):
    url = 'https://photoslibrary.googleapis.com/v1/albums'
    data = self.requestUrl(url, params={'pageSize':1})
    '''
{\n  "error": {\n    "code": 403,\n    "message": "Photos Library API has not been used in project 742138104895 before or it is disabled. Enable it by visiting https://console.developers.google.com/apis/api/photoslibrary.googleapis.com/overview?project=742138104895 then retry. If you enabled this API recently, wait a few minutes for the action to propagate to our systems and retry.",\n    "status": "PERMISSION_DENIED",\n    "details": [\n      {\n        "@type": "type.googleapis.com/google.rpc.Help",\n        "links": [\n          {\n            "description": "Google developers console API activation",\n            "url": "https://console.developers.google.com/apis/api/photoslibrary.googleapis.com/overview?project=742138104895"\n          }\n        ]\n      }\n    ]\n  }\n}\n'
    '''
    return not (data['status'] == 403 and 'Enable it by visiting' in data['content'])

  def getUrlFromImages(self, types, displaySize, images):
    # Next, pick an image
    count = len(images)
    offset = random.SystemRandom().randint(0,count-1)
    for i in range(0, count):
      index = (i + offset) % count
      proposed = images[index]['baseUrl']
      if self.memorySeen(proposed):
        continue
      self.memoryRemember(proposed)

      entry = images[index]
      # Make sure we don't get a video, unsupported for now (gif is usually bad too)
      if entry['mimeType'] in types:
        # Calculate the size we need to avoid black borders
        ow = float(entry['mediaMetadata']['width'])
        oh = float(entry['mediaMetadata']['height'])
        ar = ow/oh

        if ow > displaySize['width']:
          width = displaySize['width']
          height = int(float(displaySize['width']) / ar)
        else:
          width = int(float(displaySize['height']) * ar)
          height = displaySize['height']

        return entry['mimeType'], entry['baseUrl'] + "=w" + str(width) + "-h" + str(height), entry['productUrl']
      else:
        logging.warning('Unsupported media: %s' % (entry['mimeType']))
      entry = None
    return None, None, None

  def getQueryForKeyword(self, keyword):
    result = None
    keyword = keyword.upper().lower().strip()
    extras = self.getExtras()
    if extras is None:
      extras = {}

    if keyword == 'latest':
      logging.debug('Use latest 1000 images')
      result = {
        'pageSize' : 100, # 100 is API max
        'filters': {
          'mediaTypeFilter': {
            'mediaTypes': [
              'PHOTO'
            ]
          }
        }
      }
    elif keyword in extras:
      result = {
        'pageSize' : 100, # 100 is API max
        'albumId' : extras[keyword]['albumId']
      }
    return result

  def translateKeywordToId(self, keyword):
    keyword = keyword.upper().lower().strip()
    albumid = None
    source = None

    if keyword == '':
      logging.error('Cannot use blank album name')
      return None

    if keyword == 'latest':
      return None

    logging.debug('Query Google Photos for album named "%s"', keyword)
    url = 'https://photoslibrary.googleapis.com/v1/albums'
    params={}
    while True:
      data = self.requestUrl(url, params=params)
      if data['status'] != 200:
        return None
      data = json.loads(data['content'])
      for i in range(len(data['albums'])):
        if 'title' in data['albums'][i] and data['albums'][i]['title'].upper().lower().strip() == keyword:
          logging.debug('Found album: ' + repr(data['albums'][i]))
          albumid = data['albums'][i]['id']
          source = data['albums'][i]['productUrl']
          break
      if albumid is None and 'pageToken' in data:
        logging.info('Another page of albums available')
        params['nextPageToken'] = data['pageToken']
        continue
      break

    if albumid is None:
      url = 'https://photoslibrary.googleapis.com/v1/sharedAlbums'
      params = {}
      while True:
        data = self.requestUrl(url, params=params)
        if data['status'] != 200:
          return None
        data = json.loads(data['content'])
        for i in range(len(data['sharedAlbums'])):
          if 'title' in data['sharedAlbums'][i] and data['sharedAlbums'][i]['title'].upper().lower().strip() == keyword:
            albumid = data['sharedAlbums'][i]['id']
            source = data['albums'][i]['productUrl']
            break
        if albumid is None and 'pageToken' in data:
          logging.info('Another page of shared albums available')
          params['nextPageToken'] = data['pageToken']
          continue
        break

    if albumid is None:
      return None
    return {'albumId': albumid, 'sourceUrl' : source}

  def getImagesFor(self, keyword):
    images = None
    filename = os.path.join(self.getStoragePath(), self.hashString(keyword) + '.json')
    result = []
    if not os.path.exists(filename):
      # First time, translate keyword into albumid
      params = self.getQueryForKeyword(keyword)
      if params is None:
        logging.error('Unable to create query the keyword "%s"', keyword)
        return None

      url = 'https://photoslibrary.googleapis.com/v1/mediaItems:search'
      maxItems = 1000 # Should be configurable

      while len(result) < maxItems:
        data = self.requestUrl(url, data=params, usePost=True)
        if data['status'] != 200:
          logging.warning('Requesting photo failed with status code %d', data['status'])
          logging.warning('More details: ' + repr(data['content']))
          break
        else:
          data = json.loads(data['content'])
          logging.debug('Got %d entries, adding it to existing %d entries', len(data['mediaItems']), len(result))
          result += data['mediaItems']
          if 'nextPageToken' not in data:
            break
          params['pageToken'] = data['nextPageToken']
          logging.debug('Fetching another result-set for this keyword')

      if len(result) > 0:
        with open(filename, 'w') as f:
          json.dump(result, f)
      else:
        logging.error('No result returned for keyword "%s"!', keyword)

    # Now try loading
    if os.path.exists(filename):
      with open(filename, 'r') as f:
        images = json.load(f)
    return images
