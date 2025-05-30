#!/usr/bin/env python3
#
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
import os
import subprocess
import logging
import time
import re
import json
from pathlib import Path

import modules.debug as debug
from modules.sysconfig import sysconfig
from modules.helper import helper

class display:
    def __init__(self, use_emulator=False, emulate_width=1280, emulate_height=720):
        self.void = open(os.devnull, 'wb')
        self.params = None
        self.special = None
        self.emulate = use_emulator
        self.emulate_width = emulate_width
        self.emulate_height = emulate_height
        self.rotated = sysconfig.isDisplayRotated()
        self.xoffset = 0
        self.yoffset = 0
        self.url = None
        if self.emulate:
            logging.info('Using framebuffer emulation')
        self.lastMessage = None

    def setConfigPage(self, url):
        self.url = url

    def setConfiguration(self, tvservice_params, special=None):
        self.enabled = True

        # Erase old picture
        if self.params is not None:
            self.clear()

        if self.emulate:
            self.width = self.emulate_width
            self.height = self.emulate_height
            self.depth = 32
            self.reverse = False
            self.format = 'rgba'
            self.params = None
            self.special = None
            return (self.width, self.height, '')

        result = display.validate(tvservice_params, special)
        if result is None:
            logging.error('Unable to find a valid display mode, will default to 1280x720')
            # TODO: THis is less than ideal, maybe we should fetch resolution from fbset instead?
            #       but then we should also avoid touching the display since it will cause issues.
            self.enabled = False
            self.params = None
            self.special = None
            return (1280, 720, '')

        self.width = result['width']
        self.height = result['height']
        self.pwidth = self.width
        self.pheight = self.height

        if self.rotated:
            # Calculate offset for X, must be even dividable with 16
            self.xoffset = (16 - (self.height % 16)) % 16
            self.width = self.pheight
            self.height = self.pwidth

        self.depth = result['depth']
        self.reverse = result['reverse']
        self.params = result['tvservice']
        if self.reverse:
            self.format = 'bgr'
        else:
            self.format = 'rgb'
        if self.depth == 32:
            self.format += 'a'

        return (self.width, self.height, self.params)

    def getDevice(self):
        if self.params and self.params.split(' ')[0] == 'INTERNAL':
            device = f'/dev/fb{self.params.split(" ")[1]}'
            if os.path.exists(device):
                return device
        return '/dev/fb0'

    def isHDMI(self):
        return self.getDevice() == '/dev/fb0' and not display._isDPI()

    def get(self):
        if self.enabled:
            args = [
                'convert',
                '-depth',
                '8',
                '-size',
                f'{self.width+self.xoffset}x{self.height+self.yoffset}',
                f'{self.format}:-',
                'jpg:-'
            ]
        else:
            args = [
                'convert',
                '-size',
                '640x360',
                '-background',
                'black',
                '-fill',
                'white',
                '-gravity',
                'center',
                '-weight',
                '700',
                '-pointsize',
                '32',
                'label:Display off',
                '-depth',
                '8',
                'jpg:-'
            ]

        if not self.enabled:
            result = debug.subprocess_check_output(args, stderr=self.void)
        elif self.depth in [24, 32]:
            device = self.getDevice()
            if self.emulate:
                device = '/tmp/fb.bin'
            with open(device, 'rb') as fb:
                pip = subprocess.Popen(args, stdin=fb, stdout=subprocess.PIPE, stderr=self.void)
                result = pip.communicate()[0]
        elif self.depth == 16:
            with open(self.getDevice(), 'rb') as fb:
                src = subprocess.Popen(['/root/photoframe/rgb565/rgb565', 'reverse'], stdout=subprocess.PIPE, stdin=fb, stderr=self.void)
                pip = subprocess.Popen(args, stdin=src.stdout, stdout=subprocess.PIPE)
                src.stdout.close()
                result = pip.communicate()[0]
        else:
            logging.error('Do not know how to grab this kind of framebuffer')
        return (result, 'image/jpeg')

    def _to_display(self, arguments):
        device = self.getDevice()
        if self.emulate:
            device = '/tmp/fb.bin'
            self.depth = 32

        if self.depth in [24, 32]:
            with open(device, 'wb') as f:
                debug.subprocess_call(arguments, stdout=f, stderr=self.void)
        elif self.depth == 16:  # Typically RGB565
            # For some odd reason, cannot pipe the output directly to the framebuffer, use temp file
            with open(device, 'wb') as fb:
                src = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=self.void)
                pip = subprocess.Popen(['/root/photoframe/rgb565/rgb565'], stdin=src.stdout, stdout=fb)
                src.stdout.close()
                pip.communicate()
        else:
            logging.error(f'Do not know how to render this, depth is {self.depth}')

        self.lastMessage = None

    def message(self, message, showConfig=True):
        if not self.enabled:
            logging.debug('Don\'t bother, display is off')
            return

        url = 'caption:'
        if helper.getDeviceIp() is not None and showConfig:
            url = f'caption:Configuration available at http://{helper.getDeviceIp()}:7777'

        args = [
            'convert',
            '-size',
            f'{self.width}x{self.height}',
            '-background',
            'black',
            '-fill',
            'white',
            '-gravity',
            'center',
            '-weight',
            '700',
            '-pointsize',
            '32',
            f'caption:{message}',
            '-background',
            'none',
            '-gravity',
            'south',
            '-fill',
            '#666666',
            url,
            '-flatten',
            '-extent',
            f'{self.width + self.xoffset}x{self.height + self.yoffset}+{self.xoffset}+{self.yoffset}',
            '-depth',
            '8',
            f'{self.format}:-'
        ]

        if self.lastMessage != message:
            self._to_display(args)
            self.lastMessage = message

    def image(self, filename):
        if not self.enabled:
            logging.debug('Don\'t bother, display is off')
            return

        logging.debug('Showing image to user')
        args = [
            'convert',
            filename + '[0]',
            '-background',
            'black',
            '-gravity',
            'center',
            '-extent',
            f'{self.width + self.xoffset}x{self.height + self.yoffset}+{self.xoffset}+{self.yoffset}',
            '-depth',
            '8',
            f'{self.format}:-'
        ]
        self._to_display(args)

    def enable(self, enable, force=False):
        if enable == self.enabled and not force:
            return

        # Do not do things if we don't know how to display
        if self.params is None:
            return

        if enable:
            if self.special:
                debug.subprocess_call(['tvservice', '-p', self.special], stderr=self.void)
            else:
                debug.subprocess_call(['tvservice', '-p', self.params], stderr=self.void)
            time.sleep(1)
            debug.subprocess_call(['fbset', '-depth', str(self.depth)], stderr=self.void)
            debug.subprocess_call(['fbset', '-g', str(self.width), str(self.height), str(self.width), str(self.height), str(self.depth)], stderr=self.void)
            debug.subprocess_call(['fbset', '-accel', 'true'], stderr=self.void)
            debug.subprocess_call(['fbset', '-move', 'up'], stderr=self.void)
            debug.subprocess_call(['fbset', '-move', 'down'], stderr=self.void)
        else:
            debug.subprocess_call(['tvservice', '-o'], stderr=self.void)

        self.enabled = enable

    def isEnabled(self):
        return self.enabled

    def clear(self):
        if not self.enabled:
            return

        args = [
            'convert',
            '-size',
            f'{self.width + self.xoffset}x{self.height + self.yoffset}',
            'xc:black',
            '-depth',
            '8',
            f'{self.format}:-'
        ]
        self._to_display(args)

    @staticmethod
    def _isDPI():
        try:
            with open('/proc/device-tree/soc/video@7e900000/status', 'r') as f:
                return f.read().strip() == 'okay'
        except:
            return False

    @staticmethod
    def _internaldisplay():
        try:
            with open('/proc/device-tree/soc/video@7e900000/status', 'r') as f:
                return f.read().strip() == 'okay'
        except:
            return False

    def current(self):
        if self.params is None:
            return None

        result = {}
        result['width'] = self.pwidth
        result['height'] = self.pheight
        result['depth'] = self.depth
        result['tvservice'] = self.params
        result['special'] = self.special
        result['rotated'] = self.rotated
        return result

    @staticmethod
    def available():
        result = []
        try:
            output = subprocess.check_output(['tvservice', '-m', 'CEA'], stderr=subprocess.DEVNULL).decode('utf-8')
            for line in output.split('\n'):
                if line.startswith('mode '):
                    result.append(line[5:])
        except:
            pass

        try:
            output = subprocess.check_output(['tvservice', '-m', 'DMT'], stderr=subprocess.DEVNULL).decode('utf-8')
            for line in output.split('\n'):
                if line.startswith('mode '):
                    result.append(line[5:])
        except:
            pass

        return result

    @staticmethod
    def validate(tvservice, special):
        # Takes a string and returns valid width, height, depth and service
        if special:
            try:
                output = subprocess.check_output(['tvservice', '-s'], stderr=subprocess.DEVNULL).decode('utf-8')
                if output.find(special) != -1:
                    return {
                        'width': 1280,
                        'height': 720,
                        'depth': 32,
                        'reverse': False,
                        'tvservice': special
                    }
            except:
                pass

        if not tvservice:
            return None

        try:
            output = subprocess.check_output(['tvservice', '-s'], stderr=subprocess.DEVNULL).decode('utf-8')
            if output.find(tvservice) == -1:
                return None
        except:
            return None

        try:
            output = subprocess.check_output(['tvservice', '-v', tvservice], stderr=subprocess.DEVNULL).decode('utf-8')
            m = re.search(r'(\d+)x(\d+)', output)
            if m:
                width = int(m.group(1))
                height = int(m.group(2))
                depth = 32
                reverse = False
                return {
                    'width': width,
                    'height': height,
                    'depth': depth,
                    'reverse': reverse,
                    'tvservice': tvservice
                }
        except:
            pass

        return None
