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
import subprocess
import logging
import time
import re

class display:
	def __init__(self, width, height, depth, tvservice_params):
		self.setConfiguration(width, height, depth, tvservice_params)
		self.void = open(os.devnull, 'wb')

	def setConfiguration(self, width, height, depth, tvservice_params):
		self.width = width
		self.height = height
		self.enabled = True
		self.depth = depth
		self.params = tvservice_params

	def get(self):
		if self.enabled:
			args = [
			        'convert',
			        '-depth',
			        '8',
			        '-size',
			        '%dx%d' % (self.width, self.height),
			        'bgra:/dev/fb0[0]',
			        'jpg:-'
			]
		else:
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
				'label:%s' % "Powersave",
				'-depth',
				'8',
				'jpg:-'
			]

		result = subprocess.check_output(args, stderr=self.void)
		return (result, 'image/jpeg')

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
			filename + '[0]',
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

	@staticmethod
	def current():
		output = subprocess.check_output(['/opt/vc/bin/tvservice', '-s'], stderr=subprocess.STDOUT)
		print('"%s"' % (output))
		m = re.search('state 0x[0-9a-f]* \[([A-Z]*) ([A-Z]*) \(([0-9]*)\) [^,]*, ([0-9]*)x([0-9]*)', output)
		result = {
		'group' : m.group(2),
		'mode' : m.group(1),
		'drive' : m.group(3),
		'width' : m.group(4),
		'height' : m.group(5)
		}
		return result

