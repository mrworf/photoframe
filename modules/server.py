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
import re
import traceback
import importlib

from threading import Thread

from modules.sysconfig import sysconfig

from flask import Flask, request
from flask_httpauth import HTTPBasicAuth
from werkzeug.exceptions import HTTPException

# used if we don't find authentication json


class NoAuth:
    def __init__(self):
        pass

    def login_required(self, fn):
        def wrap(*args, **kwargs):
            return fn(*args, **kwargs)
        wrap.__name__ = fn.__name__
        return wrap


class WebServer(Thread):
    def __init__(self, run_async=False, port=7777, listen='0.0.0.0', debug=False):
        Thread.__init__(self)
        self.port = port
        self.listen = listen
        self.run_async = run_async
        self.debug = debug

        self.app = Flask(__name__, static_url_path='/--do--not--ever--use--this--')
        self.app.config['UPLOAD_FOLDER'] = '/tmp/'
        self.user = sysconfig.getHTTPAuth()
        self.auth = NoAuth()
        if self.user is not None:
            self.auth = HTTPBasicAuth()

            @self.auth.get_password
            def check_password(username):
                if self.user['user'] == username:
                    return self.user['password']
                return None
        else:
            logging.info('No http-auth.json found, disabling http authentication')

        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        logging.getLogger('oauthlib').setLevel(logging.ERROR)
        logging.getLogger('urllib3').setLevel(logging.ERROR)

        self.app.error_handler_spec = {None: {None: {Exception: self._showException}}}
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        self.app.secret_key = os.urandom(24)
        self._registerHandlers()
        self.authmethod = self.auth.login_required(lambda: None)
        self.app.after_request(self._nocache)
        self.app.before_request(self._logincheck)

    def _logincheck(self):
        if not request.endpoint:
            return

        return self.authmethod()

    def start(self):
        if self.run_async:
            self.start()
        else:
            self.run()

    def stop(self):
        try:
            func = request.environ.get('werkzeug.server.shutdown')
            if func:
                func()
                return True
            else:
                logging.error('Unable to stop webserver, cannot find shutdown() function')
                return False
        except Exception:
            # We're not running with request, so...
            raise RuntimeError('Server shutdown')

    def run(self):
        try:
            self.app.run(debug=self.debug, use_reloader=False, port=self.port, host=self.listen)
        except RuntimeError as msg:
            if str(msg) == "Server shutdown":
                pass  # or whatever you want to do when the server goes down
            else:
                raise RuntimeError(msg)

    def _nocache(self, r):
        r.headers["Pragma"] = "no-cache"
        r.headers["Expires"] = "0"
        r.headers['Cache-Control'] = 'public, max-age=0'
        return r

    def _showException(self, e):
        if isinstance(e, HTTPException):
            code = e.code
            message = str(e)
        else:
            code = 500
            lines = traceback.format_exc().splitlines()
            message = '''
      <html><head><title>Internal error</title></head><body style="font-family: Verdana">
      <h1>Uh oh, something went wrong...</h1>
      Please go to <a href="https://github.com/mrworf/photoframe/issues">github</a>
      and see if this is a known issue, if not, feel free to file a
      <a href="https://github.com/mrworf/photoframe/issues/new">new issue<a> with the
      following information:
      <pre style="margin: 15pt; padding: 10pt; border: 1px solid; background-color: #eeeeee">'''
            for line in lines:
                message += line + '\n'
            message += '''</pre>
      Thank you for your patience
      </body>
      </html>
      '''
        return message, code

    def _instantiate(self, module, klass):
        module = importlib.import_module('routes.' + module)
        my_class = getattr(module, klass)
        return my_class

    def registerHandler(self, route):
        route._assignServer(self)
        for mapping in route._MAPPINGS:
            if route.SIMPLE:
                logging.info('Registering URL %s to %s (simple)', mapping._URL, route.__class__.__name__)
            else:
                logging.info('Registering URL %s to %s', mapping._URL, route.__class__.__name__)
            self.app.add_url_rule(mapping._URL, mapping._URL, route,
                                  methods=mapping._METHODS, defaults=mapping._DEFAULTS)

    def _registerHandlers(self):
        for item in os.listdir('routes'):
            if os.path.isfile('routes/' + item) and item.endswith('.py') and item != 'baseroute.py':
                with open('routes/' + item, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('class ') and line.endswith('(BaseRoute):'):
                            m = re.search('class +([^\\(]+)\\(', line)
                            if m is not None:
                                klass = self._instantiate(item[0:-3], m.group(1))
                                if klass.SIMPLE:
                                    try:
                                        route = eval('klass()')
                                        self.registerHandler(route)
                                    except Exception:
                                        logging.exception('Failed to create route for %s' % item)
                            break
