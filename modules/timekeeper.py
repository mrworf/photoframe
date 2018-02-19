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
import logging
from threading import Thread
import time

# Start timer for keeping display on/off
class timekeeper(Thread):
	def __init__(self, cbPower, cbSlideshow):
		Thread.__init__(self)
		self.daemon = True
		self.standby = False
		self.hourOn = None
		self.hourOff = None
		self.cbPower = cbPower
		self.cbSlideshow = cbSlideshow
		self.start()

	def setConfiguration(self, hourOn, hourOff):
		self.hourOn = hourOn
		self.hourOff = hourOff
		logging.debug('hourOn = %s, hourOff = %s' % (repr(hourOn), repr(hourOff)))

	def run(self):
		while True:
			time.sleep(60) # every minute

			if self.hourOn is not None and self.hourOff is not None:
				previously = self.standby
				hour = int(time.strftime('%H'))
				if hour >= self.hourOff:
					self.standby = True
				elif hour >= self.hourOn:
					self.standby = False

				if self.standby != previously:
					logging.debug('New state for power is %s' % repr(self.standby))
					if self.standby:
						self.cbPower(False)
					else:
						self.cbPower(True)
						self.cbSlideshow()
