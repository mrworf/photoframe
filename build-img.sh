#!/bin/bash

export PHOTOFRAME_SRC="$(pwd)/*"

if [ -d pi-gen ]; then
  rm -rf pi-gen
fi

git clone https://github.com/mrworf/pi-gen.git
cd pi-gen
sudo ./build.sh
