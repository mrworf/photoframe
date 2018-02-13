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
