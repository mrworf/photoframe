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
class timekeeper(Thread):
	def __init__(self, cbPower, cbSlideshow):
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
		self.cbPower = cbPower
		self.cbSlideshow = cbSlideshow
		self.start()

	def setConfiguration(self, hourOn, hourOff):
		self.hourOn = hourOn
		self.hourOff = hourOff
		logging.debug('hourOn = %s, hourOff = %s' % (repr(hourOn), repr(hourOff)))

	def setPowermode(self, mode):
		if mode == '' or mode == 'none':
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
		logging.debug('Powermode changed to ' + mode)
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
			self.cbPower(False)
		elif self.standby and (self.ignoreSchedule or not self.scheduleOff) and (self.ignoreSensor or not self.ambientOff):
			self.standby = False
			self.cbPower(True)
			self.cbSlideshow()

	def run(self):
		while True:
			time.sleep(60) # every minute

			if self.hourOn is not None and self.hourOff is not None:
				previously = self.scheduleOff
				hour = int(time.strftime('%H'))
				if hour >= self.hourOff:
					self.scheduleOff = True
				elif hour >= self.hourOn:
					self.scheduleOff = False

				if self.scheduleOff != previously:
					logging.debug('Schedule has triggered change in power %s' % repr(self.scheduleOff))
					self.evaluatePower()
