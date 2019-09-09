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
import shutil

from modules.sysconfig import sysconfig
from modules.path import path

from baseroute import BaseRoute

class RouteDetails(BaseRoute):
  def setupex(self, displaymgr, drivermgr, colormatch, slideshow):
    self.displaymgr = displaymgr
    self.drivermgr = drivermgr
    self.colormatch = colormatch
    self.slideshow = slideshow

    self.addUrl('/details/<about>')

  def handle(self, app, about):
    if about == 'tvservice':
      result = {}
      result['resolution'] = self.displaymgr.available()
      result['status'] = self.displaymgr.current()
      return self.jsonify(result)
    elif about == 'current':
      image, mime = self.displaymgr.get()
      response = app.make_response(image)
      response.headers.set('Content-Type', mime)
      return response
    elif about == 'drivers':
      result = self.drivermgr.list().keys()
      return self.jsonify(result)
    elif about == 'timezone':
      result = helper.timezoneList()
      return self.jsonify(result)
    elif about == 'version':
      output = subprocess.check_output(['git', 'log', '-n1'], stderr=void)
      lines = output.split('\n')
      infoDate = lines[2][5:].strip()
      infoCommit = lines[0][7:].strip()
      output = subprocess.check_output(['git', 'status'], stderr=void)
      lines = output.split('\n')
      infoBranch = lines[0][10:].strip()
      return self.jsonify({'date':infoDate, 'commit':infoCommit, 'branch': infoBranch})
    elif about == 'color':
      return self.jsonify(self.slideshow.getColorInformation())
    elif about == 'sensor':
      return self.jsonify({'sensor' : self.colormatch.hasSensor()})
    elif about == 'display':
      return self.jsonify({'display' : self.displaymgr.isEnabled()})

    self.setAbort(404)
