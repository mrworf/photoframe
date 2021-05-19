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

function error
{
	echo "error: $1"
	if [ -f /tmp/update.log ]; then
		cat /tmp/update.log
	fi
	exit 255
}

function hasupdate
{
	# See if we have changes locally or commits locally (because then we cannot update)
	if git status | egrep '(not staged|Untracked|ahead|to be committed)' >/dev/null; then
		error "Unable to update due to local changes"
	fi

	BRANCH="$(git status | head -n1)" ; BRANCH=${BRANCH:10}
	git fetch 2>&1 >/tmp/update.log || error "Unable to load info about latest"
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

BASEDIR="$(dirname "$0")"

cd ${BASEDIR}

if [ "$1" = "checkversion" ]; then
	if hasupdate; then
		# Return non-zero on new version
		exit 1
	fi
	exit 0
fi

if [ "$1" = "post" ]; then
	####-vvv- ANYTHING HERE MUST HANDLE BEING RUN AGAIN AND AGAIN -vvv-####
	#######################################################################



	# Copy new service and reload systemd
	cp frame.service /etc/systemd/system/
	systemctl daemon-reload

	#######################################################################
	####-^^^- ANYTHING HERE MUST HANDLE BEING RUN AGAIN AND AGAIN -^^^-####
	touch /root/.donepost
	exit 0
elif [ ! -f /root/.donepost ]; then
	# Since we didn't have this behavior, we need to make sure it happens regardless
	# of availability of new update.
	${BASEDIR}/update.sh post
fi

if hasupdate ; then
  # Show updating message
  PID=$(pgrep -f frame.py)
  # Do NOT kill the service itself, since it will actually tear down the python script
	kill -SIGHUP $PID 2>/dev/null

	echo "New version is available (for branch ${BRANCH})"
	git pull --rebase >>/tmp/update.log 2>&1 || error "Unable to update"

	# Run again with the post option so any necessary changes can be carried out
	${BASEDIR}/update.sh post

	# Skip service restart if we were running an update only
	if [ "$1" != "updateonly" ]; then
		systemctl restart frame.service
	fi
else
	echo "No new version"
fi
# Mark this has being done
touch /root/.firstupdate

# Clean up
rm /tmp/update.log 2>/dev/null 1>/dev/null
exit 0
