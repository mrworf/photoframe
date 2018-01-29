#!/usr/bin/env python
import gdata.photos.service
import gdata.media
import gdata.geo
import json
import sys
import os
import xml.etree.ElementTree as ET

from requests_oauthlib import OAuth2Session
from flask import Flask, request, redirect, session, url_for
from flask.json import jsonify

with open('oauth.json') as f:
	oauth = json.load(f)

oauth = oauth['web']

print repr(oauth)
#sys.exit(0)

app = Flask(__name__)

@app.route("/")
def demo():
	""" Step 1: Get authorization
	"""
	auth = OAuth2Session(oauth['client_id'], scope=['https://picasaweb.google.com/data/'], redirect_uri='http://magi.sfo.sensenet.nu:7777/callback')
	authorization_url, state = auth.authorization_url(oauth['auth_uri'])

	# State is used to prevent CSRF, keep this for later.
	session['oauth_state'] = state
	return redirect(authorization_url)

# Step 2: Google stuff, essentially user consents to allowing us access

@app.route("/callback", methods=["GET"])
def callback():
	""" Step 3: Get the token
	"""

	auth = OAuth2Session(oauth['client_id'], scope=['https://picasaweb.google.com/data/'], redirect_uri='http://magi.sfo.sensenet.nu:7777/callback')
	token = auth.fetch_token(oauth['token_uri'], client_secret=oauth['client_secret'], authorization_response=request.url)

	session['oauth_token'] = token

	return redirect(url_for('.complete'))

@app.route("/complete", methods=['GET'])
def complete():
	auth = OAuth2Session(token=session['oauth_token'])

	# Always includes a "no query" too since it's going to be the latest 1000 pics :D

	keywords = [
	'"jessica huckabay"',
	'"henric huckabay"',
	'+"henric huckabay" +"jessica huckabay"',
	'cats',
	'thanksgiving',
	'christmas',
	'sweden',
	'people',
	'nature',
	'"redwood city"'
	]

	# Create filename from keyword

	if not os.path.exists('albums.xml'):
		# Request albums
		# Picasa limits all results to the first 1000, so get them
		params = {
		'kind' : 'photo',
		'start-index' : 1,
		'max-results' : 1000,
		'alt' : 'json',
		'access' : 'all',
		# This is where we get cute, we pick from a list of keywords 
		'q' : '"Jessica Huckabay"',
		'fields' : 'entry(title,content,gphoto:timestamp)'
		}
		url = 'https://picasaweb.google.com/data/feed/api/user/themrworf'

		data = auth.get(url, params=params)
		with open('albums.xml', 'w') as f:
			f.write(data.content)
	tree = ET.parse('albums.xml')
	root = tree.getroot()
	print repr(root)

	return "Well done!"


if __name__ == "__main__":
	# This allows us to use a plain HTTP callback
	os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

	app.secret_key = os.urandom(24)
	app.run(debug=False, port=7777, host='0.0.0.0' )

sys.exit(0)



