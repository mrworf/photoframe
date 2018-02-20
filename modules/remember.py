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
import json
import hashlib

class remember:
	def __init__(self, filename, count):
		self.filename = os.path.splitext(filename)[0] + '_memory.json'
		self.count = count
		if os.path.exists(self.filename):
			with open(self.filename, 'rb') as f:
				self.memory = json.load(f)
		else:
			self.memory = {'seen':[]}

	def forget(self):
		self.memory = {'seen':[]}
		if os.path.exists(self.filename):
			os.unlink(self.filename)

	def _hash(self, text):
		return hashlib.sha1(text).hexdigest()

	def saw(self, url):
		index = self._hash(url)
		if index not in self.memory['seen']:
			self.memory['seen'].append(index)
			with open(self.filename, 'wb') as f:
				json.dump(self.memory, f)

	def seenAll(self):
		return len(self.memory['seen']) == self.count

	def seen(self, id):
		index = self._hash(id)
		return index in self.memory['seen']
