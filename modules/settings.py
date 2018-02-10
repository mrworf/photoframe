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
		self.user_defaults()

	def user_defaults(self):
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

	def save(self):
		with open('/root/settings.json', 'w') as f:
			json.dump(self.settings, f)

	def setUser(self, key, value):
		self.settings['cfg'][key] = value

	def getUser(self, key):
		if key in self.settings['cfg']:
			return self.settings['cfg'][key]
		logging.warning('Trying to access non-existent user config key "%s"' % key)
		return None

	def set(self, key, value):
		self.settings[key] = value

	def get(self, key):
		if key in self.settings:
			return self.settings[key]
		logging.warning('Trying to access non-existent config key "%s"' % key)
		return None
