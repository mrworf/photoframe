#/bin/bash

echo "HIGHLY EXPERIMENTAL! USE AT YOUR OWN RISK"

if [ "$1" != "ok" ]; then
	echo "You must type ok as a parameter to initate install. Install must be as root"
	echo "!!! THERE IS NO ERROR HANDLING !!! SERIOUSLY, DO NOT USE THIS YET !!!"
	exit 255
fi

# Make it up-2-date
apt-get update
apt-get upgrade -y
apt-get install -y raspi-config git fbset python python-requests python-requests-oauthlib python-flask imagemagick python-smbus

# WiFi
apt-get install -y firmware-brcm80211 pi-bluetooth wpasupplicant iw crda wireless-regdb 

echo -n "console=tty3 loglevel=3 consoleblank=0 vt.global_cursor_default=0 logo.nologo" >> /boot/cmdline.txt 

echo "disable_splash=1" >> /boot/config.txt
echo "framebuffer_ignore_alpha=1" >> /boot/config.txt

# Stop tty1, we don't want a login
systemctl disable getty@tty1.service

# Hardcoded, is bad
timedatectl set-timezone America/Los_Angeles

# Enable service
cd /root/photoframe
cp frame.service /etc/systemd/system/
systemctl enable /etc/systemd/system/frame.service

# Horrible way of adding wifi
echo "allow-hotplug wlan0" >> /etc/network/interfaces
echo "auto wlan0" >> /etc/network/interfaces
echo "iface wlan0 inet dhcp" >> /etc/network/interfaces
echo -n '  wpa-ssid "' >> /etc/network/interfaces
cat /boot/wifi-ssid.txt >> /etc/network/interfaces
echo '"' >> /etc/network/interfaces
echo -n '  wpa-psk "' >> /etc/network/interfaces
cat /boot/wifi-password.txt >> /etc/network/interfaces
echo '"' >> /etc/network/interfaces

# Get the colortemp script
wget "http://www.fmwconcepts.com/imagemagick/downloadcounter.php?scriptname=colortemp&dirname=colortemp" -O /root/colortemp.sh
chmod +x /root/colortemp.sh

# Enable I2C and no wait network, yeah, you need to do this
raspi-config

echo "DONE! Reboot now!"
