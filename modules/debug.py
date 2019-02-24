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
import logging

def _stringify(args):
  result = ''
  if len(args) > 0:
    for arg in args:
      if ' ' in arg:
        result += '"' + arg + '" '
      else:
        result += arg + ' '
    result = result[0:-1]

  return result.replace('\n', '\\n')

def subprocess_call(cmds, stderr=None, stdout=None):
  logging.debug('subprocess.call(%s)', _stringify(cmds))
  return subprocess.call(cmds, stderr=stderr, stdout=stdout)

def subprocess_check_output(cmds, stderr=None, stdout=None):
  logging.debug('subprocess.check_output(%s)', _stringify(cmds))
  return subprocess.check_output(cmds, stderr=stderr, stdout=stdout)
