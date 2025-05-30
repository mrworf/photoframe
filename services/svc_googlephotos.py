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
from services.base import BaseService
import os
import json
import logging
import time

from modules.network import RequestResult
from modules.helper import helper

class GooglePhotos(BaseService):
  SERVICE_NAME = 'GooglePhotos'
  SERVICE_ID = 2
  MAX_ITEMS = 8000

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

  def getExtras(self):
    # Normalize
    result = BaseService.getExtras(self)
    if result is None:
      return {}
    return result

  def postSetup(self):
    extras = self.getExtras()
    keywords = self.getKeywords()

    if len(extras) == 0 and keywords is not None and len(keywords) > 0:
      logging.info('Migrating to new format with preresolved album ids')
      for key in keywords:
        if key.lower() == 'latest':
          continue
        albumId = self.translateKeywordToId(key)
        if albumId is None:
          logging.error('Existing keyword cannot be resolved')
        else:
          extras[key] = albumId
      self.setExtras(extras)
    else:
      # Make sure all keywords are LOWER CASE (which is why I wrote it all in upper case :))
      extras_old = self.getExtras()
      extras = {}

      for k in extras_old:
        kk = k.upper().lower().strip()
        if len(extras) > 0 or kk != k:
          extras[kk] = extras_old[k]

      if len(extras) > 0:
        logging.debug('Had to translate non-lower-case keywords due to bug, should be a one-time thing')
        self.setExtras(extras)

      # Sanity, also make sure extras is BLANK if keywords is BLANK
      if len(self.getKeywords()) == 0:
        extras = self.getExtras()
        if len(extras) > 0:
          logging.warning('Mismatch between keywords and extras info, corrected')
          self.setExtras({})

  def getKeywordSourceUrl(self, index):
    keys = self.getKeywords()
    if index < 0 or index >= len(keys):
      return f'Out of range, index = {index}'
    keyword = keys[index]
    extras = self.getExtras()
    if keywords not in extras:
      return 'https://photos.google.com/'
    return extras[keywords]['sourceUrl']

  def getKeywordDetails(self, index):
    # Override so we can tell more, for google it means we simply review what we would show
    keys = self.getKeywords()
    if index < 0 or index >= len(keys):
      return f'Out of range, index = {index}'
    keyword = keys[index]

    # This is not going to be fast...
    data = self.getImagesFor(keyword, rawReturn=True)
    mimes = helper.getSupportedTypes()
    memory = self.memory.getList(keyword)

    countv = 0
    counti = 0
    countu = 0
    types = {}
    for entry in data:
      if entry['mimeType'].startswith('video/'):
        countv += 1
      elif entry['mimeType'].startswith('image/'):
        if entry['mimeType'].lower() in mimes:
          counti += 1
        else:
          countu += 1

      if entry['mimeType'] in types:
        types[entry['mimeType']] += 1
      else:
        types[entry['mimeType']] = 1

    longer = ['Below is a breakdown of the content found in this album']
    unsupported = []
    for i in types:
      if i in mimes:
        longer.append(f'{i} has {types[i]} items')
      else:
        unsupported.append(f'{i} has {types[i]} items')

    extra = ''
    if len(unsupported) > 0:
      longer.append('')
      longer.append('Mime types listed below were also found but are as of yet not supported:')
      longer.extend(unsupported)
    if countu > 0:
      extra = f' where {countu} is not yet unsupported'
    return {
      'short': f'{len(data)} items fetched from album, {counti + countu} images{extra}, {countv} videos, {len(data) - counti - countv} is unknown. {len(memory)} has been shown',
      'long' : longer
    }

  def hasKeywordDetails(self):
    # Override so we can tell more, for google it means we simply review what we would show
    return True

  def removeKeywords(self, index):
    # Override since we need to delete our private data
    keys = self.getKeywords()
    if index < 0 or index >= len(keys):
      return
    keywords = keys[index].upper().lower().strip()
    filename = os.path.join(self.getStoragePath(), self.hashString(keywords) + '.json')
    if os.path.exists(filename):
      os.unlink(filename)
    if BaseService.removeKeywords(self, index):
      # Remove any extras
      extras = self.getExtras()
      if keywords in extras:
        del extras[keywords]
        self.setExtras(extras)
      return True
    else:
      return False

  def validateKeywords(self, keywords):
    tst = BaseService.validateKeywords(self, keywords)
    if tst["error"] is not None:
      return tst

    # Remove quotes around keyword
    if keywords[0] == '"' and keywords[-1] == '"':
      keywords = keywords[1:-1]
    keywords = keywords.upper().lower().strip()

    # No error in input, resolve album now and provide it as extra data
    albumId = None
    if keywords != 'latest':
      albumId = self.translateKeywordToId(keywords)
      if albumId is None:
        return {'error': f'No such album "{keywords}"', 'keywords': keywords}

    return {'error': None, 'keywords': keywords, 'extras': albumId}

  def addKeywords(self, keywords):
    result = BaseService.addKeywords(self, keywords)
    if result['error'] is None and result['extras'] is not None:
      k = result['keywords']
      extras = self.getExtras()
      extras[k] = result['extras']
      self.setExtras(extras)
    return result


  def isGooglePhotosEnabled(self):
    url = 'https://photoslibrary.googleapis.com/v1/albums'
    data = self.requestUrl(url, params={'pageSize':1})
    '''
{\n  "error": {\n    "code": 403,\n    "message": "Photos Library API has not been used in project 742138104895 before or it is disabled. Enable it by visiting https://console.developers.google.com/apis/api/photoslibrary.googleapis.com/overview?project=742138104895 then retry. If you enabled this API recently, wait a few minutes for the action to propagate to our systems and retry.",\n    "status": "PERMISSION_DENIED",\n    "details": [\n      {\n        "@type": "type.googleapis.com/google.rpc.Help",\n        "links": [\n          {\n            "description": "Google developers console API activation",\n            "url": "https://console.developers.google.com/apis/api/photoslibrary.googleapis.com/overview?project=742138104895"\n          }\n        ]\n      }\n    ]\n  }\n}\n'
    '''
    return not (data.httpcode == 403 and 'Enable it by visiting' in data.content)

  def getQueryForKeyword(self, keyword):
    result = None
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
    albumid = None
    source = None
    albumname = None

    if keyword == '':
      logging.error('Cannot use blank album name')
      return None

    if keyword == 'latest':
      return None

    logging.debug(f'Query Google Photos for album named "{keyword}"')
    url = 'https://photoslibrary.googleapis.com/v1/albums'
    params = {'pageSize': 50}  # 50 is api max
    allofit = {}  # Keep track of all responses for debugging
    while True:
      logging.debug(f'Making request to {url} with params {params}')
      data = self.requestUrl(url, params=params)
      if not data.isSuccess():
        logging.error(f'Failed to get albums: {data.content}')
        return None

      result = None
      try:
        result = json.loads(data.content)
        logging.debug(f'Response: {result}')
      except json.JSONDecodeError as e:
        logging.error(f'Failed to decode response: {e}')
        return None

      # Add to allofit for debugging
      # Recursively merge result into allofit
      def merge_dicts(d1, d2):
        for k, v in d2.items():
          if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
            merge_dicts(d1[k], v)
          elif k in d1 and isinstance(d1[k], list) and isinstance(v, list):
            d1[k].extend(v)
          else:
            d1[k] = v
      
      if not allofit:
        allofit.update(result)
      else:
        merge_dicts(allofit, result)

      if not isinstance(result, dict):
        logging.error(f'Invalid response format: {result}')
        return None

      if 'albums' not in result:
        logging.error(f'No albums in response: {result}')
        return None

      # Check personal albums
      for album in result['albums']:
        print(f'Album: {album}')  # Keep print for immediate visibility
        if 'title' in album and album['title']:
          if album['title'].upper().lower().strip() == keyword.upper().lower().strip():
            albumid = album['id']
            source = album['productUrl']
            albumname = album['title']
            break

      # Check shared albums if not found in personal albums
      if albumid is None and 'sharedAlbums' in result:
        for album in result['sharedAlbums']:
          print(f'Shared Album: {album}')  # Keep print for immediate visibility
          if 'title' in album and album['title']:
            if album['title'].upper().lower().strip() == keyword.upper().lower().strip():
              albumid = album['id']
              source = album['productUrl']
              albumname = album['title']
              break

      if albumid is not None or 'nextPageToken' not in result:
        break
      params['pageToken'] = result['nextPageToken']

    # Save allofit to a file for debugging
    with open('allofit.json', 'w') as f:
      json.dump(allofit, f)

    if albumid is None:
      logging.debug(f'No album found with name "{keyword}"')
      return None

    logging.debug(f'Found album: {albumname} (ID: {albumid})')
    return {
      'albumId': albumid,
      'sourceUrl': source,
      'albumName': albumname
    }

  def selectImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize, randomize):
    result = BaseService.selectImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize, randomize)
    if result is not None:
      return result

    if not self.isGooglePhotosEnabled():
      return BaseService.createImageHolder(self).setError('"Photos Library API" is not enabled on\nhttps://console.developers.google.com\n\nCheck the Photoframe Wiki for details')
    else:
      return BaseService.createImageHolder(self).setError('No (new) images could be found.\nCheck spelling or make sure you have added albums')

  def freshnessImagesFor(self, keyword):
    filename = os.path.join(self.getStoragePath(), self.hashString(keyword) + '.json')
    if not os.path.exists(filename):
      return 0 # Superfresh
    # Hours should be returned
    return (time.time() - os.stat(filename).st_mtime) / 3600

  def clearImagesFor(self, keyword):
    filename = os.path.join(self.getStoragePath(), self.hashString(keyword) + '.json')
    if os.path.exists(filename):
      os.unlink(filename)
    logging.info(f'Cleared image information for {keyword}')

  def getImagesFor(self, keyword, rawReturn=False):
    query = self.getQueryForKeyword(keyword)
    if query is None:
      logging.error(f'Unable to create query the keyword "{keyword}"')
      return [BaseService.createImageHolder(self).setError(f'Unable to get photos using keyword "{keyword}"')]

    result = []
    while True:
      data = self.requestUrl('https://photoslibrary.googleapis.com/v1/mediaItems:search', usePost=True, data=query)
      if not data.isSuccess():
        logging.warning(f'Requesting photo failed with status code {data.httpcode}')
        break

      response = None
      try:
        response = json.loads(data.content)
      except json.JSONDecodeError as e:
        logging.error(f'Failed to decode response: {e}')
        break

      if 'mediaItems' not in response:
        break

      logging.debug(f'Got {len(response["mediaItems"])} entries, adding it to existing {len(result)} entries')
      result.extend(response['mediaItems'])

      if 'nextPageToken' not in response:
        break
      query['pageToken'] = response['nextPageToken']

    if len(result) == 0:
      logging.error(f'No result returned for keyword "{keyword}"!')
      return []

    filename = os.path.join(self.getStoragePath(), self.hashString(keyword) + '.json')
    try:
      with open(filename, 'w') as f:
        json.dump(result, f)
    except Exception as e:
      logging.exception(f'Failed to decode JSON file, maybe it was corrupted? Size is {os.path.getsize(filename)}')
      logging.error(f'Since file is corrupt, we try to save a copy for later analysis ({filename}.corrupt)')
      try:
        os.rename(filename, filename + '.corrupt')
      except:
        pass

    if rawReturn:
      return result

    return self.parseAlbumInfo(result, keyword)

  def parseAlbumInfo(self, data, keyword):
    # parse GooglePhoto specific keys into a format that the base service can understand
    result = []
    for entry in data:
      logging.debug(f'Entry: {repr(entry)}')
      result.append(self.createImageHolder().setId(entry['id']).setMimetype(entry['mimeType']))
    return result

  def getContentUrl(self, image, hints):
    # Tricky, we need to obtain the real URL before doing anything
    data = self.requestUrl(f'https://photoslibrary.googleapis.com/v1/mediaItems/{image.id}')
    if not data.isSuccess():
      logging.error(f'{data.httpcode}: Failed to get URL')
      return None
    result = None
    try:
      result = json.loads(data.content)
      return result['baseUrl']
    except (json.JSONDecodeError, KeyError) as e:
      logging.error(f'Failed to get baseUrl: {e}')
      return None
