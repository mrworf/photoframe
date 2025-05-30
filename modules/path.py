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
import logging
from pathlib import Path

class path:
    # Default paths relative to basedir
    CONFIGFOLDER  = Path('photoframe_config')
    CONFIGFILE    = CONFIGFOLDER / 'settings.json'
    COLORMATCH    = CONFIGFOLDER / 'colortemp.sh'
    OPTIONSFILE   = CONFIGFOLDER / 'options'
    CACHEFOLDER   = Path('cache')
    HISTORYFOLDER = Path('history')

    DRV_BUILTIN   = Path('display-drivers')
    DRV_EXTERNAL  = CONFIGFOLDER / 'display-drivers'

    CONFIG_TXT    = Path('boot/config.txt')

    @classmethod
    def reassignConfigTxt(cls, newconfig):
        cls.CONFIG_TXT = Path(newconfig)

    @classmethod
    def reassignBase(cls, newbase):
        newbase = Path(newbase)
        cls.CONFIGFOLDER   = newbase / 'photoframe_config'
        cls.CONFIGFILE     = cls.CONFIGFOLDER / 'settings.json'
        cls.OPTIONSFILE    = cls.CONFIGFOLDER / 'options'
        cls.COLORMATCH     = cls.CONFIGFOLDER / 'colortemp.sh'
        cls.DRV_BUILTIN    = newbase / 'display-drivers'
        cls.DRV_EXTERNAL   = cls.CONFIGFOLDER / 'display-drivers'
        cls.CACHEFOLDER    = newbase / 'cache'
        cls.HISTORYFOLDER  = newbase / 'history'
        cls.CONFIG_TXT     = newbase / 'boot/config.txt'

    @classmethod
    def validate(cls):
        # Supercritical, since we store all photoframe files in a subdirectory, make sure to create it
        try:
            cls.CONFIGFOLDER.mkdir(parents=True, exist_ok=True)
            cls.CACHEFOLDER.mkdir(parents=True, exist_ok=True)
            cls.HISTORYFOLDER.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logging.exception(f'Unable to create configuration directory, cannot start: {e}')
            return False
