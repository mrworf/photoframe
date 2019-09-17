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

from baseroute import BaseRoute
from modules.helper import helper
from modules.shutdown import shutdown

class RouteSettings(BaseRoute):
  def setupex(self, powermanagement, settingsMgr, drivermgr, timekeeper, display, cachemgr, slideshow):
    self.powermanagement = powermanagement
    self.settingsMgr = settingsMgr
    self.drivermgr = drivermgr
    self.timekeeper = timekeeper
    self.display = display
    self.cachemgr = cachemgr
    self.slideshow = slideshow

    self.addUrl('/setting').addDefault('key', None).addDefault('value', None)
    self.addUrl('/setting/<key>').addDefault('value', None)
    self.addUrl('/setting/<key>/<value>').clearMethods().addMethod('PUT')

  def handle(self, app, key, value):
    # Depending on PUT/GET we will either change or read
    # values. If key is unknown, then this call fails with 404
    if key is not None:
      if self.settingsMgr.getUser(key) is None:
        self.abort(404)
        return

    if self.getRequest().method == 'PUT':
      status = True
      if key == "keywords":
        # Keywords has its own API
        self.setAbort(404)
        return
      self.settingsMgr.setUser(key, value)
      if key in ['display-driver']:
        drv = self.settingsMgr.getUser('display-driver')
        if drv == 'none':
          drv = None
        special = self.drivermngt.activate(drv)
        if special is None:
          self.settingsMgr.setUser('display-driver', 'none')
          self.settingsMgr.setUser('display-special', None)
          status = False
        else:
          self.settingsMgr.setUser('display-special', special)
      if key in ['timezone']:
        # Make sure we convert + to /
        self.settingsMgr.setUser('timezone', value.replace('+', '/'))
        helper.timezoneSet(self.settingsMgr.getUser('timezone'))
      if key in ['resolution', 'tvservice']:
        width, height, tvservice = self.display.setConfiguration(value, self.settingsMgr.getUser('display-special'))
        self.settingsMgr.setUser('tvservice', tvservice)
        self.settingsMgr.setUser('width',  width)
        self.settingsMgr.setUser('height', height)
        self.display.enable(True, True)
        self.cachemgr.empty()
      if key in ['display-on', 'display-off']:
        self.timekeeper.setConfiguration(self.settingsMgr.getUser('display-on'), self.settingsMgr.getUser('display-off'))
      if key in ['autooff-lux', 'autooff-time']:
        self.timekeeper.setAmbientSensitivity(self.settingsMgr.getUser('autooff-lux'), self.settingsMgr.getUser('autooff-time'))
      if key in ['powersave']:
        self.timekeeper.setPowermode(self.settingsMgr.getUser('powersave'))
      if key in ['shutdown-pin']:
        self.powermanagement.stopmonitor()
        self.powermanagement = shutdown(self.settingsMgr.getUser('shutdown-pin'))
      if key in ['imagesizing', 'randomize_images']:
        self.slideshow.createEvent("settingsChange")
      self.settingsMgr.save()
      return self.jsonify({'status':status})

    elif self.getRequest().method == 'GET':
      if key is None:
        return self.jsonify(self.settingsMgr.getUser())
      else:
        return self.jsonify({key : self.settingsMgr.getUser(key)})
    self.setAbort(404)
