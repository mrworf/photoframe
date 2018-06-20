# Manual installation

First, install your favorite debian distro (recommend minibian, https://minibianpi.wordpress.com/ )

NOTE!
Photoframe requires about 1GB of storage due to all dependencies. If you're using minibian, please see https://minibianpi.wordpress.com/how-to/resize-sd/ for instructions on how to resize the root filesystem.

Make your distro of choice is up-to-date by issuing

`apt update && apt upgrade`

Once done, we need to install all dependencies

`apt install apt-utils raspi-config git fbset python python-requests python-requests-oauthlib python-flask python-flask-httpauth imagemagick python-smbus bc`

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

If you're using a rasbian (or a varity of said distro) you may need to also do

```
systemctl mask plymouth-start.service
```

or you might still see the boot messages.

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

# faq

## I want it to auto-update

Easy, just schedule a cronjob to run `update.sh`. It will use git to update (if there are changes) as well as restart the service if it has updated. Ideally you run this once a week.
