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

import logging
import os
import shutil

from modules.path import path as syspath

class ImageHistory:
  MAX_HISTORY = 20
  def __init__(self, settings):
    self._HISTORY = []
    self.settings = settings

    # Also, make sure folder exists AND clear any existing content
    if not os.path.exists(syspath.HISTORYFOLDER):
      os.mkdir(syspath.HISTORYFOLDER)

    # Clear it
    for p, _dirs, files in os.walk(syspath.HISTORYFOLDER):
      for filename in [os.path.join(p, f) for f in files]:
        try:
          os.unlink(filename)
        except:
          logging.exception('Failed to delete "%s"' % filename)

  def _find(self, file):
    return next((entry for entry in self._HISTORY if entry.filename == file), None)

  def add(self, image):
    if image.error is not None:
      logging.warning('Will not store image errors, skipping')
      return
    historyFile = os.path.join(syspath.HISTORYFOLDER, image.getCacheId())
    if not self._find(historyFile):
      shutil.copy(image.filename, historyFile)
    h = image.copy()
    h.setFilename(historyFile)
    h.allowCache(False)

    self._HISTORY.insert(0, h)
    self._obeyLimits()

  def _obeyLimits(self):
    # Make sure history isn't too big
    while len(self._HISTORY) > ImageHistory.MAX_HISTORY:
      entry = self._HISTORY.pop()
      if not self._find(entry.filename):
        os.unlink(entry.filename)

  def getAvailable(self):
    return len(self._HISTORY)

  def getByIndex(self, index):
    if index < 0 or index >= len(self._HISTORY):
      logging.warning('History index requested is out of bounds (%d wanted, have 0-%d)', index, len(self._HISTORY)-1)
      return None
    entry = self._HISTORY[index]
    # We need to make a copy which is safe to delete!
    f = os.path.join(self.settings.get('tempfolder'), 'history')
    shutil.copy(entry.filename, f)
    return entry.copy().setFilename(f)
