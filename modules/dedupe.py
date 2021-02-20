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

class DedupeManager:
  def __init__(self, memoryLocation):
    try:
      #from PIL import Image
      #import imagehash
      self.hasImageHash = True
      logging.info('ImageHash functionality is available')
    except:
      self.hasImageHash = False
      logging.info('ImageHash functionality is unavailable')

  def _hamming_distance(self, i1, i2):
      x = i1 ^ i2
      setBits = 0

      while (x > 0):
          setBits += x & 1
          x >>= 1

      return setBits

  def _hamming(self, s1, s2):
      h = 0
      for i in range(0, len(s1)/2):
          i1 = int(s1[i*2:i*2+2], 16)
          i2 = int(s2[i*2:i*2+2], 16)
          h += self._hamming_distance(i1, i2)
      return h
