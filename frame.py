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

from modules.remember import remember
from modules.shutdown import shutdown
from modules.timekeeper import timekeeper
from modules.settings import settings
from modules.helper import helper
from modules.display import display
from modules.oauth import OAuth
from modules.slideshow import slideshow
from modules.colormatch import colormatch

void = open(os.devnull, 'wb')

import requests
from requests_oauthlib import OAuth2Session
from flask import Flask, request, redirect, session, url_for, abort
from flask.json import jsonify
from flask_httpauth import HTTPBasicAuth

# used if we don't find authentication json
class NoAuth:
	def __init__(self):
		pass

	def login_required(self, fn):
		def wrap(*args, **kwargs):
			return fn(*args, **kwargs)
		wrap.func_name = fn.func_name
		return wrap

parser = argparse.ArgumentParser(description="PhotoFrame - A RPi3 based digital photoframe", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--logfile', default=None, help="Log to file instead of stdout")
parser.add_argument('--port', default=7777, type=int, help="Port to listen on")
parser.add_argument('--listen', default="0.0.0.0", help="Address to listen on")
parser.add_argument('--debug', action='store_true', default=False, help='Enable loads more logging')
cmdline = parser.parse_args()

if cmdline.debug:
	logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
else:
	logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('oauthlib').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

app = Flask(__name__, static_url_path='')
user = None
userfiles = ['/boot/http-auth.json', '/root/http-auth.json']

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

@app.route('/setting', methods=['GET'], defaults={'key':None,'value':None})
@app.route('/setting/<key>', methods=['GET'], defaults={'value':None})
@app.route('/setting/<key>/<value>', methods=['PUT'])
@auth.login_required
def cfg_keyvalue(key, value):
	# Depending on PUT/GET we will either change or read
	# values. If key is unknown, then this call fails with 404
	if key is not None:
		if settings.getUser(key) is None:
			abort(404)
			return

	if request.method == 'PUT':
		if key == "keywords":
			# Keywords has its own API
			abort(404)
			return
		settings.setUser(key, value)
		settings.save()
		if key in ['width', 'height', 'depth', 'tvservice']:
			display.setConfiguration(settings.getUser('width'), settings.getUser('height'), settings.getUser('depth'), settings.getUser('tvservice'))
			display.enable(True, True)
		if key in ['display-on', 'display-off']:
			timekeeper.setConfiguration(settings.getUser('display-on'), settings.getUser('display-off'))
		if key in ['autooff-lux', 'autooff-time']:
			timekeeper.setAmbientSensitivity(settings.getUser('autooff-lux'), settings.getUser('autooff-time'))
		if key in ['powersave']:
			timekeeper.setPowermode(settings.getUser('powersave'))
		return jsonify({'status':True})

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

@app.route('/has/token')
@app.route('/has/oauth')
@auth.login_required
def cfg_hasthis():
	result = False
	if '/token' in request.path:
		if settings.get('oauth_token') is not None:
			result = True
	elif '/oauth' in request.path:
		result = oauth.hasOAuth()

	return jsonify({'result' : result})

@app.route('/oauth', methods=['POST'])
@auth.login_required
def cfg_oauth_info():
	if request.json is None or 'web' not in request.json:
		abort(500)
	data = request.json['web']
	oauth.setOAuth(data)
	with open('/root/oauth.json', 'wb') as f:
		json.dump(data, f);
	return jsonify({'result' : True})

@app.route('/reset')
@auth.login_required
def cfg_reset():
	settings.userDefaults();
	settings.set('oauth_token', None)
	saveSettings()
	return jsonify({'reset': True})

@app.route('/reboot')
@auth.login_required
def cfg_reboot():
	subprocess.call(['/sbin/reboot'], stderr=void);
	return jsonify({'reboot' : True})

@app.route('/shutdown')
@auth.login_required
def cfg_shutdown():
	subprocess.call(['/sbin/poweroff'], stderr=void);
	return jsonify({'shutdown': True})

@app.route('/details/<about>')
@auth.login_required
def cfg_details(about):
	if about == 'tvservice':
		result = {}
		result['cea'] = subprocess.check_output(['/opt/vc/bin/tvservice', '-m', 'cea'])
		result['dmt'] = subprocess.check_output(['/opt/vc/bin/tvservice', '-m', 'dmt'])
		result['status'] = subprocess.check_output(['/opt/vc/bin/tvservice', '-status'])
		return jsonify(result)
	elif about == 'current':
		image, mime = display.get()
		response = app.make_response(image)
		response.headers.set('Content-Type', mime)
		return response
	elif about == 'version':
		output = subprocess.check_output(['git', 'log', '-n1'], stderr=void)
		lines = output.split('\n')
		return jsonify({'date':lines[2][5:].strip(),'commit':lines[0][7:].strip()})
	elif about == 'color':
		return jsonify(slideshow.getColorInformation())
	elif about == 'display':
		return jsonify({'display':display.isEnabled()})

	abort(404)

@app.route("/link")
@auth.login_required
def oauth_step1():
	return redirect(oauth.initiate())

@app.route("/callback", methods=["GET"])
@auth.login_required
def oauth_step3():
	oauth.complete(request.url)
	return redirect(url_for('.complete'))

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
if not settings.load():
	# First run, grab display settings from current mode
	current = display.current()
	logging.info('No display settings, using: %s' % repr(current))
	settings.setUser('tvservice', '%s %s %s' % (current['group'], current['mode'], current['drive']))
	settings.setUser('width', int(current['width']))
	settings.setUser('height', int(current['height']))
	settings.save()

display = display(settings.getUser('width'), settings.getUser('height'), settings.getUser('depth'), settings.getUser('tvservice'))

# Force display to desired user setting
display.enable(True, True)

# Spin until we have internet, check every 10s
while True:
	settings.set('local-ip', helper.getIP())

	if settings.get('local-ip') is None:
		logging.error('You must have functional internet connection to use this app')
		display.message('No internet')
		time.sleep(10)
	else:
		break

def oauthGetToken():
	return settings.get('oauth_token')

def oauthSetToken(token):
	settings.set('oauth_token', token)
	settings.save()

oauth = OAuth(settings.get('local-ip'), oauthSetToken, oauthGetToken)

if os.path.exists('/root/oauth.json'):
	with open('/root/oauth.json') as f:
		data = json.load(f)
	if 'web' in data: # if someone added it via command-line
		data = data['web']
	oauth.setOAuth(data)

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

powermanagement = shutdown()

if __name__ == "__main__":
	# This allows us to use a plain HTTP callback
	os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
	app.secret_key = os.urandom(24)
	slideshow.start()
	app.run(debug=False, port=cmdline.port, host=cmdline.listen )

sys.exit(0)
