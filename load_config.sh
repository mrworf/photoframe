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
# Synopsis:
# load_config.sh sourcefile.tar.gz
#
# Description:
# Verify config file, then stop frame service, backup current config, set and test desired config.
# Finally restart frame if the set configuration looks sane, otherwise the backup is restored and an error logged.

function error
{
	echo "error: $1"
	if [ -f /tmp/update.log ]; then
		cat /tmp/update.log
	fi
	exit 255
}


cd "$(dirname "$0")"
cd ".."
BASEDIR=`pwd`

if [ file "$1" | grep "gzip" >> /tmp/load_config.log 2>&1 ] ; then
	systemctl stop frame.service
    mv photoframe_config photoframe_config.bak
else error
fi

if [ ! tar ]








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
