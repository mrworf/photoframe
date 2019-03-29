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
class PowerManager():
	def __init__(self, cbPower, cbSlideshow):
		self.standby = False
    self.powerArbiters = {}
		self.cbPower = cbPower
		self.cbSlideshow = cbSlideshow

  def arbiterRegister(self, name, description):
    self.powerArbiters[name] = {'vote' : False, 'description' : description, 'use' : False}

  def arbiterVote(self, name, vote):
    if name not in self.powerArbiters:
      return
    self.powerArbiters[name]['vote'] = vote
    self._evaluateStandby()

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

	def isStandby(self):
		return self.standby

	def _evaluateStandby(self):
    # It will check all power arbiters, if ANY says that power should be OFF, then
    # the resulting power will be off.
    standby = False
    for src in self.powerArbiters:
      if self.powerArbiters[src]['vote']
        continue
      logging.debug('PowerArbiter %s voted for standby', src)
      standby = True
      break

		if not self.standby and standby:
			self.standby = True
			self.cbPower(False)
		elif self.standby and not standby:
			self.standby = False
			self.cbPower(True)
			self.cbSlideshow()
