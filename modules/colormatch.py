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
		self.lux = None
		self.script = script
		self.void = open(os.devnull, 'wb')
		self.min = min
		self.max = max
		self.listener = None
		self.allowAdjust = False
		if self.script is not None and self.script != '':
			self.hasScript = os.path.exists(self.script)
		else:
			self.hasScript = False

		self.start()

	def setLimits(self, min, max):
		self.min = min
		self.max = max

	def hasSensor(self):
		return self.sensor

	def hasTemperature(self):
		return self.temperature != None

	def hasLux(self):
		return self.lux != None

	def getTemperature(self):
		return self.temperature

	def getLux(self):
		return self.lux

	def setUpdateListener(self, listener):
		self.listener = listener

	def adjust(self, filename, filenameTemp, temperature=None):
		if not self.allowAdjust or not self.hasScript:
			return False

		if self.temperature is None or self.sensor is None:
			logging.debug('Temperature is %s and sensor is %s', repr(self.temperature), repr(self.sensor))
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

		try:
			result = subprocess.call([self.script, '-t', "%d" % temperature, filename + '[0]', filenameTemp], stderr=self.void) == 0
			if os.path.exists(filename + '.cache'):
				os.unlink(filename + '.cache') #Leftovers

			return result
		except:
			logging.exception('Unable to run %s:', self.script)
			return False

	# The following function (_temperature_and_lux) is lifted from the
	# https://github.com/adafruit/Adafruit_CircuitPython_TCS34725 project and
	# is under MIT license, this license ONLY applies to said function and no
	# other part of this project.
	#
	# The MIT License (MIT)
	#
	# Copyright (c) 2017 Tony DiCola for Adafruit Industries
	#
	# Permission is hereby granted, free of charge, to any person obtaining a copy
	# of this software and associated documentation files (the "Software"), to deal
	# in the Software without restriction, including without limitation the rights
	# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
	# copies of the Software, and to permit persons to whom the Software is
	# furnished to do so, subject to the following conditions:
	#
	# The above copyright notice and this permission notice shall be included in
	# all copies or substantial portions of the Software.
	#
	# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
	# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
	# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
	# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
	# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
	# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
	# THE SOFTWARE.
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
	###################################################################################

	# This function is mostly based of the example provided by Brad Berkland's blog:
	# http://bradsrpi.blogspot.com/2013/05/tcs34725-rgb-color-sensor-raspberry-pi.html
	#
	def run(self):
		try:
			bus = smbus.SMBus(1)
		except:
			logging.info('No SMB subsystem, color sensor unavailable')
			return
		# I2C address 0x29
		# Register 0x12 has device ver.
		# Register addresses must be OR'ed with 0x80
		try:
			bus.write_byte(0x29,0x80|0x12)
		except:
			logging.info('ColorSensor not available')
			return
		ver = bus.read_byte(0x29)
		# version # should be 0x44
		if ver == 0x44:
			# Make sure we have the needed script
			if not os.path.exists(self.script):
				logging.info('No color temperature script, download it from http://www.fmwconcepts.com/imagemagick/colortemp/index.php and save as "%s"' % self.script)
				self.allowAdjust = False
			self.allowAdjust = True

			bus.write_byte(0x29, 0x80|0x00) # 0x00 = ENABLE register
			bus.write_byte(0x29, 0x01|0x02) # 0x01 = Power on, 0x02 RGB sensors enabled
			bus.write_byte(0x29, 0x80|0x14) # Reading results start register 14, LSB then MSB
			self.sensor = True
			logging.debug('TCS34725 detected, starting polling loop')
			while True:
				data = bus.read_i2c_block_data(0x29, 0)
				clear = clear = data[1] << 8 | data[0]
				red = data[3] << 8 | data[2]
				green = data[5] << 8 | data[4]
				blue = data[7] << 8 | data[6]
				if red > 0 and green > 0 and blue > 0 and clear > 0:
					temp, lux = self._temperature_and_lux((red, green, blue, clear))
					self.temperature = temp
					self.lux = lux
				else:
					# All zero Happens when no light is available, so set temp to zero
					self.temperature = 0
					self.lux = 0

				if self.listener:
					self.listener(self.temperature, self.lux)

				time.sleep(1)
		else:
			logging.info('No TCS34725 color sensor detected, will not compensate for ambient color temperature')
			self.sensor = False
