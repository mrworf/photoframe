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


class RequestResult:
    SUCCESS = 0
    UNKNOWN = -1
    NO_NETWORK = -2
    OAUTH_INVALID = -3
    FAILED_SAVING = -4
    TIMEOUT = -5

    def __init__(self):
        self.result = RequestResult.UNKNOWN
        self.content = None
        self.filename = None
        self.mimetype = 'none/none'
        self.headers = []
        self.httpcode = 0
        self.errormsg = None

    def setErrorMessage(self, msg):
        self.errormsg = msg
        return self

    def setResult(self, result):
        self.result = result
        return self

    def setContent(self, content):
        self.content = content
        return self

    def setFilename(self, filename):
        self.filename = filename
        return self

    def setMimetype(self, mimetype):
        self.mimetype = mimetype
        return self

    def setHeaders(self, headers):
        self.headers = headers
        if 'Content-Type' in headers:
            self.mimetype = headers['Content-Type']
        return self

    def setHTTPCode(self, code):
        self.httpcode = code
        return self

    def isSuccess(self):
        return self.result == RequestResult.SUCCESS and self.httpcode == 200

    def isNoNetwork(self):
        return self.result == RequestResult.NO_NETWORK


class RequestNoNetwork(Exception):
    pass


class RequestInvalidToken(Exception):
    pass


class RequestExpiredToken(Exception):
    pass
