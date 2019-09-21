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
import json

from baseroute import BaseRoute

class RouteOAuthLink(BaseRoute):
    def setupex(self, servicemgr, slideshow):
        self.servicemgr = servicemgr
        self.slideshow = slideshow

        self.addUrl('/callback')
        self.addUrl('/service/<service>/link')
        self.addUrl('/service/<service>/oauth').clearMethods().addMethod('POST')

    def handle(self, app, **kwargs):
      print(self.getRequest().url)
      if '/callback?' in self.getRequest().url:
          # Figure out who should get this result...
          old = self.servicemgr.hasReadyServices()
          if self.servicemgr.oauthCallback(self.getRequest()):
            # Request handled
            if old != self.servicemgr.hasReadyServices():
              self.slideshow.trigger()
            return self.redirect('/')
          else:
            self.setAbort(500)
      elif self.getRequest().url.endswith('/link'):
        return self.redirect(self.servicemgr.oauthStart(kwargs['service']))
      elif self.getRequest().url.endswith('/oauth'):
        #j = self.getRequest().json
        # This one is special, this is a file upload of the JSON config data
        # and since we don't need a physical file for it, we should just load
        # the data. For now... ignore
        if 'filename' not in self.getRequest().files:
          logging.error('No file part')
          return self.setAbort(405)
        file = self.getRequest().files['filename']
        data = json.load(file)
        if 'web' in data:
          data = data['web']
        if 'redirect_uris' in data and 'https://photoframe.sensenet.nu' not in data['redirect_uris']:
          return 'The redirect uri is not set to https://photoframe.sensenet.nu', 405
        if not self.servicemgr.oauthConfig(kwargs['service'], data):
          return 'Configuration was invalid', 405
        return 'Configuration set', 200
      else:
        self.setAbort(500)
