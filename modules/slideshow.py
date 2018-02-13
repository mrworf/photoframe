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
		self.colormatch = colormatch(self.settings.get('colortemp-script'), 3500)
		self.imageCurrent = None
		self.imageMime = None
		self.void = open(os.devnull, 'wb')

	def getCurrentImage(self):
		return self.imageCurrent, self.imageMime

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
		logging.debug('Starting presentation')
		seen = []
		while True:
			imgs = cache = memory = None
			index = self.settings.getKeyword()
			tries = 1000
			while tries > 0:
				tries -= 1
				if len(seen) == self.settings.countKeywords():
					# We've viewed all images, reset
					logging.info('All images we have keywords for have been seen, restart')
					for saw in seen:
						remember(saw, 0).forget()

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

				filename = os.path.join(self.settings.get('tempfolder'), 'image.%s' % helper.getExtension(mime))
				if self.downloadImage(uri, filename):
					self.display.image(filename)
					self.imageCurrent = filename
					self.imageMime = mime
					break

			if tries == 0:
				display.message('Ran into issues showing images.\n\nIs network down?')

			time.sleep(self.settings.getUser('interval'))
			if int(time.strftime('%H')) >= self.settings.getUser('display-off'):
				logging.debug("It's after hours, exit quietly")
				break
		self.thread = None

	def pickImage(self, images, memory):
		ext = ['jpg','png','dng','jpeg','gif','bmp']
		count = len(images['feed']['entry'])

		i = random.SystemRandom().randint(0,count-1)
		while not memory.seenAll():
			if not memory.seen(i):
				memory.saw(i)
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
		try:
			with open(filename) as f:
				images = json.load(f)
			logging.debug('Loaded %d images into list' % len(images['feed']['entry']))
			return images, filename
		except:
			logging.exception('Failed to load images')
			os.remove(filename)
			return None, filename

	def makeFullframe(self, filename):
		name, ext = os.path.splitext(filename)
		filename_temp = "%s-frame%s" % (name, ext)

		output = subprocess.check_output(['/usr/bin/identify', filename], stderr=self.void)
		m = re.search('([1-9][0-9])*x([1-9][0-9]*)', output)
		if m is None:
			logging.error('Unable to resolve regular expression for image size')
			return False
		width = int(m.group(1))
		height = int(m.group(2))

		# Since we know we're looking to get an image which is 1920x??? we can make assumptions
		width_border = 15
		width_spacing = 3
		border = None
		borderSmall = None
		if height < self.settings.getUser('height'):
			border = '0x%d' % width_border
			spacing = '0x%d' % width_spacing
			logging.debug('Landscape image, reframing')
		elif height > self.settings.getUser('height'):
			border = '%dx0' % width_border
			spacing = '%dx0' % width_spacing
			logging.debug('Portrait image, reframing')
		else:
			logging.debug('Image is fullscreen, no reframing needed')
			return False

		# Time to process
		cmd = [
			'convert',
			filename,
			'-resize',
			'%sx%s^' % (self.settings.getUser('width'), self.settings.getUser('height')),
			'-gravity',
			'center',
			'-crop',
			'%sx%s+0+0' % (self.settings.getUser('width'), self.settings.getUser('height')),
			'+repage',
			'-blur',
			'0x8',
			'-brightness-contrast',
			'-20x0',
			'(',
			filename,
			'-bordercolor',
			'black',
			'-border',
			border,
			'-bordercolor',
			'black',
			'-border',
			spacing,
			'-resize',
			'%sx%s' % (self.settings.getUser('width'), self.settings.getUser('height')),
			'-background',
			'transparent',
			'-gravity', 
			'center',
			'-extent',
			'%sx%s' % (self.settings.getUser('width'), self.settings.getUser('height')),
			')',
			'-composite',
			filename_temp
		]
		try:
			subprocess.check_output(cmd, stderr=subprocess.STDOUT) #stderr=self.void)
		except subprocess.CalledProcessError as e:
			logging.exception('Unable to reframe the image')
			logging.error('Output: %s' % repr(e.output))
			return False
		os.rename(filename_temp, filename)
		return True

	def downloadImage(self, uri, dest):
		logging.debug('Downloading %s...' % uri)
		filename, ext = os.path.splitext(dest)
		temp = "%s-org%s" % (filename, ext)
		if self.oauth.request(uri, destination=temp):
			self.makeFullframe(temp)
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

