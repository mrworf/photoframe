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

class Events:
  TYPE_PERSIST = 1
  TYPE_NORMAL = 0

  LEVEL_INFO = 0
  LEVEL_WARN = 1
  LEVEL_ERR = 2
  LEVEL_DEBUG = 3

  def __init__(self):
    self.idcount = 0
    self.msgs = []

  def add(self, message, unique=None, link=None, level=LEVEL_INFO, type=TYPE_NORMAL):
    record = {'id': self.idcount, 'unique' : unique, 'type' : type, 'level' : level, 'message' : message, 'link' : link}
    if unique is not None:
      unique = repr(unique) # Make it a string to be safe
      for i in range(0, len(self.msgs)):
        if self.msgs[i]['unique'] == unique:
          self.msgs[i] = record
          record = None
          break

    if record is not None:
      self.msgs.append(record)
    self.idcount += 1

  def remove(self, id):
    for i in range(0, len(self.msgs)):
      if self.msgs[i]['id'] == id and self.msgs[i]['type'] != Events.TYPE_PERSIST:
        self.msgs.pop(i)
        break

  def getAll(self):
    return self.msgs

  def getSince(self, id):
    ret = []
    for msg in self.msgs:
      if msg['id'] > id:
        ret.append(msg)
    return ret
