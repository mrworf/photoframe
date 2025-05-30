#!/usr/bin/env python3
#
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
import shutil
import re
import random
import time
from pathlib import Path

try:
	import netifaces
except ImportError:
	logging.error('User has not installed python-netifaces, using checkNetwork() instead (depends on internet)')

# A regular expression to determine whether a url is valid or not (e.g. "www.example.de/someImg.jpg" is missing "http://")
VALID_URL_REGEX = re.compile(
	r'^(?:http|ftp)s?://'  # http:// or https://
	r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
	r'localhost|'  # localhost...
	r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
	r'(?::\d+)?'  # optional port
	r'(?:/?|[/?]\S+)$', re.IGNORECASE)

class helper:
	TOOL_ROTATE = '/usr/bin/jpegtran'
	NETWORK_CHECK = True

	MIMETYPES = {
		'image/jpeg' : 'jpg',
		'image/png' : 'png',
		'image/gif' : 'gif',
		'image/bmp' : 'bmp'
		# HEIF to be added once I get ImageMagick running with support
	}


	@staticmethod
	def isValidUrl(url):
		# Catches most invalid URLs
		if re.match(VALID_URL_REGEX, url) is None:
			return False
		return True

	@staticmethod
	def getWeightedRandomIndex(weights):
		totalWeights = sum(weights)
		normWeights = [float(w)/totalWeights for w in weights]
		x = random.SystemRandom().random()
		for i in range(len(normWeights)):
			x -= normWeights[i]
			if x <= 0.:
				return i

	@staticmethod
	def getResolution():
		res = None
		output = subprocess.check_output(['/bin/fbset'], stderr=subprocess.DEVNULL).decode('utf-8')
		for line in output.split('\n'):
			line = line.strip()
			if line.startswith('mode "'):
				res = line[6:-1]
				break
		return res

	@staticmethod
	def getDeviceIp():
		if helper.NETWORK_CHECK:
			try:
				if 'default' in netifaces.gateways() and netifaces.AF_INET in netifaces.gateways()['default']:
					dev = netifaces.gateways()['default'][netifaces.AF_INET][1]
					if netifaces.ifaddresses(dev) and netifaces.AF_INET in netifaces.ifaddresses(dev):
						net = netifaces.ifaddresses(dev)[netifaces.AF_INET]
						if len(net) > 0 and 'addr' in net[0]:
							return net[0]['addr']
			except NameError:
				# We weren't able to import, so switch it up
				helper.NETWORK_CHECK = False
				return helper._checkNetwork()
			except Exception as e:
				helper.NETWORK_CHECK = False
				logging.exception('netifaces call failed, using checkNetwork() instead (depends on internet)')
				return helper._checkNetwork()
		else:
			return helper._checkNetwork()

	@staticmethod
	def _checkNetwork():
		ip = None
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			s.connect(("photoframe.sensenet.nu", 80))
			ip = s.getsockname()[0]

			s.close()
		except Exception as e:
			logging.exception('Failed to get IP via old method')
		return ip

	@staticmethod
	def getExtension(mime):
		mime = mime.lower()
		if mime in helper.MIMETYPES:
			return helper.MIMETYPES[mime]
		return None

	@staticmethod
	def getSupportedTypes():
		return list(helper.MIMETYPES.keys())

	@staticmethod
	def getMimetype(filename):
		if not os.path.isfile(filename):
			return None

		mimetype = ''
		cmd = ["/usr/bin/file", "--mime", filename]
		with open(os.devnull, 'wb') as void:
			try:
				output = subprocess.check_output(cmd, stderr=void).decode('utf-8').strip("\n")
				m = re.match(r'[^:]+: *([^;]+)', output)
				if m:
					mimetype = m.group(1)
			except subprocess.CalledProcessError:
				logging.debug(f"unable to determine mimetype of file: {filename}")
				return None
		return mimetype

	@staticmethod
	def copyFile(orgFilename, newFilename):
		try:
			shutil.copyfile(orgFilename, newFilename)
		except Exception as e:
			logging.exception(f'Unable copy file from "{orgFilename}" to "{newFilename}"')
			return False
		return True

	@staticmethod
	def scaleImage(orgFilename, newFilename, newSize):
		cmd = [
			'convert',
			orgFilename + '[0]',
			'-scale',
			f'{newSize["width"]}x{newSize["height"]}',
			'+repage',
			newFilename
        ]

		try:
			subprocess.check_output(cmd, stderr=subprocess.STDOUT)
		except subprocess.CalledProcessError as e:
			logging.exception('Unable to reframe the image')
			logging.error(f'Output: {repr(e.output)}')
			return False
		return True

	@staticmethod
	def getImageSize(filename):
		if not os.path.isfile(filename):
			logging.warning(f'File {filename} does not exist, so cannot get dimensions')
			return None

		with open(os.devnull, 'wb') as void:
			try:
				output = subprocess.check_output(['/usr/bin/identify', filename], stderr=void).decode('utf-8')
			except Exception as e:
				logging.exception(f'Failed to run identify to get image dimensions on {filename}')
				return None

		m = re.search('([1-9][0-9]*)x([1-9][0-9]*)', output)
		if m is None or m.groups() is None or len(m.groups()) != 2:
			logging.error('Unable to resolve regular expression for image size')
			return None

		imageSize = {}
		imageSize["width"] = int(m.group(1))
		imageSize["height"] = int(m.group(2))

		return imageSize

	@staticmethod
	def makeFullframe(filename, displayWidth, displayHeight, zoomOnly=False, autoChoose=False):
		imageSize = helper.getImageSize(filename)
		if imageSize is None:
			logging.warning(f'Cannot frame {filename} since we cannot determine image dimensions')
			return filename

		width = imageSize["width"]
		height = imageSize["height"]

		p, f = os.path.split(filename)
		filenameProcessed = os.path.join(p, "framed_" + f)

		width_border = 15
		width_spacing = 3
		border = None
		spacing = None

		# Calculate actual size of image based on display
		oar = float(width) / float(height)
		dar = float(displayWidth) / float(displayHeight)

		if not zoomOnly:
			if oar >= dar:
				adjWidth = displayWidth
				adjHeight = int(float(displayWidth) / oar)
			else:
				adjWidth = int(float(displayHeight) * oar)
				adjHeight = displayHeight

			logging.debug(f'Size of image is {width}x{height}, screen is {displayWidth}x{displayHeight}. New size is {adjWidth}x{adjHeight}')

			if width < 100 or height < 100:
				logging.error(f'Image size is REALLY small, please check "{filename}" ... something isn\'t right')
				#a=1/0

			if adjHeight < displayHeight:
				border = f'0x{width_border}'
				spacing = f'0x{width_spacing}'
				padding = ((displayHeight - adjHeight) / 2 - width_border)
				resizeString = f'{adjWidth}x{adjHeight}^'
				logging.debug(f'Landscape image, reframing (padding required {padding}px)')
			elif adjWidth < displayWidth:
				border = f'{width_border}x0'
				spacing = f'{width_spacing}x0'
				padding = ((displayWidth - adjWidth) / 2 - width_border)
				resizeString = f'^{adjWidth}x{adjHeight}'
				logging.debug(f'Portrait image, reframing (padding required {padding}px)')
			else:
				resizeString = f'{adjWidth}x{adjHeight}'
				logging.debug('Image is fullscreen, no reframing needed')
				return filename

			if padding < 20 and not autoChoose:
				logging.debug(f'That\'s less than 20px so skip reframing ({width}x{height} => {adjWidth}x{adjHeight})')
				return filename

			if padding < 60 and autoChoose:
				zoomOnly = True

		if zoomOnly:
			if oar <= dar:
				adjWidth = displayWidth
				adjHeight = int(float(displayWidth) / oar)
				logging.debug(f'Size of image is {width}x{height}, screen is {displayWidth}x{displayHeight}. New size is {adjWidth}x{adjHeight}  --> cropped to {displayWidth}x{displayHeight}')
			else:
				adjWidth = int(float(displayHeight) * oar)
				adjHeight = displayHeight
				logging.debug(f'Size of image is {width}x{height}, screen is {displayWidth}x{displayHeight}. New size is {adjWidth}x{adjHeight} --> cropped to {displayWidth}x{displayHeight}')

		cmd = None
		try:
			# Time to process
			if zoomOnly:
				cmd = [
					'convert',
					filename + '[0]',
					'-resize',
					f'{adjWidth}x{adjHeight}',
					'-gravity',
					'center',
					'-crop',
					f'{displayWidth}x{displayHeight}+0+0',
					'+repage',
					filenameProcessed
				]
			else:
				cmd = [
					'convert',
					filename + '[0]',
					'-resize',
					resizeString % (displayWidth, displayHeight),
					'-gravity',
					'center',
					'-crop',
					f'{displayWidth}x{displayHeight}+0+0',
					'+repage',
					'-blur',
					'0x12',
					'-brightness-contrast',
					'-20x0',
					'(',
					filename + '[0]',
					'-bordercolor',
					'black',
					'-border',
					border,
					'-bordercolor',
					'black',
					'-border',
					spacing,
					'-resize',
					f'{displayWidth}x{displayHeight}',
					'-background',
					'transparent',
					'-gravity',
					'center',
					'-extent',
					f'{displayWidth}x{displayHeight}',
					')',
					'-composite',
					filenameProcessed
				]
		except:
			logging.exception('Error building command line')
			logging.debug('Filename: ' + repr(filename))
			logging.debug('filenameProcessed: ' + repr(filenameProcessed))
			logging.debug('border: ' + repr(border))
			logging.debug('spacing: ' + repr(spacing))
			return filename

		try:
			subprocess.check_output(cmd, stderr=subprocess.STDOUT)
		except subprocess.CalledProcessError as e:
			logging.exception('Unable to reframe the image')
			logging.error(f'Output: {repr(e.output)}')
			return filename
		os.unlink(filename)
		return filenameProcessed

	@staticmethod
	def timezoneList():
		try:
			zones = subprocess.check_output(['/usr/bin/timedatectl', 'list-timezones']).decode('utf-8').split('\n')
			return [x for x in zones if x]
		except Exception as e:
			logging.error(f'Failed to get timezone list: {str(e)}')
			return ['UTC']  # Return UTC as fallback

	@staticmethod
	def timezoneCurrent():
		# Try different methods to get the timezone
		try:
			# Method 1: /etc/timezone (Debian/Ubuntu)
			with open('/etc/timezone', 'r') as f:
				return f.read().strip()
		except:
			try:
				# Method 2: /etc/localtime symlink (Arch Linux)
				localtime = os.path.realpath('/etc/localtime')
				if 'zoneinfo' in localtime:
					return localtime.split('zoneinfo/')[-1]
			except:
				try:
					# Method 3: timedatectl (systemd)
					output = subprocess.check_output(['timedatectl'], stderr=subprocess.DEVNULL).decode('utf-8')
					for line in output.split('\n'):
						if 'Time zone' in line:
							return line.split(':')[1].strip()
				except:
					pass
		# Default to UTC if all methods fail
		return 'UTC'

	@staticmethod
	def timezoneSet(zone):
		try:
			subprocess.check_output(['/usr/bin/timedatectl', 'set-timezone', zone], stderr=subprocess.STDOUT)
			return True
		except subprocess.CalledProcessError as e:
			logging.error(f'Failed to set timezone to {zone}: {e.output.decode("utf-8")}')
			return False

	@staticmethod
	def hasNetwork():
		return helper._checkNetwork() is not None

	@staticmethod
	def waitForNetwork(funcNoNetwork, funcExit):
		while True:
			if helper.hasNetwork():
				return
			funcNoNetwork()
			if funcExit():
				return
			time.sleep(5)

	@staticmethod
	def autoRotate(ifile):
		if not os.path.exists('/usr/bin/jpegexiforient'):
			logging.warning('jpegexiforient is missing, no auto rotate available. Did you forget to run "apt install libjpeg-turbo-progs" ?')
			return ifile

		p, f = os.path.split(ifile)
		ofile = os.path.join(p, "rotated_" + f)

		# First, use jpegexiftran to determine orientation
		parameters = ['', '-flip horizontal', '-rotate 180', '-flip vertical', '-transpose', '-rotate 90', '-transverse', '-rotate 270']
		with open(os.devnull, 'wb') as void:
			result = subprocess.check_output(['/usr/bin/jpegexiforient', ifile]) #, stderr=void)
		if result:
			orient = int(result)-1
			if orient < 0 or orient >= len(parameters):
				logging.info('Orientation was %d, not transforming it', orient)
				return ifile
			cmd = [helper.TOOL_ROTATE]
			cmd.extend(parameters[orient].split())
			cmd.extend(['-outfile', ofile, ifile])
			with open(os.devnull, 'wb') as void:
				result = subprocess.check_call(cmd, stderr=void)
			if result == 0:
				os.unlink(ifile)
				return ofile
		return ifile

	@staticmethod
	def resizeImage(image, displayWidth, displayHeight):
		"""Resize image to fit display"""
		cmd = [
			'convert',
			image,
			f'-resize {displayWidth}x{displayHeight}^',
			'-gravity center',
			f'-extent {displayWidth}x{displayHeight}',
			image
		]
		subprocess.check_call(cmd)

	@staticmethod
	def fixImageOrientation(image):
		"""Fix image orientation based on EXIF data"""
		try:
			cmd = ['identify', '-format', '%[orientation]', image]
			orient = subprocess.check_output(cmd).decode('utf-8').strip()
			if orient == 'TopLeft':
				return
			logging.info(f'Orientation was {orient}, not transforming it')
			cmd = ['convert', image, '-auto-orient', image]
			subprocess.check_call(cmd)
		except Exception as e:
			logging.error(f'Failed to fix image orientation: {str(e)}')
