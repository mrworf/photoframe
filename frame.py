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
from modules.colormatch import colormatch
from modules.settings import settings
from modules.helper import helper
from modules.display import display

# From https://stackoverflow.com/questions/11269575/how-to-hide-output-of-subprocess-in-python-2-7
try:
    from subprocess import DEVNULL
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')
###

import requests
from requests_oauthlib import OAuth2Session
from flask import Flask, request, redirect, session, url_for, abort
from flask.json import jsonify

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('oauthlib').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

app = Flask(__name__, static_url_path='')

oauth = None
rid = None

def pick_image(images, memory):
	ext = ['jpg','png','dng','jpeg','gif','bmp']
	count = len(images['feed']['entry'])
	tries = 5

	while tries > 0:
		i = random.SystemRandom().randint(0,count-1)
		if not memory.seen(i):
			memory.saw(i)
			entry = images['feed']['entry'][i]
			# Make sure we don't get a video, unsupported for now (gif is usually bad too)
			if 'image' in entry['content']['type'] and not 'gif' in entry['content']['type']:
				break
			else:
				logging.warning('Unsupported media: %s' % entry['content']['type'])
		else:
			logging.debug('Already seen index %d' % i)
		tries -= 1

	if tries == 0:
		logging.error('Failed to find any image, abort')
		return ('', '', '', 0)

	title = entry['title']['$t']
	parts = title.lower().split('.')
	if len(parts) > 0 and parts[len(parts)-1] in ext:
		# Title isn't title, it's a filename
		title = ""
	uri = entry['content']['src']
	timestamp = datetime.datetime.fromtimestamp((float)(entry['gphoto$timestamp']['$t']) / 1000)
	mime = entry['content']['type']

	# Due to google's unwillingness to return what I own, we need to hack the URI
	uri = uri.replace('/s1600/', '/s%s/' % settings.getUser('width'), 1)

	return (uri, mime, title, timestamp)

def getAuth(refresh=False):
	if not refresh:
		auth = OAuth2Session(oauth['client_id'], token=settings.get('oauth_token'))
	else:
		def token_updater(token):
			settings.set('oauth_token', token)
			saveSettings()

		auth = OAuth2Session(oauth['client_id'],
	                         token=settings.get('oauth_token'),
	                         auto_refresh_kwargs={'client_id':oauth['client_id'],'client_secret':oauth['client_secret']},
	                         auto_refresh_url=oauth['token_uri'],
	                         token_updater=token_updater)
	return auth

def performGet(uri, stream=False, params=None):
	try:
		auth = getAuth()
		return auth.get(uri, stream=stream, params=params)
	except:
		auth = getAuth(True)
		return auth.get(uri, stream=stream, params=params)

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
			enable_display(True, True)
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
		result = oauth != None

	return jsonify({'result' : result})

@app.route('/oauth', methods=['POST'])
def cfg_oauth_info():
	global oauth

	if request.json is None or 'web' not in request.json:
		abort(500)
	oauth = request.json['web']
	with open('/root/oauth.json', 'wb') as f:
		json.dump(oauth, f);
	return jsonify({'result' : True})

@app.route('/reset')
def cfg_reset():
	settings.userDefaults();
	settings.set('oauth_token', None)
	settings.set('oauth_state', None)
	saveSettings()
	return jsonify({'reset': True})

@app.route('/reboot')
def cfg_reboot():
	subprocess.call(['/sbin/reboot'], stderr=DEVNULL);
	return jsonify({'reboot' : True})

@app.route('/shutdown')
def cfg_shutdown():
	subprocess.call(['/sbin/poweroff'], stderr=DEVNULL);
	return jsonify({'shutdown': True})

@app.route('/')
def web_main():
	return app.send_static_file('index.html')

@app.route("/link")
def oauth_step1():
	""" Step 1: Get authorization
	"""
	global rid
	r = requests.get('https://photoframe.sensenet.nu/?register')
	rid = r.content
	auth = OAuth2Session(oauth['client_id'],
						scope=['https://picasaweb.google.com/data/'],
						redirect_uri='https://photoframe.sensenet.nu',
						state='%s-%s' % (rid, settings.get('local-ip')))
	authorization_url, state = auth.authorization_url(oauth['auth_uri'],
	 													access_type="offline",
														prompt="consent")

	# State is used to prevent CSRF, keep this for later.
	settings.set('oauth_state', state)
	return redirect(authorization_url)

# Step 2: Google stuff, essentially user consents to allowing us access

@app.route("/callback", methods=["GET"])
def oauth_step3():
	""" Step 3: Get the token
	"""
	auth = OAuth2Session(oauth['client_id'], scope=['https://picasaweb.google.com/data/'], redirect_uri='https://photoframe.sensenet.nu', state='%s-%s' % (rid, settings.get('local-ip')))
	token = auth.fetch_token(oauth['token_uri'], client_secret=oauth['client_secret'], authorization_response=request.url)

	settings.set('oauth_token', token)
	settings.save()
	return redirect(url_for('.complete'))

@app.route("/complete", methods=['GET'])
def complete():
	slideshow(True)
	return redirect('/')

