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
import subprocess
import os
import platform
import datetime
import sys
import traceback
from modules.path import path


def _stringify(args):
    result = ''
    if len(args) > 0:
        for arg in args:
            if ' ' in arg:
                result += '"' + arg + '" '
            else:
                result += arg + ' '
        result = result[0:-1]

    return result.replace('\n', '\\n')


def subprocess_call(cmds, stderr=None, stdout=None):
    return subprocess.call(cmds, stderr=stderr, stdout=stdout)
    # TODO  Relocate to helper?  Convert to subprocess.run?  Add exception to collect output
    # in an error log.  Add debug logging option as well?  Add **kwargs

def subprocess_check_output(cmds, stderr=None):
    return subprocess.check_output(cmds, stderr=stderr).decode("utf-8")
    # TODO basically same treatment as suborocess_call.  Although, with using subprocess.run,
    # check output or not is just another arg.  So, this might just set that arg and subprocess_call.

def stacktrace():
    title = 'Stacktrace of all running threads'
    lines = []
    for threadId, stack in list(sys._current_frames().items()):
        lines.append("\n# ThreadID: %s" % threadId)
        for filename, lineno, name, line in traceback.extract_stack(stack):
            lines.append('File: "%s", line %d, in %s' % (filename, lineno, name))
            if line:
                lines.append("  %s" % (line.strip()))
    return (title, lines, None)


def logfile(all=False):
    stats = os.stat('/var/log/syslog')
    cmd = 'grep -a "photoframe\\[" /var/log/syslog | tail -n 100'
    title = 'Last 100 lines from the photoframe log'
    if all:
        title = 'Last 100 lines from the system log (/var/log/syslog)'
        cmd = 'tail -n 100 /var/log/syslog'
    lines = subprocess.check_output(cmd, shell=True).decode("utf-8")
    # TODO - convert this to use a common subprocess._check_output dunction
    if lines:
        lines = lines.splitlines()
    suffix = '(size of logfile %d bytes, created %s)' % (stats.st_size,
                                                         datetime.datetime.fromtimestamp(stats.st_ctime).strftime('%c'))
    return (title, lines, suffix)


def version():
    title = 'Running version'
    lines = subprocess.check_output('git log HEAD~1..HEAD ; echo "" ; git status', shell=True).decode("utf-8")
    # TODO - convert this to use a common subprocess_check_output function
    if lines:
        lines = lines.splitlines()
    return (title, lines, None)

def config_version():
    origin = subprocess_check_output('git config --get remote.origin.url')
    statlines = subprocess_check_output('git status')
    for line in statlines:
        line = line.strip()
        if line.startswith('On branch'):
            branch = txt.partition("branch")[2].strip()
        else:
            branch = ""
    commitlines = subprocess_check_output('git log HEAD~1..HEAD')
    for line in commitlines:
        line = line.strip()
        if line.startswith('commit'):
            commit = txt.partition("commit")[2].strip()
        else:
            commit = ""

    config = {
        "release:" platform.release(),
        "python_version": platform.python_version(),
        "origin": origin,
        "branch": branch,
        "commit": commit
     }
    versionfile = path.CONFIGFOLDER + "/version.json"
    
    
    
    # TODO - convert this to use a common subprocess_check_output function
    if lines:
        lines = lines.splitlines()
    return (title, lines, None)
