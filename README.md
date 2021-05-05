# Philip Branch
This is a special branch of photoframe customized for a specific photoframe.  This was done because 
there are too many changes from the master branch.  Significant changes for this photoframe branch include:

- Designed to be used with a manual installation on top of a Raspberry Pi OS Lite `Buster` release
- Use of Python 3.  The Python 3 branch is the starting point for this one.
- Support for HEIC photos.  This drove the need for the latest OS release.
- ddcutil driven brightness and temperature changes.  This photoframe is based on an HP Z24i monitor,
  which can be adjusted using ddc over HDMI, including brightness and temperature. 
  Existing branches do not adjust the screen brightness.
- Support for TCS34727 color and lumen module e.g. https://www.ebay.com/itm/133600154256 
- Stretch Goal - to add an iCloud photo provider.

# photoframe

A Raspberry Pi (Zero, 1 or 3) software which automatically pulls photos from Google Photos and displays them
on the attached screen, just like a photoframe. No need to upload photos to 3rd party service
or fiddle with local storage or SD card.

## why use this as opposed to buying one?

Unlike most other frames out there, this one will automatically refresh and grab content
from your photo collection, making it super simple to have a nice photo frame. Also uses
keywords so you can make sure the relevant photos are shown and not the reciepts for
your expense report.

It also has more unique features like ambient color temperature adjustments which allows
the images to meld better with the room where it's running.

# features

- Simple web interface for configuration
- Google Photo search integration for more interesting images
- Blanking of screen (ie, off hours)
- Simple OAuth2.0 even though behind firewall (see further down)
- Shows error messages on screen
- Supports ambient room color temperature adjustments
- Uses ambient sensor to improve powersave
- Power control via GPIO (turn RPi on/off)
- Non-HDMI displays (SPI, DPI, etc)

# requirements

- Raspberry Pi 1, 3 or Zero
- Display of some sort (HDMI or SPI/DPI displays)
- Google Photos account
- Internet

# installation

This branch is not compatible with existing images available at mrworf/photoframe.

Start by installing Raspberry Pi OS Lite from a Buster release.  Jan 2021 or later.

Make a shell available either by attaching a keyboard, or by enabling ssh 

   Note: to enable ssh add two files to the SSD /boot drive:
   
   ssh
```   
     (no contents)
```
   wpa_supplicant.conf 
```
# Use this file instead of wifi-config.txt
# Should set country properly

country=us
update_config=1
ctrl_interface=/var/run/wpa_supplicant

network={
scan_ssid=1
ssid="YourSSID"
psk="YourWiFiPassword"
}
```

If a keyboard is attached you can user raspi-config to set up WiFi.

use `sudo raspi-config` to set locale, time zone, overscan (black space around picture) and to enable I2C kernel module

Bring the distro up to date:

`sudo apt update && apt upgrade`

Install additional dependencies:

`apt install git python3-pip python3-requests python3-requests-oauthlib python3-flask`
`apt install imagemagick python3-smbus bc ddcutil`
`pip3 install requests requests-oauthlib flask flask-httpauth smbus`
`pip3 install netifaces` 

Next, let's tweak the boot so we don't get a bunch of output

Edit the `/boot/cmdline.txt` and add the following to the end of the line:

```
console=tty3 loglevel=3 consoleblank=0 vt.global_cursor_default=0 logo.nologo
```

You also need to edit the `/boot/config.txt`  in two places

Add the following before the first `# uncomment` section

```
disable_splash=1
framebuffer_ignore_alpha=1
```

And add the following to the `dtparam` section

```
dtparam=i2c2_iknowwhatimdoing
```

