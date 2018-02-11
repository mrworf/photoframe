from threading import Thread
import smbus
import time
import os
import subprocess
import logging

class colormatch(Thread):
	def __init__(self, script, min = None, max = None):
		Thread.__init__(self)
		self.daemon = True
		self.sensor = False
		self.temperature = None
		self.script = script
		self.void = open(os.devnull, 'wb')
		self.min = min
		self.max = max
		self.start()

	def setLimits(self, min, max):
		self.min = min
		self.max = max

	def hasSensor(self):
		return self.sensor

	def hasTemperature(self):
		return self.temperature != None

	def getTemperature(self):
		return self.temperature

	def adjust(self, src, dst, temperature = None):
		if self.temperature is None or self.sensor is None:
			return False
		if temperature is None:
			temperature = self.temperature
		if self.min is not None and temperature < self.min:
			logging.debug('Actual color temp measured is %d, but we cap to %dK' % (temperature, self.min))
			temperature = self.min
		elif self.max is not None and temperature > self.max:
			logging.debug('Actual color temp measured is %d, but we cap to %dK' % (temperature, self.max))
			temperature = self.max
		else:
			logging.debug('Adjusting color temperature to %dK' % temperature)

		return subprocess.call([self.script, '-t', "%d" % temperature, src, dst], stderr=self.void) == 0

	def _temperature_and_lux(self, data):
		"""Convert the 4-tuple of raw RGBC data to color temperature and lux values. Will return
		   2-tuple of color temperature and lux."""
		r, g, b, _ = data
		x = -0.14282 * r + 1.54924 * g + -0.95641 * b
		y = -0.32466 * r + 1.57837 * g + -0.73191 * b
		z = -0.68202 * r + 0.77073 * g +  0.56332 * b
		divisor = x + y + z
		n = (x / divisor - 0.3320) / (0.1858 - y / divisor)
		cct = 449.0 * n**3 + 3525.0 * n**2 + 6823.3 * n + 5520.33
		return cct, y

	def run(self):
		bus = smbus.SMBus(1)
		# I2C address 0x29
		# Register 0x12 has device ver. 
		# Register addresses must be OR'ed with 0x80
		bus.write_byte(0x29,0x80|0x12)
		ver = bus.read_byte(0x29)
		# version # should be 0x44
		if ver == 0x44:
			# Make sure we have the needed script
			if not os.path.exists(self.script):
				logging.info('No color temperature script, download it from http://www.fmwconcepts.com/imagemagick/colortemp/index.php and save as "%s"' % self.script)
				self.sensor = False
				return

			bus.write_byte(0x29, 0x80|0x00) # 0x00 = ENABLE register
			bus.write_byte(0x29, 0x01|0x02) # 0x01 = Power on, 0x02 RGB sensors enabled
			bus.write_byte(0x29, 0x80|0x14) # Reading results start register 14, LSB then MSB
			self.sensor = True
			while True:
				data = bus.read_i2c_block_data(0x29, 0)
				clear = clear = data[1] << 8 | data[0]
				red = data[3] << 8 | data[2]
				green = data[5] << 8 | data[4]
				blue = data[7] << 8 | data[6]
				if red >0 and green > 0 and blue > 0:
					temp, lux = self._temperature_and_lux((red, green, blue, clear))
					self.temperature = temp
				time.sleep(1)
		else: 
			logging.info('No TCS34725 color sensor detected, will not compensate for ambient color temperature')
			self.sensor = False
