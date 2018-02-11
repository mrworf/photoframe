from threading import Thread
import time

# Start timer for keeping display on/off
class timekeeper(Thread):
	def __init__(self, cbPower, cbSlideshow):
		Thread.__init__(self)
		self.daemon = True
		self.start()
		self.standby = False
		self.hourOn = None
		self.hourOff = None
		self.cbPower = cbPower
		self.cbSlideshow = cbSlideshow

	def setConfiguration(self, hourOn, hourOff):
		self.hourOn = hourOn
		self.hourOff = hourOff

	def run(self):
		while True:
			time.sleep(60) # every minute

			if self.hourOn is None or self.hourOff is None:
				previously = self.standby
				if hour >= self.hourOff:
					self.standby = True
				elif hour >= self.hourOn:
					self.standby = False

				if self.standby != previously:
					if self.standby:
						self.cbPower(False)
					else:
						self.cbPower(True)
						self.cbSlideshow()
