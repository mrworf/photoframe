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

import logging
import os
import subprocess

from werkzeug.utils import secure_filename
from .baseroute import BaseRoute
from modules.path import path


class RouteUpload(BaseRoute):
    def setupex(self, settingsmgr, drivermgr):
        self.settingsmgr = settingsmgr
        self.drivermgr = drivermgr

        self.addUrl('/upload/<item>').clearMethods().addMethod('POST')

    def handle(self, app, item):
        retval = {'status': 200, 'return': {}}
        # check if the post request has the file part
        if 'filename' not in self.getRequest().files:
            logging.error('No file part in upload request')
            self.setAbort(405)
            return

        file = self.getRequest().files['filename']
        if item == 'driver':
            # if user does not select file, browser also
            # submit an empty part without filename
            if file.filename == '' or not file.filename.lower().endswith('.zip'):
                logging.error('No driver filename or invalid filename')
                self.setAbort(405)
                return
        elif item == 'config':
            # if user does not select file, browser also
            # submit an empty part without filename
            if file.filename == '' or not file.filename.lower().endswith('.tar.gz'):
                logging.error('No configuration filename or does not end in .tar.gz')
                self.setAbort(405)
                return

        filename = os.path.join('/tmp/', secure_filename(file.filename))
        file.save(filename)
        logging.debug('Upload.py saved %s', filename)

        if item == 'driver':
            result = self.drivermgr.install(filename)
            if result is not False:
                # Check and see if this is the driver we're using
                if result['driver'] == self.settingsmgr.getUser('display-driver'):
                    # Yes it is, we need to activate it and return info about restarting
                    special = self.drivermgr.activate(result['driver'])
                    if special is None:
                        self.settingsmgr.setUser('display-driver', 'none')
                        self.settingsmgr.setUser('display-special', None)
                        retval['status'] = 500
                    else:
                        self.settingsmgr.setUser('display-special', special)
                        retval['return'] = {'reboot': True}
                else:
                    retval['return'] = {'reboot': False, 'restart': False}

        elif item == 'config':
            logging.info('loading settings with: ' + path.BASEDIR + 'photoframe/load_config.py' + filename)
            subprocess.run(path.BASEDIR + 'photoframe/load_config.py' + filename, shell=True)
            retval['return'] = {'reboot': False, 'restart': True}
        
        if retval['status'] == 200:
            return self.jsonify(retval['return'])
        self.setAbort(retval['status'])
