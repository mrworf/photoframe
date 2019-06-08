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
import re

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
from modules.sysconfig import sysconfig
from modules.cachemanager import CacheManager

parser = argparse.ArgumentParser(description="PhotoFrame - A RaspberryPi based digital photoframe", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--logfile', default=None, help="Log to file instead of stdout")
parser.add_argument('--port', default=7777, type=int, help="Port to listen on")
parser.add_argument('--listen', default="0.0.0.0", help="Address to listen on")
parser.add_argument('--debug', action='store_true', default=False, help='Enable loads more logging')
parser.add_argument('--basedir', default=None, help='Change the root folder of photoframe')
parser.add_argument('--emulate', action='store_true', help='Run as an app without root access or framebuffer')
parser.add_argument('--size', default='1280x720', help='Set the resolution to be used when emulating the framebuffer')
cmdline = parser.parse_args()

if cmdline.debug:
  logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
else:
  logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if cmdline.emulate:
  logging.info('Running in emulation mode, settings are stored in /tmp/photoframe/')
  if not os.path.exists('/tmp/photoframe'):
    os.mkdir('/tmp/photoframe')
  settings().reassignBase('/tmp/photoframe/')
  settings().reassignConfigTxt('extras/config.txt')

if cmdline.basedir is not None:
  newpath = cmdline.basedir + '/'
  logging.info('Altering basedir to %s', newpath)
  settings().reassign(newpath)

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

def debug_stacktrace():
    title = 'Stacktrace of all running threads'
    lines = []
    for threadId, stack in sys._current_frames().items():
        lines.append("\n# ThreadID: %s" % threadId)
        for filename, lineno, name, line in traceback.extract_stack(stack):
            lines.append('File: "%s", line %d, in %s' % (filename, lineno, name))
            if line:
                lines.append("  %s" % (line.strip()))
    return (title, lines, None)

def debug_logfile(all=False):
    stats = os.stat('/var/log/syslog')
    cmd = 'grep -a "photoframe\[" /var/log/syslog | tail -n 100'
    title = 'Last 100 lines from the photoframe log'
    if all:
      title = 'Last 100 lines from the system log (/var/log/syslog)'
      cmd = 'tail -n 100 /var/log/syslog'
    lines = subprocess.check_output(cmd, shell=True)
    if lines:
      lines = lines.splitlines()
    suffix = '(size of logfile %d bytes, created %s)' % (stats.st_size, datetime.datetime.fromtimestamp(stats.st_ctime).strftime('%c'))
    return (title, lines, suffix)

@app.route('/debug', methods=['GET'])
def show_logs():
  # Special URL, we simply try to extract latest 100 lines from syslog
  # and filter out frame messages. These are shown so the user can
  # add these to issues.
  report = []
  report.append(debug_logfile(False))
  report.append(debug_logfile(True))
  report.append(debug_stacktrace())

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
      CacheManager.empty(settings.get("cachefolder"))
    if key in ['display-on', 'display-off']:
      timekeeper.setConfiguration(settings.getUser('display-on'), settings.getUser('display-off'))
    if key in ['autooff-lux', 'autooff-time']:
      timekeeper.setAmbientSensitivity(settings.getUser('autooff-lux'), settings.getUser('autooff-time'))
    if key in ['powersave']:
      timekeeper.setPowermode(settings.getUser('powersave'))
    if key in ['shutdown-pin']:
      powermanagement.stopmonitor()
      powermanagement = shutdown(settings.getUser('shutdown-pin'))
    if key in ['imagesizing', 'randomize_images']:
      slideshow.createEvent("settingsChange")
    settings.save()
    return jsonify({'status':status})

  elif request.method == 'GET':
    if key is None:
      return jsonify(settings.getUser())
    else:
      return jsonify({key : settings.getUser(key)})
  abort(404)

@app.route('/keywords/<service>/help', methods=['GET'])
@auth.login_required
def cfg_keywords_help(service):
  return jsonify({'message' : services.helpServiceKeywords(service)})

@app.route('/keywords/<service>', methods=['GET'])
@app.route('/keywords/<service>/add', methods=['POST'])
@app.route('/keywords/<service>/delete', methods=['POST'])
@app.route('/keywords/<service>/source/<int:index>', methods=['GET'])
@auth.login_required
def cfg_keywords(service, index=None):
  if request.method == 'GET':
    if 'source' in request.url:
      return redirect(services.sourceServiceKeywords(service, index))
    else:
      return jsonify({'keywords' : services.getServiceKeywords(service)})
  elif request.method == 'POST' and request.json is not None:
    result = True
    if 'id' not in request.json:
      hadKeywords = services.hasKeywords()
      result = services.addServiceKeywords(service, request.json['keywords'])
      if result['error'] is not None:
        result['status'] = False
      else:
        result['status'] = True
        if hadKeywords != services.hasKeywords():
          # Make slideshow show the change immediately, we have keywords
          slideshow.trigger()
    else:
      if not services.removeServiceKeywords(service, request.json['id']):
        result = {'status':False, 'error' : 'Unable to remove keyword'}
      else:
        # Trigger slideshow, we have removed some keywords
        slideshow.trigger()
    return jsonify(result)
  abort(500)

@app.route('/rotation', methods=['GET'], defaults={'orient':None})
@app.route('/rotation/<int:orient>', methods=['PUT'])
@auth.login_required
def cfg_rotation(orient):
  if orient is None:
    return jsonify({'rotation' : sysconfig.getDisplayOrientation()})
  else:
    if orient >= 0 and orient < 360:
      sysconfig.setDisplayOrientation(orient)
      CacheManager.empty(settings.get("cachefolder"))
      return jsonify({'rotation' : sysconfig.getDisplayOrientation()})
  abort(500)

@app.route('/maintenance/<cmd>')
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
  elif cmd == 'clearCache':
    slideshow.createEvent("clearCache")
    return jsonify({'clearCache': True})
  elif cmd == 'forgetMemory':
    slideshow.createEvent("memoryForget")
    return jsonify({'forgetMemory': True})


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
    infoDate = lines[2][5:].strip()
    infoCommit = lines[0][7:].strip()
    output = subprocess.check_output(['git', 'status'], stderr=void)
    lines = output.split('\n')
    infoBranch = lines[0][10:].strip()
    return jsonify({'date':infoDate, 'commit':infoCommit, 'branch': infoBranch})
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

@app.route("/callback", methods=["GET"])
@auth.login_required
def oauth_callback():
  # Figure out who should get this result...
  old = services.hasReadyServices()
  if services.oauthCallback(request):
    # Request handled
    if old != services.hasReadyServices():
      slideshow.trigger()
    return redirect('/')
  else:
    abort(500)

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

@app.route('/service/<service>/oauth', methods=['POST'])
@auth.login_required
def services_oauth(service):
  j = request.json
  # This one is special, this is a file upload of the JSON config data
  # and since we don't need a physical file for it, we should just load
  # the data. For now... ignore
  if 'filename' not in request.files:
    logging.error('No file part')
    abort(405)
  file = request.files['filename']
  data = json.load(file)
  if 'web' in data:
    data = data['web']
  if 'redirect_uris' in data and 'https://photoframe.sensenet.nu' not in data['redirect_uris']:
    return 'The redirect uri is not set to https://photoframe.sensenet.nu', 405
  if not services.oauthConfig(service, data):
    return 'Configuration was invalid', 405
  return 'Configuration set', 200

@app.route('/service/<service>/link', methods=['GET'])
@auth.login_required
def service_link(service):
  return redirect(services.oauthStart(service))

@app.route('/service/<action>',  methods=['GET', 'POST'])
@auth.login_required
def services_operations(action):
  j = request.json
  if action == 'available':
    return jsonify(services.listServices())
  if action == 'list':
    return jsonify(services.getServices())
  if action == 'add' and j is not None:
    if 'name' in j and 'id' in j:
      old = services.hasReadyServices()
      svcid = services.addService(int(j['id']), j['name'])
      if old != services.hasReadyServices():
        slideshow.trigger()
      return jsonify({'id':svcid})
  if action == 'remove' and j is not None:
    if 'id' in j:
      services.deleteService(j['id'])
      slideshow.trigger() # Always trigger since we don't know who was on-screen
      return jsonify({'status':'Done'})
  if action == 'rename' and j is not None:
    if 'name' in j and 'id' in j:
      if services.renameService(j['id'], j['name']):
        return jsonify({'status':'Done'})
  if request.url.endswith('/config/fields'):
    return jsonify(services.getServiceConfigurationFields(id))
  if request.url.endswith('/config'):
    if request.method == 'POST' and j is not None and 'config' in j:
      if services.setServiceConfiguration(id, j['config']):
        return 'Configuration saved', 200
    elif request.method == 'GET':
      return jsonify(services.getServiceConfiguration(id))

  abort(500)

@app.route('/control/<cmd>')
@auth.login_required
def control_slideshow(cmd):
  slideshow.createEvent(cmd)
  return jsonify({'control': True})


settings = settings()
drivers = drivers()

m = re.search('([0-9]+)x([0-9]+)', cmdline.size)
if m is None:
    logging.error('--size has to be WIDTHxHEIGHT')
    sys.exit(1)

display = display(cmdline.emulate, int(m.group(1)), int(m.group(2)))

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
    display.message('No internet\n\nCheck wifi-config.txt or cable')
    time.sleep(10)
  else:
    break

# Let the display know the URL to use
display.setConfigPage('http://%s:%d/' % (settings.get('local-ip'), 7777))

# Prep random
random.seed(long(time.clock()))
colormatch = colormatch(settings.get('colortemp-script'), 2700) # 2700K = Soft white, lowest we'll go
slideshow = slideshow(display, settings, colormatch)
timekeeper = timekeeper(display.enable, slideshow.start)
slideshow.setQueryPower(timekeeper.getDisplayOn)
slideshow.setServiceManager(services)

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
