#!/usr/bin/env python

import json
import sys
import os
import random
import hashlib
import datetime
import threading
import time
import math
import subprocess
import logging
import socket

import requests
from requests_oauthlib import OAuth2Session
from flask import Flask, request, redirect, session, url_for, abort
from flask.json import jsonify

app = Flask(__name__, static_url_path='')

with open('oauth.json') as f:
	oauth = json.load(f)

oauth = oauth['web']

rid = None

settings = {
	'oauth_token' : None,
	'oauth_state' : None,
	'local-ip' : None,
	'resolution' : None,
	'width' : None,
	'cfg' : None
}


def set_defaults():
	settings['cfg'] = {
		'interval' : 60,					# Delay in seconds between images (minimum)
		'display-off' : 22,				# What hour (24h) to disable display and sleep
		'display-on' : 4,					# What hour (24h) to enable display and continue
		'refresh-content' : 24,		# After how many hours we should force reload of image lists from server
		'keywords' : [						# Keywords for search (blank = latest 1000 images)
			""
#			'"jessica huckabay"',
#			'"henric huckabay"',
#			'+"henric huckabay" +"jessica huckabay"',
#			'cats',
#			'thanksgiving',
#			'christmas',
#			'sweden',
#			'people',
#			'nature',
#			'"redwood city"',
#			''
		]
	}

def get_resolution():
	res = None
	output = subprocess.check_output(['/bin/fbset'])
	for line in output.split('\n'):
		line = line.strip()
		if line.startswith('mode "'):
			res = line[6:-1]
			break
	return res

def get_my_ip():
	ip = None
	try:
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(("photoframe.sensenet.nu", 80))
		ip = s.getsockname()[0]
		s.close()
	except:
		pass
	return ip

def pick_image(images):
	ext = ['jpg','png','dng','jpeg','gif','bmp']
	count = len(images['feed']['entry'])
	tries = 5

	while tries > 0:
		entry = images['feed']['entry'][random.randint(0,count-1)]
		# Make sure we don't get a video, unsupported for now
		if 'image' in entry['content']['type']:
			print('Mime is: ', entry['content']['type'])
			break
		else:
			tries -= 1
			print('Warning, unsupported media: %s' % entry['content']['type'])

	if tries == 0:
		print('Failed to find any image, abort')
		return ('', '', 0)

	title = entry['title']['$t']
	parts = title.lower().split('.')
	if len(parts) > 0 and parts[len(parts)-1] in ext:
		# Title isn't title, it's a filename
		title = ""
	uri = entry['content']['src']
	timestamp = datetime.datetime.fromtimestamp((float)(entry['gphoto$timestamp']['$t']) / 1000)
	mime = entry['content']['type']

	# Due to google's unwillingness to return what I own, we need to hack the URI
	uri = uri.replace('/s1600/', '/s%s/' % settings['width'], 1)

	return (uri, mime, title, timestamp)

def get_extension(mime):
	mapping = {
		'image/jpeg' : 'jpg',
		'image/png' : 'png',
		'image/gif' : 'gif',
	}
	mime = mime.lower()
	if mime in mapping:
		return mapping[mime]
	print 'Mime %s unsupported' % mime
	return 'xxx'

def saveSettings():
	with open('settings.json', 'w') as f:
		json.dump(settings, f)

def getAuth(refresh=False):
	if not refresh:
		auth = OAuth2Session(oauth['client_id'], token=settings['oauth_token'])
	else:
		print('Token have expired, try refresh')
		def token_updater(token):
			settings['oauth_token'] = token
			print('I haz new token')
			saveSettings()

		auth = OAuth2Session(oauth['client_id'],
	                         token=settings['oauth_token'],
	                         auto_refresh_kwargs={'client_id':oauth['client_id'],'client_secret':oauth['client_secret']},
	                         auto_refresh_url=oauth['token_uri'],
	                         token_updater=token_updater)
		print('New token!')
	return auth

