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
from flask import send_from_directory

from .baseroute import BaseRoute

class RoutePages(BaseRoute):
    SIMPLE = True

    def setup(self):
        self.addUrl('/<path:file>')
        self.addUrl('/').addDefault('file', None)

    def handle(self, app, **kwargs):
      file = kwargs['file']
      if file is None:
        file = 'index.html'

      root_dir = os.path.join(os.getcwd(), 'static')
      if '..' in file:
        return 'File not found', 404
      return send_from_directory(root_dir, file)
