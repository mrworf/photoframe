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

class Interval():
	def __init__(self, onHour, offHour, onDay = -1, offDay = -1):
		# Day can be 0-6 (mon-sun) or both can be -1 for all days
		if onDay == -1 and offDay == -1:
			self.start = onHour
			self.end = offHour
			self.includeDays = False
		else:
			self.start = onDay * 24 + onHour
			self.end = offDay * 24 + offHour
			self.includeDays = True

	def __testRange(self, start, end, value):
		if start > end:
			stateBegin = end
			stateEnd = start
			stateMode = False
		else:
			stateBegin = start
			stateEnd = end
			stateMode = True

		print('Testing if %d >= %d and %d < %d (mode = %d)' % (value, stateBegin, value, stateEnd, stateMode))
		if value >= stateBegin and value < stateEnd:
			print('  True, returning %d' % stateMode)
			return stateMode
		else:
			print('  False, returning %d' % (not stateMode))
			return not stateMode

	def testSchedule(self):
		# Returns True if within the on hours
		current = int(time.strftime('%H'))
		if self.includeDays:
			current += ((int(time.strftime('%w')) - 1) % 7)*24
		return self.__testRange(self.start, self.end, current):

# Start timer for keeping display on/off
class timekeeper(Thread):
	def __init__(self):
		Thread.__init__(self)
		self.daemon = True
		self.scheduleOff = False
		self.ambientOff = False
		self.standby = False
		self.ignoreSensor = True
		self.ignoreSchedule = True

		self.hourOn = None
		self.hourOff = None
		self.luxLimit = None
		self.luxTimeout = None
		self.luxLow = None
		self.luxHigh = None
		self.listeners = []
		self.start()

	def registerListener(self, cbPowerState):
		logging.debug('Adding listener %s' % repr(cbPowerState))
		self.listeners.append(cbPowerState)

	def addInterval(self, onDay, onHour, offDay, offHour):
		self.intervals.append(Interval(onDay, onHour, offDay, offHour))

	def setConfiguration(self, hourOn, hourOff):
		self.hourOn = hourOn
		self.hourOff = hourOff
		logging.debug('hourOn = %s, hourOff = %s' % (repr(hourOn), repr(hourOff)))

	def setPowermode(self, mode):
		if mode == '' or mode == 'none':
			mode = 'none'
			self.ignoreSensor = True
			self.ignoreSchedule = True
		elif mode == 'sensor':
			self.ignoreSensor = False
			self.ignoreSchedule = True
		elif mode == 'schedule':
			self.ignoreSensor = True
			self.ignoreSchedule = False
		elif mode == 'sensor+schedule':
			self.ignoreSensor = False
			self.ignoreSchedule = False
		logging.debug('Powermode changed to ' + repr(mode))
		self.luxLow = None
		self.luxHigh = None
		self.ambientOff = False
		self.evaluatePower()

	def setAmbientSensitivity(self, luxLimit, timeout):
		self.luxLimit = luxLimit
		self.luxTimeout = timeout
		self.luxLow = None
		self.luxHigh = None
		self.ambientOff = False

	def getDisplayOn(self):
		return not self.standby

	def sensorListener(self, temperature, lux):
		if self.luxLimit is None or self.luxTimeout is None:
			return
		if lux < self.luxLimit and self.luxLow is None:
			self.luxLow = time.time() + self.luxTimeout * 60
			self.luxHigh = None
		elif lux >= self.luxLimit and self.luxLow is not None:
			self.luxLow = None
			self.luxHigh = time.time() + self.luxTimeout * 60

		previously = self.ambientOff
		if not self.standby and self.luxLow and time.time() > self.luxLow:
			self.ambientOff = True
		elif self.standby and self.luxHigh and time.time() > self.luxHigh:
			self.ambientOff = False
		if previously != self.ambientOff:
			logging.debug('Ambient power state has changed: %s', repr(self.ambientOff))
			self.evaluatePower()

	def evaluatePower(self):
		# Either source can turn off display but scheduleOff takes priority on power on
		# NOTE! Schedule and sensor can be overriden
		if not self.standby and ((not self.ignoreSchedule and self.scheduleOff) or (not self.ignoreSensor and self.ambientOff)):
			self.standby = True
			self.notifyListeners(False)
		elif self.standby and (self.ignoreSchedule or not self.scheduleOff) and (self.ignoreSensor or not self.ambientOff):
			self.standby = False
			self.notifyListeners(True)

	def notifyListeners(self, hasPower):
		if len(self.listeners) == 0:
			logging.warning('No registered listeners')
		for listener in self.listeners:
			logging.debug('Notifying %s of power change to %d' % (repr(listener), hasPower))
			listener(hasPower)

	def run(self):
		self.scheduleOff = False
		while True:
			time.sleep(60) # every minute
			if self.hourOn is not None and self.hourOff is not None:
				i = Interval(self.hourOn, self.hourOff)

				previouslyOff = self.scheduleOff
				self.scheduleOff = not i.testSchedule()

				if self.scheduleOff != previouslyOff:
					logging.debug('Schedule has triggered change in power, standby is now %s' % repr(self.scheduleOff))
					self.evaluatePower()
