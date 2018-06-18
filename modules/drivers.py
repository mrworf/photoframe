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
import time
import os
import subprocess
import logging
import tempfile
import shutil
import json

class drivers:
	BUILTIN = '/root/photoframe/display-drivers'
	EXTERNAL = '/root/display-drivers/'
	MARKER = '### DO NOT EDIT BEYOND THIS COMMENT, IT\'S AUTOGENERATED BY PHOTOFRAME ###'

	def __init__(self):
		self.void = open(os.devnull, 'wb')
		if not os.path.exists(drivers.EXTERNAL):
			try:
				os.mkdir(drivers.EXTERNAL)
			except:
				logging.exception('Unable to create "%s"', drivers.EXTERNAL)

	def _list_dir(self, path):
		result = {}
		contents = os.listdir(path)
		for entry in contents:
			if not os.path.isdir(os.path.join(path, entry)):
				continue
			result[entry] = os.path.join(path, entry)
		return result

	def list(self):
		result = {}
		result = self._list_dir(drivers.BUILTIN)
		# Any driver defined in external that has the same name as an internal one
		# will replace the internal one.
		result.update(self._list_dir(drivers.EXTERNAL))

		return result

	def _find(self, filename, basedir):
		for root, dirnames, filenames in os.walk(basedir):
			for filename in filenames:
				if filename == 'INSTALL':
					return os.path.join(root, filename)
		return None

	def _deletefolder(self, folder):
		try:
			shutil.rmtree(folder)
		except:
			logging.exception('Failed to delete "%s"', folder)

	def _parse(self, installer):
		root = os.path.dirname(installer)
		config = {'driver' : os.path.basename(root), 'install' : [], 'options' : {}}
		state = 0
		lc = 0
		try:
			with open(installer, 'r') as f:
				for line in f:
					lc += 1
					line = line.strip()
					if line.startswith('#') or len(line) == 0:
						continue
					if line.lower() == '[install]':
						state = 1
						continue
					if line.lower() == '[options]':
						state = 2
						continue
					if state == 1:
						src, dst = line.split('=', 1)
						src = src.strip()
						dst = dst.strip()
						if dst == '' or src == '':
							logging.error('Install section cannot have an empty source or destination filename (Line %d)', lc)
							return None
						if '..' in src or src.startswith('/'):
							logging.error('Install section must use files within package (Line %d)', lc)
							return None
						src = os.path.join(root, src)
						if not os.path.exists(src):
							logging.error('INSTALL manifest points to non-existant file (Line %d)', lc)
							return None
						config['install'].append({'src':src, 'dst':dst})
					elif state == 2:
						key, value = line.split('=', 1)
						key = key.strip()
						value = value.strip()
						if key == '' or value == '':
							logging.error('Options section cannot have an empty key or value (Line %d)', lc)
							return None
						if key in config['options']:
							logging.warning('Key "%s" will be overridden since it is defined multiple times (Line %d)', lc)
						config['options'][key] = value
		except:
			logging.exception('Failed to read INSTALL manifest')
			return None
		return config

	def install(self, file):
		'''
		Takes a zip file, extracts it and stores the necessary parts in a new
		folder under EXTERNAL. Does NOT make it active.
		'''
		folder = tempfile.mkdtemp()
		extra, _ = os.path.basename(file).rsplit('.', 1) # This is to make sure we have a foldername
		try:
			result = subprocess.check_call(['/usr/bin/unzip', file, '-d', os.path.join(folder, extra)], stdout=self.void, stderr=self.void)
		except:
			result = 255

		if result != 0:
			logging.error('Failed to extract files from zipfile')
			self._deletefolder(folder)
			return False

		# Locate the meat of the file, ie, the INSTALL file
		installer = self._find('INSTALL', folder)
		if installer is None:
			logging.error('No INSTALL manifest, abort driver installation')
			self._deletefolder(folder)
			return False

		config = self._parse(installer)
		if config is None:
			logging.error('INSTALL manifest corrupt, abort driver installation')
			self._deletefolder(folder)
			return False

		# First, make sure we erase existing driver
		dstfolder = os.path.join(drivers.EXTERNAL, config['driver'])
		if os.path.exists(dstfolder):
			logging.info('"%s" already exists, delete before installing', dstfolder)
			self._deletefolder(dstfolder)
		os.mkdir(dstfolder)

		# Copy all files as needed
		files = []
		for entry in config['install']:
			src = entry['src']
			dst = os.path.basename(entry['src']).replace('/', '_')
			files.append({'src':dst, 'dst':entry['dst']})
			try:
				shutil.copyfile(os.path.join(folder, extra, src), os.path.join(dstfolder, dst))
			except:
				logging.exception('Failed to copy "%s" to "%s"', os.path.join(folder, extra, src), os.path.join(dstfolder, dst))
				# Shitty, but we cannot leave this directory with partial files
				self._deletefolder(dstfolder)
				self._deletefolder(folder)
				return False
		config['install'] = files

		# Just save our config, saving us time next time
		with open(os.path.join(dstfolder, 'manifest.json'), 'w') as f:
			json.dump(config, f)

		self._deletefolder(folder)
		return True

	def activate(self, driver=None):
		'''
		Activates a driver, meaning it gets copied into the necessary places and
		the config.txt is updated. Setting driver to None removes the active driver
		'''
		driverlist = self.list()
		if driver is not None:
			# Check that this driver exists
			if driver not in driverlist:
				logging.error('Tried to active non-existant driver "%s"', driver)
				return False

		config = {'name':'', 'install':[], 'options':{}}
		root = ''
		if driver:
			try:
				with open(os.path.join(driverlist[driver], 'manifest.json'), 'rb') as f:
					config = json.load(f)
				root = driverlist[driver]
			except:
				logging.exception('Failed to load manifest for %s', driver)
				return False

		# Copy the files into desired locations
		for copy in config['install']:
			try:
				shutil.copyfile(os.path.join(root, copy['src']), copy['dst'])
			except:
				logging.exception('Failed to copy "%s" to "%s"', copy['src'], copy['dst'])
				return False

		# Next, load the config.txt and insert/replace our section
		lines = []
		try:
			with open('/boot/config.txt', 'rb') as f:
				for line in f:
					line = line.strip()
					if line == drivers.MARKER:
						break
					lines.append(line)
		except:
			logging.exception('Failed to read /boot/config.txt')
			return False

		# Add our options
		if len(config['options']) > 0:
			lines.append(drivers.MARKER)
			for key in config['options']:
				lines.append('%s=%s' % (key, config['options'][key]))

		# Save the new file
		try:
			with open('/boot/config.txt.new', 'wb') as f:
				for line in lines:
					f.write('%s\n' % line)
		except:
			logging.exception('Failed to generate new config.txt')
			return False

		# On success, we rename and delete the old config
		try:
			os.rename('/boot/config.txt', '/boot/config.txt.old')
			os.rename('/boot/config.txt.new', '/boot/config.txt')
			# Keep the first version of the config.txt just-in-case
			if os.path.exists('/boot/config.txt.original'):
				os.unlink('/boot/config.txt.old')
			else:
				os.rename('/boot/config.txt.old', '/boot/config.txt.original')
		except:
			logging.exception('Failed to activate new config.txt, you may need to restore the config.txt')
		return True