def performGet(uri, stream=False, params=None):
	try:
		auth = getAuth()
		return auth.get(uri, stream=stream, params=params)
	except:
		logging.exception('Ran into issues')
		auth = getAuth(True)
		return auth.get(uri, stream=stream, params=params)

@app.route('/setting', methods=['GET'], defaults={'key':None,'value':None})
@app.route('/setting/<key>', methods=['GET'], defaults={'value':None})
@app.route('/setting/<key>/<value>', methods=['PUT'])
def cfg_keyvalue(key, value):
	# Depending on PUT/GET we will either change or read
	# values. If key is unknown, then this call fails with 404
	if key is not None:
		if key not in settings['cfg']:
			abort(404)
			return

	if request.method == 'PUT':
		if key == "keywords":
			# Keywords has its own API
			abort(404)
			return
		settings['cfg'][key] = value
		saveSettings()
	elif request.method == 'GET':
		if key is None:
			return jsonify(settings['cfg'])
		else:
			return jsonify({key : settings['cfg'][key]})
	return

@app.route('/keywords', methods=['GET'])
@app.route('/keywords/add', methods=['POST'])
@app.route('/keywords/delete', methods=['POST'])
def cfg_keywords():
	if request.method == 'GET':
		return jsonify(settings['cfg']['keywords'])
	elif request.method == 'POST' and request.json is not None:
		if id == -1: # It's a new keyword
			keywords = request.json['keywords'].strip()
			if keywords not in settings['cfg']['keywords']:
				settings['cfg']['keywords'].append(keywords)
				saveSettings()
		else:
			id = request.json('id')
			if id > -1 and id < len(settings['cfg']['keywords']):
				settings['cfg']['keywords'].pop(id)
				saveSettings()
		return jsonify({'status':True})
	abort(500)

@app.route('/islinked')
def cfg_islinked():
	if settings['oauth_token'] is None:
		return jsonify({'linked' : False})
	return jsonify({'linked' : True})

@app.route('/reset')
def cfg_reset():
	set_defaults();
	settings['oauth_token'] = None
	settings['oauth_state'] = None
	saveSettings()
	return jsonify({'reset': True})


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
						state='%s-%s' % (rid, settings['local-ip']))
	authorization_url, state = auth.authorization_url(oauth['auth_uri'],
	 													access_type="offline",
														prompt="consent")

	# State is used to prevent CSRF, keep this for later.
	settings['oauth_state'] = state
	return redirect(authorization_url)

# Step 2: Google stuff, essentially user consents to allowing us access

@app.route("/callback", methods=["GET"])
def oauth_step3():
	""" Step 3: Get the token
	"""
	auth = OAuth2Session(oauth['client_id'], scope=['https://picasaweb.google.com/data/'], redirect_uri='https://photoframe.sensenet.nu', state='%s-%s' % (rid, settings['local-ip']))
	token = auth.fetch_token(oauth['token_uri'], client_secret=oauth['client_secret'], authorization_response=request.url)

	settings['oauth_token'] = token
	saveSettings()
	return redirect(url_for('.complete'))

@app.route("/complete", methods=['GET'])
def complete():
	slideshow(True)
	return redirect('/')

def get_images():
	random.seed()
	keyword = settings['cfg']['keywords'][random.randint(0, len(settings['cfg']['keywords'])-1)]

	# Create filename from keyword
	filename = hashlib.new('md5')
	filename.update(keyword)
	filename = filename.hexdigest() + ".json"

	if os.path.exists(filename): # Check age!
		age = math.floor( (time.time() - os.path.getctime(filename)) / 3600)
		if age >= settings['cfg']['refresh-content']:
			print('File too old, %dh > %dh' % (age, settings['cfg']['refresh-content']))
			os.remove(filename)

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
		'q' : keyword,
		'fields' : 'entry(title,content,gphoto:timestamp)' # No unnecessary stuff
		}
		url = 'https://picasaweb.google.com/data/feed/api/user/default'
		print('Downloading image list for %s...' % keyword)
		data = performGet(url, params=params)
		with open(filename, 'w') as f:
			f.write(data.content)
		print('Done')
	images = None
	with open(filename) as f:
		images = json.load(f)
	return images

