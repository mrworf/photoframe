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
from baseroute import BaseRoute

#@app.route('/options/<cmd>')
class RouteOptions(BaseRoute):
  SIMPLE = True

  def setup(self):
    self.addUrl('/options/<cmd>')

  def handle(self, app, cmd):
    if cmd == 'DEBUG':
      sysconfig.setOption('POSTCMD', '"--debug"')
    elif cmd == 'NODEBUG':
      sysconfig.setOption('POSTCMD', '')
    return 'Options changed', 200
