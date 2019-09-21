#!/bin/bash

if [ "${OFFICIAL}" != "yes" ]; then
  echo "Not doing a build since OFFICIAL flag is not 'yes'"
  exit 0
fi

export PHOTOFRAME_SRC="$(pwd)"

if [ -d pi-gen ]; then
  sudo rm -rf pi-gen
fi

git clone https://github.com/mrworf/pi-gen.git
cd pi-gen
echo >config.local "PHOTOFRAME_SRC=\"${PHOTOFRAME_SRC}\""
sudo ./build.sh
