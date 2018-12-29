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

class PicasaWeb(BaseService):
  SERVICE_NAME = 'PicasaWeb'
  SERVICE_ID = 1

  def __init__(self, configDir, id, name):
    BaseService.__init__(self, configDir, id, name, needConfig=False, needOAuth=True)

  def getOAuthScope(self):
    return ['https://www.googleapis.com/auth/photos']

  def helpOAuthConfig(self):
    return 'Please upload client.json from the Google API Console'

  def helpKeywords(self):
    return 'Name of people, location, colors, depiction, pretty much anything that Google Photo search accepts'

  def getMessage(self):
    return 'This provider will cease to function January 1st, 2019. Please use GooglePhotos. For more details, see photoframe wiki'

  def getMessageLink(self):
    return 'https://github.com/mrworf/photoframe/wiki/PicasaWeb-API-ceases-to-work-January-1st,-2019'

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

      mimeType, imageUrl = self.getUrlFromImages(supportedMimeTypes, displaySize['width'], images)
      if imageUrl is None:
        continue
      result = self.requestUrl(imageUrl, destination=destinationFile)
      if result['status'] == 200:
        return {'mimetype' : mimeType, 'error' : None, 'source':None}
      return {'mimetype' : None, 'error' : 'Could not download images from Google Photos', 'source':None}

  def getUrlFromImages(self, types, width, images):
    # Next, pick an image
    count = len(images['feed']['entry'])
    offset = random.SystemRandom().randint(0,count-1)
    for i in range(0, count):
      index = (i + offset) % count
      proposed = images['feed']['entry'][index]['content']['src']
      if self.memorySeen(proposed):
        continue
      self.memoryRemember(proposed)

      entry = images['feed']['entry'][index]
      # Make sure we don't get a video, unsupported for now (gif is usually bad too)
      if entry['content']['type'] in types and 'gphoto$videostatus' not in entry:
        return entry['content']['type'], entry['content']['src'].replace('/s1600/', '/s%d/' % width, 1)
      elif 'gphoto$videostatus' in entry:
        logging.debug('Image is thumbnail for videofile')
      else:
        logging.warning('Unsupported media: %s (video = %s)' % (entry['content']['type'], repr('gphoto$videostatus' in entry)))
      entry = None
    return None, None

  def getImagesFor(self, keyword):
    images = None
    filename = os.path.join(self.getStoragePath(), self.hashString(keyword) + '.json')
    if not os.path.exists(filename):
      # Request albums
      # Picasa limits all results to the first 1000, so get them
      params = {
        'kind' : 'photo',
        'start-index' : 1,
        'max-results' : 1000,
        'alt' : 'json',
        'access' : 'all',
        'imgmax' : '1600u', # We will replace this with width of framebuffer in pick_image
        # This is where we get cute, we pick from a list of keywords
        'fields' : 'entry(title,content,gphoto:timestamp,gphoto:videostatus)', # No unnecessary stuff
        'q' : keyword
      }
      url = 'https://picasaweb.google.com/data/feed/api/user/default'
      data = self.requestUrl(url, params=params)
      if data['status'] != 200:
        logging.warning('Requesting photo failed with status code %d', data['status'])
      else:
        with open(filename, 'w') as f:
          f.write(data['content'])

    # Now try loading
    if os.path.exists(filename):
      with open(filename, 'r') as f:
        images = json.load(f)
    return images