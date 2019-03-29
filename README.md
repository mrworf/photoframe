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

# requires

- Raspberry Pi 1, 3 or Zero
- Display of some sort (HDMI or SPI/DPI displays)
- Google Photos account
- Internet

# installation

On the release page, you'll find prepared raspbian image(s) for RaspberryPi 1, 3 or Zero

To use these (and I really recommend that to doing the manual steps), here's how:

1. Download the image from the release page
2. Use your favorite tool to load image onto a SD card, I recommend https://etcher.io/ which works on Windows, OSX and Linux
3. Open the new drive called `boot` and edit the file called `wifi-config.txt`
   Change the two fields to point out your wifi and the password needed for it
4. Save the file
5. Place SDcard in your RPi3 which is connected to a monitor/TV
6. Start the RPi
7. Wait (takes up to a minute depending on card and the fact that it's expanding to use the entire SDcard ... slower still on non-RPi3)
8. Follow instructions shown on the display

The default username/password for the web page is `photoframe` and `password`. This can be changed by editing the file called `http-auth.json` on the `boot` drive

## tl;dr

Flash image to SDcard, edit `wifi-config.txt` and boot the RPi3 with the SDcard and follow instructions. Username and password is above this paragraph.

Once inside the web interface, select `GooglePhotos` from dropdown list in bottom-left corner and press `Add photo service`.

# color temperature?

Yes, photoframe can actually adjust the temperature of the image to suit the light in the room. For this to work, you need to install a TCS34725,
see https://www.adafruit.com/product/1334 . This should be hooked up to the I2C bus, using this:

```
3.3V -> Pin 1 (3.3V)
SDA -> Pin 3 (GPIO 0)
SCL -> Pin 5 (GPIO 1)
GND -> Pin 9 (GND)
```

You also need to tell your RPi3 to enable the I2C bus, start the `raspi-config` and go to submenu 5 (interfaces) and select I2C and enable it.

Once all this is done, you have one more thing left to do before rebooting, you need to download the imagemagick script that will adjust the image,
please visit http://www.fmwconcepts.com/imagemagick/colortemp/index.php and download and store it as `colortemp.sh` inside `/root/photoframe_config`.

Don't forget to make it executable by `chmod +x /root/photoframe_config/colortemp.sh` or it will still not work.

You're done! Reboot your RPi3 (So I2C gets enabled) and from now on, all images will get adjusted to match the ambient color temperature.

If photoframe is unable to use the sensor, it "usually" gives you helpful hints. Check the `/var/log/syslog` file for `frame.py` entries.

## Annoyed with the LED showing on the TCS34725 board from Adafruit?

Just ground the LED pin (for example by connecting it to Pin 9 on your RPi3)

## Ambient powersave?

Yes, using the same sensor, you can set a threshold and duration, if the ambient light is below said threshold for the duration, it will trigger
powersave on the display. If the ambient brightness is above the threshold for same duration, it will wake up the display.

However, if you're combining this with the scheduler, the scheduler takes priority and will keep the display in powersave during the scheduled hours,
regardless of what the sensor says. The sensor is only used to extend the periods, it cannot power on the display during the off hours.

# Power on/off?

Photoframe listens to GPIO 26 to power off (and also power on). If you connect a switch between pin 37 (GPIO 26) and pin 39 (GND), you'll be able
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

# todo

Tracks ideas and improvements planned. No specific timeframe is mentioned, but the order of things should be fairly true

Moved to [github.com](https://github.com/mrworf/photoframe/issues?utf8=%E2%9C%93&q=is%3Aissue+is%3Aopen+label%3Aenhancement) for more dynamic tracking :-)
