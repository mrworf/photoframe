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
	def __init__(self, width, height, depth, tvservice_params):
		self.setConfiguration(width, height, depth, tvservice_params)
		self.void = open(os.devnull, 'wb')

	def setConfiguration(self, width, height, depth, tvservice_params):
		self.width = width
		self.height = height
		self.enabled = True
		self.depth = depth
		self.reverse = False
		self.params = tvservice_params
		self.device = '/dev/fb1'
		if self.reverse:
			self.format = 'bgr'
		else:
			self.format = 'rgb'
		if self.depth == 32:
			self.format += 'a'

	def isHDMI(self):
		return self.device == '/dev/fb0'

	def get(self):
		if not self.isHDMI():
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
				'24',
				'label:%s' % "Unavailable for non-HDMI displays",
				'-depth',
				'8',
				'jpg:-'
			]
		elif self.enabled:
			args = [
			        'convert',
			        '-depth',
			        '8',
			        '-size',
			        '%dx%d' % (self.width, self.height),
			        '%s:%s[0]' % (self.format, self.device),
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

	def _display(self, arguments):
		if not self.enabled:
			logging.debug('Don\'t bother, display is off')
			return

		if self.depth in [24, 32]:
			logging.debug('Sending image directly to framebuffer')
			with open(self.device, 'wb') as f:
				ret = subprocess.call(arguments, stdout=f, stderr=self.void)
		elif self.depth == 16: # Typically RGB565
			logging.debug('Sending image via RGB565 conversion to framebuffer')
			# For some odd reason, cannot pipe the output directly to the framebuffer, use temp file
			with open(self.device, 'wb') as fb:
				src = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=self.void)
				pip = subprocess.Popen(['/root/photoframe/rgb565/rgb565'], stdin=src.stdout, stdout=fb)
				src.stdout.close()
				pip.communicate()
			'''
			with open(self.device, 'wb') as fb:
				with open('/tmp/fbdump', 'rb') as i:
					while True:
						b = i.read(8192)
						if not b:
							break
						fb.write(b)
			os.remove('/tmp/fbdump')
			'''
		else:
			logging.error('Do not know how to render this, depth is %d', self.depth)


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
			'%s:-' % self.format
		]
		self._display(args)

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
			'%s:-' % self.format
		]
		self._display(args)

	def enable(self, enable, force=False):
		if enable == self.enabled and not force:
			return

		if enable:
			if force: # Make sure display is ON and set to our preference
				subprocess.call(['/opt/vc/bin/tvservice', '-e', self.params], stderr=self.void, stdout=self.void)
				time.sleep(1)
				subprocess.call(['/bin/fbset', '-fb', self.device, '-depth', '8'], stderr=self.void)
				subprocess.call(['/bin/fbset', '-fb', self.device, '-depth', str(self.depth), '-xres', str(self.width), '-yres', str(self.height), '-vxres', str(self.width), '-vyres', str(self.height)], stderr=self.void)
			else:
				subprocess.call(['/usr/bin/vcgencmd', 'display_power', '1'], stderr=self.void)
		else:
			self.clear()
			subprocess.call(['/usr/bin/vcgencmd', 'display_power', '0'], stderr=self.void)
		self.enabled = enable

	def isEnabled(self):
		return self.enabled

	def clear(self):
		with open(self.device, 'wb') as f:
			subprocess.call(['cat' , '/dev/zero'], stdout=f, stderr=self.void)

	@staticmethod
	def _internaldisplay():
		if os.path.exists('/dev/fb1'):
			entry = {
				'mode' : 'INTERNAL',
				'code' : '0',
				'width' : 0,
				'height' : 0,
				'rate' : 60,
				'aspect_ratio' : '',
				'scan' : '(internal)',
				'3d_modes' : []
			}
			info = subprocess.check_output(['/bin/fbset', '-fb', '/dev/fb1'], stderr=subprocess.STDOUT).split('\n')
			for line in info:
				line = line.strip()
				if line.startswith('geometry'):
					parts = line.split(' ')
					entry['width'] = int(parts[1])
					entry['height'] = int(parts[2])
					entry['code'] = int(parts[5])
			if entry['code'] != 0:
				return entry
		return None

	def current(self):
		result = None
		if self.isHDMI():
			output = subprocess.check_output(['/opt/vc/bin/tvservice', '-s'], stderr=subprocess.STDOUT)
			# state 0x120006 [DVI DMT (82) RGB full 16:9], 1920x1080 @ 60.00Hz, progressive
			m = re.search('state 0x[0-9a-f]* \[([A-Z]*) ([A-Z]*) \(([0-9]*)\) [^,]*, ([0-9]*)x([0-9]*) \@ ([0-9]*)\.[0-9]*Hz, (.)', output)
			result = {
				'mode' : m.group(2),
				'code' : int(m.group(3)),
				'width' : int(m.group(4)),
				'height' : int(m.group(5)),
				'rate' : int(m.group(6)),
				'aspect_ratio' : '',
				'scan' : m.group(7),
				'3d_modes' : []
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
			result.append(entry)
		for entry in dmt:
			entry['mode'] = 'DMT'
			result.append(entry)

		internal = display._internaldisplay()
		if internal:
			result.append(internal)

		# Finally, sort by pixelcount
		return sorted(result, key=lambda k: k['width']*k['height'])
