#!/bin/bash
#
# This file is part of photoframe (https://github.com/mrworf/photoframe).
#
# photoframe is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
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

git fetch 2>&1 >/tmp/update.log || error "Unable to load info about latest"
git log -n1 --oneline origin >/tmp/server.txt
git log -n1 --oneline >/tmp/client.txt
if ! diff /tmp/server.txt /tmp/client.txt >/dev/null ; then
	echo "New version is available"
	git pull --rebase 2>&1 >>/tmp/update.log && error "Unable to update"
	cp frame.service /etc/systemd/system/
	systemctl restart frame.service
fi

# Clean up
rm /tmp/server.txt 2>&- 1>&-
rm /tmp/client.txt 2>&- 1>&-
rm /tmp/update.log 2>&- 1>&-
exit 0
