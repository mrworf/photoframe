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

import modules.debug as debug
from .baseroute import BaseRoute

class RouteDebug(BaseRoute):
  SIMPLE = True # We have no dependencies to the rest of the system

  def setup(self):
    self.addUrl('/debug')    

  def handle(self, app, **kwargs):
    # Special URL, we simply try to extract latest 100 lines from syslog
    # and filter out frame messages. These are shown so the user can
    # add these to issues.
    report = []
    report.append(debug.version())
    report.append(debug.logfile(False))
    report.append(debug.logfile(True))
    report.append(debug.stacktrace())

    message = '<html><head><title>Photoframe Log Report</title></head><body style="font-family: Verdana">'
    message = '''<h1>Photoframe Log report</h1><div style="margin: 15pt; padding 10pt">This page is intended to be used when you run into issues which cannot be resolved by the messages displayed on the frame. Please save and attach this information
    when you <a href="https://github.com/mrworf/photoframe/issues/new">create a new issue</a>.<br><br>Thank you for helping making this project better &#128517;</div>'''
    for item in report:
      message += '<h1>%s</h1><pre style="margin: 15pt; padding: 10pt; border: 1px solid; background-color: #eeeeee">' % item[0]
      if item[1]:
        for line in item[1]:
          message += line + '\n'
      else:
        message += '--- Data unavailable ---'
      message += '''</pre>'''
      if item[2] is not None:
        message += item[2]
    message += '</body></html>'
    return message, 200
