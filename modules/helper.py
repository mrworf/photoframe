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
import subprocess
import socket
import logging
import os
import shutil
import re
import random
import time
from . import debug

# A regular expression to determine whether a url is valid or not
# (e.g. "www.example.de/someImg.jpg" is missing "http://")
VALID_URL_REGEX = re.compile(
    r'^(?:http|ftp)s?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


class helper:
    TOOL_ROTATE = '/usr/bin/jpegtran'

    MIMETYPES = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/bmp': 'bmp'
        # HEIF to be added once I get ImageMagick running with support
    }

    @staticmethod
    def isValidUrl(url):
        # Catches most invalid URLs
        if re.match(VALID_URL_REGEX, url) is None:
            return False
        return True

    @staticmethod
    def getWeightedRandomIndex(weights):
        totalWeights = sum(weights)
        normWeights = [float(w)/totalWeights for w in weights]
        x = random.SystemRandom().random()
        for i in range(len(normWeights)):
            x -= normWeights[i]
            if x <= 0.:
                return i

    @staticmethod
    def getResolution():
        res = None
        output = debug.subprocess_check_output(['/bin/fbset'], stderr=subprocess.DEVNULL)
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('mode "'):
                res = line[6:-1]
                break
        return res

    @staticmethod
    def getDeviceIp():
        try:
            import netifaces
            if 'default' in netifaces.gateways() and netifaces.AF_INET in netifaces.gateways()['default']:
                dev = netifaces.gateways()['default'][netifaces.AF_INET][1]
                if netifaces.ifaddresses(dev) and netifaces.AF_INET in netifaces.ifaddresses(dev):
                    net = netifaces.ifaddresses(dev)[netifaces.AF_INET]
                    if len(net) > 0 and 'addr' in net[0]:
                        return net[0]['addr']
        except ImportError:
            logging.error('User has not installed python-netifaces, using checkNetwork() instead (depends on internet)')
            return helper._checkNetwork()
        except Exception:
            logging.exception('netifaces call failed, using checkNetwork() instead (depends on internet)')
            return helper._checkNetwork()

    @staticmethod
    def _checkNetwork():
        ip = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("photoframe.sensenet.nu", 80))
            ip = s.getsockname()[0]

            s.close()
        except Exception:
            logging.exception('Failed to get IP via old method')
        return ip

    @staticmethod
    def getExtension(mime):
        mime = mime.lower()
        if mime in helper.MIMETYPES:
            return helper.MIMETYPES[mime]
        return None

    @staticmethod
    def getSupportedTypes():
        ret = []
        for i in helper.MIMETYPES:
            ret.append(i)
        return ret

    @staticmethod
    def getMimetype(filename):
        if not os.path.isfile(filename):
            return None

        mimetype = ''
        cmd = ["/usr/bin/file", "--mime", filename]
        with open(os.devnull, 'wb') as void:
            try:
                output = debug.subprocess_check_output(cmd, stderr=void).strip("\n")
                m = re.match('[^\\:]+\\: *([^;]+)', output)
                if m:
                    mimetype = m.group(1)
            except subprocess.CalledProcessError:
                logging.debug("unable to determine mimetype of file: %s" % filename)
                return None
        return mimetype

    @staticmethod
    def copyFile(orgFilename, newFilename):
        try:
            shutil.copyfile(orgFilename, newFilename)
        except Exception:
            logging.exception('Unable copy file from "%s" to "%s"' % (orgFilename, newFilename))
            return False
        return True

    @staticmethod
    def scaleImage(orgFilename, newFilename, newSize):
        cmd = [
            'convert',
            orgFilename + '[0]',
            '-scale',
            '%sx%s' % (newSize["width"], newSize["height"]),
            '+repage',
            newFilename
        ]

        try:
            debug.subprocess_check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            logging.exception('Unable to reframe the image')
            logging.error('Output: %s' % repr(e.output))
            return False
        return True

    @staticmethod
    def getImageSize(filename):
        if not os.path.isfile(filename):
            logging.warning('File %s does not exist, so cannot get dimensions', filename)
            return None

        with open(os.devnull, 'wb') as void:
            try:
                output = debug.subprocess_check_output(['/usr/bin/identify', filename], stderr=void)
            except Exception:
                logging.exception('Failed to run identify to get image dimensions on %s', filename)
                return None

        m = re.search('([1-9][0-9]*)x([1-9][0-9]*)', output)
        if m is None or m.groups() is None or len(m.groups()) != 2:
            logging.error('Unable to resolve regular expression for image size')
            return None

        imageSize = {}
        imageSize["width"] = int(m.group(1))
        imageSize["height"] = int(m.group(2))

        return imageSize

    @staticmethod
    def makeFullframe(filename, displayWidth, displayHeight, zoomOnly=False, autoChoose=False):
        imageSize = helper.getImageSize(filename)
        if imageSize is None:
            logging.warning('Cannot frame %s since we cannot determine image dimensions', filename)
            return filename

        width = imageSize["width"]
        height = imageSize["height"]

        p, f = os.path.split(filename)
        filenameProcessed = os.path.join(p, "framed_" + f)

        width_border = 15
        width_spacing = 3
        border = None
        spacing = None

        # Calculate actual size of image based on display
        oar = (float)(width) / (float)(height)
        dar = (float)(displayWidth) / (float)(displayHeight)

        if not zoomOnly:
            if oar >= dar:
                adjWidth = displayWidth
                adjHeight = int(float(displayWidth) / oar)
            else:
                adjWidth = int(float(displayHeight) * oar)
                adjHeight = displayHeight

            logging.debug('Size of image is %dx%d, screen is %dx%d. New size is %dx%d',
                          width, height, displayWidth, displayHeight, adjWidth, adjHeight)

            if width < 100 or height < 100:
                logging.error('Image size is REALLY small, please check "%s" ... something isn\'t right', filename)
                # a=1/0

            if adjHeight < displayHeight:
                border = '0x%d' % width_border
                spacing = '0x%d' % width_spacing
                padding = ((displayHeight - adjHeight) / 2 - width_border)
                resizeString = '%sx%s^'
                logging.debug('Landscape image, reframing (padding required %dpx)' % padding)
            elif adjWidth < displayWidth:
                border = '%dx0' % width_border
                spacing = '%dx0' % width_spacing
                padding = ((displayWidth - adjWidth) / 2 - width_border)
                resizeString = '^%sx%s'
                logging.debug('Portrait image, reframing (padding required %dpx)' % padding)
            else:
                resizeString = '%sx%s'
                logging.debug('Image is fullscreen, no reframing needed')
                return filename

            if padding < 20 and not autoChoose:
                logging.debug('That\'s less than 20px so skip reframing (%dx%d => %dx%d)',
                              width, height, adjWidth, adjHeight)
                return filename

            if padding < 60 and autoChoose:
                zoomOnly = True

        if zoomOnly:
            if oar <= dar:
                adjWidth = displayWidth
                adjHeight = int(float(displayWidth) / oar)
                logging.debug('Size of image is %dx%d, screen is %dx%d. New size is %dx%d  --> cropped to %dx%d',
                              width,
                              height,
                              displayWidth,
                              displayHeight,
                              adjWidth,
                              adjHeight,
                              displayWidth,
                              displayHeight)
            else:
                adjWidth = int(float(displayHeight) * oar)
                adjHeight = displayHeight
                logging.debug('Size of image is %dx%d, screen is %dx%d. New size is %dx%d --> cropped to %dx%d',
                              width,
                              height,
                              displayWidth,
                              displayHeight,
                              adjWidth,
                              adjHeight,
                              displayWidth,
                              displayHeight)

        cmd = None
        try:
            # Time to process
            if zoomOnly:
                cmd = [
                    'convert',
                    filename + '[0]',
                    '-resize',
                    '%sx%s' % (adjWidth, adjHeight),
                    '-gravity',
                    'center',
                    '-crop',
                    '%sx%s+0+0' % (displayWidth, displayHeight),
                    '+repage',
                    filenameProcessed
                ]
            else:
                cmd = [
                    'convert',
                    filename + '[0]',
                    '-resize',
                    resizeString % (displayWidth, displayHeight),
                    '-gravity',
                    'center',
                    '-crop',
                    '%sx%s+0+0' % (displayWidth, displayHeight),
                    '+repage',
                    '-blur',
                    '0x12',
                    '-brightness-contrast',
                    '-20x0',
                    '(',
                    filename + '[0]',
                    '-bordercolor',
                    'black',
                    '-border',
                    border,
                    '-bordercolor',
                    'black',
                    '-border',
                    spacing,
                    '-resize',
                    '%sx%s' % (displayWidth, displayHeight),
                    '-background',
                    'transparent',
                    '-gravity',
                    'center',
                    '-extent',
                    '%sx%s' % (displayWidth, displayHeight),
                    ')',
                    '-composite',
                    filenameProcessed
                ]
        except Exception:
            logging.exception('Error building command line')
            logging.debug('Filename: ' + repr(filename))
            logging.debug('filenameProcessed: ' + repr(filenameProcessed))
            logging.debug('border: ' + repr(border))
            logging.debug('spacing: ' + repr(spacing))
            return filename

        try:
            debug.subprocess_check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            logging.exception('Unable to reframe the image')
            logging.error('Output: %s' % repr(e.output))
            return filename
        os.unlink(filename)
        return filenameProcessed

    @staticmethod
    def timezoneList():
        zones = subprocess.check_output(['/usr/bin/timedatectl', 'list-timezones']).split('\n')
        return [x for x in zones if x]

    @staticmethod
    def timezoneCurrent():
        with open('/etc/timezone', 'r') as f:
            result = f.readlines()
        return result[0].strip()

    @staticmethod
    def timezoneSet(zone):
        result = 1
        try:
            with open(os.devnull, 'wb') as void:
                result = subprocess.check_call(['/usr/bin/timedatectl', 'set-timezone', zone], stderr=void)
        except Exception:
            logging.exception('Unable to change timezone')
            pass
        return result == 0

    @staticmethod
    def hasNetwork():
        return helper._checkNetwork() is not None

    @staticmethod
    def waitForNetwork(funcNoNetwork, funcExit):
        shownError = False
        while True and not funcExit():
            if not helper.hasNetwork():
                funcNoNetwork()
                if not shownError:
                    logging.error('You must have functional internet connection to use this app')
                    shownError = True
                time.sleep(10)
            else:
                logging.info('Network connection reestablished')
                break

    @staticmethod
    def autoRotate(ifile):
        if not os.path.exists('/usr/bin/jpegexiforient'):
            logging.warning(
                'jpegexiforient is missing, no auto rotate available. '
                'Did you forget to run "apt install libjpeg-turbo-progs" ?'
            )
            return ifile

        p, f = os.path.split(ifile)
        ofile = os.path.join(p, "rotated_" + f)

        # First, use jpegexiftran to determine orientation
        parameters = ['', '-flip horizontal', '-rotate 180', '-flip vertical',
                      '-transpose', '-rotate 90', '-transverse', '-rotate 270']
        with open(os.devnull, 'wb') as void:
            result = subprocess.check_output(['/usr/bin/jpegexiforient', ifile])  # , stderr=void)
        if result:
            orient = int(result)-1
            if orient < 0 or orient >= len(parameters):
                logging.info('Orientation was %d, not transforming it', orient)
                return ifile
            cmd = [helper.TOOL_ROTATE]
            cmd.extend(parameters[orient].split())
            cmd.extend(['-outfile', ofile, ifile])
            with open(os.devnull, 'wb') as void:
                result = subprocess.check_call(cmd, stderr=void)
            if result == 0:
                os.unlink(ifile)
                return ofile
        return ifile
