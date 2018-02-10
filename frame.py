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
import select
import smbus

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

settings = {
	'oauth_token' : None,
	'oauth_state' : None,
	'local-ip' : None,
	'tempfolder' : '/tmp/',
	'colortemp' : None,
	'colortemp-script' : '/root/colortemp.sh',
	'cfg' : None
}

class remember:
	def __init__(self, filename, count):
		self.filename = os.path.splitext(filename)[0] + '_memory.json'
		self.count = count
		if os.path.exists(self.filename):
			with open(self.filename, 'rb') as f:
				self.memory = json.load(f)
		else:
			self.memory = {'seen':[]}

	def forget(self):
		self.memory = {'seen':[]}
		if os.path.exists(self.filename):
			os.unlink(self.filename)		

	def saw(self, index):
		if index not in self.memory['seen']:
			self.memory['seen'].append(index)
			with open(self.filename, 'wb') as f:
				json.dump(self.memory, f)

	def seenAll(self):
		return len(self.memory['seen']) == self.count

	def seen(self, index):
		return index in self.memory['seen']

def _temperature_and_lux(data):
	"""Convert the 4-tuple of raw RGBC data to color temperature and lux values. Will return
	   2-tuple of color temperature and lux."""
	r, g, b, _ = data
	x = -0.14282 * r + 1.54924 * g + -0.95641 * b
	y = -0.32466 * r + 1.57837 * g + -0.73191 * b
	z = -0.68202 * r + 0.77073 * g +  0.56332 * b
	divisor = x + y + z
	n = (x / divisor - 0.3320) / (0.1858 - y / divisor)
	cct = 449.0 * n**3 + 3525.0 * n**2 + 6823.3 * n + 5520.33
	return cct, y

def poll_colortemp():
	bus = smbus.SMBus(1)
	# I2C address 0x29
	# Register 0x12 has device ver. 
	# Register addresses must be OR'ed with 0x80
	bus.write_byte(0x29,0x80|0x12)
	ver = bus.read_byte(0x29)
	# version # should be 0x44
	if ver == 0x44:
		# Make sure we have the needed script
		if not os.path.exists(settings['colortemp-script']):
			logging.info('No color temperature script, download it from http://www.fmwconcepts.com/imagemagick/colortemp/index.php and save as "%s"')
			return

		bus.write_byte(0x29, 0x80|0x00) # 0x00 = ENABLE register
		bus.write_byte(0x29, 0x01|0x02) # 0x01 = Power on, 0x02 RGB sensors enabled
		bus.write_byte(0x29, 0x80|0x14) # Reading results start register 14, LSB then MSB
		while True:
			data = bus.read_i2c_block_data(0x29, 0)
			clear = clear = data[1] << 8 | data[0]
			red = data[3] << 8 | data[2]
			green = data[5] << 8 | data[4]
			blue = data[7] << 8 | data[6]
			if red >0 and green > 0 and blue > 0:
				temp, lux = _temperature_and_lux((red, green, blue, clear))
				settings['colortemp'] = temp
			time.sleep(1)
	else: 
		logging.info('No TCS34725 color sensor detected, will not compensate for ambient color temperature')

def set_defaults():
	settings['cfg'] = {
		'width' : 1920,
		'height' : 1080,
		'depth' : 32,
		'tvservice' : 'DMT 82 DVI',
		'interval' : 60,					# Delay in seconds between images (minimum)
		'display-off' : 22,				# What hour (24h) to disable display and sleep
		'display-on' : 4,					# What hour (24h) to enable display and continue
		'refresh-content' : 24,		# After how many hours we should force reload of image lists from server
		'keywords' : [						# Keywords for search (blank = latest 1000 images)
			""
		]
	}

def get_resolution():
	res = None
	output = subprocess.check_output(['/bin/fbset'], stderr=DEVNULL)
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
	uri = uri.replace('/s1600/', '/s%s/' % settings['cfg']['width'], 1)

	return (uri, mime, title, timestamp)

def get_extension(mime):
	mapping = {
		'image/jpeg' : 'jpg',
		'image/png' : 'png',
	}
	mime = mime.lower()
	if mime in mapping:
		return mapping[mime]
	logging.warning('Mime %s unsupported' % mime)
	return 'xxx'

