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

MIN = 60
HOUR = MIN  * 60
DAY = HOUR  * 24
MONTH = DAY * 30
YEAR = DAY  * 365

# all values are in Bytes!
KB = 10**3
MB = KB * 10**3
GB = MB * 10**3

def formatBytes(size):
  if size > 0.1*GB:
    return "%.1fGB" % (float(size)/GB)
  elif size > 0.1*MB:
    return "%.1fMB" % (float(size)/MB)
  elif size > 0.1*KB:
    return "%.1fKB" % (float(size)/KB)
  return "%dB"%size

class DiskManager:
  STATE_HEAPS = 0
  STATE_ENOUGH = 1
  STATE_WORRISOME = 2
  STATE_CRITICAL = 3
  STATE_FULL = 4

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

    for p, dirs, files in os.walk(path):
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
    for path, dirs, files in os.walk(topPath):
      for filename in [os.path.join(path, f) for f in files]:
        stat = os.stat(filename)
        if stat.st_mtime < now - minAge:
          logging.debug("deleting old file '%s'"%filename)
          freedUpSpace += stat.st_size
          os.remove(filename)
    return freedUpSpace

  @staticmethod
  def getDirSize(path):
    size = 0
    for path, dirs, files in os.walk(path):
      for filename in [os.path.join(path, f) for f in files]:
        size += os.stat(filename).st_size
    return size

  # classify disk space usage into five differnt states based on free/total ratio
  @staticmethod
  def getDiskSpaceState(path):
    # all values are in bytes!
    dirSize = float(DiskManager.getDirSize(path))

    stat = os.statvfs(path)
    total = float(stat.f_blocks*stat.f_bsize)
    free = float(stat.f_bfree*stat.f_bsize)

    logging.debug("'%s' takes up %s" % (path, formatBytes(dirSize)))
    logging.debug("free space on partition: %s" % formatBytes(free))
    logging.debug("total space on partition: %s" % formatBytes(total))

    if free < 50*MB:
      return DiskManager.STATE_FULL
    elif free/total < 0.1:
      return DiskManager.STATE_CRITICAL
    elif free/total < 0.2:
      return DiskManager.STATE_WORRISOME
    elif free/total < 0.5:
      return DiskManager.STATE_ENOUGH
    else:
      return DiskManager.STATE_HEAPS

  # Free up space of any tmp/cache folder
  # Frequently calling this function will make sure, less important files are deleted before having to delete more important ones.
  # Of course a manual cache reset is possible via the photoframe web interface
  @staticmethod
  def garbageCollect(path, lessImportantDirs):
    logging.debug("Garbage Collector started!")
    state = DiskManager.getDiskSpaceState(path)
    freedUpSpace = 0
    if state == DiskManager.STATE_FULL:
      freedUpSpace = DiskManager.empty(path)
    elif state == DiskManager.STATE_CRITICAL:
      for subDir in [os.path.join(path, d) for d in lessImportantDirs]:
        freedUpSpace += DiskManager.empty(subDir)
    elif state == DiskManager.STATE_WORRISOME:
      freedUpSpace = DiskManager.deleteOldFiles(path, 7*DAY)
    elif state == DiskManager.STATE_ENOUGH:
      freedUpSpace = DiskManager.deleteOldFiles(path, MONTH)
    else:
      freedUpSpace = DiskManager.deleteOldFiles(path, 6*MONTH)

    if freedUpSpace:
      logging.info("Garbage Collector was able to free up %s of disk space!"%formatBytes(freedUpSpace))
    else:
      logging.debug("Garbage Collector was able to free up %s of disk space!" % formatBytes(freedUpSpace))

