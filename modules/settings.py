import os
import json
import logging
import random

class settings:
	def __init__(self):
		self.settings = {
			'oauth_token' : None,
			'oauth_state' : None,
			'local-ip' : None,
			'tempfolder' : '/tmp/',
			'colortemp' : None,
			'colortemp-script' : '/root/colortemp.sh',
			'cfg' : None
		}
		self.userDefaults()

	def userDefaults(self):
		self.settings['cfg'] = {
			'width' : 1920,
			'height' : 1080,
			'depth' : 32,
			'tvservice' : 'DMT 82 DVI',
			'interval' : 60,					# Delay in seconds between images (minimum)
			'display-off' : 22,				# What hour (24h) to disable display and sleep
			'display-on' : 4,					# What hour (24h) to enable display and continue
			'refresh-content' : 24,		# After how many hours we should force reload of image lists from server
			'keywords' : [						# Keywords for search (blank = latest 1000 images)
				""
			]
		}

	def load(self):
		if os.path.exists('/root/settings.json'):
			with open('/root/settings.json') as f:
				self.settings = json.load(f)
			return True
		else:
			return False

	def save(self):
		with open('/root/settings.json', 'w') as f:
			json.dump(self.settings, f)

	def setUser(self, key, value):
		self.settings['cfg'][key] = value

	def getUser(self, key=None):
		if key is None:
			return self.settings['cfg']

		if key in self.settings['cfg']:
			return self.settings['cfg'][key]
		logging.warning('Trying to access non-existent user config key "%s"' % key)
		return None

	def addKeyword(self, keyword):
		if keyword is None:
			return False
		keyword = keyword.strip()
		if keyword not in self.settings['cfg']['keywords']:
			self.settings['cfg']['keywords'].append(keyword.strip())
			return True
		return False

	def removeKeyword(self, id):
		if id < 0 or id >= len(self.settings['cfg']['keywords']):
			return False
		self.settings['cfg']['keywords'].pop(id)
		if len(self.settings['cfg']['keywords']) == 0:
			self.addKeyword('')
		return True

	def getKeyword(self, id=None):
		if id is None:
			rnd = random.SystemRandom().randint(0, len(self.settings['cfg']['keywords'])-1)
			return rnd # self.settings['cfg']['keywords'][rnd]
		elif id >= 0 and id < len(self.settings['cfg']['keywords']):
			return self.settings['cfg']['keywords'][id]
		else:
			return None

	def countKeywords(self):
		return len(self.settings['cfg']['keywords'])

	def set(self, key, value):
		self.settings[key] = value

	def get(self, key):
		if key in self.settings:
			return self.settings[key]
		logging.warning('Trying to access non-existent config key "%s"' % key)
		return None
