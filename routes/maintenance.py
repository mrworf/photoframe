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
import subprocess

from modules.helper import helper

from baseroute import BaseRoute

class RouteMaintenance(BaseRoute):
  def setupex(self, emulator, drivermgr, slideshow):
    self.drivermgr = drivermgr
    self.emulator = emulator
    self.slideshow = slideshow

    self.addUrl('/maintenance/<cmd>')

  def handle(self, app, cmd):
    if cmd == 'reset':
      # Remove driver if active
      self.drivermgr.activate(None)
      # Delete configuration data
      if os.path.exists(path.CONFIGFOLDER):
        shutil.rmtree(path.CONFIGFOLDER, True)
      # Reboot
      if not emulator:
        subprocess.call(['/sbin/reboot'], stderr=void);
      else:
        self.server.stop()
      return self.jsonify({'reset': True})
    elif cmd == 'reboot':
      if not emulator:
        subprocess.call(['/sbin/reboot'], stderr=void);
      else:
        self.server.stop()
      return self.jsonify({'reboot' : True})
    elif cmd == 'shutdown':
      if not emulator:
        subprocess.call(['/sbin/poweroff'], stderr=void);
      else:
        self.server.stop()
      return self.jsonify({'shutdown': True})
    elif cmd == 'update':
      if emulator:
        return 'Cannot run update from emulation mode', 200
      if os.path.exists('/root/photoframe/update.sh'):
        p = subprocess.Popen('/bin/bash /root/photoframe/update.sh 2>&1 | logger -t forced_update', shell=True)
        return 'Update in process', 200
      else:
        return 'Cannot find update tool', 404
    elif cmd == 'clearCache':
      self.slideshow.createEvent("clearCache")
      return self.jsonify({'clearCache': True})
    elif cmd == 'forgetMemory':
      self.slideshow.createEvent("memoryForget")
      return self.jsonify({'forgetMemory': True})
