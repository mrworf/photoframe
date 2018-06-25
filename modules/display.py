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
import json

class display:
	def __init__(self):
		self.void = open(os.devnull, 'wb')
		self.params = None

	def setConfiguration(self, tvservice_params):
		self.enabled = True

		# Erase old picture
		if self.params is not None:
			self.clear()

		result = display.validate(tvservice_params)
		if result is None:
			self.enabled = False
			self.params = None
			return (1280, 720, '')

		self.width = result['width']
		self.height = result['height']
		self.depth = result['depth']
		self.reverse = result['reverse']
		self.params = result['tvservice']
		if self.reverse:
			self.format = 'bgr'
		else:
			self.format = 'rgb'
		if self.depth == 32:
			self.format += 'a'

		return (self.width, self.height, self.params)

	def getDevice(self):
		if self.params and self.params.split(' ')[0] == 'INTERNAL':
			device = '/dev/fb' + self.params.split(' ')[1]
			if os.path.exists(device):
				return device
		return '/dev/fb0'

	def isHDMI(self):
		return self.getDevice() == '/dev/fb0' and not display._isDPI()

	def get(self):
		if self.enabled:
			args = [
			        'convert',
			        '-depth',
			        '8',
			        '-size',
			        '%dx%d' % (self.width, self.height),
			        '%s:-' % (self.format),
			        'jpg:-'
			]
		else:
			args = [
				'convert',
				'-size',
				'%dx%d' % (640, 360),
				'-background',
				'black',
				'-fill',
				'white',
				'-gravity',
				'center',
				'-weight',
				'700',
				'-pointsize',
				'32',
				'label:%s' % "Display off",
				'-depth',
				'8',
				'jpg:-'
			]

		if not self.enabled:
			result = subprocess.check_output(args, stderr=self.void)
		elif self.depth in [24, 32]:
			with open(self.getDevice(), 'rb') as fb:
				pip = subprocess.Popen(args, stdin=fb, stdout=subprocess.PIPE, stderr=self.void)
				result = pip.communicate()[0]
		elif self.depth == 16:
			with open(self.getDevice(), 'rb') as fb:
				src = subprocess.Popen(['/root/photoframe/rgb565/rgb565', 'reverse'], stdout=subprocess.PIPE, stdin=fb, stderr=self.void)
				pip = subprocess.Popen(args, stdin=src.stdout, stdout=subprocess.PIPE)
				src.stdout.close()
				result = pip.communicate()[0]
		else:
			logging.error('Do not know how to grab this kind of framebuffer')
		return (result, 'image/jpeg')

	def _to_display(self, arguments):
		if self.depth in [24, 32]:
			logging.debug('Sending image directly to framebuffer')
			with open(self.getDevice(), 'wb') as f:
				ret = subprocess.call(arguments, stdout=f, stderr=self.void)
		elif self.depth == 16: # Typically RGB565
			logging.debug('Sending image via RGB565 conversion to framebuffer')
			# For some odd reason, cannot pipe the output directly to the framebuffer, use temp file
			with open(self.getDevice(), 'wb') as fb:
				src = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=self.void)
				pip = subprocess.Popen(['/root/photoframe/rgb565/rgb565'], stdin=src.stdout, stdout=fb)
				src.stdout.close()
				pip.communicate()
		else:
			logging.error('Do not know how to render this, depth is %d', self.depth)


	def message(self, message):
		if not self.enabled:
			logging.debug('Don\'t bother, display is off')
			return

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
			'%s:-' % self.format
		]
		self._to_display(args)

	def image(self, filename):
		if not self.enabled:
			logging.debug('Don\'t bother, display is off')
			return

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
			'%s:-' % self.format
		]
		self._to_display(args)

	def enable(self, enable, force=False):
		if enable == self.enabled and not force:
			return

		# Do not do things if we don't know how to display
		if self.params is None:
			return

		if enable:
			if self.isHDMI():
				if force: # Make sure display is ON and set to our preference
					subprocess.call(['/opt/vc/bin/tvservice', '-e', self.params], stderr=self.void, stdout=self.void)
					time.sleep(1)
					subprocess.call(['/bin/fbset', '-fb', self.getDevice(), '-depth', '8'], stderr=self.void)
					subprocess.call(['/bin/fbset', '-fb', self.getDevice(), '-depth', str(self.depth), '-xres', str(self.width), '-yres', str(self.height), '-vxres', str(self.width), '-vyres', str(self.height)], stderr=self.void)
				else:
					subprocess.call(['/usr/bin/vcgencmd', 'display_power', '1'], stderr=self.void)
		else:
			self.clear()
			if self.isHDMI():
				subprocess.call(['/usr/bin/vcgencmd', 'display_power', '0'], stderr=self.void)
		self.enabled = enable

	def isEnabled(self):
		return self.enabled

	def clear(self):
		with open(self.getDevice(), 'wb') as f:
			subprocess.call(['cat' , '/dev/zero'], stdout=f, stderr=self.void)

	@staticmethod
	def _isDPI():
		output = subprocess.check_output(['/opt/vc/bin/tvservice', '-s'], stderr=subprocess.STDOUT)
		return '[LCD]' in output

	@staticmethod
	def _internaldisplay():
		entry = {
			'mode' : 'INTERNAL',
			'code' : None,
			'width' : 0,
			'height' : 0,
			'rate' : 60,
			'aspect_ratio' : '',
			'scan' : '(internal)',
			'3d_modes' : [],
			'reverse' : False
		}
		device = '/dev/fb1'
		if not os.path.exists(device):
			if display._isDPI():
				device = '/dev/fb0'
			else:
				device = None
		if device:
			info = subprocess.check_output(['/bin/fbset', '-fb', device], stderr=subprocess.STDOUT).split('\n')
			for line in info:
				line = line.strip()
				if line.startswith('geometry'):
					parts = line.split(' ')
					entry['width'] = int(parts[1])
					entry['height'] = int(parts[2])
					entry['depth'] = int(parts[5])
					entry['code'] = int(device[-1])
				# rgba 8/16,8/8,8/0,8/24 <== Detect rgba order
				if line.startswith('rgba'):
					m = re.search('rgba [0-9]*/([0-9]*),[0-9]*/([0-9]*),[0-9]*/([0-9]*),[0-9]*/([0-9]*)', line)
					if m is None:
						logging.error('fbset output has changed, cannot parse')
						return None
					entry['reverse'] = m.group(1) != 0
			if entry['code'] is not None:
				return entry
		return None

	def current(self):
		result = None
		if self.isHDMI():
			output = subprocess.check_output(['/opt/vc/bin/tvservice', '-s'], stderr=subprocess.STDOUT)
			# state 0x120006 [DVI DMT (82) RGB full 16:9], 1920x1080 @ 60.00Hz, progressive
			m = re.search('state 0x[0-9a-f]* \[([A-Z]*) ([A-Z]*) \(([0-9]*)\) [^,]*, ([0-9]*)x([0-9]*) \@ ([0-9]*)\.[0-9]*Hz, (.)', output)
			if m is None:
				return None
			result = {
				'mode' : m.group(2),
				'code' : int(m.group(3)),
				'width' : int(m.group(4)),
				'height' : int(m.group(5)),
				'rate' : int(m.group(6)),
				'aspect_ratio' : '',
				'scan' : m.group(7),
				'3d_modes' : [],
				'depth':32,
				'reverse':True,
			}
		else:
			result = display._internaldisplay()

		return result

	@staticmethod
	def available():
		cea = json.loads(subprocess.check_output(['/opt/vc/bin/tvservice', '-j', '-m', 'CEA'], stderr=subprocess.STDOUT))
		dmt = json.loads(subprocess.check_output(['/opt/vc/bin/tvservice', '-j', '-m', 'DMT'], stderr=subprocess.STDOUT))
		result = []
		for entry in cea:
			entry['mode'] = 'CEA'
			entry['depth'] = 32
			entry['reverse'] = True
			result.append(entry)
		for entry in dmt:
			entry['mode'] = 'DMT'
			entry['depth'] = 32
			entry['reverse'] = True
			result.append(entry)

		internal = display._internaldisplay()
		if internal:
			result.append(internal)

		# Finally, sort by pixelcount
		return sorted(result, key=lambda k: k['width']*k['height'])

	@staticmethod
	def validate(tvservice):
		# Takes a string and returns valid width, height, depth and service
		items = tvservice.split(' ')
		resolutions = display.available()
		if len(resolutions) == 0:
			return None

		res = resolutions[0]
		if len(items) == 3:
			for res in resolutions:
				if res['code'] == int(items[1]) and res['mode'] == items[0]:
					break
		else:
			logging.warning('Invalid tvservice data, using first available instead')

		return {
			'width':res['width'],
			'height':res['height'],
			'depth':res['depth'],
			'reverse':res['reverse'],
			'tvservice':'%s %s %s' % (res['mode'], res['code'], 'HDMI')
		}
