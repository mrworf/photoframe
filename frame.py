#!/usr/bin/env python
#
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
import json
import sys
import os
import random
import hashlib
import datetime
import time
import math
import subprocess
import logging
import socket
import threading
import argparse
import shutil
import traceback

from modules.remember import remember
from modules.shutdown import shutdown
from modules.timekeeper import timekeeper
from modules.settings import settings
from modules.helper import helper
from modules.display import display
from modules.oauth import OAuth
from modules.slideshow import slideshow
from modules.colormatch import colormatch
from modules.drivers import drivers

from modules.servicemanager import ServiceManager

parser = argparse.ArgumentParser(description="PhotoFrame - A RPi3 based digital photoframe", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--logfile', default=None, help="Log to file instead of stdout")
parser.add_argument('--port', default=7777, type=int, help="Port to listen on")
parser.add_argument('--listen', default="0.0.0.0", help="Address to listen on")
parser.add_argument('--debug', action='store_true', default=False, help='Enable loads more logging')
parser.add_argument('--emulatefb', action='store_true', default=False, help='Emulate the framebuffer')
parser.add_argument('--basedir', default=None, help='Change the root folder of photoframe')
cmdline = parser.parse_args()

if cmdline.debug:
  logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
else:
  logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if cmdline.basedir is not None:
  logging.info('Altering default basedir from /root/ to %s', cmdline.basedir)
  settings().reassign(cmdline.basedir)

void = open(os.devnull, 'wb')

# Supercritical, since we store all photoframe files in a subdirectory, make sure to create it
if not os.path.exists(settings.CONFIGFOLDER):
  try:
    os.mkdir(settings.CONFIGFOLDER)
  except:
    logging.exception('Unable to create configuration directory, cannot start')
    sys.exit(255)
elif not os.path.isdir(settings.CONFIGFOLDER):
  logging.error('%s isn\'t a folder, cannot start', settings.CONFIGFOLDER)
  sys.exit(255)

if cmdline.emulatefb and not os.path.exists('/usr/bin/fim'):
  logging.error('--emulatefb requires fim to be installed')
  sys.exit(255)

import requests
from requests_oauthlib import OAuth2Session
from flask import Flask, request, redirect, session, url_for, abort, flash
from flask.json import jsonify
from flask_httpauth import HTTPBasicAuth
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException

logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('oauthlib').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)


# used if we don't find authentication json
class NoAuth:
  def __init__(self):
    pass

  def login_required(self, fn):
    def wrap(*args, **kwargs):
      return fn(*args, **kwargs)
    wrap.func_name = fn.func_name
    return wrap

app = Flask(__name__, static_url_path='')
app.config['UPLOAD_FOLDER'] = '/tmp/'
user = None
services = None

userfiles = ['/boot/http-auth.json', settings.CONFIGFOLDER + '/http-auth.json']
for userfile in userfiles:
  if os.path.exists(userfile):
    logging.debug('Found "%s", loading the data' % userfile)
    try:
      with open(userfile, 'rb') as f:
        user = json.load(f)
        if 'user' not in user or 'password' not in user:
          logging.warning("\"%s\" doesn't contain a user and password key" % userfile)
          user = None
        else:
          break
    except:
      logging.exception('Unable to load JSON from "%s"' % userfile)
      user = None

if user is None:
  logging.info('No http-auth.json found, disabling http authentication')

auth = NoAuth()
if user is not None:
  auth = HTTPBasicAuth()
  @auth.get_password
  def check_password(username):
    if user['user'] == username:
      return user['password']
    return None

@app.after_request
def nocache(r):
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r

