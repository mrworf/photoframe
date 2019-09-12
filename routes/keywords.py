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

from baseroute import BaseRoute
from modules.helper import helper

class RouteKeywords(BaseRoute):
  def setupex(self, servicemgr, slideshow):
    self.servicemgr = servicemgr
    self.slideshow = slideshow

    self.addUrl('/keywords/<service>/help')
    self.addUrl('/keywords/<service>')
    self.addUrl('/keywords/<service>/add').clearMethods().addMethod('POST')
    self.addUrl('/keywords/<service>/delete').clearMethods().addMethod('POST')
    self.addUrl('/keywords/<service>/source/<int:index>')

  def handle(self, app, service, index=None):
    if self.getRequest().method == 'GET':
      if 'source' in self.getRequest().url:
        return self.redirect(self.servicemgr.sourceServiceKeywords(service, index))
      elif 'help' in self.getRequest().url:
        return self.jsonify({'message' : self.servicemgr.helpServiceKeywords(service)})
      else:
        return self.jsonify({'keywords' : self.servicemgr.getServiceKeywords(service)})
    elif self.getRequest().method == 'POST' and self.getRequest().json is not None:
      result = True
      if 'id' not in self.getRequest().json:
        hadKeywords = self.servicemgr.hasKeywords()
        result = self.servicemgr.addServiceKeywords(service, self.getRequest().json['keywords'])
        if result['error'] is not None:
          result['status'] = False
        else:
          result['status'] = True
          if hadKeywords != self.servicemgr.hasKeywords():
            # Make slideshow show the change immediately, we have keywords
            self.slideshow.trigger()
      else:
        if not self.servicemgr.removeServiceKeywords(service, self.getRequest().json['id']):
          result = {'status':False, 'error' : 'Unable to remove keyword'}
        else:
          # Trigger slideshow, we have removed some keywords
          self.slideshow.trigger()
      return self.jsonify(result)
    self.setAbort(500)
