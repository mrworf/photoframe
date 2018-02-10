from threading import Thread
import time

# Start timer for keeping display on/off
class timekeeper(Thread):
	def __init__(self, hourOn, hourOff, cbPower, cbSlideshow):
		Thread.__init__(self)
		self.daemon = True
		self.start()
		self.standby = False
		self.hourOn = hourOn
		self.hourOff = hourOff
		self.cbPower = cbPower
		self.cbSlideshow = cbSlideshow

	def run(self):
		while True:
			time.sleep(60) # every minute

			hour = int(time.strftime('%H'))
			if not self.standby and hour >= self.hourOff:
				self.standby = True
				self.cbPower(False)
			elif self.standby and hour >= self.hourOn:
				self.standby = False
				self.cbPower(True)
				# Make sure slideshow starts again
				self.cbSlideshow()
