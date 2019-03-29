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
import logging
from threading import Thread
import time

# Start timer for keeping display on/off
class schedule(Thread):
  NAME = 'schedule'
  DESCRIPTION = 'Scheduled on/off'
  
	def __init__(self, powermanager):
    Thread.__init__(self)
    self.daemon = True
    self.standby = False
    self.hourOn = None
    self.hourOff = None
    self.powermanager = powermanager
    self.powermanager.arbiterRegister(schedule.NAME, schedule.DESCRIPTION)
    self.start()

	def setActiveHours(self, hourOn, hourOff):
		self.hourOn = hourOn
		self.hourOff = hourOff

	def run(self):
		while True:
			time.sleep(60) # every minute

			standby = False

			if self.hourOn is not None and self.hourOff is not None:
				if self.hourOn > self.hourOff:
					stateBegin = self.hourOff
					stateEnd = self.hourOn
					stateMode = True
				else:
					stateBegin = self.hourOn
					stateEnd = self.hourOff
					stateMode = False

				previouslyState = self.standby
				hour = int(time.strftime('%H'))
				if hour >= stateBegin and hour < stateEnd:
					self.standby = stateMode
				else:
					self.standby = not stateMode

				if self.standby != previouslyState:
					logging.debug('Schedule has triggered change in power %s' % repr(self.scheduleOff))
					self.powermanager.arbiterVote(self.standby)
