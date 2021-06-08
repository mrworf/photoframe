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
import re
import subprocess
import logging
from . import debug


class colormatch(Thread):
    def __init__(self, script, min=None, max=None):
        Thread.__init__(self)
        self.daemon = True
        self.sensor = False
        self.temperature = None
        self.default_temp = 3350.0
        self.lux = None
        self.sensor_scale = 6.0  # ToDo - set this from Configuration - This is (GA) from AMS App note DN40
        self.lux_scale = 1.0  # ToDo - set this from Configuration - Monitor Brightness = lux * lux_scale
        self.script = script
        self.mon_adjust = False
        self.mon_min_bright = 0.0  # Can't get this through ddc - assume 0
        self.mon_max_bright = 0.0
        self.mon_min_temp = 0.0
        self.mon_max_temp = 0.0
        self.mon_temp_inc = 0.0
        self.mon_max_inc = 126.0  # Can't get this through ddc - has to be set by hand for now
        self.void = open(os.devnull, 'wb')
        self.min = min
        self.max = max
        self.listener = None
        self.allowAdjust = False
        if self.script is not None and self.script != '':
            self.hasScript = os.path.exists(self.script)
        else:
            self.hasScript = False
        if os.path.exists("/usr/bin/ddcutil") and os.path.exists("/dev/i2c-2"):
            # Logic to read monitor adjustment ranges and increments from ddc channel
            # This is written assuming the monitor is a HP Z24i - If the regex strings differ for other
            #    monitors, then this section may need to be replicated and "ddcutil detect" used to
            #    determine the monitor type.  At that point, it may be better to have a new module -
            #    similar to self.script - or a data file/structure can be created with the regex expressions for
            #    various monitors
            self.mon_adjust = True
            try:
                temp_str = debug.subprocess_check_output(['/usr/bin/ddcutil', 'getvcp', '0B'])
                self.mon_temp_inc = int(re.search('([0-9]*) (degree)', temp_str).group(1))
                logging.debug('Monitor temp increment is %i' % self.mon_temp_inc)
            except:
                logging.exception('ddcutil is present but not getting temp increment from monitor. ')
                self.mon_adjust = False
            try:
                temp_str = debug.subprocess_check_output(['/usr/bin/ddcutil', 'getvcp', '0C'])
                self.mon_min_temp = int(re.search('([0-9]*) (\\+)', temp_str).group(1))
                logging.debug('Monitor min temp is %i' % self.mon_min_temp)
            except:
                logging.exception('ddcutil is present but not getting min temp status from monitor. ')
                self.mon_adjust = False
            try:
                temp_str = debug.subprocess_check_output(['/usr/bin/ddcutil', 'getvcp', '10'])
                self.mon_max_bright = int(re.search('(max value \\= *) ([0-9]*)', temp_str).group(2))
                logging.debug('Monitor max brightness is %i' % self.mon_max_bright)
            except:
                logging.exception('ddcutil is present but not getting brightness info from monitor')
                self.mon_adjust = False
            if self.mon_adjust == True:
                logging.info('Monitor adjustments enabled')
        else:
            logging.debug('/usr/bin/ddcutil or /dev/i2c-2 not found - cannot adjust monitor')
            self.mon_adjust = False

        self.start()

    def setLimits(self, min, max):
        self.min = min
        self.max = max

    def hasSensor(self):
        return self.sensor

    def hasTemperature(self):
        return self.temperature is not None

    def hasLux(self):
        return self.lux is not None

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
            result = subprocess.call([self.script, '-t', "%d" % temperature, filename +
                                      '[0]', filenameTemp], stderr=self.void) == 0
            if os.path.exists(filenameTemp + '.cache'):
                logging.warning('colormatch called without filename extension, lingering .cache file will stay behind')

            return result
        except Exception:
            logging.exception('Unable to run %s:', self.script)
            return False

    def adjustableMonitor(self):
        return self.mon_adjust
    
    def setMonBright(self):
        brightness = self.lux * self.lux_scale
        if brightness > self.mon_max_bright:
            brightness = self.mon_max_bright
        if brightness < self.mon_min_bright:
            brightness = self.mon_min_bright
        try:
            debug.subprocess_call(['/usr/bin/ddcutil', 'setvcp', '10', repr(int(brightness))])
            logging.debug('setMonBright set monitor to %s percent' % repr(int(brightness)))
        except:
            logging.debug('setMonBright failed to set monitor to %s' % repr(int(brightness)))
            return False
        return True
            
    def setMonTemp(self):
        temp = self.temperature
        if self.max:
            if temp > self.max:
                temp = self.max
        if self.min:
            if temp < self.min:
                temp = self.min
        if temp > self.mon_max_temp:
            temp = self.mon_max_temp
        if temp < self.mon_min_temp:
            temp = self.mon_min_temp
        tempset = int((temp - self.mon_min_temp)/self.mon_temp_inc)
        if tempset > self.mon_max_inc:
            tempset = self.mon_max_inc
        try:
            debug.subprocess_call(['/usr/bin/ddcutil', 'setvcp', '0C', repr(tempset)])
            logging.debug('setMonTempt set monitor to %s temp' % repr(temp))
        except:
            logging.debug('setMonTemp failed to set monitor to %s' % repr(temp))
            return False
        return True

    ###################################################################################
    # It seems that there is a widespread sharing of incorrect code to read the TCS3472.
    #
    # The following is based on the equations and coefficients provided by the manufacturer
    # (AMS) in their Application Note DN40-Rev 1.0 Appendix I
    # While it's hard to test this without expensive equipment, I was able to get a temp reading
    # very close to 2700K using LED lighting from a bulb with the same spec.
    #
    # Note, if a sensor other than a TCS3472 is used, these will no longer be correct.
    # However this is correct for TCS34721, TCS34723, TCS34725 and TCS34727
    #
    # Finally, the vairable sensor_scale is used to compensate for light attenuation for sensors
    # behind glass, or in some cases behind acrylic rods.
    #
    def _temperature_and_lux(self, r, g, b, c, tms_gain, tms_atime):
        itime = (256 - tms_atime) * 2.4
        gain_table = {0: 1, 1: 4, 2: 16, 3: 60}
        gain = gain_table[tms_gain]
        if (self.sensor_scale <= 0):
            cpl = 1.0  # protect from bad settings
        else:
            cpl = (gain * itime) / (self.sensor_scale * 310)
        ir = float(r + g + b - c)/2
        rp = float(r) - ir
        gp = float(g) - ir
        bp = float(b) - ir
        lux = ((.136 * rp) + gp - (.444 * bp))/cpl
        if (lux < 0):
            lux = 0
        if (rp == 0):
            temp = self.default_temp
        else:
            temp = (3810 * ( bp / rp )) + 1391
        return temp, lux
    
    
    def run(self):
        try:
            bus = smbus.SMBus(1)
        except Exception:
            logging.info('No SMB subsystem, color sensor unavailable')
            return
        # I2C address 0x29
        # Register 0x12 has device ver.
        # Register addresses must be OR'ed with 0x80
        try:
            bus.write_byte(0x29, 0x80 | 0x12)
        except Exception:
            logging.info('ColorSensor not available')
            return
        ver = bus.read_byte(0x29)
        # version # should be 0x44 or 0x4D
        if (ver == 0x44) or (ver == 0x4D):
            # Make sure we have the needed script
            if not (os.path.exists(self.script) or self.mon_adjust):
                logging.info(
                    'No color temperature script or adjustable monitor detected, download the script from '
                    'http://www.fmwconcepts.com/imagemagick/colortemp/index.php and save as "%s"' % self.script
                )
                self.allowAdjust = False
            else:
                self.allowAdjust = True
            self.sensor = True
            
            # Configure Sensor
            # Todo - The app note suggests checking the clear value, and if it's less than 100,
            # to change the gain to increase sensitivity.  That's not yet implemented here.
            # Lok here for algorithm:
            # https://ams.com/documents/20143/36005/AmbientLightSensors_AN000171_2-00.pdf/9d1f1cd6-4b2d-1de7-368f-8b372f3d8517
            #
            tms_gain = 0x1    # Must be 0, 1, 2, 3 which become 1x, 4x, 16x, and 60x gain
            tms_atime = 0x0   # Must be 0xFF, 0xF6, 0xDB, 0xC0, 0x00 which become 2.4, 24, 101, 154, 700ms
            tms_wtime = 0xFF  # Must be 0xFF, 0xAB, 0x00 which become 2.4, 204 614ms
            
            bus.write_byte(0x29, 0x80 | 0x00)  # 0x00 = ENABLE register
            bus.write_byte(0x29, 0x01 | 0x02)  # 0x01 = Power on, 0x02 RGB sensors enabled
            bus.write_byte(0x29, 0x80 | 0x01)  # 0x01 = ATIME (Integration time) register
            bus.write_byte(0x29, tms_atime)
            bus.write_byte(0x29, 0x80 | 0x03)  # 0x03 = WTIME (Wait) register
            bus.write_byte(0x29, tms_wtime)
            bus.write_byte(0x29, 0x80 | 0x0F)  # 0x0F = Control register
            bus.write_byte(0x29, tms_gain)
            
            
            bus.write_byte(0x29, 0x80 | 0x14)  # Reading results start register 14, LSB then MSB
            logging.debug('TCS34725 detected, starting polling loop')
            while True:
                data = bus.read_i2c_block_data(0x29, 0)
                clear = clear = data[1] << 8 | data[0]
                red = data[3] << 8 | data[2]
                green = data[5] << 8 | data[4]
                blue = data[7] << 8 | data[6]
                
                self.temperature, self.lux = self._temperature_and_lux(red, green, blue, clear, tms_gain, tms_atime)
                                  
                if self.listener:
                    self.listener(self.temperature, self.lux)
                    
                if self.mon_adjust:
                    logging.debug('Adjusting monitor to %3.2f lux and %5.0fK temp' % (self.lux, self.temperature))
                    self.setMonBright()
                    self.setMonTemp()

                time.sleep(15)  # Not sure how often it's acceptable to change monitor settings
        else:
            logging.info('No TCS34725 color sensor detected, will not compensate for ambient color temperature')
            self.sensor = False
