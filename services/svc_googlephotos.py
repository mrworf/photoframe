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
from .base import BaseService
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
        return 'Currently, each entry represents the name of an album (case-insensitive). ' \
            'If you want the latest photos, simply write "latest" as album'

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
            return 'Out of range, index = %d' % index
        keywords = keys[index]
        extras = self.getExtras()
        if keywords not in extras:
            return 'https://photos.google.com/'
        return extras[keywords]['sourceUrl']

    def getKeywordDetails(self, index):
        # Override so we can tell more, for google it means we simply review what we would show
        keys = self.getKeywords()
        if index < 0 or index >= len(keys):
            return 'Out of range, index = %d' % index
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
                longer.append('%s has %d items' % (i, types[i]))
            else:
                unsupported.append('%s has %d items' % (i, types[i]))

        extra = ''
        if len(unsupported) > 0:
            longer.append('')
            longer.append('Mime types listed below were also found but are as of yet not supported:')
            longer.extend(unsupported)
        if countu > 0:
            extra = ' where %d is not yet unsupported' % countu
        return {
            'short': '%d items fetched from album, %d images%s, %d videos, %d is unknown. %d has been shown' %
            (
                len(data),
                counti + countu,
                extra,
                countv,
                len(data) - counti - countv,
                len(memory)
            ),
            'long': longer
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
                return {'error': 'No such album "%s"' % keywords, 'keywords': keywords}

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
        data = self.requestUrl(url, params={'pageSize': 1})
        ''' The error we see from google in this case:
        {
            "error": {
                "code": 403,
                "message": "Photos Library API has not been used in project 742138104895 before or it is disabled.
                            Enable it by visiting https://console.developers.google.com/someurl then retry.
                            If you enabled this API recently, wait a few minutes for the action to propagate
                            to our systems and retry.",
                "status": "PERMISSION_DENIED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.Help",
                        "links": [
                            {
                                "description": "Google developers console API activation",
                                "url": "https://console.developers.google.com/someurl"
                            }
                        ]
                    }
                ]
            }
        }
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
                'pageSize': 100,  # 100 is API max
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
                'pageSize': 100,  # 100 is API max
                'albumId': extras[keyword]['albumId']
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

        logging.debug('Query Google Photos for album named "%s"', keyword)
        url = 'https://photoslibrary.googleapis.com/v1/albums'
        params = {'pageSize': 50}  # 50 is api max
        while True:
            data = self.requestUrl(url, params=params)
            if not data.isSuccess():
                return None
            data = json.loads(data.content.decode('utf-8'))
            for i in range(len(data['albums'])):
                if 'title' in data['albums'][i]:
                    logging.debug('Album: %s' % data['albums'][i]['title'])
                if 'title' in data['albums'][i] and data['albums'][i]['title'].upper().lower().strip() == keyword:
                    logging.debug('Found album: ' + repr(data['albums'][i]))
                    albumname = data['albums'][i]['title']
                    albumid = data['albums'][i]['id']
                    source = data['albums'][i]['productUrl']
                    break
            if albumid is None and 'nextPageToken' in data:
                logging.debug('Another page of albums available')
                params['pageToken'] = data['nextPageToken']
                continue
            break

        if albumid is None:
            url = 'https://photoslibrary.googleapis.com/v1/sharedAlbums'
            params = {'pageSize': 50}  # 50 is api max
            while True:
                data = self.requestUrl(url, params=params)
                if not data.isSuccess():
                    return None
                data = json.loads(data.content.decode('utf-8'))
                if 'sharedAlbums' not in data:
                    logging.debug('User has no shared albums')
                    break
                for i in range(len(data['sharedAlbums'])):
                    if 'title' in data['sharedAlbums'][i]:
                        logging.debug('Shared Album: %s' % data['sharedAlbums'][i]['title'])
                    if 'title' in data['sharedAlbums'][i] \
                       and data['sharedAlbums'][i]['title'].upper().lower().strip() == keyword:
                        albumname = data['sharedAlbums'][i]['title']
                        albumid = data['sharedAlbums'][i]['id']
                        source = data['sharedAlbums'][i]['productUrl']
                        break
                if albumid is None and 'nextPageToken' in data:
                    logging.debug('Another page of shared albums available')
                    params['pageToken'] = data['nextPageToken']
                    continue
                break

        if albumid is None:
            return None
        return {'albumId': albumid, 'sourceUrl': source, 'albumName': albumname}

    def selectImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize, randomize):
        result = BaseService.selectImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize, randomize)
        if result is not None:
            return result

        if not self.isGooglePhotosEnabled():
            return BaseService.createImageHolder(self) \
                .setError('"Photos Library API" is not enabled on\nhttps://console.developers.google.com\n\n'
                          'Check the Photoframe Wiki for details')
        else:
            return BaseService.createImageHolder(self).setError('No (new) images could be found.\n'
                                                                'Check spelling or make sure you have added albums')

    def freshnessImagesFor(self, keyword):
        filename = os.path.join(self.getStoragePath(), self.hashString(keyword) + '.json')
        if not os.path.exists(filename):
            return 0  # Superfresh
        # Hours should be returned
        return (time.time() - os.stat(filename).st_mtime) / 3600

    def clearImagesFor(self, keyword):
        filename = os.path.join(self.getStoragePath(), self.hashString(keyword) + '.json')
        if os.path.exists(filename):
            logging.info('Cleared image information for %s' % keyword)
            os.unlink(filename)

    def getImagesFor(self, keyword, rawReturn=False):
        filename = os.path.join(self.getStoragePath(), self.hashString(keyword) + '.json')
        result = []
        if not os.path.exists(filename):
            # First time, translate keyword into albumid
            params = self.getQueryForKeyword(keyword)
            if params is None:
                logging.error('Unable to create query the keyword "%s"', keyword)
                return [BaseService.createImageHolder(self)
                        .setError('Unable to get photos using keyword "%s"' % keyword)]

            url = 'https://photoslibrary.googleapis.com/v1/mediaItems:search'
            maxItems = GooglePhotos.MAX_ITEMS  # Should be configurable

            while len(result) < maxItems:
                data = self.requestUrl(url, data=params, usePost=True)
                if not data.isSuccess():
                    logging.warning('Requesting photo failed with status code %d', data.httpcode)
                    logging.warning('More details: ' + repr(data.content))
                    break
                else:
                    data = json.loads(data.content.decode('utf-8'))
                    if 'mediaItems' not in data:
                        break
                    logging.debug('Got %d entries, adding it to existing %d entries',
                                  len(data['mediaItems']), len(result))
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
                return []

        # Now try loading
        if os.path.exists(filename):
            try:
                print(filename)
                with open(filename, 'r') as f:
                    albumdata = json.load(f)
            except Exception:
                logging.exception('Failed to decode JSON file, maybe it was corrupted? Size is %d',
                                  os.path.getsize(filename))
                logging.error('Since file is corrupt, we try to save a copy for later analysis (%s.corrupt)', filename)
                try:
                    if os.path.exists(filename + '.corrupt'):
                        os.unlink(filename + '.corrupt')
                    os.rename(filename, filename + '.corrupt')
                except Exception:
                    logging.exception('Failed to save copy of corrupt file, deleting instead')
                    os.unlink(filename)
                albumdata = None
        if rawReturn:
            return albumdata
        return self.parseAlbumInfo(albumdata, keyword)

    def parseAlbumInfo(self, data, keyword):
        # parse GooglePhoto specific keys into a format that the base service can understand
        if data is None:
            return None
        parsedImages = []
        for entry in data:
            try:
                if entry['mimeType'] not in helper.getSupportedTypes():
                    continue
                item = BaseService.createImageHolder(self)
                item.setId(entry['id'])
                item.setSource(entry['productUrl']).setMimetype(entry['mimeType'])
                item.setDimensions(entry['mediaMetadata']['width'], entry['mediaMetadata']['height'])
                item.allowCache(True)
                item.setContentProvider(self)
                item.setContentSource(keyword)
                parsedImages.append(item)
            except Exception:
                logging.exception('Entry could not be loaded')
                logging.debug('Contents of entry: ' + repr(entry))
        return parsedImages

    def getContentUrl(self, image, hints):
        # Tricky, we need to obtain the real URL before doing anything
        data = self.requestUrl('https://photoslibrary.googleapis.com/v1/mediaItems/%s' % image.id)
        if data.result != RequestResult.SUCCESS:
            logging.error('%d,%d: Failed to get URL', data.httpcode, data.result)
            return None

        data = json.loads(data.content.decode('utf-8'))
        if 'baseUrl' not in data:
            logging.error('Data from Google didn\'t contain baseUrl, see original content:')
            logging.error(repr(data))
            return None
        return data['baseUrl'] + "=w" + str(hints['size']["width"]) + "-h" + str(hints['size']["height"])
