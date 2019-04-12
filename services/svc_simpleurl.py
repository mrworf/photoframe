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

  def helpKeywords(self):
    return 'Each item is a URL that should return a single image. The URL may contain the terms "{width}" and/or "{height}" which will be replaced by numbers describing the size of the display.'

  def prepareNextItem(self, destinationDir, supportedMimeTypes, displaySize, randomize):
    urlList = list(self.getKeywords())
    count = len(urlList)
    if count == 0:
      return {'mimetype': None, 'error': 'No URLs have been specified', 'source': None, 'filename': None}

    if randomize:
      offset = self.getRandomKeywordIndex()
    else:
      offset = self.keywordIndex + self.imageIndex

    self.imageIndex = 0
    for i in range(0, count):
      if not randomize and (offset + i) >= count:
        break

      self.keywordIndex = (offset + i) % count
      imageUrl = urlList[self.keywordIndex]
      imageUrl = imageUrl.replace('{width}', str(displaySize['width']))
      imageUrl = imageUrl.replace('{height}', str(displaySize['height']))
      imageId = self.hashString(imageUrl)
      filename = os.path.join(destinationDir, imageId)
      if randomize and self.memorySeen(imageId):
        logging.debug("Skipping already displayed image '%s'!" % filename)
        continue
      cachedImageSize = helper.getImageSize(filename, deleteCurruptedImage=True)
      if cachedImageSize is not None:
        if not self.isCorrectOrientation(cachedImageSize, displaySize):
          logging.debug("Skipping image '%s' due to wrong orientation!" % filename)
          continue

        # use cached image
        logging.debug("using cached image: '%s'" % filename)
        return {'id': imageId, 'mimetype': helper.getMimeType(filename), 'error': None, 'source': None}

      # download image
      result = self.requestUrl(imageUrl, destination=filename)
      if result['status'] == 200:
        imageSize = helper.getImageSize(filename, deleteCurruptedImage=True)
        if not self.isCorrectOrientation(cachedImageSize, displaySize):
          logging.debug("Skipping image '%s' due to wrong orientation!" % filename)
          continue
        return {'id': imageId, 'mimetype': result['mimetype'], 'error': None, 'source': imageUrl}

      logging.warning('SimpleUrl could not fetch image - status code ' + str(result['status']))
    
    return {'id': None, 'mimetype': None, 'error': 'No images could be found.\nMake sure your urls each link to the actual image file!', 'source': None}


  # Treat the entire service as one album
  # That way you can group images by creating multiple Simple Url Services
  def nextAlbum(self):
    return False

  def prevAlbum(self):
    return False

  def resetToLastAlbum(self):
    self.resetIndices()
