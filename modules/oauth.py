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
import requests
import logging
import time
from oauthlib.oauth2 import TokenExpiredError
from requests_oauthlib import OAuth2Session

class OAuth:
	def __init__(self, ip, setToken, getToken):
		self.ip = ip
		self.oauth = None
		self.cbGetToken = getToken
		self.cbSetToken = setToken
		self.ridURI = 'https://photoframe.sensenet.nu'
		self.state = None

	def setOAuth(self, oauth):
		self.oauth = oauth

	def hasOAuth(self):
		return self.oauth != None

	def getSession(self, refresh=False):
		if not refresh:
			auth = OAuth2Session(self.oauth['client_id'], token=self.cbGetToken())
		else:
			auth = OAuth2Session(self.oauth['client_id'],
		                         token=self.cbGetToken(),
		                         auto_refresh_kwargs={'client_id' : self.oauth['client_id'], 'client_secret' : self.oauth['client_secret']},
		                         auto_refresh_url=self.oauth['token_uri'],
		                         token_updater=self.cbSetToken)
		return auth

	def request(self, uri, destination=None, params=None):
		result = None
		stream = destination != None
		tries = 0
		while tries < 5:
			try:
				try:
					auth = self.getSession()
					result = auth.get(uri, stream=stream, params=params)
					break
				except TokenExpiredError as e:
					auth = self.getSession(True)
					result = auth.get(uri, stream=stream, params=params)
					break
			except:
				logging.exception('Issues downloading')
			time.sleep(tries * 10) # Back off 10, 20, ... depending on tries
			tries += 1

		if tries == 5:
			logging.error('Failed to download due to network issues')
			return False

		if result is not None and destination is not None:
			try:
				with open(destination, 'wb') as handle:
					for chunk in result.iter_content(chunk_size=512):
						if chunk:  # filter out keep-alive new chunks
							handle.write(chunk)
				return True
			except:
				logging.exception('Failed to download %s' % uri)
				return False
		else:
			return result

	def getRedirectId(self):
		r = requests.get('%s/?register' % self.ridURI)
		return r.content

	def initiate(self):
		self.rid = self.getRedirectId()

		auth = OAuth2Session(self.oauth['client_id'],
							scope=['https://www.googleapis.com/auth/photos'],
							redirect_uri=self.ridURI,
							state='%s-%s' % (self.rid, self.ip))
		authorization_url, state = auth.authorization_url(self.oauth['auth_uri'],
		                                                  access_type="offline",
		                                                  prompt="consent")

		self.state = state
		return authorization_url

	def complete(self, url):
		auth = OAuth2Session(self.oauth['client_id'],
		                     scope=['https://www.googleapis.com/auth/photos'],
		                     redirect_uri=self.ridURI,
		                     state='%s-%s' % (self.rid, self.ip))

		token = auth.fetch_token(self.oauth['token_uri'],
		                         client_secret=self.oauth['client_secret'],
		                         authorization_response=url)

		self.cbSetToken(token)
		return

