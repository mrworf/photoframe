# photoframe
Software to pull random photos from Google Photos and show them, like a photo frame. 

Unlike most other frames out there, this one will automatically refresh and grab content
from your photo album, making it super simple to have a nice photo frame. Also uses
keywords so you can make sure the relevant photos are shown and not the reciepts for
your expense report.

# features

- Simple web interface for configuration
- Google Photo integration
- Blanking of screen (ie, off hours)
- Simple OAuth2.0 even though behind firewall (see technical section)
- Shows error messages on screen

# requires

- Raspberry Pi 3
- *bian distro (recommend minibian, https://minibianpi.wordpress.com/)
- Display of some sort
- Google Photos account
- Internet

# installation

First, install your favorite debian ditro (recommend minibian, https://minibianpi.wordpress.com/) and
make sure it's up-to-date by issuing

`apt update && apt upgrade`

Once done, we need to install all dependencies

`apt install raspi-config git fbset python python-requests python-requests-oauthlib python-flask imagemagick`

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

Almost there, we also need to set the timezone for the device, or it will be confusing.

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

# technical

Since Google doesn't approve of OAuth with dynamic redirect addresses,
this project makes use of a lightweight service which allows registration
of desired redirect (as long as it's a LAN address) and then when 
Google redirects, this service will make another redirect back to your
raspberry.

Add diagram (TBD)

The code for this service is available under `extras` and requires
php with memcached. Ideally you use a SSL endpoint as well.

# todo

- Make photo sources modular (allow multiple Google Photos)
- Enhance web interface
- Create installer to simplify setup
- Timezone control from web UI
- More services: Instagram, Amazon, ...

