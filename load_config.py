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
# stop frame process,
# backup current config,
# set desired config.
# Note: restarting the frame service is up to the caller.
#
#
import sys
import os
import subprocess
import shutil

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
try:
    filetype = subprocess.check_output(['file', '-b', '--mime-type', updatefile]).decode("utf-8").strip()
except Exception:
    print('Error determining Mime-type of ', updatefile)
    sys.exit(1)
if filetype != 'application/gzip':
    print(updatefile, 'is not a tar.gz archive')
    sys.exit(1)

#Stop existing frame thread
# Do NOT kill the service itself, since it will actually tear down the python script
subprocess.call(['pkill', '-SIGHUP', '-f', 'frame.py'])

# move existing config if necessary
configdir=path.CONFIGFOLDER
if os.path.isdir(configdir):
    had_config = True
    shutil.rmtree(configdir + '.bak', ignore_errors = True)
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
    subprocess.call(['tar', '-xzf', updatefile, '-C', configdir])
except Exception:
    print('tar failed to unpack', updatefile, 'into', configdir)
    if had_config:
        print('Restoring Previous configuration')
        shutil.rmtree(configdir, ignore_errors = True)
        os.rename(configdir + '.bak', configdir)
    sys.exit(1)

#Test config data for validity
if not all([os.path.isdir(configdir + '/display-drivers'), os.path.isdir(configdir + '/services'),
           os.path.isfile(configdir + '/settings.json'), os.path.isfile(configdir + '/version.json')]):
    print('New config is incomplete')
    if had_config:
        print('Restoring Previous configuration')
        shutil.rmtree(configdir, ignore_errors = True)
        os.rename(configdir + '.bak', configdir)
    sys.exit(1)

#All done
print('Successfully loaded new config from ', updatefile)
sys.exit(0)
