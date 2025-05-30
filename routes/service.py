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

from routes.baseroute import BaseRoute

#@app.route('/service/<action>',  methods=['GET', 'POST'])
#@auth.login_required
class RouteService(BaseRoute):
  def setupex(self, servicemgr, slideshow):
    self.servicemgr = servicemgr
    self.slideshow = slideshow

    self.addUrl('/service/<action>').addMethod('POST')

  def handle(self, app, action):
    if action == 'available':
      return self.jsonify(self.servicemgr.listServices())
    if action == 'list':
      return self.jsonify(self.servicemgr.getServices())
    
    if self.getRequest().method == 'POST':
      j = self.getRequest().json
      if action == 'add' and j is not None:
        if 'name' in j and 'id' in j:
          old = self.servicemgr.hasReadyServices()
          svcid = self.servicemgr.addService(int(j['id']), j['name'])
          if old != self.servicemgr.hasReadyServices():
            self.slideshow.trigger()
          return self.jsonify({'id':svcid})
      if action == 'remove' and j is not None:
        if 'id' in j:
          self.servicemgr.deleteService(j['id'])
          self.slideshow.trigger() # Always trigger since we don't know who was on-screen
          return self.jsonify({'status':'Done'})
      if action == 'rename' and j is not None:
        if 'name' in j and 'id' in j:
          if self.servicemgr.renameService(j['id'], j['name']):
            return self.jsonify({'status':'Done'})
      if self.getRequest().url.endswith('/config/fields'):
        return self.jsonify(self.servicemgr.getServiceConfigurationFields(id))
      if self.getRequest().url.endswith('/config'):
        if j is not None and 'config' in j:
          if self.servicemgr.setServiceConfiguration(id, j['config']):
            return 'Configuration saved', 200
    elif self.getRequest().method == 'GET':
      if self.getRequest().url.endswith('/config'):
        return self.jsonify(self.servicemgr.getServiceConfiguration(id))
    
    self.setAbort(500)

