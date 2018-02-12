# photoframe

A Raspberry Pi 3 software which automatically pulls photos from Google Photos and displays them
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
- Power control via GPIO (turn RPi3 on/off)

# requires

- Raspberry Pi 3
- *bian distro (recommend minibian, https://minibianpi.wordpress.com/ )
- Display of some sort
- Google Photos account
- Internet

# installation

First, install your favorite debian distro (recommend minibian, https://minibianpi.wordpress.com/ )

NOTE!
Photoframe requires about 1GB of storage due to all dependencies. If you're using minibian, please see https://minibianpi.wordpress.com/how-to/resize-sd/ for instructions on how to resize the root filesystem.

Make your distro of choice is up-to-date by issuing

`apt update && apt upgrade`

Once done, we need to install all dependencies

`apt install apt-utils raspi-config git fbset python python-requests python-requests-oauthlib python-flask imagemagick python-smbus`

Next, let's tweak the boot so we don't get a bunch of output

Edit the `/boot/cmdline.txt` and add the following to the end of the line:

```
console=tty3 loglevel=3 consoleblank=0 vt.global_cursor_default=0 logo.nologo
```

You also need to edit the `/boot/config.txt`

Add the following

```
disable_splash=1
framebuffer_ignore_alpha=1
```

We also want to disable the first console (since that's going to be our frame). This is done by
issuing

```
systemctl disable getty@tty1.service
```

Almost there, we also need to set the timezone for the device, or it will be confusing when the on/off hours doesn't meet expectations.

```
timedatectl set-timezone America/Los_Angeles
```

If you don't know your timezone, you can list all supported

```
timedatectl list-timezones
```

Finally, time to install photoframe, which means downloading the repo, install the service and reboot

```
cd /root
git clone https://github.com/mrworf/photoframe.git
cd photoframe
cp frame.service /etc/systemd/system/
systemctl enable /etc/systemd/system/frame.service
reboot
```

Done! Once the device has rebooted, it will tell you how to connect to it and then using your webbrowser you can link it to Google Photos.

## It keeps asking for OAuth2.0 data?

You have to tell photoframe about OAuth2.0 secrets. 

First step, login to your google API console (you have this by default if you have a google photos account). You'll find the console
at https://console.developers.google.com/apis/dashboard

Next, you're going to create a new project, you can call it whatever you want, for this example, I'm using `Photo Frame`.

Once created, we're going to click on `Credentials` in the menu on the left. After it loads, click `Create credentials` and select
`OAuth client id`. This leads to a new screen where it will ask you to create a consent screen, so click the button to get that started.

Next, you're going to fill out the form. All but two fields are optional, so it's an easy thing to do. 

Email Address: `<Your email>` (usually prefilled with your google email)

Product name shown to users: `Photo Frame`

Hit `save` and it will take you to a screen where you choose what kind of application you're making. It's important you choose `Web Application`.
Doing so opens up a couple of extra fields. First, change the name from `Web Client 1` to something better (for example `Photo Frame`). You also need
to fill out `Authorized redirect URIs`. 

Please add `https://photoframe.sensenet.nu` to this list and then press `Create`

This action will open a box with client ID and secret. Don't worry about it, just click `OK`. On the new screen, you'll find your newly created client id.
On the line with the name of your app, there will be a download button at the right-most side. 

Click it, and it downloads a JSON file. It is the contents of this file which needs to be copy-n-paste:ed into the box you see in photoframe.

Once you've copy-n-paste:ed this and submit it to photoframe, it will unlock the main settings and allow you to perform the google photos link, configure parameters, etc.

# wifi setup

This requires a couple of extra steps, first we need more software

```
apt install firmware-brcm80211 pi-bluetooth wpasupplicant iw crda wireless-regdb 
```

Next, we need to configure the wifi interface, open `/etc/network/interfaces` in your favorite editor and
add the following

```
allow-hotplug wlan0
auto wlan0

iface wlan0 inet dhcp
        wpa-ssid "<replace with the name of your wifi>"
        wpa-psk "<replace with the password for your wifi>"
```

Next, let's make sure it works, so issue `ifup wlan0` and after it completes, running `ifconfig wlan0` and it should show something similar to this

```
wlan0     Link encap:Ethernet  HWaddr de:ad:be:ef:11:11
          inet addr:10.0.0.2  Bcast:10.0.0.255  Mask:255.255.255.0
          inet6 addr: fe80::bc27:ffff:fe9c:aa6/64 Scope:Link
          UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
          RX packets:108005 errors:0 dropped:0 overruns:0 frame:0
          TX packets:77150 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:1000
          RX bytes:129102030 (123.1 MiB)  TX bytes:7841326 (7.4 MiB)
```

What we care about is that the line with `inet addr:` is present, it indicates network. At this point, try using SSH to connect to this IP just to be sure it works.
If that pans out, reboot and make sure it still works, I've been biten by this before. Once you see that you can SSH into the RPi3 using the wifi address, it's time
to disable the wired interface.

Open `/etc/network/interfaces` and add a hash `#` in front of the two lines with `eth0`, it should look like this

```
#auto eth0
#iface eth0 inet dhcp
```

Save it and then start `raspi-config`.

Here you need to go to option 3, boot options and choose option 2, wait for network. It should be set to no.

Exit the config tool and then reboot, now your RPi3 will boot directly to WiFi and WiFi only. If you don't do it this way, the RPi3 will wait forever for a wired connection.

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
please visit http://www.fmwconcepts.com/imagemagick/colortemp/index.php and download and store it as `colortemp.sh` inside `/root/`.

You're done! Reboot your RPi3 (So I2C gets enabled) and from now on, all images will get adjusted to match the ambient color temperature.

If photoframe is unable to use the sensor, it "usually" gives you helpful hints. Check the `/var/log/syslog` file for `frame.py` entries.

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

## My screen is black or won't show anything?

The default for photoframe is 1920x1080 at 60Hz, this may or may not be the correct settings for your screen. The web interface is located on port 7777 on your RPi3, by going there you can change these defaults. It also allows you to configure tvservice. By SSH:ing into your RPi3, you can list all available modes exposed by your monitor by issuing `/opt/vc/bin/tvservice -m <CEA or DMT>`. From here you should be able to find the correct mode to use for your screen.

The syntax for `Arguments for Raspberry Pi 3 tv service` in the web interface is:

`<DMT or CEA> <mode id> <DVI or HDMI>`

If it still doesn't work, I'd recommend googling it a bit, you may need to add parameters to the `/boot/config.txt` file to make it all work.

## Can I avoid photoframe.sensenet.nu ?

You could run the same service yourself (see `extras/`). It requires a DNS name which doesn't change and HTTPS support. You'll also need to change the relevant parts of this guide and the `frame.py` file so all references are correct. You might also be able to use server tokens instead, but that would require you to do more invasive changes. I don't have any support for this at this time.

## I made a mistake and my RPi3 is unreachable

### Option 1 - Hard but fast
Install vmware player, run ubuntu on your computer and then attach the memory card to your computer. It should be recognized and allow you to
edit the `/etc/network/interfaces` file located on the SD card. This method retains all work you've done. 

### Option 2 - Easy but slow
Start over from step 1 and install your distribution of choice on the memory card

# todo

- Make photo sources modular (allow multiple Google Photos)
- Enhance web interface
- Create installer to simplify setup
- Timezone control from web UI
- More services: Instagram, Amazon, ...

