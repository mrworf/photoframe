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

class ImageHolder:
  def __init__(self):
    #  "id" : a unique - preferably not-changing - ID to identify the same image in future requests, e.g. hashString(imageUrl)
    #  "mimetype" : the filetype you downloaded, for example "image/jpeg"
    #  "error" : None or a human readable text string as to why you failed
    #  "source" : Link to where the item came from or None if not provided
    # "url":      Link to the actual image file
    # "dimensions":     a key/value map containing "width" and "height" of the image
    #             can be None, but the service won't be able to determine a recommendedImageSize for 'addUrlParams'
    # "filename": the original filename of the image or None if unknown (only used for debugging purposes)
    self.id = None
    self.mimetype = None
    self.error = None
    self.source = None
    self.url = None
    self.filename = None
    self.dimensions = None
    self.cacheAllow = False
    self.cacheUsed = False

  def setId(self, id):
    self.id = id
    return self

  def setMimetype(self, mimetype):
    self.mimetype = mimetype
    return self

  def setError(self, error):
    self.error = error
    return self

  def setSource(self, source):
    self.source = source
    return self

  def setUrl(self, url):
    self.url = url
    return self

  def setFilename(self, filename):
    self.filename = filename
    return self

  def setDimensions(self, width, height):
    self.dimensions = {'width': int(width), 'height': int(height)}
    return self

  def allowCache(self, allow):
    self.cacheAllow = allow
    return self

  def getCacheId(self):
    if self.id is None:
      return None
    return hashlib.sha1(self.id).hexdigest()
