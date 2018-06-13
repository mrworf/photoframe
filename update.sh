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
	echo "ERROR: $1"
	if [ -f /tmp/update.log ]; then
		cat /tmp/update.log
	fi
	exit 255
}

cd /root/photoframe

if [ "$1" = "post" ]; then
	echo "Performing post-update changes (if any)"
	# Due to older version not enabling the necessary parts,
	# we need to add i2c-dev to modules if not there
	if ! grep "i2c-dev" /etc/modules-load.d/modules.conf >/dev/null ; then
		echo "i2c-dev" >> /etc/modules-load.d/modules.conf
		modprobe i2c-dev
	fi
	touch .donepost
fi	exit 0
elif [ ! -f .donepost ]; then
	# Since we didn't do this before, we need to make sure it happens regardless
	# of availability of new update.
	/root/photoframe/update.sh post
fi

git fetch 2>&1 >/tmp/update.log || error "Unable to load info about latest"
git log -n1 --oneline origin >/tmp/server.txt
git log -n1 --oneline >/tmp/client.txt
if ! diff /tmp/server.txt /tmp/client.txt >/dev/null ; then
	echo "New version is available"
	git pull --rebase 2>&1 >>/tmp/update.log && error "Unable to update"

	# Run again with the post option so any necessary changes can be carried out
	/root/photoframe/update.sh post

	cp frame.service /etc/systemd/system/
	systemctl restart frame.service
fi

# Clean up
rm /tmp/server.txt 2>&- 1>&-
rm /tmp/client.txt 2>&- 1>&-
rm /tmp/update.log 2>&- 1>&-
exit 0
