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

from .baseroute import BaseRoute

class RouteEvents(BaseRoute):
  def setupex(self, events):
    self.events = events

    self.addUrl('/events').addDefault('since', None).addDefault('id', None)
    self.addUrl('/events/<int:since>').addDefault('id', None)
    self.addUrl('/events/remove/<int:id>').addDefault('since', None)

  def handle(self, app, since, id):
    if since is not None:
      return self.jsonify(self.events.getSince(since))
    elif id is not None:
      self.events.remove(id)
      return 'ok'
    else:
      return self.jsonify(self.events.getAll())