def loadSettings():
	global settings

	if os.path.exists('/root/settings.json'):
		with open('/root/settings.json') as f:
			settings = json.load(f)

def saveSettings():
	with open('/root/settings.json', 'w') as f:
		json.dump(settings, f)

def getAuth(refresh=False):
	if not refresh:
		auth = OAuth2Session(oauth['client_id'], token=settings['oauth_token'])
	else:
		def token_updater(token):
			settings['oauth_token'] = token
			saveSettings()

		auth = OAuth2Session(oauth['client_id'],
	                         token=settings['oauth_token'],
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
		if key in ['width', 'height', 'depth', 'tvservice']:
			enable_display(True, True)
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
		return jsonify({'keywords' : settings['cfg']['keywords']})
	elif request.method == 'POST' and request.json is not None:
		if 'id' not in request.json:
			keywords = request.json['keywords'].strip()
			if keywords not in settings['cfg']['keywords']:
				settings['cfg']['keywords'].append(keywords)
				saveSettings()
		else:
			id = request.json['id']
			if id > -1 and id < len(settings['cfg']['keywords']):
				settings['cfg']['keywords'].pop(id)
				# Make sure we always have ONE entry
				if len(settings['cfg']['keywords']) == 0:
					settings['cfg']['keywords'].append('')
				saveSettings()
		return jsonify({'status':True})
	abort(500)

@app.route('/has/token')
@app.route('/has/oauth')
def cfg_hasthis():
	result = False
	if '/token' in request.path:
		if settings['oauth_token'] is not None:
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
	set_defaults();
	settings['oauth_token'] = None
	settings['oauth_state'] = None
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
	keyword = settings['cfg']['keywords'][random.SystemRandom().randint(0, len(settings['cfg']['keywords'])-1)]

	# Create filename from keyword
	filename = hashlib.new('md5')
	filename.update(keyword)
	filename = filename.hexdigest() + ".json"
	filename = os.path.join(settings['tempfolder'], filename)

	if os.path.exists(filename): # Check age!
		age = math.floor( (time.time() - os.path.getctime(filename)) / 3600)
		if age >= settings['cfg']['refresh-content']:
			logging.debug('File too old, %dh > %dh, refreshing' % (age, settings['cfg']['refresh-content']))
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
	if settings['colortemp'] is not None:
		temp = settings['colortemp']
		if temp < 3500:
			logging.debug('Actual color temp measured is %d, but we cap to 3500K', temp)
			temp = 3500
		logging.debug('Adjusting color temperature to %dK' % temp)
		subprocess.check_output([settings['colortemp-script'], '-t', "%d" % temp, "%s-org%s" % (filename, ext), dest], stderr=DEVNULL)
	else:
		logging.info('No color temperature info yet')
		os.rename("%s-org%s" % (filename, ext), dest)
	return True

def show_message(message):
	args = [
		'convert',
		'-size',
		'%dx%d' % (settings['cfg']['width'], settings['cfg']['height']),
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
		ret = subprocess.call(args, stdout=f, stderr=DEVNULL)

def show_image(filename):
	logging.debug('Showing image to user')
	args = [
		'convert',
		filename,
		'-resize',
		'%dx%d' % (settings['cfg']['width'], settings['cfg']['height']),
		'-background',
		'black',
		'-gravity',
		'center',
		'-extent',
		'%dx%d' % (settings['cfg']['width'], settings['cfg']['height']), 
		'-depth',
		'8',
		'bgra:-'
	]
	with open('/dev/fb0', 'wb') as f:
		ret = subprocess.call(args, stdout=f, stderr=DEVNULL)

display_enabled = True

def enable_display(enable, force=False):
	global display_enabled

	if enable == display_enabled and not force:
		return

	if enable:
		if force: # Make sure display is ON and set to our preference
			subprocess.call(['/opt/vc/bin/tvservice', '-e', settings['cfg']['tvservice']], stderr=DEVNULL, stdout=DEVNULL)
			time.sleep(1)
			subprocess.call(['/bin/fbset', '-depth', '8'], stderr=DEVNULL)
			subprocess.call(['/bin/fbset', '-depth', str(settings['cfg']['depth']), '-xres', str(settings['cfg']['width']), '-yres', str(settings['cfg']['height'])], stderr=DEVNULL)
		else:
			subprocess.call(['/usr/bin/vcgencmd', 'display_power', '1'], stderr=DEVNULL)
	else:
		subprocess.call(['/usr/bin/vcgencmd', 'display_power', '0'], stderr=DEVNULL)
	display_enabled = enable

def is_display_enabled():
	return display_enabled

slideshow_thread = None

def slideshow(blank=False):
	global slideshow_thread

	if blank:
		# lazy
		with open('/dev/fb0', 'wb') as f:
			subprocess.call(['cat' , '/dev/zero'], stdout=f, stderr=DEVNULL)

	def imageloop():
		global slideshow_thread
		time.sleep(1) # Ugly, but works... allows server to get going

		# Make sure we have OAuth2.0 ready
		while True:
			if settings['oauth_token'] is None:
				show_message('Please link photoalbum\n\nSurf to http://%s:7777/' % settings['local-ip'])
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

				filename = os.path.join(settings['tempfolder'], 'image.%s' % get_extension(mime))
				if download_image(uri, filename):
					show_image(filename)
					break
				else:
					tries -= 1

			if tries == 0:
				show_message("Unable to download ANY images\nCheck that you have photos\nand queries aren't too strict")
			time.sleep(settings['cfg']['interval'])
			if int(time.strftime('%H')) >= settings['cfg']['display-off']:
				logging.debug("It's after hours, exit quietly")
				break
		slideshow_thread = None

	if slideshow_thread is None and oauth is not None:
		slideshow_thread = threading.Thread(target=imageloop)
		slideshow_thread.daemon = True
		slideshow_thread.start()
	

set_defaults()
loadSettings()

# Force display to desired user setting
enable_display(True, True)

# Spin until we have internet, check every 10s
while True:
	settings['local-ip'] = get_my_ip()
	settings['colortemp'] = None

	if settings['local-ip'] is None:
		logging.error('You must have functional internet connection to use this app')
		show_message('No internet')
		time.sleep(10)
	else:
		break

if os.path.exists('/root/oauth.json'):
	with open('/root/oauth.json') as f:
		oauth = json.load(f)
	if 'web' in oauth: # if someone added it via command-line
		oauth = oauth['web']
else:
	show_message('You need to provide OAuth details\nSee README.md')

# Prep random
random.seed(long(time.clock()))

# Start timer for keeping display on/off
def isittime():
	off = False
	while True:
		time.sleep(60) # every minute

		hour = int(time.strftime('%H'))
		if not off and hour >= settings['cfg']['display-off']:
			off = True
			enable_display(False)
		elif off and hour >= settings['cfg']['display-on']:
			off = False
			enable_display(True)
			# Make sure slideshow starts again
			slideshow()

timekeeper = threading.Thread(target=isittime)
timekeeper.daemon = True
timekeeper.start()

def checkshutdown():
	# Shutdown can be initated from GPIO26
	poller = select.poll()
	try:
		with open('/sys/class/gpio/export', 'wb') as f:
			f.write('26')
	except:
		# Usually it means we ran this before
		pass
	with open('/sys/class/gpio/gpio26/direction', 'wb') as f:
		f.write('in')
	with open('/sys/class/gpio/gpio26/edge', 'wb') as f:
		f.write('both')
	with open('/sys/class/gpio/gpio26/value', 'rb') as f:
		data = f.read()
		poller.register(f, select.POLLPRI)
		while True:
			i = poller.poll(None)
			subprocess.call(['/sbin/poweroff'], stderr=DEVNULL);

shutdown = threading.Thread(target=checkshutdown)
shutdown.daemon = True
shutdown.start()

colortemp = threading.Thread(target=poll_colortemp)
colortemp.daemon = True
colortemp.start()

if __name__ == "__main__":
	# This allows us to use a plain HTTP callback
	os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
	app.secret_key = os.urandom(24)
	slideshow()
	app.run(debug=False, port=7777, host='0.0.0.0' )

sys.exit(0)