We also want to disable the first console (since that's going to be our frame). This is done by
issuing

```
systemctl disable getty@tty1.service
```

And also do

```
systemctl mask plymouth-start.service
```

or you might still see the boot messages.

Finally, time to install photoframe, which means downloading the repo, install the service and reboot

```
cd /root
git clone --branch Philip --single-branch https://github.com/dadr/photoframe.git
cd photoframe
cp frame.service /etc/systemd/system/
systemctl enable /etc/systemd/system/frame.service
reboot now
```

# Usage

photoframe is managed using a browser on the same WiFi subnet.  The URL is shown when no configuration is present, 
and shown for a few seconds on bootup for a photoframe that has a working configuration.

The default username/password for the web page is `photoframe` and `password`. This can be changed by editing the file called `http-auth.json` on the `boot` drive


# color temperature

This branck of photoframe is intended to work with color temperature modules.   Yes, photoframe can actually adjust the temperature of the image to suit the light in the room. For this to work, you need to install a TCS34725 or TCS34727,
see https://www.adafruit.com/product/1334  and https://www.ebay.com/itm/133600154256. These should be hooked up to the I2C bus like this:

```
3.3V -> Pin 1 (3.3V)
SDA -> Pin 3 (GPIO 0)
SCL -> Pin 5 (GPIO 1)
GND -> Pin 9 (GND)
LED -> Pin 9 (GND)
```

Instructions above include enabling the I2C bus by using `raspi-config` and going to submenu 5 (interfaces) and select I2C and enable it.

Once all this is done, you have one more thing left to do before rebooting, you need to download the imagemagick script that will adjust the image,
please visit http://www.fmwconcepts.com/imagemagick/colortemp/index.php and download and store it as `colortemp.sh` inside `/root/photoframe_config`.

Don't forget to make it executable by `chmod +x /root/photoframe_config/colortemp.sh` or it will still not work.

You're done! Reboot your RPi3 (So I2C gets enabled) and from now on, all images will get adjusted to match the ambient color temperature.

If photoframe is unable to use the sensor, it "usually" gives you helpful hints. Check the `/var/log/syslog` file for `frame.py` entries.

*Note*

The sensor is automatically detected as long as it is a TCS34725 device and it's connected correctly to the I2C bus of the raspberry pi. Once detected you'll get a new read-out in the web interface which details both white balance (kelvin) and light (lux).

If you don't get this read-out, look at your logfile. There will be hints like sensor not found or sensor not being the expected one, etc.


## Ambient powersave?

Yes, using the same sensor, you can set a threshold and duration, if the ambient light is below said threshold for the duration, it will trigger
powersave on the display. If the ambient brightness is above the threshold for same duration, it will wake up the display.

However, if you're combining this with the scheduler, the scheduler takes priority and will keep the display in powersave during the scheduled hours,
regardless of what the sensor says. The sensor is only used to extend the periods, it cannot power on the display during the off hours.

# Power on/off?

Photoframe listens to GPIO 26 (default, can be changed) to power off (and also power on). If you connect a switch between pin 37 (GPIO 26) and pin 39 (GND), you'll be able
to do a graceful shutdown as well as power on.

# How come you contact photoframe.sensenet.nu ???

Since Google doesn't approve of OAuth with dynamic redirect addresses,
this project makes use of a lightweight service which allows registration
of desired redirect (as long as it's a LAN address) and then when
Google redirects, this service will make another redirect back to your
raspberry. The registered addresses are only kept for 10min and is only
stored in RAM, so nothing is kept.

```
User                 RPi3                    Google            Sensenet
 |--[Start linking]--->|                         |                 |
 |                     |                         |                 |
 |                     |-------[Register LAN address]------------->|
 |                     |                         |                 |
 |                     |<---------[Unique ID to use]---------------|
 |                     |                         |                 |
 |<--[OAuth2.0 begin]--|                         |                 |
 |                     |                         |                 |
 |<-[OAuth2.0 exchange, state holds unique ID]-->|                 |
 |                     |                         |                 |
 |<---[Redirect to photoframe.sensenet.nu]-------|                 |
 |                     |                         |                 |
 |----[Load photoframe.sensenet.nu with unique ID]---------------->|
 |                     |                         |                 |
 |<---[New redirect to registered LAN address from earlier]--------|
 |                     |                         |                 |
 |--[Load local web]-->|                         |                 |
 |                     |                         |                 |
 ```

It's somewhat simplified, but shows the extra step taken to register your LAN address so redirection works.

If you want to see how it works and/or run your own, you'll find the code for this service under `extras` and requires
php with memcached. Ideally you use a SSL endpoint as well.

# faq

## Can I avoid photoframe.sensenet.nu ?

You could run the same service yourself (see `extras/`). It requires a DNS name which doesn't change and HTTPS support. You'll also need to change the relevant parts of this guide and the `frame.py` file so all references are correct. You might also be able to use server tokens instead, but that would require you to do more invasive changes. I don't have any support for this at this time.

## I want to build my own ready-made image of this

Check out the `photoframe` branch on https://github.com/mrworf/pi-gen ... It contains all the changes and patches needed to create the image. Starting with v1.1.1 it will match tags.

## How do I get ssh access?

Place a file called `ssh` on the boot drive and the ssh daemon will be enabled. Login is pi/raspberry (just like raspbian). Beware that if you start changing files inside `/root/photoframe/` the automatic update will no longer function as expected.

## Are there any logs?

By default, it logs very little and what it logs can be found under `/var/log/syslog`, just look for frame entries

## What if I want more logs?

If you're having issues and you want more details, do the following as root:
```
service frame stop
/root/photoframe/frame.py --debug
```
This will cause photoframe to run in the foreground and provide tons of debug information

## How do I run USB provider when emulated?

Add the following to your `/etc/sudoers`

```
<your username>      ALL=(root) NOPASSWD: /bin/mount
```

But please note that this will enable your user to use mount via sudo *WITHOUT PASSWORD PROMPTING*

## How do I test and develop on a desktop?

Start `frame.py` with `--emulate` to run without a RPi

## I can't seem to use some USB sticks?

You might be missing exFAT support. If you used this on RPi, it comes preinstalled, but if you're running this manually, please install the following (assumes ubuntu distro)

```
sudo apt install exfat-fuse exfat-utils
```

After this, you should be able to use exFAT

## How does "Refresh keywords" option work?

By default, most photo providers will fetch a list of available photos for a given keyword. This list isn't refreshed until one of the following events happen:

- No more photos are available from ANY photo provider in your frame
- User presses "Forget Memory" in web UI
- The age of the downloaded index exceeds the hours specified by "Refresh keywords" option

To disable the last item on that list, set the "Refresh keywords" to 0 (zero). This effectively disables this and now the frame will only refresh if no more photos are available or if user presses the forget memory item.

## Why isn't it showing all my photos?

Given you haven't set any options to limit based on orientation or a refresh which is too short to show them all, it should walk through the provided list from your provider.

*however*

Not all content is supported. To help troubleshoot why some content is missing, you can press "Details" for any keyword (given that the provider supports it) and the frame will let you know what content it has found. It should also give you an indication if there's a lot of content which is currently unsupported.
