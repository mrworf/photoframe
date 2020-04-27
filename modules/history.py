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

class ImageHistory:
  MAX_HISTORY = 20
  def __init__(self):
    self._HISTORY_FOLDER = ''
    self._HISTORY = []

  def add(self, image):
    if image.id not in self._HISTORY:
      # Copy the file
      pass
    self._HISTORY.insert(image.id, 0)

    # Make sure history isn't too big
    while len(self._HISTORY) > MAX_HISTORY:
      file = self._HISTORY.pop()
      if file not in self._HISTORY:
        os.unlink(os.path.join(self._HISTORY_FOLDER, file))
