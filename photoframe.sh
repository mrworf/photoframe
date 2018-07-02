#!/bin/bash
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

# Make sure we're running from where the script is located
cd "$(dirname "$0")"

# Allow photoframe to change itself
if [ -f /root/photoframe_config/options ]; then
  source /root/photoframe_config/options
fi

# If we never did update, this would be a good time
if [ ! -f /root/.firstupdate ]; then
  ./update.sh onlyupdate
fi

# Allows options to inject pre/post commands and options,
# paving the way for grabbing logs via web interface.
${PRERUN}
${PRECMD} ./frame.py ${POSTCMD}
${POSTRUN}
