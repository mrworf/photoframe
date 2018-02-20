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
import subprocess
import socket
import logging
import os
import re

class helper:
	@staticmethod
	def getResolution():
		res = None
		output = subprocess.check_output(['/bin/fbset'], stderr=DEVNULL)
		for line in output.split('\n'):
			line = line.strip()
			if line.startswith('mode "'):
				res = line[6:-1]
				break
		return res

	@staticmethod
	def getIP():
		ip = None
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			s.connect(("photoframe.sensenet.nu", 80))
			ip = s.getsockname()[0]
			s.close()
		except:
			pass
		return ip

	@staticmethod
	def getExtension(mime):
		mapping = {
			'image/jpeg' : 'jpg',
			'image/png' : 'png',
			'image/gif' : 'gif',
			'image/x-adobe-dng' : 'dng',
			'image/bmp' : 'bmp'
		}
		mime = mime.lower()
		if mime in mapping:
			return mapping[mime]
		return None

	@staticmethod
	def makeFullframe(filename, imageWidth, imageHeight):
		name, ext = os.path.splitext(filename)
		filename_temp = "%s-frame%s" % (name, ext)

		with open(os.devnull, 'wb') as void:
			try:
				output = subprocess.check_output(['/usr/bin/identify', filename], stderr=void)
			except:
				logging.exception('Error trying to identify image')
				return False

		m = re.search('([1-9][0-9]*)x([1-9][0-9]*)', output)
		if m is None or m.groups() is None or len(m.groups()) != 2:
			logging.error('Unable to resolve regular expression for image size')
			return False
		width = int(m.group(1))
		height = int(m.group(2))

		# Since we know we're looking to get an image which is 1920x??? we can make assumptions
		width_border = 15
		width_spacing = 3
		border = None
		borderSmall = None
		if height < imageHeight:
			border = '0x%d' % width_border
			spacing = '0x%d' % width_spacing
			logging.debug('Landscape image, reframing')
		elif height > imageHeight:
			border = '%dx0' % width_border
			spacing = '%dx0' % width_spacing
			logging.debug('Portrait image, reframing')
		else:
			logging.debug('Image is fullscreen, no reframing needed')
			return False

		cmd = None
		try:
			# Time to process
			cmd = [
				'convert',
				filename,
				'-resize',
				'%sx%s^' % (imageWidth, imageHeight),
				'-gravity',
				'center',
				'-crop',
				'%sx%s+0+0' % (imageWidth, imageHeight),
				'+repage',
				'-blur',
				'0x12',
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
				'%sx%s' % (imageWidth, imageHeight),
				'-background',
				'transparent',
				'-gravity',
				'center',
				'-extent',
				'%sx%s' % (imageWidth, imageHeight),
				')',
				'-composite',
				filename_temp
			]
		except:
			logging.exception('Error building command line')
			logging.debug('Filename: ' + repr(filename))
			logging.debug('Filename_temp: ' + repr(filename_temp))
			logging.debug('border: ' + repr(border))
			logging.debug('spacing: ' + repr(spacing))
			return False

		try:
			subprocess.check_output(cmd, stderr=subprocess.STDOUT)
		except subprocess.CalledProcessError as e:
			logging.exception('Unable to reframe the image')
			logging.error('Output: %s' % repr(e.output))
			return False
		os.rename(filename_temp, filename)
		return True
