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
from path import path
import logging

class sysconfig:
  @staticmethod
  def _getConfigFileState(key):
    if os.path.exists(path.CONFIG_TXT):
      with open(path.CONFIG_TXT, 'r') as f:
        for line in f:
          clean = line.strip()
          if clean == '':
            continue
          if clean.startswith('%s=' % key):
            _, value = clean.split('=', 1)
            return value
    return None

  @staticmethod
  def _changeConfigFile(key, value):
    configline = '%s=%s\n' % (key, value)
    found = False
    if os.path.exists(path.CONFIG_TXT):
      with open(path.CONFIG_TXT, 'r') as ifile:
        with open(path.CONFIG_TXT + '.new', 'w') as ofile:
          for line in ifile:
            clean = line.strip()
            if clean.startswith('%s=' % key):
              found = True
              line = configline
            ofile.write(line)
          if not found:
            ofile.write(configline)
      try:
        os.rename(path.CONFIG_TXT, path.CONFIG_TXT + '.old')
        os.rename(path.CONFIG_TXT + '.new', path.CONFIG_TXT)
        # Keep the first version of the config.txt just-in-case
        if os.path.exists(path.CONFIG_TXT + '.original'):
          os.unlink(path.CONFIG_TXT + '.old')
        else:
          os.rename(path.CONFIG_TXT + '.old', path.CONFIG_TXT + '.original')
        return True
      except:
        logging.exception('Failed to activate new config.txt, you may need to restore the config.txt')

  @staticmethod
  def isDisplayRotated():
    state = sysconfig._getConfigFileState('display_rotate')
    if state is not None:
      return state.endswith('1') or state.endswith('3')
    return False

  @staticmethod
  def getDisplayOrientation():
    rotate = 0
    state = sysconfig._getConfigFileState('display_rotate')
    if state is not None:
      rotate = int(state)*90
    return rotate

  @staticmethod
  def setDisplayOverscan(enable):
    if enable:
      return sysconfig._changeConfigFile('disable_overscan', '0')
    else:
      return sysconfig._changeConfigFile('disable_overscan', '1')

  @staticmethod
  def isDisplayOverscan():
    state = sysconfig._getConfigFileState('disable_overscan')
    if state is not None:
      return state == '0'
    return True # Typically true for RPi

  @staticmethod
  def setDisplayOrientation(deg):
    return sysconfig._changeConfigFile('display_rotate', '%d' % int(deg/90))

  @staticmethod
  def _app_opt_load():
    if os.path.exists(path.OPTIONSFILE):
      lines = {}
      with open(path.OPTIONSFILE, 'r') as f:
        for line in f:
          key, value = line.strip().split('=',1)
          lines[key.strip()] = value.strip()
      return lines
    return None

  @staticmethod
  def _app_opt_save(lines):
    with open(path.OPTIONSFILE, 'w') as f:
      for key in lines:
        f.write('%s=%s\n' % (key, lines[key]))

  @staticmethod
  def setOption(key, value):
    lines = self.app_opt_load()
    if lines is None:
      lines = {}
    lines[key] = value
    self.app_opt_save(lines)

  @staticmethod
  def removeOption(key):
    lines = self.app_opt_load()
    if lines is None:
      return
    lines.pop(key, False)
    self.app_opt_save(lines)

  @staticmethod
  def getHTTPAuth():
    user = None
    userfiles = ['/boot/http-auth.json', path.CONFIGFOLDER + '/http-auth.json']
    for userfile in userfiles:
      if os.path.exists(userfile):
        logging.debug('Found "%s", loading the data' % userfile)
        try:
          with open(userfile, 'rb') as f:
            user = json.load(f)
            if 'user' not in user or 'password' not in user:
              logging.warning("\"%s\" doesn't contain a user and password key" % userfile)
              user = None
            else:
              break
        except:
          logging.exception('Unable to load JSON from "%s"' % userfile)
          user = None
    return user
