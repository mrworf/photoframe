#!/bin/bash

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
