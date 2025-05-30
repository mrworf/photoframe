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

import os
import json
import logging
import hashlib
from pathlib import Path

class MemoryManager:
    def __init__(self, memoryLocation):
        self._MEMORY = []
        self._MEMORY_KEY = None
        self._DIR_MEMORY = memoryLocation
        self._MEMORY_COUNT = {}

    def _hashString(self, text):
        if not isinstance(text, str):
            # make sure it's str
            text = str(text)
        return hashlib.sha1(text.encode('utf-8', errors='replace')).hexdigest()

    def _fetch(self, key):
        if key is None:
            raise Exception('No key provided to _fetch')
        h = self._hashString(key)
        if self._MEMORY_KEY == h:
            return
        # Save work and swap
        if self._MEMORY is not None and len(self._MEMORY) > 0:
            with open(os.path.join(self._DIR_MEMORY, f'{self._MEMORY_KEY}.json'), 'w') as f:
                json.dump(self._MEMORY, f)
        if os.path.exists(os.path.join(self._DIR_MEMORY, f'{h}.json')):
            try:
                with open(os.path.join(self._DIR_MEMORY, f'{h}.json'), 'r') as f:
                    self._MEMORY = json.load(f)
            except Exception as e:
                logging.exception(f'File {os.path.join(self._DIR_MEMORY, f"{h}.json")} is corrupt: {e}')
                self._MEMORY = []
        else:
            logging.debug('_fetch returned no memory')
            self._MEMORY = []
        self._MEMORY_COUNT[h] = len(self._MEMORY)
        self._MEMORY_KEY = h

    def remember(self, itemId, keywords, alwaysRemember=True):
        # The MEMORY makes sure that this image won't be shown again until memoryForget is called
        self._fetch(keywords)
        h = self._hashString(itemId)
        if h not in self._MEMORY:
            self._MEMORY.append(h)
            k = self._hashString(keywords)
            if k in self._MEMORY_COUNT:
                self._MEMORY_COUNT[k] += 1
            else:
                self._MEMORY_COUNT[k] = 1

        # save memory
        if (len(self._MEMORY) % 20) == 0:
            logging.info('Interim saving of memory every 20 entries')
            with open(os.path.join(self._DIR_MEMORY, f'{self._MEMORY_KEY}.json'), 'w') as f:
                json.dump(self._MEMORY, f)

    def getList(self, keywords):
        self._fetch(keywords)
        return self._MEMORY

    def count(self, keywords):
        if self._MEMORY_KEY is None:
            self._fetch(keywords)
        h = self._hashString(keywords)
        if h in self._MEMORY_COUNT:
            return self._MEMORY_COUNT[h]
        return 0

    def seen(self, itemId, keywords):
        self._fetch(keywords)
        h = self._hashString(itemId)
        return h in self._MEMORY

    def forget(self, keywords):
        self._fetch(keywords)
        n = os.path.join(self._DIR_MEMORY, f'{self._MEMORY_KEY}.json')
        if os.path.exists(n):
            logging.debug(f'Removed memory file {n}')
            os.unlink(n)
        logging.debug(f'Has {len(self._MEMORY)} memories before wipe')
        self._MEMORY = []
        self._MEMORY_COUNT.pop(self._hashString(keywords), None)