def get_images():
	keyword = settings.getKeyword()

	# Create filename from keyword
	filename = hashlib.new('md5')
	filename.update(keyword)
	filename = filename.hexdigest() + ".json"
	filename = os.path.join(settings.get('tempfolder'), filename)

	if os.path.exists(filename): # Check age!
		age = math.floor( (time.time() - os.path.getctime(filename)) / 3600)
		if age >= settings.getUser('refresh-content'):
			logging.debug('File too old, %dh > %dh, refreshing' % (age, settings.getUser('refresh-content')))
			os.remove(filename)
			# Make sure we don't remember since we're refreshing
			memory = remember(filename, 0)
			memory.forget()

	if not os.path.exists(filename):
		# Request albums
		# Picasa limits all results to the first 1000, so get them
		params = {
			'kind' : 'photo',
			'start-index' : 1,
			'max-results' : 1000,
			'alt' : 'json',
			'access' : 'all',
			'imgmax' : '1600u', # We will replace this with width of framebuffer in pick_image
			# This is where we get cute, we pick from a list of keywords
			'fields' : 'entry(title,content,gphoto:timestamp)' # No unnecessary stuff
		}
		if keyword != "":
			params['q'] = keyword
		url = 'https://picasaweb.google.com/data/feed/api/user/default'
		logging.debug('Downloading image list for %s...' % keyword)
		data = performGet(url, params=params)
		with open(filename, 'w') as f:
			f.write(data.content)
	images = None
	with open(filename) as f:
		images = json.load(f)
	logging.debug('Loaded %d images into list' % len(images['feed']['entry']))
	return images, filename

def download_image(uri, dest):
	logging.debug('Downloading %s...' % uri)
	filename, ext = os.path.splitext(dest)
	response = performGet(uri, stream=True)
	with open("%s-org%s" % (filename, ext), 'wb') as handle:
		for chunk in response.iter_content(chunk_size=512):
			if chunk:  # filter out keep-alive new chunks
				handle.write(chunk)
	if settings.get('colortemp') is not None:
		temp = settings.get('colortemp')
		if temp < 3500:
			logging.debug('Actual color temp measured is %d, but we cap to 3500K', temp)
			temp = 3500
		logging.debug('Adjusting color temperature to %dK' % temp)
		subprocess.check_output([settings.get('colortemp-script'), '-t', "%d" % temp, "%s-org%s" % (filename, ext), dest], stderr=DEVNULL)
	else:
		logging.info('No color temperature info yet')
		os.rename("%s-org%s" % (filename, ext), dest)
	return True

slideshow_thread = None

def slideshow(blank=False):
	global slideshow_thread

	if blank:
		display.clear()

	def imageloop():
		global slideshow_thread
		time.sleep(1) # Ugly, but works... allows server to get going

		# Make sure we have OAuth2.0 ready
		while True:
			if settings.get('oauth_token') is None:
				show_message('Please link photoalbum\n\nSurf to http://%s:7777/' % settings.get('local-ip'))
				logging.info('You need to link your photoalbum first')
				break

			imgs = cache = memory = None
			tries = 50
			while tries > 0:
				imgs, cache = get_images()
				if not imgs:
					tries -= 1
					continue

				memory = remember(cache, len(imgs['feed']['entry']))
				if memory.seenAll():
					logging.debug('Seen all images, try again')
					tries -= 1
					continue

				# Now, lets make sure we didn't see this before
				uri, mime, title, ts = pick_image(imgs, memory)
				if uri == '':
					tries -= 1
					continue

				filename = os.path.join(settings.get('tempfolder'), 'image.%s' % helper.getExtension(mime))
				if download_image(uri, filename):
					display.image(filename)
					break
				else:
					tries -= 1

			if tries == 0:
				show_message("Unable to download ANY images\nCheck that you have photos\nand queries aren't too strict")
			time.sleep(settings.getUser('interval'))
			if int(time.strftime('%H')) >= settings.getUser('display-off'):
				logging.debug("It's after hours, exit quietly")
				break
		slideshow_thread = None

	if slideshow_thread is None and oauth is not None:
		slideshow_thread = threading.Thread(target=imageloop)
		slideshow_thread.daemon = True
		slideshow_thread.start()

settings = settings()
settings.load()	

display = display(settings.getUser('width'), settings.getUser('height'), settings.getUser('depth'), settings.getUser('tvservice'))

# Force display to desired user setting
display.enable(True, True)

# Spin until we have internet, check every 10s
while True:
	settings.set('local-ip', helper.getIP())
	settings.set('colortemp', None)

	if settings.get('local-ip') is None:
		logging.error('You must have functional internet connection to use this app')
		display.message('No internet')
		time.sleep(10)
	else:
		break

if os.path.exists('/root/oauth.json'):
	with open('/root/oauth.json') as f:
		oauth = json.load(f)
	if 'web' in oauth: # if someone added it via command-line
		oauth = oauth['web']
else:
	display.message('You need to provide OAuth details\nSee README.md')

# Prep random
random.seed(long(time.clock()))

color_thread = colormatch(settings.get('colortemp-script'))
time_thread = timekeeper(settings.getUser('display-on'), settings.getUser('display-off'), display.enable, slideshow)
power_thread = shutdown()

if __name__ == "__main__":
	# This allows us to use a plain HTTP callback
	os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
	app.secret_key = os.urandom(24)
	slideshow()
	app.run(debug=False, port=7777, host='0.0.0.0' )

sys.exit(0)