def download_image(uri, dest):
	print 'Downloadiing %s...' % uri
	response = performGet(uri, stream=True)
	with open(dest, 'wb') as handle:
		for chunk in response.iter_content(chunk_size=512):
			if chunk:  # filter out keep-alive new chunks
				handle.write(chunk)
	print 'Done'
	return True

def show_message(message):
	"""convert -size 2400x1200 xc:White ^
	  -gravity Center ^
	  -weight 700 -pointsize 200 ^
	  -annotate 0 "OIL\nFOUND\nIN CENTRAL PARK" ^
	  oil.png
	"""
	args = [
		'convert',
		'-size',
		settings['resolution'],
		'-background',
		'black',
		'-fill',
		'white',
		'-gravity',
		'center',
		'-weight',
		'700',
		'-pointsize',
		'64',
		'label:%s' % message,
		'-depth',
		'8',
		'bgra:-'
	]
	with open('/dev/fb0', 'wb') as f:
		ret = subprocess.call(args, stdout=f)


def show_image(filename):
	args = [
		'convert',
		filename,
		'-resize',
		settings['resolution'],
		'-background',
		'black',
		'-gravity',
		'center',
		'-extent',
		settings['resolution'],
		'-depth',
		'8',
		'bgra:-'
	]
	with open('/dev/fb0', 'wb') as f:
		ret = subprocess.call(args, stdout=f)

display_enabled = True

def enable_display(enable):
	global display_enabled

	if enable == display_enabled:
		return

	if enable:
		subprocess.call(['/opt/vc/bin/tvservice', '-p'])
		subprocess.call(['/bin/fbset', '-depth', '8'])
		subprocess.call(['/bin/fbset', '-depth', '32'])
	else:
		subprocess.call(['/opt/vc/bin/tvservice', '-o'])
	display_enabled = enable

def is_display_enabled():
	return display_enabled

slideshow_thread = None

def slideshow(blank=False):
	global slideshow_thread

	if blank:
		# lazy
		with open('/dev/fb0', 'wb') as f:
			subprocess.call(['cat' , '/dev/zero'], stdout=f)

	def imageloop():
		global slideshow_thread
		time.sleep(1) # Ugly, but works... allows server to get going

		# Make sure we have OAuth2.0 ready
		while True:
			if settings['oauth_token'] is None:
				show_message('Please link photoalbum\n\nSurf to http://%s:7777/' % settings['local-ip'])
				print('You need to link your photoalbum first')
				break
			imgs = get_images()
			if imgs:
				uri, mime, title, ts = pick_image(imgs)
				filename = '/tmp/image.%s' % get_extension(mime)
				if download_image(uri, filename):
					show_image(filename)
			else:
				print('Need configuration')
				break
			print('Sleeping %d seconds...' % settings['cfg']['interval'])
			time.sleep(settings['cfg']['interval'])
			print('Next!')
		slideshow_thread = None

	if slideshow_thread is None:
		slideshow_thread = threading.Thread(target=imageloop)
		slideshow_thread.daemon = True
		slideshow_thread.start()
	

set_defaults()

if os.path.exists('settings.json'):
	with open('settings.json') as f:
		settings = json.load(f)

settings['resolution'] = get_resolution()
settings['local-ip'] = get_my_ip()
settings['width'] = int(settings['resolution'].split('x')[0])

if settings['local-ip'] is None:
	print('ERROR: You must have functional internet connection to use this app')
	show_message('No internet')
	sys.exit(255)

if __name__ == "__main__":
	# This allows us to use a plain HTTP callback
	os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
	app.secret_key = os.urandom(24)
	slideshow()
	app.run(debug=False, port=7777, host='0.0.0.0' )

sys.exit(0)
