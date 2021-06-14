# Photoframe V2
This is a development branch of photoframe targeting the next version of the software.  

photoframe is software to allow a Raspberry Pi to display photos in a "slideshow" format on an attached screen.  
One of the more attractive features is that it can automatically pull photos from Google Photos and display them based on 
keywords that match albums and other metadata.  However, it can also show photos from an attached USB "thumb drive" 
or from an arbitrary URL.   

photoframe remains extensible, with well-defined service modules to make it easy to add additional photo sources to the system.

Significant new features and changes for photoframe v2 include:

- Designed to be used with a manual installation on top of a Raspberry Pi OS Lite `Buster` release
- Use of Python 3.  (The previous photoframe was based on Python 2, which reached end-of-life in 2020)
- Support for HEIC photos.  This drove the need for the latest OS release.
- For monitors that support DDC, photoframe will adjust brightness and temperature. 
- Support for a larger set of TCS3472* color and lumen modules e.g. https://www.ebay.com/itm/133600154256 
- Improved color and temperature calculations both for accuracy and sensitivity
- Managed at port 80 - no need to add :7777 to the URL.
- Ability to integrate with home automation for screen standby (sleep)
- An improved update mechanism to make updates more streamlined and robust
- Support for Raspberry Pi 4
These are in addition to the original features:
- Simple web interface for configuration
- Google Photo search integration for more interesting images
- Blanking of screen (ie, off hours)
- Simple OAuth2.0 even though behind firewall (see further down)
- Shows error messages on screen
- Supports ambient room color temperature adjustments
- Uses ambient sensor to improve powersave
- Power control via GPIO (turn RPi on/off)
- Non-HDMI displays (SPI, DPI, etc)
- Display photos from USB attached media
- Display photos available using simple URLs 

## Why use this as opposed to buying one?

Unlike most other frames out there, this one will automatically refresh and grab content
from your photo collection, making it super simple to have a nice photo frame. Also uses
keywords so you can make sure the relevant photos are shown and not the reciepts for
your expense report.

It also has more unique features like ambient color temperature adjustments which allows
the images to meld better with the room where it's running.


# Requirements

- Any Raspberry Pi
- Display of some sort (HDMI or SPI/DPI displays)
- Another device with a web browser to manage the photoframe
- Internet photos from Google or from URLs require Internet access for the Raspberry Pi
- Familiarity wih Raspberry Pi and Linux command line procedures

# Installation

This branch is not compatible with existing SD card images available at mrworf/photoframe.
Once a new SD card image is create for V2, then much of this goes into MANUAL.md

Start by installing Raspberry Pi OS Lite from a Buster release.  Jan 2021 or later.

Make a shell available either by attaching a keyboard, or by enabling ssh 

If you choose to attach a keyboard, use `sudo raspi-config` to set up WiFi - including country.

If you choose to use ssh, then you need to enable ssh by adding two files to the SSD in the /boot drive on your computer 
that you used to image the SD card.  Those files are:
   
   /boot/ssh
```   
     (no contents)
```
   /boot/wpa_supplicant.conf 
```
# Use this file instead of wifi-config.txt
# Should set country properly
# ssid and password should be in double-quotes

ctrl_interface=/var/run/wpa_supplicant
update_config=1
country=us

network={
    scan_ssid=1
    ssid="YourSSID"
    psk="YourWiFiPassword"
}
```


use `sudo raspi-config` to set locale, time zone, and to enable I2C kernel module.  If you are using a keyboard and want the option to
access the raspberry pi later using ssh, you also need to enable it in raspi-config.

Bring the distro up to date:

`sudo apt update && apt upgrade`

From this point forward, it's recommended to `sudo bash` and then `cd` so that the commands are performed as root the /root directory

Install additional dependencies:

`apt install git python3-pip python3-requests-oauthlib python3-flask`

`apt install imagemagick python3-smbus bc ddcutil libjpeg-turbo-progs`

`pip3 install requests requests-oauthlib flask flask-httpauth smbus netifaces`

Next, let's tweak the boot so we don't get a bunch of output

Edit the `/boot/cmdline.txt` and add replace the term `console=tty1` with all of the following:

```
console=tty3 loglevel=3 consoleblank=0 vt.global_cursor_default=0 logo.nologo
```

Then edit the `/boot/config.txt`  file in two places. 

