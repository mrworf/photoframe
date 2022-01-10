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
# load_config.py settings.tar.gz
#
# Description:
# This program loads a saved configuration into the system.  It will:
# Verify config file,
# stop frame service,
# backup current config,
# set desired config.
# Finally restart frame service.
#
#
import sys
import os
import subprocess
import magic
import importlib
import shutil

from modules.settings import settings
from modules.helper import helper
from modules.servicemanager import ServiceManager
from modules.path import path

# Make sure we run from our own directory
os.chdir(os.path.dirname(sys.argv[0]))

# get input filename from command line
if len(sys.argv) < 2:
    print('Argument missing')
    print('Usage:', sys.argv[0], ' settings.tar.gz')
    sys.exit(1)
if len(sys.argv) > 2:
    print('Too many arguments')
    print('Usage:', sys.argv[0], ' settings.tar.gz')
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
    shutil.rmtree(configdir + '.bak', ignore_errors = True)
    os.rename(configdir, configdir + '.bak')  #Todo what if bak already exists
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
    subprocess.call(['/usr/bin/tar', '-xzf', updatefile, '-C', configdir])
except Exception:
    print('tar failed to unpack', updatefile, 'into', configdir)
    if had_config:
        print('Previous configuration is in ', configdir + '.bak')
    sys.exit(1)

#Todo test config data for validity
#Todo test that video mode is supported by current hardware

#Restart frame process
subprocess.call(['/usr/bin/systemctl', 'start', 'frame.service'])

#All done
sys.exit(0)
