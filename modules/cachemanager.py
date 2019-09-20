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
import os
import time
import shutil

from modules.path import path as syspath

### CONSTANTS ###

MIN = 60
HOUR = MIN * 60
DAY = HOUR * 24
MONTH = DAY * 30
YEAR = DAY * 365

KB = 10**3
MB = KB * 10**3
GB = MB * 10**3
#NOTE: all values are in Bytes!

##################

class CacheManager:
  STATE_HEAPS = 0
  STATE_ENOUGH = 1
  STATE_WORRISOME = 2
  STATE_CRITICAL = 3
  STATE_FULL = 4

  def __init__(self):
    self.enable = True

  def enableCache(self, enable):
    self.enable = enable
    logging.info('Cache is set to %s' + repr(enable))

  def validate(self):
    self.createDirs()
    self.garbageCollect()

  def formatBytes(self, size):
    if size > 0.1*GB:
      return "%.1fGB" % (float(size)/GB)
    elif size > 0.1*MB:
      return "%.1fMB" % (float(size)/MB)
    elif size > 0.1*KB:
      return "%.1fKB" % (float(size)/KB)
    return "%dB" % size

  def getCachedImage(self, cacheId, destination):
    if not self.enable:
      return None

    filename = os.path.join(syspath.CACHEFOLDER, cacheId)
    if os.path.isfile(filename):
      try:
        shutil.copy(filename, destination)
        logging.debug('Cache hit, using %s as %s', cacheId, destination)
        return destination
      except:
        logging.exception('Failed to copy cached image')
    return None

  def setCachedImage(self, filename, cacheId):
    if not self.enable:
      return None

    # Will copy the file if possible, otherwise
    # copy/delete it.
    cacheFile = os.path.join(syspath.CACHEFOLDER, cacheId)
    try:
      if os.path.exists(cacheFile):
        os.unlink(cacheFile)
      shutil.copy(filename, cacheFile)
      logging.debug('Cached %s as %s', filename, cacheId)
      return filename
    except:
      logging.exception('Failed to ownership of file')
      return None

  def createDirs(self, subDirs=[]):
    if not os.path.exists(syspath.CACHEFOLDER):
      os.mkdir(syspath.CACHEFOLDER)
    for subDir in[os.path.join(syspath.CACHEFOLDER, d) for d in subDirs]:
      if not os.path.exists(subDir):
        os.mkdir(subDir)

  # delete all files but keep directory structure intact
  def empty(directory = syspath.CACHEFOLDER):
    freedUpSpace = 0
    if not os.path.isdir(directory):
      logging.exception('Failed to delete "%s". Directory does not exist!' % directory)
      return freedUpSpace

    for p, _dirs, files in os.walk(directory):
      for filename in [os.path.join(p, f) for f in files]:
        freedUpSpace += os.stat(filename).st_size
        try:
          os.unlink(filename)
        except:
          logging.exception('Failed to delete "%s"' % filename)
    logging.info("'%s' has been emptied"%directory)
    return freedUpSpace


  # delete all files that were modified earlier than {minAge}
  # return total freedUpSpace in bytes
  def deleteOldFiles(self, topPath, minAge):
    freedUpSpace = 0
    now = time.time()
    for path, _dirs, files in os.walk(topPath):
      for filename in [os.path.join(path, f) for f in files]:
        stat = os.stat(filename)
        if stat.st_mtime < now - minAge:
          try:
            os.remove(filename)
            logging.debug("old file '%s' deleted" % filename)
            freedUpSpace += stat.st_size
          except OSError as e:
            logging.warning("unable to delete file '%s'!" % filename)
            logging.exception("Output: "+e.strerror)
    return freedUpSpace

  def getDirSize(self, path):
    size = 0
    for path, _dirs, files in os.walk(path):
      for filename in [os.path.join(path, f) for f in files]:
        size += os.stat(filename).st_size
    return size

  # classify disk space usage into five differnt states based on free/total ratio
  def getDiskSpaceState(self, path):
    # all values are in bytes!
    #dirSize = float(self.getDirSize(path))

    stat = os.statvfs(path)
    total = float(stat.f_blocks*stat.f_bsize)
    free = float(stat.f_bfree*stat.f_bsize)

    #logging.debug("'%s' takes up %s" % (path, CacheManager.formatBytes(dirSize)))
    #logging.debug("free space on partition: %s" % CacheManager.formatBytes(free))
    #logging.debug("total space on partition: %s" % CacheManager.formatBytes(total))

    if free < 50*MB:
      return CacheManager.STATE_FULL
    elif free/total < 0.1:
      return CacheManager.STATE_CRITICAL
    elif free/total < 0.2:
      return CacheManager.STATE_WORRISOME
    elif free/total < 0.5:
      return CacheManager.STATE_ENOUGH
    else:
      return CacheManager.STATE_HEAPS

  # Free up space of any tmp/cache folder
  # Frequently calling this function will make sure, less important files are deleted before having to delete more important ones.
  # Of course a manual cache reset is possible via the photoframe web interface
  def garbageCollect(self, lessImportantDirs=[]):
    #logging.debug("Garbage Collector started!")
    state = self.getDiskSpaceState(syspath.CACHEFOLDER)
    freedUpSpace = 0
    if state == CacheManager.STATE_FULL:
      freedUpSpace = self.empty(syspath.CACHEFOLDER)
    elif state == CacheManager.STATE_CRITICAL:
      for subDir in [os.path.join(syspath.CACHEFOLDER, d) for d in lessImportantDirs]:
        freedUpSpace += self.empty(subDir)
    elif state == CacheManager.STATE_WORRISOME:
      freedUpSpace = self.deleteOldFiles(syspath.CACHEFOLDER, 7*DAY)
    elif state == CacheManager.STATE_ENOUGH:
      freedUpSpace = self.deleteOldFiles(syspath.CACHEFOLDER, MONTH)
    else:
      freedUpSpace = self.deleteOldFiles(syspath.CACHEFOLDER, 6*MONTH)
    '''
    if freedUpSpace:
      logging.info("Garbage Collector was able to free up %s of disk space!" % CacheManager.formatBytes(freedUpSpace))
    else:
      logging.debug("Garbage Collector was able to free up %s of disk space!" % CacheManager.formatBytes(freedUpSpace))
    '''
