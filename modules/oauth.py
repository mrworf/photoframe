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

from modules.helper import helper
from modules.network import RequestResult

class OAuth:
	def __init__(self, setToken, getToken, scope, extras=''):
		self.ip = helper.getIP()
		self.scope = scope
		self.oauth = None
		self.cbGetToken = getToken
		self.cbSetToken = setToken
		self.ridURI = 'https://photoframe.sensenet.nu'
		self.state = None
		self.extras = extras

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

	def request(self, uri, destination=None, params=None, data=None, usePost=False):
		ret = RequestResult()
		result = None
		stream = destination != None
		tries = 0

		while tries < 5:
			try:
				try:
					auth = self.getSession()
					if auth is None:
						logging.error('Unable to get OAuth session, probably expired')
						ret.setResult(RequestResult.OAUTH_INVALID)
						return ret
					if usePost:
						result = auth.post(uri, stream=stream, params=params, json=data)
					else:
						result = auth.get(uri, stream=stream, params=params)
					if result is not None:
						break
				except TokenExpiredError as e:
					auth = self.getSession(True)
					if auth is None:
						logging.error('Unable to get OAuth session, probably expired')
						ret.setResult(RequestResult.OAUTH_INVALID)
						return ret

					if usePost:
						result = auth.post(uri, stream=stream, params=params, json=data)
					else:
						result = auth.get(uri, stream=stream, params=params)
					if result is not None:
						break
			except:
				logging.exception('Issues downloading')
			time.sleep(tries * 10) # Back off 10, 20, ... depending on tries
			tries += 1

		if tries == 5:
			logging.error('Failed to download due to network issues')
			ret.setResult(RequestResult.NO_NETWORK) # Not necessarily true, need to properly handle it
			return ret

		if destination is not None:
			try:
				with open(destination, 'wb') as handle:
					for chunk in result.iter_content(chunk_size=512):
						if chunk:  # filter out keep-alive new chunks
							handle.write(chunk)
				ret.setResult(RequestResult.SUCCESS).setHTTPCode(result.status_code)
				ret.setHeaders(result.headers)
			except:
				logging.exception('Failed to download %s' % uri)
				ret.setResult(RequestResult.FAILED_SAVING)
		else:
			ret.setResult(RequestResult.SUCCESS).setHTTPCode(result.status_code)
			ret.setHeaders(result.headers)
			ret.setContent(result.content)
		return ret

	def getRedirectId(self):
		r = requests.get('%s/?register' % self.ridURI)
		return r.content

	def initiate(self):
		self.rid = self.getRedirectId()

		auth = OAuth2Session(self.oauth['client_id'],
							scope=self.scope, # ['https://www.googleapis.com/auth/photos'],
							redirect_uri=self.ridURI,
							state='%s-%s-%s' % (self.rid, self.ip, self.extras))
		authorization_url, state = auth.authorization_url(self.oauth['auth_uri'],
		                                                  access_type="offline",
		                                                  prompt="consent")

		self.state = state
		return authorization_url

	def complete(self, url):
		try:
			auth = OAuth2Session(self.oauth['client_id'],
			                     scope=self.scope, # ['https://www.googleapis.com/auth/photos'],
			                     redirect_uri=self.ridURI,
			                     state='%s-%s-%s' % (self.rid, self.ip, self.extras))

			token = auth.fetch_token(self.oauth['token_uri'],
			                         client_secret=self.oauth['client_secret'],
			                         authorization_response=url)

			self.cbSetToken(token)
			return True
		except:
			logging.exception('Failed to complete OAuth')
		return False

