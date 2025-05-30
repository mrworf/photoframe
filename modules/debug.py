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
import subprocess
import logging
import os
import datetime
import sys
import traceback
from pathlib import Path

def _stringify(args):
    result = ''
    if len(args) > 0:
        for arg in args:
            if ' ' in arg:
                result += f'"{arg}" '
            else:
                result += f'{arg} '
        result = result[0:-1]

    return result.replace('\n', '\\n')

def subprocess_call(cmds, stderr=None, stdout=None):
    #logging.debug('subprocess.call(%s)', _stringify(cmds))
    return subprocess.call(cmds, stderr=stderr, stdout=stdout)

def subprocess_check_output(cmds, stderr=None):
    #logging.debug('subprocess.check_output(%s)', debug._stringify(cmds))
    return subprocess.check_output(cmds, stderr=stderr).decode('utf-8')

def stacktrace():
    title = 'Stacktrace of all running threads'
    lines = []
    for threadId, stack in sys._current_frames().items():
        lines.append(f"\n# ThreadID: {threadId}")
        for filename, lineno, name, line in traceback.extract_stack(stack):
            lines.append(f'File: "{filename}", line {lineno}, in {name}')
            if line:
                lines.append(f"  {line.strip()}")
    return (title, lines, None)

def logfile(all=False):
    # Try different common log locations
    log_locations = [
        '/var/log/syslog',  # Debian/Ubuntu
        '/var/log/messages',  # RHEL/CentOS
        '/var/log/journal',  # systemd journal
        '/var/log/system.log'  # macOS
    ]
    
    log_file = None
    for loc in log_locations:
        if os.path.exists(loc):
            log_file = loc
            break
    
    if log_file is None:
        return ('System Log', ['No system log file found in common locations'], None)
    
    try:
        stats = os.stat(log_file)
        cmd = r'grep -a "photoframe\[" ' + log_file + ' | tail -n 100'
        title = 'Last 100 lines from the photoframe log'
        if all:
            title = f'Last 100 lines from the system log ({log_file})'
            cmd = f'tail -n 100 {log_file}'
        lines = subprocess.check_output(cmd, shell=True).decode('utf-8')
        if lines:
            lines = lines.splitlines()
        suffix = f'(size of logfile {stats.st_size} bytes, created {datetime.datetime.fromtimestamp(stats.st_ctime).strftime("%c")})'
        return (title, lines, suffix)
    except (subprocess.CalledProcessError, OSError) as e:
        logging.exception('Unable to read log file')
        return (title, [f'Unable to read log file: {str(e)}'], None)

def version():
    title = 'Running version'
    try:
        lines = subprocess.check_output('git log HEAD~1..HEAD ; echo "" ; git status', shell=True).decode('utf-8')
        if lines:
            lines = lines.splitlines()
        return (title, lines, None)
    except subprocess.CalledProcessError:
        logging.exception('Unable to get version information from git')
        return (title, ['Unable to get version information from git'], None)
