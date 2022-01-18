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
import shutil
import flask
import modules.debug as debug

from .baseroute import BaseRoute
from modules.path import path


class RouteMaintenance(BaseRoute):
    def setupex(self, emulator, drivermgr, slideshow, timekeeper):
        self.drivermgr = drivermgr
        self.emulator = emulator
        self.slideshow = slideshow
        self.timekeeper = timekeeper
        self.void = open(os.devnull, 'wb')

        self.addUrl('/maintenance/<cmd>')

    def handle(self, app, cmd):
        if cmd == 'reset':
            # Remove driver if active
            self.drivermgr.activate(None)
            # Delete configuration data
            if os.path.exists(path.CONFIGFOLDER):
                shutil.rmtree(path.CONFIGFOLDER, True)
            # Reboot
            if not self.emulator:
                subprocess.call(['/sbin/reboot'], stderr=self.void)
            else:
                self.server.stop()
            return self.jsonify({'reset': True})
        elif cmd == 'reboot':
            if not self.emulator:
                subprocess.call(['/sbin/reboot'], stderr=self.void)
            else:
                self.server.stop()
            return self.jsonify({'reboot': True})
        elif cmd == 'shutdown':
            if not self.emulator:
                subprocess.call(['/sbin/poweroff'], stderr=self.void)
            else:
                self.server.stop()
            return self.jsonify({'shutdown': True})
        elif cmd == 'checkversion':
            if os.path.exists('update.sh'):
                with open(os.devnull, 'wb') as void:
                    result = subprocess.call(['/bin/bash', 'update.sh', 'checkversion'], stderr=void)
                    if result == 0:
                        return self.jsonify({'checkversion': False})
                    elif result == 1:
                        return self.jsonify({'checkversion': True})
                    else:
                        return self.jsonify({'checkversion': False, 'error': True})
            else:
                return 'Cannot find update tool', 404
        elif cmd == 'update':
            if self.emulator:
                return 'Cannot run update from emulation mode', 200
            if os.path.exists('update.sh'):
                subprocess.Popen('/bin/bash update.sh 2>&1 | logger -t forced_update', shell=True)
                return 'Update in process', 200
            else:
                return 'Cannot find update tool', 404
        elif cmd == 'clearCache':
            self.slideshow.createEvent("clearCache")
            return self.jsonify({'clearCache': True})
        elif cmd == 'forgetMemory':
            self.slideshow.createEvent("memoryForget")
            return self.jsonify({'forgetMemory': True})
        elif cmd == 'ssh':
            subprocess.call(['systemctl', 'restart', 'ssh'], stderr=self.void)
            return self.jsonify({'ssh': True})
        elif cmd == 'backup':
            if debug.config_version():
                try:
                    subprocess.call(['tar', '-czf', '/boot/settings.tar.gz', '-C', path.CONFIGFOLDER, '.'])
                except:
                    return 'Backup Failed', 404
                else:
                    return 'Backup Successful', 200
            else:
                return 'Backup Failed', 404
        elif cmd == 'restore':
            if os.path.isfile("/boot/settings.tar.gz"):
                try:
                    subprocess.run(path.BASEDIR + 'photoframe/load_config.py /boot/settings.tar.gz', shell=True)
                except:
                    logging.info('FAILED to load new settings with: ' + path.BASEDIR + 'photoframe/load_config.py /boot/settings.tar.gz')
                    return 'Failed to load new settings', 404
                else:
                    logging.info('Loaded new settings with: ' + path.BASEDIR + 'photoframe/load_config.py /boot/settings.tar.gz')
                    subprocess.Popen('systemctl restart frame', shell=True)
                    return 'Restoring settings and restarting photofame', 200
            else:
                return 'File not found: /boot/settings.tar.gz', 404
        elif cmd == 'dnldcfg':
            if debug.config_version():
                try:
                    subprocess.call(['tar', '-czf', '/tmp/settings.tar.gz', '-C', path.CONFIGFOLDER, '.'], stderr=self.void)
                except:
                    return 'Download Failed', 404
                else:
                    return flask.send_from_directory("/tmp", "settings.tar.gz", as_attachment=True)
            else:
                return 'Download failed', 404
        # The route to upload settings from the browser is in routes/upload.py
        elif cmd == 'restart':
            subprocess.Popen('systemctl restart frame', shell=True)
            return 'Restarting photoframe', 200
        elif cmd == 'standby':
            self.timekeeper.setExternalStandby(True)
            return self.jsonify({'standby': self.timekeeper.getExternalStandby()})
        elif cmd == 'resume':
            self.timekeeper.setExternalStandby(False)
            return self.jsonify({'standby': self.timekeeper.getExternalStandby()})
        elif cmd == 'get_standby':
            return self.jsonify({'standby': self.timekeeper.getExternalStandby()})
