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
import sys
import subprocess
from settings import settings
import logging

class sysconfig:
  @staticmethod
  def isDisplayRotated():
    rotate = False
    if os.path.exists(settings.CONFIG_TXT):
      with open(settings.CONFIG_TXT, 'r') as f:
        for line in f:
          clean = line.strip()
          if clean == '':
            continue
          if clean.startswith('display_rotate='):
            if clean.endswith('1') or clean.endswith('3'):
              rotate = True
            else:
              rotate = False
    return rotate

  @staticmethod
  def getDisplayOrientation():
    rotate = 0
    if os.path.exists(settings.CONFIG_TXT):
      with open(settings.CONFIG_TXT, 'r') as f:
        for line in f:
          clean = line.strip()
          if clean == '':
            continue
          if clean.startswith('display_rotate='):
            rotate = int(clean[-1])*90
    return rotate

  @staticmethod
  def setDisplayOrientation(deg):
    found = False
    configline = 'display_rotate=%d\n' % int(deg/90)
    if os.path.exists(settings.CONFIG_TXT):
      with open(settings.CONFIG_TXT, 'r') as ifile:
        with open(settings.CONFIG_TXT + '.new', 'w') as ofile:
          for line in ifile:
            clean = line.strip()
            if clean.startswith('display_rotate='):
              found = True
              line = configline
            ofile.write(line)
          if not found:
            ofile.write(configline)
      try:
        os.rename(settings.CONFIG_TXT, settings.CONFIG_TXT + '.old')
        os.rename(settings.CONFIG_TXT + '.new', settings.CONFIG_TXT)
        # Keep the first version of the config.txt just-in-case
        if os.path.exists(settings.CONFIG_TXT + '.original'):
          os.unlink(settings.CONFIG_TXT + '.old')
        else:
          os.rename(settings.CONFIG_TXT + '.old', settings.CONFIG_TXT + '.original')
        return True
      except:
        logging.exception('Failed to activate new config.txt, you may need to restore the config.txt')
    return False
