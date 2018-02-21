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
import threading
import logging
import os
import random
import datetime
import hashlib
import time
import json
import math
import re
import subprocess

from modules.remember import remember
from modules.helper import helper
from modules.colormatch import colormatch

class slideshow:
	def __init__(self, display, settings, oauth):
		self.thread = None
		self.display = display
		self.settings = settings
		self.oauth = oauth
		self.colormatch = colormatch(self.settings.get('colortemp-script'), 2700) # 2700K = Soft white, lowest we'll go
		self.imageCurrent = None
		self.imageMime = None
		self.void = open(os.devnull, 'wb')

	def getCurrentImage(self):
		return self.imageCurrent, self.imageMime

	def start(self, blank=False):
		if blank:
			self.display.clear()

		if self.settings.get('oauth_token') is None:
			self.display.message('Photoalbum isn\'t ready yet\n\nPlease direct your webbrowser to\n\nhttp://%s:7777/' % self.settings.get('local-ip'))
			logging.info('You need to link your photoalbum first')
		elif self.thread is None:
			self.thread = threading.Thread(target=self.presentation)
			self.thread.daemon = True
			self.thread.start()

	def presentation(self):
		logging.debug('Starting presentation')
		seen = []
		delay = 0
		while True:
			# Avoid showing images if we're past bedtime
			if int(time.strftime('%H')) >= self.settings.getUser('display-off'):
				logging.debug("It's after hours, exit quietly")
				break

			imgs = cache = memory = None
			index = self.settings.getKeyword()
			tries = 1000
			time_process = time.time()
			while tries > 0:
				tries -= 1
				if len(seen) == self.settings.countKeywords():
					# We've viewed all images, reset
					logging.info('All images we have keywords for have been seen, restart')
					for saw in seen:
						remember(saw, 0).forget()
					remember('/tmp/overallmemory.json', 0).forget()
					if self.settings.getUser('refresh-content') == 0:
						logging.info('Make sure we refresh all images now')
						for saw in seen:
							os.remove(saw)
					seen = []


				keyword = self.settings.getKeyword(index)
				imgs, cache = self.getImages(keyword)
				memory = remember(cache, len(imgs['feed']['entry']))

				if not imgs or memory.seenAll():
					if not imgs:
						logging.error('Failed to load image list for keyword %s' % keyword)
					elif memory.seenAll():
						seen.append(cache)
						logging.debug('All images for keyword %s has been shown' % keyword)
					index += 1
					if index == self.settings.countKeywords():
						index = 0
					continue

				# Now, lets make sure we didn't see this before
				uri, mime, title, ts = self.pickImage(imgs, memory)
				if uri == '':
					continue # Do another one (well, it means we exhausted available images for this keyword)

				# Avoid having duplicated because of overlap from keywords
				memory = remember('/tmp/overallmemory.json', 0)
				if memory.seen(uri):
					continue
				else:
					memory.saw(uri)

				ext = helper.getExtension(mime)
				if ext is not None:
					filename = os.path.join(self.settings.get('tempfolder'), 'image.%s' % ext)
					if self.downloadImage(uri, filename):
						self.imageCurrent = filename
						self.imageMime = mime
						break
				else:
					logging.warning('Mime type %s isn\'t supported' % mime)

			time_process = time.time() - time_process

			if tries == 0:
				display.message('Ran into issues showing images.\n\nIs network down?')

			# Delay before we show the image (but take processing into account)
			# This should keep us fairly consistent
			if time_process < delay:
				time.sleep(delay - time_process)
			self.display.image(self.imageCurrent)
			os.remove(self.imageCurrent)

			delay = self.settings.getUser('interval')
		self.thread = None

	def pickImage(self, images, memory):
		ext = ['jpg','png','dng','jpeg','gif','bmp']
		count = len(images['feed']['entry'])

		i = random.SystemRandom().randint(0,count-1)
		while not memory.seenAll():
			proposed = images['feed']['entry'][i]['content']['src']
			if not memory.seen(proposed):
				memory.saw(proposed)
				entry = images['feed']['entry'][i]
				# Make sure we don't get a video, unsupported for now (gif is usually bad too)
				if 'image' in entry['content']['type'] and 'gphoto$videostatus' not in entry:
					break
				else:
					logging.warning('Unsupported media: %s' % entry['content']['type'])
			else:
				i += 1
				if i == count:
					i = 0

		if memory.seenAll():
			logging.error('Failed to find any image, abort')
			return ('', '', '', 0)

		title = entry['title']['$t']
		parts = title.lower().split('.')
		if len(parts) > 0 and parts[len(parts)-1] in ext:
			# Title isn't title, it's a filename
			title = ""
		uri = entry['content']['src']
		timestamp = datetime.datetime.fromtimestamp((float)(entry['gphoto$timestamp']['$t']) / 1000)
		mime = entry['content']['type']

		# Due to google's unwillingness to return what I own, we need to hack the URI
		uri = uri.replace('/s1600/', '/s%s/' % self.settings.getUser('width'), 1)

		return (uri, mime, title, timestamp)

	def getImages(self, keyword):
		# Create filename from keyword
		filename = hashlib.new('md5')
		filename.update(keyword)
		filename = filename.hexdigest() + ".json"
		filename = os.path.join(self.settings.get('tempfolder'), filename)

		if os.path.exists(filename) and self.settings.getUser('refresh-content') > 0: # Check age!
			age = math.floor( (time.time() - os.path.getctime(filename)) / 3600)
			if age >= self.settings.getUser('refresh-content'):
				logging.debug('File too old, %dh > %dh, refreshing' % (age, self.settings.getUser('refresh-content')))
				os.remove(filename)
				# Make sure we don't remember since we're refreshing
				memory = remember(filename, 0)
				memory.forget()

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
				'fields' : 'entry(title,content,gphoto:timestamp,gphoto:videostatus)' # No unnecessary stuff
			}
			if keyword != "":
				params['q'] = keyword
			url = 'https://picasaweb.google.com/data/feed/api/user/default'
			logging.debug('Downloading image list for %s...' % keyword)
			data = self.oauth.request(url, params=params)
			with open(filename, 'w') as f:
				f.write(data.content)
		images = None
		try:
			with open(filename) as f:
				images = json.load(f)
			logging.debug('Loaded %d images into list' % len(images['feed']['entry']))
			return images, filename
		except:
			logging.exception('Failed to load images')
			os.remove(filename)
			return None, filename

	def downloadImage(self, uri, dest):
		logging.debug('Downloading %s...' % uri)
		filename, ext = os.path.splitext(dest)
		temp = "%s-org%s" % (filename, ext)
		if self.oauth.request(uri, destination=temp):
			helper.makeFullframe(temp, self.settings.getUser('width'), self.settings.getUser('height'))
			if self.colormatch.hasSensor():
				if not self.colormatch.adjust(temp, dest):
					logging.warning('Unable to adjust image to colormatch, using original')
					os.rename(temp, dest)
				else:
					os.remove(temp)
			else:
				os.rename(temp, dest)
			return True
		else:
			return False

