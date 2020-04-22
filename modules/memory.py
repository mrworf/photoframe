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
import logging
import hashlib

class MemoryManager:
  def __init__(self, memoryLocation):
    self._MEMORY = []
    self._MEMORY_KEY = None
    self._HISTORY = []
    self._DIR_MEMORY = memoryLocation
    self.resetIndices()

  def _hashString(self, text):
    if type(text) is not unicode:
      # make sure it's unicode
      a = text.decode('ascii', errors='replace')
    else:
      a = text
    a = a.encode('utf-8', errors='replace')
    return hashlib.sha1(a).hexdigest()

  def _fetch(self, key):
    if key is None:
      raise Exception('No key provided to _fetch')
    h = self._hashString(key)
    if self._MEMORY_KEY == h:
      return
    # Save work and swap
    if self._MEMORY is not None and len(self._MEMORY) > 0:
      with open(os.path.join(self._DIR_MEMORY, '%s.json' % self._MEMORY_KEY), 'w') as f:
        json.dump(self._MEMORY, f)
    if os.path.exists(os.path.join(self._DIR_MEMORY, '%s.json' % h)):
      try:
        with open(os.path.join(self._DIR_MEMORY, '%s.json' % h), 'r') as f:
          self._MEMORY = json.load(f)
      except:
        logging.exception('File %s is corrupt' % os.path.join(self._DIR_MEMORY, '%s.json' % h))
        self._MEMORY = []
    else:
      logging.debug('_fetch returned no memory')
      self._MEMORY = []
    self._MEMORY_KEY = h

  def _differentThanLastHistory(self, keywordindex, imageIndex):
    # just a little helper function to compare indices with the indices of the previously displayed image
    if len(self._HISTORY) == 0:
      return True
    if keywordindex == self._HISTORY[-1][0] and imageIndex == self._HISTORY[-1][1]:
      return False
    return True

  def remember(self, itemId, keywords, alwaysRemember=True):
    # The MEMORY makes sure that this image won't be shown again until memoryForget is called
    self._fetch(keywords)
    h = self._hashString(itemId)
    if h not in self._MEMORY:
      self._MEMORY.append(h)
    # save memory
    if (len(self._MEMORY) % 20) == 0:
      logging.info('Interim saving of memory every 20 entries')
      with open(os.path.join(self._DIR_MEMORY, '%s.json' % self._MEMORY_KEY), 'w') as f:
        json.dump(self._MEMORY, f)

    # annoying behaviour fix: only remember current image in history if the image has actually changed
    rememberInHistory = alwaysRemember or self._differentThanLastHistory(self.keywordIndex, self.imageIndex)
    if rememberInHistory:
      # The HISTORY makes it possible to show previously displayed images
      self._HISTORY.append((self.keywordIndex, self.imageIndex))

    # (non-random image order only): on 'prepareNextItem' --> make sure to preload the following image
    self.imageIndex += 1

    return rememberInHistory

  def getList(self, keywords):
    self._fetch(keywords)
    return self._MEMORY

  def seen(self, itemId, keywords):
    self._fetch(keywords)
    h = self._hashString(itemId)
    return h in self._MEMORY

  def forgetLast(self, keywords):
    # remove the currently displayed image from memory as well as history
    # implications:
    # - the image will be treated as never seen before (random image order)
    # - the same image will be preloaded again during 'prepareNextItem' (non-random image order)
    self._fetch(keywords)
    if len(self._MEMORY) != 0:
      self._MEMORY.pop()
    if len(self._HISTORY) != 0:
      self.keywordIndex, self.imageIndex = self._HISTORY.pop()
    else:
      raise Exception("Trying to forget a single memory, but 'self._HISTORY' is empty. This should have never happened!")

  def forget(self, keywords, forgetHistory=False):
    self._fetch(keywords)
    n = os.path.join(self._DIR_MEMORY, '%s.json' % self._MEMORY_KEY)
    if os.path.exists(n):
      logging.debug('Removed memory file %s' % n)
      os.unlink(n)
    logging.debug('Has %d memories before wipe' % len(self._MEMORY))
    self._MEMORY = []
    if forgetHistory:
      self._HISTORY = []

  def resetIndices(self):
    self.keywordIndex = 0
    self.imageIndex = 0

  def resetToLastAlbum(self):
    self.keywordIndex = max(0, len(self.getKeywords())-1)
    self.imageIndex = 0
