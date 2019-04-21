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

from modules.helper import helper

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

  @staticmethod
  def formatBytes(size):
    if size > 0.1*GB:
      return "%.1fGB" % (float(size)/GB)
    elif size > 0.1*MB:
      return "%.1fMB" % (float(size)/MB)
    elif size > 0.1*KB:
      return "%.1fKB" % (float(size)/KB)
    return "%dB" % size

  @staticmethod
  def useCachedImage(filename):
    # check if ImageMagick can determine the imageSize
    # otherwise the image is probably currupted and should not be used anymore
    if helper.getImageSize(filename) is not None:
      logging.debug("using cached image: '%s'" % filename)
      return True
    elif os.path.isfile(filename):
      logging.debug("Deleting currupted (cached) image: %s" % filename)
      os.unlink(filename)
    return False

  @staticmethod
  def createDirs(path, subDirs=[]):
    if not os.path.exists(path):
      os.mkdir(path)
    for subDir in[os.path.join(path, d) for d in subDirs]:
      if not os.path.exists(subDir):
        os.mkdir(subDir)

  # delete all files but keep directory structure intact
  @staticmethod
  def empty(path):
    freedUpSpace = 0
    if not os.path.isdir(path):
      logging.exception('Failed to delete "%s". Directory does not exist!' % path)
      return freedUpSpace

    for p, _dirs, files in os.walk(path):
      for filename in [os.path.join(p, f) for f in files]:
        freedUpSpace += os.stat(filename).st_size
        try:
          os.unlink(filename)
        except:
          logging.exception('Failed to delete "%s"' % filename)
    logging.info("'%s' has been emptied"%path)
    return freedUpSpace


  # delete all files that were modified earlier than {minAge}
  # return total freedUpSpace in bytes
  @staticmethod
  def deleteOldFiles(topPath, minAge):
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

  @staticmethod
  def getDirSize(path):
    size = 0
    for path, _dirs, files in os.walk(path):
      for filename in [os.path.join(path, f) for f in files]:
        size += os.stat(filename).st_size
    return size

  # classify disk space usage into five differnt states based on free/total ratio
  @staticmethod
  def getDiskSpaceState(path):
    # all values are in bytes!
    dirSize = float(CacheManager.getDirSize(path))

    stat = os.statvfs(path)
    total = float(stat.f_blocks*stat.f_bsize)
    free = float(stat.f_bfree*stat.f_bsize)

    logging.debug("'%s' takes up %s" % (path, CacheManager.formatBytes(dirSize)))
    logging.debug("free space on partition: %s" % CacheManager.formatBytes(free))
    logging.debug("total space on partition: %s" % CacheManager.formatBytes(total))

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
  @staticmethod
  def garbageCollect(path, lessImportantDirs):
    logging.debug("Garbage Collector started!")
    state = CacheManager.getDiskSpaceState(path)
    freedUpSpace = 0
    if state == CacheManager.STATE_FULL:
      freedUpSpace = CacheManager.empty(path)
    elif state == CacheManager.STATE_CRITICAL:
      for subDir in [os.path.join(path, d) for d in lessImportantDirs]:
        freedUpSpace += CacheManager.empty(subDir)
    elif state == CacheManager.STATE_WORRISOME:
      freedUpSpace = CacheManager.deleteOldFiles(path, 7*DAY)
    elif state == CacheManager.STATE_ENOUGH:
      freedUpSpace = CacheManager.deleteOldFiles(path, MONTH)
    else:
      freedUpSpace = CacheManager.deleteOldFiles(path, 6*MONTH)

    if freedUpSpace:
      logging.info("Garbage Collector was able to free up %s of disk space!" % CacheManager.formatBytes(freedUpSpace))
    else:
      logging.debug("Garbage Collector was able to free up %s of disk space!" % CacheManager.formatBytes(freedUpSpace))

