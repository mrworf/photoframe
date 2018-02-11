import requests
from requests_oauthlib import OAuth2Session

class OAuth:
	def __init__(self, ip, setToken, getToken):
		self.ip = ip
		self.cbGetToken = getToken
		self.cbSetToken = setToken
		self.ridURI = 'https://photoframe.sensenet.nu'
		self.state = None

	def setOAuth(self, oauth):
		self.oauth = oauth

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

	def requestURI(self, uri, stream=False, params=None):
		try:
			auth = self.getSession()
			return auth.get(uri, stream=stream, params=params)
		except:
			auth = self.getSession(True)
			return auth.get(uri, stream=stream, params=params)

	def getRedirectId(self):
		r = requests.get('%s/?register' % self.ridURI)
		return r.content

	def intiate(self):
		self.rid = self.getRedirectId()

		auth = OAuth2Session(self.oauth['client_id'],
							scope=['https://picasaweb.google.com/data/'],
							redirect_uri=self.ridURI,
							state='%s-%s' % (self.rid, self.ip))
		authorization_url, state = auth.authorization_url(self.oauth['auth_uri'], 
		                                                  access_type="offline",
		                                                  prompt="consent")

		self.state = state
		return authorization_url

	def complete(self, url):
		auth = OAuth2Session(self.oauth['client_id'], 
		                     scope=['https://picasaweb.google.com/data/'], 
		                     redirect_uri=self.ridURI,
		                     state='%s-%s' % (self.rid, self.ip))

		token = auth.fetch_token(self.oauth['token_uri'],
		                         client_secret=self.oauth['client_secret'], 
		                         authorization_response=url)

		self.cbSetToken(token)
		return

