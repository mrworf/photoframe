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
import logging

class path:
  BASEDIR = '/root/'
  CONFIGFOLDER  = '/root/photoframe_config'
  CONFIGFILE    = '/root/photoframe_config/settings.json'
  COLORMATCH    = '/root/photoframe_config/colortemp.sh'
  OPTIONSFILE   = '/root/photoframe_config/options'
  CACHEFOLDER   = '/root/cache/'
  HISTORYFOLDER = '/root/history/'

  DRV_BUILTIN   = '/root/photoframe/display-drivers'
  DRV_EXTERNAL  = '/root/photoframe_config/display-drivers/'

  CONFIG_TXT    = '/boot/config.txt'

  def reassignConfigTxt(self, newconfig):
    path.CONFIG_TXT = newconfig

  def reassignBase(self, newbase):
    path.BASEDIR = path.BASEDIR = newbase
    path.CONFIGFOLDER   = path.CONFIGFOLDER.replace('/root/', newbase)
    path.CONFIGFILE     = path.CONFIGFILE.replace('/root/', newbase)
    path.OPTIONSFILE    = path.OPTIONSFILE.replace('/root/', newbase)
    path.COLORMATCH     = path.COLORMATCH.replace('/root/', newbase)
    path.DRV_BUILTIN    = path.DRV_BUILTIN.replace('/root/', newbase)
    path.DRV_EXTERNAL   = path.DRV_EXTERNAL.replace('/root/', newbase)
    path.CACHEFOLDER    = path.CACHEFOLDER.replace('/root/', newbase)
    path.HISTORYFOLDER  = path.HISTORYFOLDER.replace('/root/', newbase)

  def validate(self):
    # Supercritical, since we store all photoframe files in a subdirectory, make sure to create it
    if not os.path.exists(path.CONFIGFOLDER):
      try:
        os.mkdir(path.CONFIGFOLDER)
      except:
        logging.exception('Unable to create configuration directory, cannot start')
        return False
    elif not os.path.isdir(path.CONFIGFOLDER):
      logging.error('%s isn\'t a folder, cannot start', path.CONFIGFOLDER)
      return False
    return True
