import threading
import logging
import os
import random
import datetime
import hashlib
import time
import json
import math

from modules.remember import remember
from modules.helper import helper
from modules.colormatch import colormatch

class slideshow:
	def __init__(self, display, settings, oauth):
		self.thread = None
		self.display = display
		self.settings = settings
		self.oauth = oauth
		self.colormatch = colormatch(self.settings.get('colortemp-script'), 3500)

	def start(self, blank=False):
		if blank:
			self.display.clear()

		if self.settings.get('oauth_token') is None:
			self.display.message('Please link photoalbum\n\nSurf to http://%s:7777/' % self.settings.get('local-ip'))
			logging.info('You need to link your photoalbum first')
		elif self.thread is None:
			self.thread = threading.Thread(target=self.presentation)
			self.thread.daemon = True
			self.thread.start()

	def presentation(self):
		while True:
			imgs = cache = memory = None
			tries = 50
			while tries > 0:
				imgs, cache = self.getImages()
				if not imgs:
					tries -= 1
					continue

				memory = remember(cache, len(imgs['feed']['entry']))
				if memory.seenAll():
					logging.debug('Seen all images, try again')
					tries -= 1
					continue

				# Now, lets make sure we didn't see this before
				uri, mime, title, ts = self.pickImage(imgs, memory)
				if uri == '':
					tries -= 1
					continue

				filename = os.path.join(self.settings.get('tempfolder'), 'image.%s' % helper.getExtension(mime))
				if self.downloadImage(uri, filename):
					self.display.image(filename)
					break
				else:
					tries -= 1

			if tries == 0:
				self.display.message("Unable to download ANY images\nCheck that you have photos\nand queries aren't too strict")
			time.sleep(self.settings.getUser('interval'))
			if int(time.strftime('%H')) >= self.settings.getUser('display-off'):
				logging.debug("It's after hours, exit quietly")
				break
		self.thread = None

	def pickImage(self, images, memory):
		ext = ['jpg','png','dng','jpeg','gif','bmp']
		count = len(images['feed']['entry'])
		tries = 5

		while tries > 0:
			i = random.SystemRandom().randint(0,count-1)
			if not memory.seen(i):
				memory.saw(i)
				entry = images['feed']['entry'][i]
				# Make sure we don't get a video, unsupported for now (gif is usually bad too)
				if 'image' in entry['content']['type'] and 'gphoto$videostatus' not in entry:
					break
				else:
					logging.warning('Unsupported media: %s' % entry['content']['type'])
			else:
				logging.debug('Already seen index %d' % i)
			tries -= 1

		if tries == 0:
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

	def getImages(self):
		keyword = self.settings.getKeyword()

		# Create filename from keyword
		filename = hashlib.new('md5')
		filename.update(keyword)
		filename = filename.hexdigest() + ".json"
		filename = os.path.join(self.settings.get('tempfolder'), filename)

		if os.path.exists(filename): # Check age!
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
		with open(filename) as f:
			images = json.load(f)
		logging.debug('Loaded %d images into list' % len(images['feed']['entry']))
		return images, filename

	def downloadImage(self, uri, dest):
		logging.debug('Downloading %s...' % uri)
		filename, ext = os.path.splitext(dest)
		temp = "%s-org%s" % (filename, ext)
		if self.oauth.request(uri, destination=temp):
			if self.colormatch.hasSensor():
				if not self.colormatch.adjust(temp, dest):
					logging.warning('Unable to adjust image to colormatch, using original')
					os.rename(temp, dest)
			else:
				logging.info('No color temperature info yet')
				os.rename(temp, dest)
			return True
		else:
			return False

