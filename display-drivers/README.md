# Display Drivers

Photoframe now supports uploading and enabling of internal displays for the Raspberry Pi family,
the only requirement is that it can be supported by the currently used kernel and modules.

Since a lot of the smaller displays rely on the built-in fbtft driver, it means that in many
cases, all you really need is a DeviceTree Overlay, essentially configuration files for the
device driver so it knows how to talk to the new display.

## What's included

Today, only the waveshare 3.5" IPS (model B) is provided since that was my development system.
But you can create and share these display "drivers" easily yourself.

## How to write a display driver package

Start with an empty folder, copy the necessary files for it to work, usually one or two files
ending in `.dtb` or `.dtbo`.

Next, create a file called `INSTALL` (yes, all caps, important) in the same folder. Open the
file and create the following structure:

```
[install]

[options]
```

### The install section
This is a very simple `key/value` pair setup. First part (key) refers to the file included in the
package. The path to the file is based on the location of the `INSTALL` file. You can use 
sub-directories if you need to, but if you do so, they must adhere to the same rule.

The value part refers to where the file should be copied when activated. Typically this is
somewhere in `/boot/`.

For example, in the waveshare case, this section looks like this:
```
[install]
waveshare35b-overlay.dtb=/boot/overlays/waveshare35b.dtbo
waveshare35b-overlay.dtb=/boot/overlays/waveshare35b-overlay.dtb
```
As you can see, the key here is used multiple times, this is because they place this file in two
locations with different names (but it's the same file).

NOTE! The installer will NOT create any directories when activating.

### The options section

This is also a `key/value` setup, but unlike the `install` section, here the key is UNIQUE. If you
define a key multiple times, only the last definition will be used.

At the very least, this section holds the key `dtoverlay` which is the `/boot/config.txt` keyword
for pointing out an overlay to use. But you can add as many things as you'd like (some DPI displays
require a multitude of key/value pairs).

In the waveshare 3.5" display case, all it does is point out the overlay:
```
[options]
dtoverlay=waveshare35b
```

## Saving the display driver package

Once you have written your `INSTALL` file and added the needed files to the folder you
created earlier, all you need to do now is create a zip file out of the contents and give
the file a nice name (like, `waveshare35b.zip`) since that's the name used to identify
the driver.

## I updated my driver, now what?

Simply upload it again. The old driver will be deleted and replaced with the new one.

## This all seem complicated, do you have an example?

Sure, just unzip the `waveshare35b.zip` and look at it for guidance.

## What is `manifest.json` ?

That's a generated file by photoframe which it creates upon installing a driver. You can
create sub-directories in `display-drivers` with pre-processed drivers which will then be
available by default when installing photoframe.

Note that if you install a driver with the same name as one of the provided ones, the new
driver will take priority

## Known gotchas

If you install a driver which you're already using, you need to switch to HDMI and back to
force update the active driver (and no, no need to reboot when going to HDMI, only when
you go back to your updated driver). 

This will eventually be fixed.