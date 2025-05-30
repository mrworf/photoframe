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

from modules.sysconfig import sysconfig
from .baseroute import BaseRoute

#@auth.login_required
class RouteOrientation(BaseRoute):
  def setupex(self, cachemgr):
    self.cachemgr = cachemgr

    self.addUrl('/rotation').addDefault('orient', None)
    self.addUrl('/rotation/<int:orient>').clearMethods().addMethod('PUT')

  def handle(self, app, orient):
    if orient is None:
      return self.jsonify({'rotation' : sysconfig.getDisplayOrientation()})
    else:
      if orient >= 0 and orient < 360:
        sysconfig.setDisplayOrientation(orient)
        self.cachemgr.empty()
        return self.jsonify({'rotation' : sysconfig.getDisplayOrientation()})
    self.setAbort(500)
