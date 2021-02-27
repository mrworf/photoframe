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
from threading import Thread
import select
import subprocess
import os
import socket
import logging


class shutdown(Thread):
    def __init__(self, usePIN=26):
        Thread.__init__(self)
        self.daemon = True
        self.gpio = usePIN
        self.void = open(os.devnull, 'wb')
        self.client, self.server = socket.socketpair()
        self.start()

    def stopmonitor(self):
        self.client.close()

    def run(self):
        logging.info('GPIO shutdown can be triggered by GPIO %d', self.gpio)
        # Shutdown can be initated from GPIO26
        poller = select.poll()
        try:
            with open('/sys/class/gpio/export', 'w') as f:
                f.write('%d' % self.gpio)
        except Exception:
            # Usually it means we ran this before
            pass
        try:
            with open('/sys/class/gpio/gpio%d/direction' % self.gpio, 'w') as f:
                f.write('in')
        except Exception:
            logging.warn('Either no GPIO subsystem or no access')
            return
        with open('/sys/class/gpio/gpio%d/edge' % self.gpio, 'w') as f:
            f.write('both')
        with open('/sys/class/gpio/gpio%d/active_low' % self.gpio, 'w') as f:
            f.write('1')
        with open('/sys/class/gpio/gpio%d/value' % self.gpio, 'r') as f:
            f.read()
            poller.register(f, select.POLLPRI)
            poller.register(self.server, select.POLLHUP)
            i = poller.poll(None)
            for (fd, event) in i:
                if f.fileno() == fd:
                    subprocess.call(['/sbin/poweroff'], stderr=self.void)
                    logging.debug('Shutdown GPIO triggered')
                elif self.server.fileno() == fd:
                    logging.debug('Quitting shutdown manager')
