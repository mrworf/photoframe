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
import time
import subprocess
import os
import socket
import logging

class motiondetect(Thread):
  def __init__(self, callback=None, delay=-1, usePIN=20):
    Thread.__init__(self)
    self.daemon = True
    self.gpio = usePIN
    self.callback = callback
    self.void = open(os.devnull, 'wb')
    self.client, self.server = socket.socketpair()
    self.quit = False
    self.timeout = None
    self.callbackDelay = int(delay*1000.0)
    self.start()

  def stop(self):
    self.client.close()

  def handleMotion(self, motion):
    if motion:
      # Only call when we change state
      if self.timeout is not None:
        self.handleCallback(True)
      self.timeout = None
    else:
      self.timeout = delay

  def handleCallback(self, motion):
    if self.callback is None:
      return
    self.callback(motion)

  def run(self):
    # Motion can be initated from GPIO20
    poller = select.poll()
    try:
      with open('/sys/class/gpio/export', 'wb') as f:
        f.write('%d' % self.gpio)
    except:
      # Usually it means we ran this before
      pass
    try:
      with open('/sys/class/gpio/gpio%d/direction' % self.gpio, 'wb') as f:
        f.write('in')
    except:
      logging.warn('Either no GPIO subsystem or no access')
      return
    with open('/sys/class/gpio/gpio%d/edge' % self.gpio, 'wb') as f:
      f.write('both')
    with open('/sys/class/gpio/gpio%d/value' % self.gpio, 'rb') as f:
      self.motion = int(f.read()) == 1
      self.handleMotion(self.motion)
      poller.register(f, select.POLLPRI)
      poller.register(self.server, select.POLLHUP)
      while not self.quit:
        i = poller.poll(self.timeout)
        if len(i) == 0:
          self.handleCallback(False)
        else:
          for (fd, event) in i:
            if f.fileno() == fd:
              logging.debug('Motion triggered')
              f.seek(0)
              self.motion = int(f.read()) == 1
              self.handleMotion(self.motion)
            elif self.server.fileno() == fd:
              logging.debug('Quitting motion manager')
              self.quit = True
