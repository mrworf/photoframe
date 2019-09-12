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
import modules.debug as debug
import flask
#from flask import request, redirect, session, url_for, abort, flash

class BaseRoute:
  SIMPLE = False

  class Mapping:
    def __init__(self, url):
        self._URL = url.strip()
        self._METHODS = ['GET']
        self._DEFAULTS = {}

    def addMethod(self, method):
      self._METHODS.append(method.upper().strip())
      return self

    def clearMethods(self):
      self._METHODS = []
      return self

    def addDefault(self, key, value):
      self._DEFAULTS[key] = value
      return self

    def clearDefaults(self):
      self._DEFAULTS = {}
      return self

  def __init__(self):
    self._MAPPINGS = []
    self.app = None
    self.setup()

  def _assignServer(self, server):
    self.server = server
    self.app = server.app

  def addUrl(self, url):
    mapping = self.Mapping(url)
    self._MAPPINGS.append(mapping)
    return mapping

  def setup(self):
    pass

  def __call__(self, **kwargs):
    return self.handle(self.app, **kwargs)    

  def handle(self, app, **kwargs):
    msg = '%s does not have an implementation' % self._URL
    logging.error(msg)
    return msg, 200

  def getRequest(self):
    return flask.request

  def setAbort(self, code):
    return flask.abort(code)

  def redirect(self, url):
    return flask.redirect(url)

  def jsonify(self, data):
    return flask.json.jsonify(data)
