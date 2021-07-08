#!/usr/bin/env python3
#
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
# Synopsis:
# load_config.py sourcefile.tar.gz
#
# Description:
# This program loads a saved configuration into the system.  It will:
# Verify config file, stop frame service, backup current config, set and test desired config.
# Finally restart frame service.
#
#
import sys
import os
import subprocess
import magic
import importlib

from modules.settings import settings
from modules.helper import helper
from modules.servicemanager import ServiceManager
from modules.path import path

# Make sure we run from our own directory
os.chdir(os.path.dirname(sys.argv[0]))


class Updater:
    def __init__(self, cmdline):
        
        if not path().validate():
            sys.exit(255)

        self.settingsMgr = settings()
        self.displayMgr = display(self.emulator)
        # Validate all settings, prepopulate with defaults if needed
        self.validateSettings()

        

    def validateSettings(self):
        if not self.settingsMgr.load():
            # First run, grab display settings from current mode
            current = self.displayMgr.current()
            if current is not None:
                logging.info('No display settings, using: %s' % repr(current))
                self.settingsMgr.setUser('tvservice', '%s %s HDMI' % (current['mode'], current['code']))
                self.settingsMgr.save()
            else:
                logging.info('No display attached?')
        
        #TODO: Test the imported display settings against the settings supported by the current display
        #If the current display cannot support the setting, then change resolution to something reasonable.


# get input filename from command line
if len(sys.argv) < 1:
    print('Argument missing')
    print('Usage:', sys.argv[0], ' backupfile.tar.gz'
    sys.exit(1)
if len(sys.argv) > 1:
    print('Too many arguments')
    print('Usage:', sys.argv[0], ' backupfile.tar.gz')
    sys.exit(1)
updatefile = sys.argv[1]

# test that the file exists and is a tar.gz file
if not os.path.isfile(updatefile):
    print('file not found: ', updatefile)
    sys.exit(1)
if magic.from_file(updatefile, mime=True) != 'application/gzip':
    print(updatefile, 'is not a tar.gz archive')
    sys.exit(1)

#Stop existing frame processes
subprocess.call(['/usr/bin/systemctl', 'stop', 'frame.service'])

# move existing config if necessary
configdir=path.CONFIGFOLDER
if os.path.isdir(configdir):
    had_config = True
    os.rename(configdir, configdir + '.bak')
else:
    had_config = False
try:
    os.mkdir(configdir)
except Exception:
    print('Cannot make new configuration directory:', configdir)
    os.rename(configdir + '.bak', configdir)
    sys.exit(1)

#Un-tar the config file
try:
    subprocess.call(['/usr/bin/tar', '-xzf', updatefile, '-C', configdir],])
except Exception:
    print('tar failed to unpack', updatefile, 'into', configdir)
    os.rename(configdir + '.bak', configdir)
    sys.exit(1)

# test config data for validity
if not settings.load():
    print('settings failed to load from', updatefile)
    os.rename(configdir, configdir)
    
    os.rename(configdir + '.bak', configdir)
    sys.exit(1)
    
    

frame = Updater(cmdline)

sys.exit(0)
