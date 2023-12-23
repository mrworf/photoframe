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


class Pexels(BaseService):
    SERVICE_NAME = 'Pexels'
    SERVICE_ID = 5
    MAX_ITEMS = 1000

    # Under development, uses configuration which the UX doesn't handle yet
    AUTHKEY = ''

    def __init__(self, configDir, id, name):
        BaseService.__init__(self, configDir, id, name, needConfig=False)

    def getConfigurationFields(self):
        return {'authkey' : {'type' : 'STR', 'name' : 'API key', 'description' : 'A pexels.com API key in order to access their API endpoints'}}

    def helpKeywords(self):
        return 'Type in a query for the kind of images you want. Can also use "curated" for a curated selection'

    def getQueryForKeyword(self, keyword):
        result = None
        extras = self.getExtras()
        if extras is None:
            extras = {}

        if keyword == 'curated':
            logging.debug('Use latest 1000 images')
            result = {
                'per_page': 80  # 80 is API max
            }
        else:
            result = {
                'per_page': 80,  # 80 is API max
                'query' : keyword
            }
        return result

    def selectImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize, randomize):
        result = BaseService.selectImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize, randomize)
        if result is not None:
            return result

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
            # First time, translate keyword into query
            params = self.getQueryForKeyword(keyword)
            if params is None:
                logging.error('Unable to create query the keyword "%s"', keyword)
                return [BaseService.createImageHolder(self)
                        .setError('Unable to get photos using keyword "%s"' % keyword)]

            if keyword == 'curated':
                url = 'https://api.pexels.com/v1/curated'
            else:
                url = 'https://api.pexels.com/v1/search'
            maxItems = Pexels.MAX_ITEMS  # Should be configurable

            while len(result) < maxItems:
                data = self.requestUrl(url, params=params, extraHeaders={'Authorization' : Pexels.AUTHKEY})
                if not data.isSuccess():
                    logging.warning('Requesting photo failed with status code %d', data.httpcode)
                    logging.warning('More details: ' + repr(data.content))
                    break
                else:
                    data = json.loads(data.content.decode('utf-8'))
                    if 'photos' not in data:
                        break
                    logging.debug('Got %d entries, adding it to existing %d entries',
                                  len(data['photos']), len(result))
                    result += data['photos']
                    if 'next_page' not in data:
                        break
                    url = data['next_page']
                    params = None # Since they're built-in
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
        # parse Pexels specific keys into a format that the base service can understand
        if data is None:
            return None
        parsedImages = []
        for entry in data:
            try:
                item = BaseService.createImageHolder(self)
                item.setId(entry['id'])
                item.setSource(entry['url'])
                item.setUrl(entry['src']['original'])
                item.setDimensions(entry['width'], entry['height'])
                item.allowCache(True)
                item.setContentProvider(self)
                item.setContentSource(keyword)
                parsedImages.append(item)
            except Exception:
                logging.exception('Entry could not be loaded')
                logging.debug('Contents of entry: ' + repr(entry))
        return parsedImages

    def getContentUrl(self, image, hints):
        # Utilize pexels to shrink it for us
        logging.debug('PEXEL URL: %s', image.url)
        return image.url + "?auto=compress&cs=tinysrgb&fit=crop&h=%d&w=%s" % (hints['size']["height"], hints['size']["width"])
