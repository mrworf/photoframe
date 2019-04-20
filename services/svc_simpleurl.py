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
import logging

from modules.helper import helper

class SimpleUrl(BaseService):
  SERVICE_NAME = 'Simple URL'
  SERVICE_ID   = 3

  def __init__(self, configDir, id, name):
    BaseService.__init__(self, configDir, id, name, needConfig=False, needOAuth=False)

    self.brokenUrls = []

  def helpKeywords(self):
    return 'Each item is a URL that should return a single image. The URL may contain the terms "{width}" and/or "{height}" which will be replaced by numbers describing the size of the display.'

  def removeKeywords(self, index):
    url = self.getKeywords()[index]
    result = BaseService.removeKeywords(self, index)
    if result and url in self.brokenUrls:
      self.brokenUrls.remove(url)
    return result

  def getMessages(self):
    msgs = BaseService.getMessages(self)
    if len(self.brokenUrls) != 0:
      msgs.append(
        {
          'level': 'WARNING',
          'message': 'Broken urls or unsupported images detected!\nPlease remove %s' % str([".../"+self.getUrlFilename(url) for url in self.brokenUrls]),
          'link': None
        }
      )
    return msgs


  def getUrlFilename(self, url):
    return url.rsplit("/", 1)[-1]

  def selectImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize, randomize):
    result = BaseService.selectImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize, randomize)
    
    # catch unsupported mimetypes (can only be done after downloading the image)
    # if no other errors occured
    if result is not None and result["error"] is None and result["mimetype"] not in supportedMimeTypes:
      logging.warning("unsupported mimetype '%s'. You should remove '.../%s' from keywords" % (result["mimetype"], self.getUrlFilename(result["source"])))
      self.brokenUrls.append(result["source"])
      # retry once (with another image)
      result = BaseService.selectImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize, randomize)
      if result is not None and result["error"] is None and result["mimetype"] not in supportedMimeTypes:
        logging.warning("unsupported mimetype '%s'. You should remove '.../%s' from keywords" % (result["mimetype"], self.getUrlFilename(result["source"])))
        self.brokenUrls.append(result["source"])
        return {'id': None, 'mimetype': None, 'error': '%s includes urls that link to unsupported files!' % self.SERVICE_NAME, 'source': None}

    return result

  def getImagesFor(self, keyword):
    url = keyword
    if url in self.brokenUrls:
      return []
    image = {"id": self.hashString(url), "url": url, "source": url, "mimetype": None, "size": None, "filename": self.getUrlFilename(url)}
    return [image]

  def addUrlParams(self, url, _recommendedSize, displaySize):
    url = url.replace('{width}', str(displaySize['width']))
    url = url.replace('{height}', str(displaySize['height']))
    return url

  # Treat the entire service as one album
  # That way you can group images by creating multiple Simple Url Services
  def nextAlbum(self):
    # Tell the serviceManager to use next service instead
    return False

  def prevAlbum(self):
    # Tell the serviceManager to use previous service instead
    return False

  def resetToLastAlbum(self):
    self.resetIndices()
