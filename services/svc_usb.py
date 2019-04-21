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

from base import BaseService
import random
import subprocess
import os
import logging

from modules.helper import helper


class USB_Photos(BaseService):
  SERVICE_NAME = 'USB-Photos'
  SERVICE_ID = 4

  USB_DIR = "/mnt/usb"
  BASE_DIR = "/mnt/usb/photoframe"

  def __init__(self, configDir, id, name):
    BaseService.__init__(self, configDir, id, name, needConfig=False, needOAuth=False)

  def preSetup(self):
    self.device = None
    if not os.path.exists(USB_Photos.BASE_DIR):
      self.mountStorageDevice()
    else:
      self.checkForInvalidKeywords()
      for device, mountPath in self.detectAllStorageDevices(onlyMounted=True):
        if mountPath == USB_Photos.USB_DIR:
          self.device = device
          logging.info("USB-Service has detected device '%s'" % self.device)
          break
      if device is None:
        # Service should still be working fine
        logging.warning("Unable to determine which storage device is mounted to '%s'" % USB_Photos.USB_DIR)

  def helpKeywords(self):
    return "Place photo albums in /photoframe/{album_name} on your usb-device.\nUse the {album_name} as keyword (CasE-seNsitiVe!).\nIf you want to display all albums simply write 'ALLALBUMS' as keyword.\nAlternatively, place images directly inside the '/photoframe/' directory. "

  def validateKeywords(self, keyword):
    # Quick check, don't allow duplicates!
    if keyword in self.getKeywords():
      logging.error('Album was already in list')
      return {'error': 'Album already in list', 'keywords': keyword}

    if keyword != 'ALLALBUMS':
      if keyword not in self.getAllAlbumNames():
        return {'error': 'No such album "%s"' % keyword, 'keywords': keyword}

    return {'error': None, 'keywords': keyword, 'extras': None}

  def getKeywords(self):
    if not os.path.exists(USB_Photos.BASE_DIR):
      #wrong error TODO
      return []

    keywords = list(self._STATE['_KEYWORDS'])
    if "ALLALBUMS" in keywords:
      # No, you can't have an album called /photoframe/ALLALBUMS ...
      keywords.remove("ALLALBUMS")
      albums = self.getAllAlbumNames()
      keywords.extend(filter(lambda a: a not in keywords, albums))

    if len(keywords) == 0 and len(self.getBaseDirImages()) != 0 and "_PHOTOFRAME_" not in keywords:
      keywords.append("_PHOTOFRAME_")
      # _PHOTOFRAME_ can be manually deleted via web interface if other keywords are specified!

    self._STATE['_KEYWORDS'] = keywords
    self.saveState()
    return keywords

  def checkForInvalidKeywords(self):
    index = len(self._STATE['_KEYWORDS'])-1
    for keyword in reversed(self._STATE['_KEYWORDS']):
      if keyword == "_PHOTOFRAME_":
        if len(self.getBaseDirImages()) == 0:
          logging.debug("USB-Service: removing keyword '%s' because there are no images directly inside the basedir!" % keyword)
          self.removeKeywords(index)
      elif keyword not in self.getAllAlbumNames():
        logging.info("USB-Service: removing invalid keyword: %s" % keyword)
        self.removeKeywords(index)
      index -= 1

  def updateState(self):
    state = None
    if not os.path.exists(USB_Photos.BASE_DIR):
      if not self.mountStorageDevice():
        state = BaseService.STATE_NOT_CONNECTED
    if len(self.getAllAlbumNames()) == 0 and len(self.getBaseDirImages()) == 0:
      self.unmountBaseDir()
      state = BaseService.STATE_NO_IMAGES
    if state is None:
      state = BaseService.updateState(self)

    self._CURRENT_STATE = state
    return self._CURRENT_STATE

  def explainState(self):
    if self._CURRENT_STATE == BaseService.STATE_NOT_CONNECTED:
      return "no storage device (e.g. USB-stick) detected!"
    elif self._CURRENT_STATE == BaseService.STATE_NO_IMAGES:
      return "no images could be found!\nPlace images and/or albums inside a '/photoframe'-directory on your storage device"
    return None

  def getMessages(self):
    if os.path.exists(USB_Photos.BASE_DIR):
      msgs = BaseService.getMessages(self)
    else:
      msgs = [
          {
              'level': 'WARNING',
              'message': 'No storage device could be found that contains the "/photoframe/"-directory!',
              'link': None
          }
      ]
    return msgs

  def detectAllStorageDevices(self, onlyMounted=False, onlyUnmounted=False, reverse=False):
    storageDevices = []
    try:
      fdisk = subprocess.Popen(["lsblk", "-p", "--noheadings", "--raw", "-o", "NAME,MOUNTPOINT"], stdout=subprocess.PIPE)
      grep = subprocess.Popen(["grep", "/dev/sd.1"], stdin=fdisk.stdout, stdout=subprocess.PIPE)
      fdisk.stdout.close()
      output = grep.communicate()[0].strip()
      if output != "":
        devices = [d.strip() for d in output.split("\n") if d.strip() != ""]
        for sd, mountPath in map(lambda d: d.split(" ", 1) if d.find(" ") != -1 else (d, None), devices):
          if onlyMounted and mountPath is not None:
            storageDevices.append((sd, mountPath))
          elif onlyUnmounted and mountPath is not None:
            logging.debug("'%s' is already mounted to '%s'" % (sd, mountPath))
          else:
            storageDevices.append(sd)
    except subprocess.CalledProcessError as e:
      logging.exception('USB-Service: unable to detect storage devices!')
      logging.error('Output: %s' % repr(e.output))

    # reverse list, because last plugged in storage device is probably the one we are looking for
    if reverse:
      storageDevices.reverse()
    return storageDevices

  def mountStorageDevice(self, storageDevices=None):
    if not os.path.exists(USB_Photos.USB_DIR):
      cmd = ["sudo", "mkdir", USB_Photos.USB_DIR]
      try:
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)
      except subprocess.CalledProcessError as e:
        logging.exception('Unable to create directory: %s' % cmd[-1])
        logging.error('Output: %s' % repr(e.output))

    if storageDevices is None:
      storageDevices = self.detectAllStorageDevices(onlyUnmounted=True, reverse=True)
    elif isinstance(storageDevices, basestring):
      storageDevices = list(storageDevices)

    # unplugging/replugging usb-stick causes system to detect it as a new storage device!
    for device in storageDevices:
      cmd = ["sudo", "mount", device, USB_Photos.USB_DIR]
      try:
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        logging.info("USB-device '%s' successfully mounted to '%s'!" % (cmd[-2], cmd[-1]))
        if os.path.exists(USB_Photos.BASE_DIR):
          self.device = device
          self.checkForInvalidKeywords()
          return True
      except subprocess.CalledProcessError as e:
        logging.warning('Unable to mount storage device "%s" to "%s"!' % (device, USB_Photos.USB_DIR))
        logging.warning('Output: %s' % repr(e.output))

    logging.debug("unable to mount any storage device %s to '%s'" % (storageDevices, USB_Photos.USB_DIR))
    return False

  def unmountBaseDir(self):
    cmd = ["sudo", "umount", USB_Photos.USB_DIR]
    try:
      subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
      logging.debug("unable to UNMOUNT '%s'" % USB_Photos.USB_DIR)

  # All images directly inside '/photoframe' directory will be displayed without any keywords
  def getBaseDirImages(self):
    return filter(lambda x: os.path.isfile(os.path.join(USB_Photos.BASE_DIR, x)), os.listdir(USB_Photos.BASE_DIR))

  def getAllAlbumNames(self):
    return filter(lambda x: os.path.isdir(os.path.join(USB_Photos.BASE_DIR, x)), os.listdir(USB_Photos.BASE_DIR))

  def selectImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize, randomize):
    result = BaseService.selectImageFromAlbum(self, destinationDir, supportedMimeTypes, displaySize, randomize)
    if result is not None:
      return result

    if os.path.exists(USB_Photos.USB_DIR):
      return {'id': None, 'mimetype': None, 'error': 'No images could be found on storage device "%s"!\n\nPlease place albums inside /photoframe/{album_name} directory and add each {album_name} as keyword.\n\nAlternatively, put images directly inside the "/photoframe/"-directory on your storage device.' % self.device}
    else:
      return {'id': None, 'mimetype': None, 'error': 'No external storage device detected! Please connect a USB-stick!\n\n Place albums inside /photoframe/{album_name} directory and add each {album_name} as keyword.\n\nAlternatively, put images directly inside the "/photoframe/"-directory on your storage device.'}

  def getImagesFor(self, keyword):
    if not os.path.isdir(USB_Photos.BASE_DIR):
      #no usb device connected?
      return []
    images = []
    if keyword == "_PHOTOFRAME_":
      files = self.getBaseDirImages()
      images = self.getAlbumInfo(USB_Photos.BASE_DIR, files)
    else:
      if os.path.isdir(os.path.join(USB_Photos.BASE_DIR, keyword)):
        files = os.listdir(os.path.join(USB_Photos.BASE_DIR, keyword))
        images = self.getAlbumInfo(os.path.join(USB_Photos.BASE_DIR, keyword), files)
      else:
        logging.warning("The album '%s' does not exist. Did you unplug the storage device assosiated with '%s'?!" % (os.path.join(USB_Photos.BASE_DIR, keyword), self.device))
    return images

  def getAlbumInfo(self, path, files):
    images = []
    for filename in files:
      fullFilename = os.path.join(path, filename)
      images.append({
          "id": self.hashString(fullFilename),
          "url": fullFilename,
          "source": fullFilename,
          "mimetype": helper.getMimeType(fullFilename),
          "size": helper.getImageSize(fullFilename),
          "filename": filename
      })
    return images

  def addUrlParams(self, url, recommendedSize, displaySize):
    if recommendedSize is None:
      return url
    return "%s||%d||%d" % (url, recommendedSize["width"], recommendedSize["height"])

  def requestUrl(self, url, destination=None, params=None, data=None, usePost=False):
    # pretend to download the file (for compatability with 'selectImageFromAlbum' of baseService)
    # instead just cache a scaled version of the file and return {status: 200}
    if url.count("||") == 2:
      filename, width, height = url.split("||", 2)
      recSize = {"width": width, "height": height}
    else:
      filename = url
      recSize = None

    if destination is None or not os.path.isfile(filename):
      return {"status": 400}
    if recSize is not None:
      if helper.scaleImage(filename, destination, recSize):
        return {"status": 200}
    else:
      if helper.copyFile(filename, destination):
        return {"status": 200}
    return {"status": 418}
