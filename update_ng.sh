#!/bin/bash
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
# Update NG (ie, 2.0)
#
# Works differently than the old one, it will allow future versions to
# use individual files and then track them once done.
#
# Flow:
#   1. Check new version
#   2. Kill frame.py (do not stop service, it will kill us too)
#   3. Perform git pull
#   4. Process any new update scripts
#   5. Restart frame service
#
# If we get interrupted in step 4, reboot will cause remaining steps to be executed
#
# To run this in a test environment, you can override the use of /root by exporting
# STORAGE set to a path you have write access to.
#
if [ -z ${STORAGE} ]; then
    STORAGE="/root"
else
    echo >&2 "WARNING: Using ${STORAGE} instead of /root"
fi

BASEDIR="$(dirname "$0")" # Where we are
GITLOG="/tmp/update.log" # Where to store the log

UPDATEDIR="${BASEDIR}/updates/" # Where to find updates
UPDATELOG="${STORAGE}/.update_done" # Tracks which updates we've applied
UPDATEINIT="${STORAGE}/.firstupdate" # If we ever ran
UPDATEPOST="/tmp/photoframe_post_update.done" # If this file is missing, will rerun "post" mode to catch any missing

function error
{
	echo >&2 "error: $1"
	if [ -f ${GITLOG} ]; then
		cat >&2 ${GITLOG}
        echo >&2 "=== This logfile is located at ${GITLOG} ==="
	fi
	exit 255
}

function has_update
{
	# See if we have changes locally or commits locally (because then we cannot update)
	if git status | egrep '(not staged|Untracked|ahead|to be committed)' >/dev/null; then
		error "Unable to update due to local changes"
	fi

	BRANCH="$(git status | head -n1)" ; BRANCH=${BRANCH:10}
	git fetch 2>&1 >${GITLOG} || error "Unable to load info about latest"
	git log -n1 --oneline origin/${BRANCH} >/tmp/server.txt
	git log -n1 --oneline >/tmp/client.txt

	local RET=1
	if ! diff /tmp/server.txt /tmp/client.txt >/dev/null ; then
		RET=0
	fi

	rm /tmp/server.txt 2>/dev/null 1>/dev/null
	rm /tmp/client.txt 2>/dev/null 1>/dev/null
	return ${RET}
}

function perform_update
{
    # Show updating message
    PID=$(pgrep -f frame.py)

    # Do NOT kill the service itself, since it will actually tear down the python script
    kill -SIGHUP $PID 2>/dev/null

    echo "New version is available (for branch ${BRANCH})"
    git pull --rebase >>${GITLOG} 2>&1 || error "Unable to update"

    # Run again with the post option so any necessary changes can be carried out
    ${BASEDIR}/update.sh post

    # Always refresh our services by default since you never know
    cp ${BASEDIR}/frame.service /etc/systemd/system/
    systemctl daemon-reload

    # Skip service restart if we were running an update only
    if [ "$1" != "updateonly" ]; then
        systemctl restart frame.service
    fi
}

function track_first_run
{
    # Mark this has being done
    touch ${UPDATEINIT}
}

function track_post_done
{
    # Mark that we did post update stuff
    touch ${UPDATEPOST}
}

function has_post_done
{
    if [ ! -f ${UPDATEPOST} ]; then
        return 1
    fi
    return 0
}

function perform_post_update
{
    # This is the magic, we now use a file to track what we've done.
    # Once an update has been done, the script is logged.

    if [ ! -d ${UPDATEDIR} ]; then
        error "Directory with updates is missing (${UPDATEDIR})"
    fi

    # Avoids us failing for missing file
    touch ${UPDATELOG}
    local LST_DONE=$(cat ${UPDATELOG})
    local LST_AVAILABLE=$(ls -1 ${UPDATEDIR})
    local UPDATE
    local I
    local DONE=false

    for UPDATE in ${LST_AVAILABLE} ; do
        DONE=false
        for I in ${LST_DONE} ; do
            if [ "${I}" = "${UPDATE}" ]; then
                DONE=true
                break
            fi
        done
        if ${DONE}; then
            continue
        fi
        echo "Applying ${UPDATE}"
        (
            source ${UPDATEDIR}/${UPDATE}
        )
        if [ $? -ne 0 ]; then
            # Would be nice if we could do something with this
            # For now, let's just log it at least. In the future, we may render something to the screen if we can
            echo >&2 "WARNING: ${UPDATE} failed to apply"
        fi
        echo >>${UPDATELOG} "${UPDATE}"
    done
    track_post_done
}

cd ${BASEDIR}

# ALWAYS make sure update completed last time
if ! has_post_done; then
    echo >&2 "INFO: Cannot detect post run from last update, making sure all updates are applied before continuing"
    perform_post_update
fi

if [ "$1" = "checkversion" ]; then
	if has_update; then
		# Return non-zero on new version
		exit 1
	fi
	exit 0
elif [ "$1" = "post" ]; then
    # Do post update things, do not call this manually, intended to be used by
    # this script itself.
    perform_post_update
elif has_update ; then
    perform_update
    track_first_run
else
    echo "No new version available"
    track_first_run
fi

# Remove any potential left-over log at this time
if [ -f ${GITLOG} ]; then
    rm ${GITLOG}
fi
