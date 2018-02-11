import os
import subprocess
import logging
import time

class display:
	def __init__(self, width, height, depth, tvservice_params):
		self.width = width
		self.height = height
		self.enabled = True
		self.depth = depth
		self.params = tvservice_params
		self.void = open(os.devnull, 'wb')

	def message(self, message):
		args = [
			'convert',
			'-size',
			'%dx%d' % (self.width, self.height),
			'-background',
			'black',
			'-fill',
			'white',
			'-gravity',
			'center',
			'-weight',
			'700',
			'-pointsize',
			'64',
			'label:%s' % message,
			'-depth',
			'8',
			'bgra:-'
		]
		with open('/dev/fb0', 'wb') as f:
			ret = subprocess.call(args, stdout=f, stderr=self.void)

	def image(self, filename):
		logging.debug('Showing image to user')
		args = [
			'convert',
			filename,
			'-resize',
			'%dx%d' % (self.width, self.height),
			'-background',
			'black',
			'-gravity',
			'center',
			'-extent',
			'%dx%d' % (self.width, self.height), 
			'-depth',
			'8',
			'bgra:-'
		]
		with open('/dev/fb0', 'wb') as f:
			ret = subprocess.call(args, stdout=f, stderr=self.void)

	def enable(self, enable, force=False):
		if enable == self.enabled and not force:
			return

		if enable:
			if force: # Make sure display is ON and set to our preference
				subprocess.call(['/opt/vc/bin/tvservice', '-e', self.params], stderr=self.void, stdout=self.void)
				time.sleep(1)
				subprocess.call(['/bin/fbset', '-depth', '8'], stderr=self.void)
				subprocess.call(['/bin/fbset', '-depth', str(self.depth), '-xres', str(self.width), '-yres', str(self.height)], stderr=self.void)
			else:
				subprocess.call(['/usr/bin/vcgencmd', 'display_power', '1'], stderr=self.void)
		else:
			subprocess.call(['/usr/bin/vcgencmd', 'display_power', '0'], stderr=self.void)
		self.enabled = enable

	def isEnabled(self):
		return self.enabled

	def clear(self):
		with open('/dev/fb0', 'wb') as f:
			subprocess.call(['cat' , '/dev/zero'], stdout=f, stderr=self.void)
