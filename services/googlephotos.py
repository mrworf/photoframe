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
import os
import hashlib
import json
import ..modules.settings as settings

class GooglePhotos:
	def __init__(self, storage):
		self.scope = ['https://picasaweb.google.com/data/']
		self.oauth = '/root/google_oauth.json'
		self.storage = storage
		self.cacheImages = None
		self.cacheId = None
		self.settings = settings()
		self.settings.load()

	def getScope(self):
		return self.scope

	def getOAuth(self):
		with open(self.oauth, 'rb') as f:
			return json.load(f)

	def setOAuth(self, data):
		with open(self.oauth, 'wb') as f:
			json.dump(data, f)

	def flushImages(self, id):
		if os.path.exists(id):
			os.remove(id)
		if id == self.cacheId:
			self.cacheId = None
			self.cacheImages = None

	def loadImages(self, keyword, force=False):
		"""Has to load images from the service.
		   If possible, use keyword to limit what is being obtained
		   If force is true, has to request data from backend, cannot use any cache
		   Return an id for this list, should cache the data internally if possible
		"""
		# Create filename from keyword
		filename = hashlib.new('md5')
		filename.update(keyword)
		filename = filename.hexdigest() + ".json"
		filename = os.path.join(self.storage, filename)

		if not os.path.exists(filename) or force:
			# Request albums
			# Picasa limits all results to the first 1000, so get them
			params = {
				'kind' : 'photo',
				'start-index' : 1,
				'max-results' : self.settings.get('no_of_pic'),
				'alt' : 'json',
				'access' : 'all',
				'imgmax' : '1600u', # We will replace this with width of framebuffer in pick_image
				# This is where we get cute, we pick from a list of keywords
				'fields' : 'entry(title,content,gphoto:timestamp)' # No unnecessary stuff
			}
			if keyword != "":
				params['q'] = keyword
			url = 'https://picasaweb.google.com/data/feed/api/user/default'
			logging.debug('Downloading image list for %s...' % keyword)
			data = self.oauth.request(url, params=params)
			with open(filename, 'w') as f:
				f.write(data.content)
		images = None
		with open(filename) as f:
			images = json.load(f)
		logging.debug('Loaded %d images into list' % len(images['feed']['entry']))
		self.cacheImages = images
		self.cacheId = filename
		return filename

	def _prepCache(self, id):
		if self.cacheId != id:
			with open(id, 'rb') as f:
				self.cacheImages = json.load(f)
				self.cacheId = id

	def getCount(self, id):
		self._prepCache(id)
		return len(self.cacheImages['feed']['entry'])

	def getImage(self, id, image, width, height):
		self._prepCache(id)

		ext = ['jpg','png','dng','jpeg','gif','bmp']
		count = len(images['feed']['entry'])
		if image < 0 or image >= count:
			return False

		entry = images['feed']['entry'][i]
		# Make sure we don't get a video, unsupported for now (gif is usually bad too)
		if 'image' in entry['content']['type'] and 'gphoto$videostatus' not in entry:
			return None
		else:
			logging.warning('Unsupported media: %s' % entry['content']['type'])
		"""
		title = entry['title']['$t']
		parts = title.lower().split('.')
		if len(parts) > 0 and parts[len(parts)-1] in ext:
			# Title isn't title, it's a filename
			title = ""
		uri = entry['content']['src']
		timestamp = datetime.datetime.fromtimestamp((float)(entry['gphoto$timestamp']['$t']) / 1000)
		mime = entry['content']['type']
		"""

		# Due to google's unwillingness to return what I own, we need to hack the URI
		uri = uri.replace('/s1600/', '/s%s/' % width, 1)

		return uri
