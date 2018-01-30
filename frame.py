#!/usr/bin/env python
import gdata.photos.service
import gdata.media
import gdata.geo
import json
import sys
import os
import random
import hashlib
import datetime
import threading
import time
import math

from requests_oauthlib import OAuth2Session
from flask import Flask, request, redirect, session, url_for
from flask.json import jsonify

with open('oauth.json') as f:
	oauth = json.load(f)

oauth = oauth['web']

settings = {
	'oauth_token' : None,
	'oauth_state' : None,
	'linked' : False,					# Indicates if we've ever linked with google

	'user' : 'themrworf',			# User in picasa to view (usually yourself)
	'interval' : 60,					# Delay in seconds between images (minimum)
	'display-off' : 22,				# What hour (24h) to disable display and sleep
	'display-on' : 4,					# What hour (24h) to enable display and continue
	'refresh-content' : 24,		# After how many hours we should force reload of image lists from server
	'keywords' : [						# Keywords for search (blank = latest 1000 images)
		'"jessica huckabay"',
		'"henric huckabay"',
		'+"henric huckabay" +"jessica huckabay"',
		'cats',
		'thanksgiving',
		'christmas',
		'sweden',
		'people',
		'nature',
		'"redwood city"',
		''
	]
}

app = Flask(__name__)

def pick_image(images):
	ext = ['jpg','png','dng','jpeg','gif','bmp']
	count = len(images['feed']['entry'])
	tries = 5

	while tries > 0:
		entry = images['feed']['entry'][random.randint(0,count-1)]
		# Make sure we don't get a video, unsupported for now
		if 'image' in entry['content']['type']:
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

	# Due to google's unwillingness to return what I own, we need to hack the URI
	uri = uri.replace('/s1600/', '/s1920/', 1)

	return (uri, title, timestamp)


@app.route("/")
def oauth_step1():
	""" Step 1: Get authorization
	"""
	auth = OAuth2Session(oauth['client_id'], scope=['https://picasaweb.google.com/data/'], redirect_uri='http://magi.sfo.sensenet.nu:7777/callback')
	authorization_url, state = auth.authorization_url(oauth['auth_uri'])

	# State is used to prevent CSRF, keep this for later.
	settings['oauth_state'] = state
	return redirect(authorization_url)

# Step 2: Google stuff, essentially user consents to allowing us access

@app.route("/callback", methods=["GET"])
def oauth_step3():
	""" Step 3: Get the token
	"""

	auth = OAuth2Session(oauth['client_id'], scope=['https://picasaweb.google.com/data/'], redirect_uri='http://magi.sfo.sensenet.nu:7777/callback')
	token = auth.fetch_token(oauth['token_uri'], client_secret=oauth['client_secret'], authorization_response=request.url)

	settings['oauth_token'] = token
	settings['linked'] = True
	return redirect(url_for('.complete'))

@app.route("/complete", methods=['GET'])
def complete():
	if settings['oauth_token'] is None:
		if not settings['linked']:
			return 'You need to login & authorize'
		else:
			return redirect('/')
	return 'Done'

def get_images():
	if settings['oauth_token'] is None and settings['linked']:
		# Do some magic on the backend
		request.get('http://127.0.0.1:7777/')
		if settings['oauth_token'] is None:
			print('Unable to get token!')
			return None

	auth = OAuth2Session(token=settings['oauth_token'])

	random.seed()
	keyword = settings['keywords'][random.randint(0, len(settings['keywords'])-1)]

	# Create filename from keyword
	filename = hashlib.new('md5')
	filename.update(keyword)
	filename = filename.hexdigest() + ".json"

	if os.path.exists(filename): # Check age!
		age = math.floor( (time.time() - os.path.getctime(filename)) / 3600)
		if age >= settings['refresh-content']:
			print('File too old, %dh > %dh' % (age, settings['refresh-content']))
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
		url = 'https://picasaweb.google.com/data/feed/api/user/%s' % (settings['user'])

		data = auth.get(url, params=params)
		with open(filename, 'w') as f:
			f.write(data.content)
	images = None
	with open(filename) as f:
		images = json.load(f)
	return images

def slideshow():
	time.sleep(1) # Ugly, but works...
	while True:
		imgs = get_images()
		if imgs:
			uri, title, ts = pick_image(imgs)
			print ts.strftime('%c %Z')
		else:
			print('Need configuration')
			break
		print('Sleeping %d seconds...' % settings['interval'])
		time.sleep(settings['interval'])

if __name__ == "__main__":
	# This allows us to use a plain HTTP callback
	os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
	app.secret_key = os.urandom(24)

	t = threading.Thread(target=slideshow)
	t.daemon = True
	t.start()
	app.run(debug=False, port=7777, host='0.0.0.0' )

sys.exit(0)