1) Add the following before the first `# uncomment` section

```
disable_splash=1
framebuffer_ignore_alpha=1
```

2) And, if you have or intend to use a monitor with DDC control, add the following to the `dtparam` section if you have 
a Raspberry Pi Zero, 1, 2, or 3.

```
dtparam=i2c2_iknowwhatimdoing
```
If you have the DDC monitor and a Raspberry Pi 4, then replace `dtoverlay=vc4-fkms-v3d` in the `[Pi4]` section with :
```
dtoverlay=vc4-kms-v3d
```

Once again, for the Pi4 and a DDC monitor, add `i2c_dev` in `/etc/modules`


Disable the first console (since that's going to be our frame). This is done by issuing:

```
systemctl disable getty@tty1.service
```

And also do

```
systemctl mask plymouth-start.service
```

or you might still see the boot messages.

To get automatic updates, create a file `/etc/cron.d/photoframe`  with the following contents:
```
# Check once a week for updates to the photoframe software.
15 3    * * *   root    /root/photoframe/update.sh
```

If you want the web interface to be login-password protected, then create the file `/boot/http-auth.json`  with the following edited to suit:

```
{"user":"photoframe","password":"password"}

```
Finally, install photoframe, which means downloading the repo, installing the service and then rebooting the system

```
cd /root
git clone --branch python3 --single-branch https://github.com/mrworf/photoframe.git
cd photoframe
cp frame.service /etc/systemd/system/
systemctl enable /etc/systemd/system/frame.service
reboot now
```


# Usage

photoframe is managed using a browser on the same WiFi subnet.  The URL and current IP address is shown when no configuration is present, 
and shown for a few seconds on bootup for a photoframe that has a working configuration.
For many users it's also possible to use the name of your photoframe like this:
`http://photoframe.local`

The default username/password for the web page is `photoframe` and `password`. This can be changed by editing the file called `http-auth.json` on the `boot` drive


# Color temperature and monitor brightness

Photoframe works with color temperature modules.   Yes, photoframe can actually adjust the temperature of the image to suit the light in the room. For this to work, 
you need to install a TCS3472*,  see https://www.adafruit.com/product/1334  and https://www.ebay.com/itm/133600154256. 

Additionally, if your photoframe is based on a monitor that supports DDC management of brightness and temperature, then adding a temperature molule lets you have 
those controls adjusted automatically based on ambient light brightness and color.

These should be hooked up to the I2C bus like this:

```
3.3V -> Pin 1 (3.3V)
SDA -> Pin 3 (GPIO 2)
SCL -> Pin 5 (GPIO 3)
GND -> Pin 9 (GND)
LED -> Pin 9 (GND)
```

Instructions above include enabling the I2C bus by using `raspi-config` and going to submenu 5 (interfaces) and select I2C and enable it.

Once all this is done, you have one more thing left to do before rebooting, you need to download the imagemagick script that will adjust the image,
please visit http://www.fmwconcepts.com/imagemagick/colortemp/index.php and download and store it as `colortemp.sh` inside `/root/photoframe_config`.

Don't forget to make it executable by `chmod +x /root/photoframe_config/colortemp.sh` or it will still not work.

You're done! Reboot your Pi (So I2C gets enabled) and from now on, all images will get adjusted to match the ambient color temperature.

The sensor is automatically detected as long as it is a TCS3472* device and it's connected correctly to the I2C bus of the raspberry pi. 
Once detected you'll get a new read-out in the web interface which details both ambient light (lux) and color temperature (kelvin).

If photoframe is unable to use the sensor, it "usually" gives you helpful hints. Check the photoframe log using  the `Log report` button in the configuration page, 
or you can log in and  look through the `/var/log/syslog` file for `frame.py` entries.

## Power saving features

Using the same sensor just described, you can set an Auto off lux threshold and duration, if the ambient light is below said threshold for the duration, 
it will trigger powersave on the display. If the ambient light goes back above the threshold for same duration, it will wake up the display.

It's also possible to set the hours at which the photoframe should sleep and wake in the configuration page.

Finally, photoframe also supports 3 web/URL commands to allow controlling the screen through home automation:
```
http://photoframeip/maintenance/standby   will put the screen to sleep
http://photoframeip/maintenance/resume   will wake the screen up again
http://photoframeip/maintenance/get_standby   will return the current state of this feature
````
each of these commands will return (in json) a standby : T/F keyword/state pair.
NOTE: this state is not remembered across reboots or updates. This is intentional to allow recovery to a working system. 

One example using the curl command to script this function would be:
`curl -u 'photoframe:password' http://photoframe.local/maintenance/standby`

Note:  If you combine these power save features the power save state is a logical OR among their inputs.   
That means if any of these inputs ask the frame to go into standy, it will.  But for the frame to wake up again *all* of the inputs must must be "on".

# Power on/off?

Photoframe listens to GPIO 3 (default, can be changed) to power off (and also power on if using GPIO3). 
If you connect a (normally open, momentary contact) pushbutton switch between pin 5 (GPIO 3) and pin 6 (GND), you'll be able to do a graceful 
shutdown as well as power on. 

*Note:*  If you install a color temperature module, you cannot use GPIO3 for this feature.   It's still possible to install a button 
to power-down the photoframe gracefully, but restarting will require a power-cycle.

To use of a shutdown button with a color temperature module, connect the switch between pin 37 (GPIO 26) and pin 39 (GND), and set the GPIO to monitor `26` in 
the photoframe configuration page.  Now you'll be able  to do a graceful shutdown. 


# How come the Google service contacts photoframe.sensenet.nu ???

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

# FAQs

See more FAQs at https://github.com/mrworf/photoframe/wiki/Frequently-Asked-Questions 

## Why didn't my existing photoframe update to this version?

photoframe V2 is based on Raspberry Pi OS "Buster," whereas the previous versions were based on "Stretch."
While is is possible to upgrade a raspberry pi from Stretch to Buster, it is a fragile process that typically requires expert intervention.
That's why the Raspberry Pi organization recommends doing a fresh install of the OS.

Additionally, the new Buster OS provides some key advantages that have been taken in photoframe v2.   The most obvious is support to work
with HEIC photos, like are typically made by iPhones.  It also has a more robust networking stack, and better system management tools.

## Can I avoid photoframe.sensenet.nu ?

You could run the same service yourself (see `extras/`). It requires a DNS name which doesn't change and HTTPS support. You'll also need to change the relevant parts of this guide and the `frame.py` file so all references are correct. You might also be able to use server tokens instead, but that would require you to do more invasive changes. There is no support for this at this time.

## I want to build my own ready-made image of this

Check out the `photoframe` branch on https://github.com/mrworf/pi-gen ... It contains all the changes and patches needed to create the image. Starting with v1.1.1 it will match tags.

## How do I get ssh access?

Place a file called `ssh` on the boot drive and the ssh daemon will be enabled. Login is pi/raspberry (just like raspbian). Beware that if you start changing files inside `/root/photoframe/` the automatic update will no longer function as expected.

## Are there any logs?

Yes, check logs by using the `Log report` button.  If you want to look farther back in the logs, they can be found under `/var/log/syslog`, just look for frame entries.

## What if I want more logs?

If you're having issues and you want more details, do the following as root:
```
systemctl stop frame
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
- User presses "Forget Memory" in the web UI
- The age of the downloaded index exceeds the hours specified by "Refresh keywords" option

To disable the last item on that list, set the "Refresh keywords" to 0 (zero). This effectively disables this and now the frame will only refresh if no more photos are available or if user presses the forget memory item.

## Why isn't it showing all my photos?

If you haven't set any options that limit, ( e.g. orientation or a refresh which is too short to show them all)  photoframe should walk through the whole list from your provider.

*however*

Not all content is supported. To help troubleshoot why some content is missing, you can press "Details" for any keyword (given that the provider supports it) and the frame will let you know what content it has found. It should also give you an indication if there's a lot of content which is currently unsupported.

## What if I need to be able to access more than one WiFi?

Sometimes you might want to ship a photoframe to a relative, or you might have more than one SSID in your home with variable signal strength.
To set up more than one possible SSID edit `/etc/wpa_supplicant.conf` and add an additional network section:
```
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={
    ssid="YourWifi"
    psk="YourPassword"
    priority=1
}

network={
    ssid="YourInLawsWifi"
    psk="TheirPassword"
    priority=2
}
```
The `priority` statements are optional, but when included they set the priority of selection if both SSIDs are available to connect to.
The network that is selected is the highest priority that's available.   So if both of these networks were available `YourInLawsWiFi` would be selected.
