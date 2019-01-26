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
import os
import requests

class SimpleUrl(BaseService):
  SERVICE_NAME = 'Simple URL'
  SERVICE_ID   = 3


  def __init__(self, configDir, id, name):
    BaseService.__init__(self, configDir, id, name, needConfig=False, needOAuth=False)


  def helpKeywords(self):
    return 'Each item is a URL that should return a single image. The URL may contain the terms "{width}" and/or "{height}" which will be replaced by numbers describing the size of the display.'


  def fetchImage(self, destinationFile, supportedMimeTypes, displaySize):
    urlList = list(self.getKeywords())
    if len(urlList) == 0:
      return {'mimetype' : None, 'error' : 'No URLs have been specified', 'source': None}

    Url = urlList[self.getRandomKeywordIndex()]

    Url = Url.replace('{width}', str(displaySize['width']))
    Url = Url.replace('{height}', str(displaySize['height']))

    r = requests.get(Url)
    with open(destinationFile, 'wb') as f:
      for chunk in r.iter_content(chunk_size=1024):
        f.write(chunk)

    if r.status_code == 200:
      return {'mimetype' : r.headers.get('content-type'), 'error' : None, 'source': Url}

    return {'mimetype' : None, 'error' : 'Could not fetch image - status code ' + str(result['status']), 'source': None}


  def prepareNextItem(self, destinationFile, supportedMimeTypes, displaySize):
    self.memoryForget()
    for file in os.listdir(self.getStoragePath()):
      os.unlink(os.path.join(self.getStoragePath(), file))
    result = self.fetchImage(destinationFile, supportedMimeTypes, displaySize)
    return result