@app.errorhandler(Exception)
def show_error(e):
  if isinstance(e, HTTPException):
    code = e.code
    message = str(e)
  else:
    code = 500
    #exc_type, exc_value, exc_traceback = sys.exc_info()
    lines = traceback.format_exc().splitlines()
    issue = lines[-1]
    message = '''
    <html><head><title>Internal error</title></head><body style="font-family: Verdana"><h1>Uh oh, something went wrong...</h1>
    Please go to <a href="https://github.com/mrworf/photoframe/issues">github</a>
    and see if this is a known issue, if not, feel free to file a <a href="https://github.com/mrworf/photoframe/issues/new">new issue<a> with the
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

@app.route('/debug', methods=['GET'], defaults={'all' : False})
@app.route('/debug/all', methods=['GET'], defaults={'all' : True})
def show_logs(all):
  # Special URL, we simply try to extract latest 100 lines from syslog
  # and filter out frame messages. These are shown so the user can
  # add these to issues.
  stats = os.stat('/var/log/syslog')
  cmd = 'grep "photoframe\[" /var/log/syslog | tail -n 100'
  title = 'Last 100 lines from the log'
  if all:
    title = 'Last 100 lines from the log (unfiltered)'
    cmd = 'tail -n 100 /var/log/syslog'
  lines = subprocess.check_output(cmd, shell=True)
  message = '''
  <html><head><title>Internal debugging</title></head><body style="font-family: Verdana"><h1>%s</h1>
  <pre style="margin: 15pt; padding: 10pt; border: 1px solid; background-color: #eeeeee">''' % title
  if lines:
    for line in lines.splitlines():
      message += line + '\n'
  else:
    message += 'Logs unavailable, perhaps it was archived recently (size will be less than 5000 bytes)'
  message += '''</pre>
  (size of logfile %d bytes, created %s)
  </body>
  </html>
  ''' % (stats.st_size, datetime.datetime.fromtimestamp(stats.st_ctime).strftime('%c'))
  return message, 200

@app.route('/setting', methods=['GET'], defaults={'key':None,'value':None})
@app.route('/setting/<key>', methods=['GET'], defaults={'value':None})
@app.route('/setting/<key>/<value>', methods=['PUT'])
@auth.login_required
def cfg_keyvalue(key, value):
  global powermanagement

  # Depending on PUT/GET we will either change or read
  # values. If key is unknown, then this call fails with 404
  if key is not None:
    if settings.getUser(key) is None:
      abort(404)
      return

  if request.method == 'PUT':
    status = True
    if key == "keywords":
      # Keywords has its own API
      abort(404)
      return
    settings.setUser(key, value)
    if key in ['display-driver']:
      drv = settings.getUser('display-driver')
      if drv == 'none':
        drv = None
      special = drivers.activate(drv)
      if special is None:
        settings.setUser('display-driver', 'none')
        settings.setUser('display-special', None)
        status = False
      else:
        settings.setUser('display-special', special)
    if key in ['timezone']:
      # Make sure we convert + to /
      settings.setUser('timezone', value.replace('+', '/'))
      helper.timezoneSet(settings.getUser('timezone'))
    if key in ['resolution', 'tvservice']:
      width, height, tvservice = display.setConfiguration(value, settings.getUser('display-special'))
      settings.setUser('tvservice', tvservice)
      settings.setUser('width',  width)
      settings.setUser('height', height)
      display.enable(True, True)
    if key in ['display-on', 'display-off']:
      timekeeper.setConfiguration(settings.getUser('display-on'), settings.getUser('display-off'))
    if key in ['autooff-lux', 'autooff-time']:
      timekeeper.setAmbientSensitivity(settings.getUser('autooff-lux'), settings.getUser('autooff-time'))
    if key in ['powersave']:
      timekeeper.setPowermode(settings.getUser('powersave'))
    if key in ['shutdown-pin']:
      powermanagement.stopmonitor()
      powermanagement = shutdown(settings.getUser('shutdown-pin'))
    settings.save()
    return jsonify({'status':status})

  elif request.method == 'GET':
    if key is None:
      return jsonify(settings.getUser())
    else:
      return jsonify({key : settings.getUser(key)})
  abort(404)

@app.route('/keywords', methods=['GET'])
@app.route('/keywords/add', methods=['POST'])
@app.route('/keywords/delete', methods=['POST'])
@auth.login_required
def cfg_keywords():
  if request.method == 'GET':
    return jsonify({'keywords' : settings.getUser('keywords')})
  elif request.method == 'POST' and request.json is not None:
    result = True
    if 'id' not in request.json:
      if settings.addKeyword(request.json['keywords']):
        settings.save()
    else:
      if settings.removeKeyword(request.json['id']):
        settings.save()
      else:
        result = False
    return jsonify({'status':result})
  abort(500)

@app.route('/maintainence/<cmd>')
@auth.login_required
def cfg_reset(cmd):
  if cmd == 'reset':
    # Remove driver if active
    drivers.activate(None)
    # Delete configuration data
    if os.path.exists(settings.CONFIGFOLDER):
      shutil.rmtree(settings.CONFIGFOLDER, True)
    # Reboot
    subprocess.call(['/sbin/reboot'], stderr=void);
    return jsonify({'reset': True})
  elif cmd == 'reboot':
    subprocess.call(['/sbin/reboot'], stderr=void);
    return jsonify({'reboot' : True})
  elif cmd == 'shutdown':
    subprocess.call(['/sbin/poweroff'], stderr=void);
    return jsonify({'shutdown': True})
  elif cmd == 'update':
    if os.path.exists('/root/photoframe/update.sh'):
      p = subprocess.Popen('/bin/bash /root/photoframe/update.sh 2>&1 | logger -t forced_update', shell=True)
      return 'Update in process', 200
    else:
      return 'Cannot find update tool', 404

@app.route('/details/<about>')
@auth.login_required
def cfg_details(about):
  if about == 'tvservice':
    result = {}
    result['resolution'] = display.available()
    result['status'] = display.current()
    return jsonify(result)
  elif about == 'current':
    image, mime = display.get()
    response = app.make_response(image)
    response.headers.set('Content-Type', mime)
    return response
  elif about == 'drivers':
    result = drivers.list().keys()
    return jsonify(result)
  elif about == 'timezone':
    result = helper.timezoneList()
    return jsonify(result)
  elif about == 'version':
    output = subprocess.check_output(['git', 'log', '-n1'], stderr=void)
    lines = output.split('\n')
    return jsonify({'date':lines[2][5:].strip(),'commit':lines[0][7:].strip()})
  elif about == 'color':
    return jsonify(slideshow.getColorInformation())
  elif about == 'sensor':
    return jsonify({'sensor' : colormatch.hasSensor()})
  elif about == 'display':
    return jsonify({'display':display.isEnabled()})

  abort(404)

@app.route('/upload/<item>', methods=['POST'])
@auth.login_required
def upload(item):
  retval = {'status':200, 'return':{}}

  if request.method == 'POST':
    # check if the post request has the file part
    if 'filename' not in request.files:
      logging.error('No file part')
      abort(405)
    file = request.files['filename']
    if item == 'driver':
      # if user does not select file, browser also
      # submit an empty part without filename
      if file.filename == '' or not file.filename.lower().endswith('.zip'):
        logging.error('No filename or invalid filename')
        abort(405)
    filename = os.path.join('/tmp/', secure_filename(file.filename))
    file.save(filename)

    if item == 'driver':
      result = drivers.install(filename)
      if result is not False:
        # Check and see if this is the driver we're using
        if result['driver'] == settings.getUser('display-driver'):
          # Yes it is, we need to activate it and return info about restarting
          special = drivers.activate(result['driver'])
          if special is None:
            settings.setUser('display-driver', 'none')
            settings.setUser('display-special', None)
            retval['status'] = 500
          else:
            settings.setUser('display-special', special)
            retval['return'] = {'reboot' : True}
        else:
          retval['return'] = {'reboot' : False}

    try:
      os.remove(filename)
    except:
      pass
    if retval['status'] == 200:
      return jsonify(retval['return'])
    abort(retval['status'])
  abort(405)

@app.route("/link/<service>")
@auth.login_required
def oauth_start(service):
  url = services.handleOAuthStart(service)
  if url is None:
    abort(500)
  else:
    return redirect(url)

@app.route("/callback", methods=["GET"])
@auth.login_required
def oauth_callback():
  # Figure out who should get this result...
  if services.handleOAuthCallback(request):
    # Request handled
    return redirect('/')
  else:
    abort(500)

@app.route("/complete", methods=['GET'])
@auth.login_required
def complete():
  slideshow.start(True)
  return redirect('/')

@app.route('/', defaults={'file':None})
@app.route('/<file>')
@auth.login_required
def web_main(file):
  if file is None:
    return app.send_static_file('index.html')
  else:
    return app.send_static_file(file)

@app.route('/template/<file>')
@auth.login_required
def web_template(file):
  return app.send_static_file('template/' + file)

settings = settings()
drivers = drivers()
display = display(cmdline.emulatefb)

if not settings.load():
  # First run, grab display settings from current mode
  current = display.current()
  if current is not None:
    logging.info('No display settings, using: %s' % repr(current))
    settings.setUser('tvservice', '%s %s HDMI' % (current['mode'], current['code']))
    settings.save()
  else:
    logging.info('No display attached?')
if settings.getUser('timezone') == '':
  settings.setUser('timezone', helper.timezoneCurrent())
  settings.save()

width, height, tvservice = display.setConfiguration(settings.getUser('tvservice'), settings.getUser('display-special'))
settings.setUser('tvservice', tvservice)
settings.setUser('width',  width)
settings.setUser('height', height)
settings.save()

# Force display to desired user setting
display.enable(True, True)

# Load services
services = ServiceManager(settings)

# Spin until we have internet, check every 10s
while True:
  settings.set('local-ip', helper.getIP())

  if settings.get('local-ip') is None:
    logging.error('You must have functional internet connection to use this app')
    display.message('No internet')
    time.sleep(10)
  else:
    break


# Once we have IP, show for 10s
cd = 10
while (cd > 0):
	display.message('Starting in %d seconds\n\nFrame configuration\n\nhttp://%s:7777' % (cd, settings.get('local-ip')))
	cd -= 1
	time.sleep(1)

# Prep random
random.seed(long(time.clock()))
colormatch = colormatch(settings.get('colortemp-script'), 2700) # 2700K = Soft white, lowest we'll go
slideshow = slideshow(display, settings, oauth, colormatch)
timekeeper = timekeeper(display.enable, slideshow.start)
slideshow.setQueryPower(timekeeper.getDisplayOn)

timekeeper.setConfiguration(settings.getUser('display-on'), settings.getUser('display-off'))
timekeeper.setAmbientSensitivity(settings.getUser('autooff-lux'), settings.getUser('autooff-time'))
timekeeper.setPowermode(settings.getUser('powersave'))
colormatch.setUpdateListener(timekeeper.sensorListener)

powermanagement = shutdown(settings.getUser('shutdown-pin'))

if __name__ == "__main__":
  # This allows us to use a plain HTTP callback
  os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
  app.secret_key = os.urandom(24)
  slideshow.start()
  app.run(debug=False, port=cmdline.port, host=cmdline.listen )

sys.exit(0)
