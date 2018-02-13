#!/usr/bin/env python

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

from modules.remember import remember
from modules.shutdown import shutdown
from modules.timekeeper import timekeeper
from modules.settings import settings
from modules.helper import helper
from modules.display import display
from modules.oauth import OAuth
from modules.slideshow import slideshow

void = open(os.devnull, 'wb')

import requests
from requests_oauthlib import OAuth2Session
from flask import Flask, request, redirect, session, url_for, abort
from flask.json import jsonify

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('oauthlib').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

app = Flask(__name__, static_url_path='')

@app.route('/setting', methods=['GET'], defaults={'key':None,'value':None})
@app.route('/setting/<key>', methods=['GET'], defaults={'value':None})
@app.route('/setting/<key>/<value>', methods=['PUT'])
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
			
	elif request.method == 'GET':
		if key is None:
			return jsonify(settings.getUser())
		else:
			return jsonify({key : settings.getUser(key)})
	return

@app.route('/keywords', methods=['GET'])
@app.route('/keywords/add', methods=['POST'])
@app.route('/keywords/delete', methods=['POST'])
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
def cfg_hasthis():
	result = False
	if '/token' in request.path:
		if settings.get('oauth_token') is not None:
			result = True
	elif '/oauth' in request.path:
		result = oauth.hasOAuth()

	return jsonify({'result' : result})

@app.route('/oauth', methods=['POST'])
def cfg_oauth_info():
	if request.json is None or 'web' not in request.json:
		abort(500)
	data = request.json['web']
	oauth.setOAuth(data)
	with open('/root/oauth.json', 'wb') as f:
		json.dump(data, f);
	return jsonify({'result' : True})

@app.route('/reset')
def cfg_reset():
	settings.userDefaults();
	settings.set('oauth_token', None)
	saveSettings()
	return jsonify({'reset': True})

@app.route('/reboot')
def cfg_reboot():
	subprocess.call(['/sbin/reboot'], stderr=void);
	return jsonify({'reboot' : True})

@app.route('/shutdown')
def cfg_shutdown():
	subprocess.call(['/sbin/poweroff'], stderr=void);
	return jsonify({'shutdown': True})

@app.route('/details/<about>')
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
	abort(404)

@app.route('/')
def web_main():
	return app.send_static_file('index.html')

@app.route("/link")
def oauth_step1():
	return redirect(oauth.initiate())

@app.route("/callback", methods=["GET"])
def oauth_step3():
	oauth.complete(request.url)
	return redirect(url_for('.complete'))

@app.route("/complete", methods=['GET'])
def complete():
	slideshow.start(True)
	return redirect('/')

settings = settings()
settings.load()	

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
else:
	display.message('You need to provide OAuth details\nSee README.md')

# Prep random
random.seed(long(time.clock()))
slideshow = slideshow(display, settings, oauth)
timekeeper = timekeeper(display.enable, slideshow.start)
timekeeper.setConfiguration(settings.getUser('display-on'), settings.getUser('display-off'))
powermanagement = shutdown()

if __name__ == "__main__":
	# This allows us to use a plain HTTP callback
	os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
	app.secret_key = os.urandom(24)
	slideshow.start()
	app.run(debug=False, port=7777, host='0.0.0.0' )

sys.exit(0)
