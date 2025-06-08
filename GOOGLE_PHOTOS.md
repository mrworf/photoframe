# Why doesn't Photoframe work with Google Photos?

[Google made a change in March of 2025](https://developers.google.com/photos/support/updates) to deprecate all API access to your photos. Henceforth, only content created by your app would be available to you. 

This is not an option for a photo frame since it needs to be able to consume photos. To this end, Google added a new API called the "Google Photos Picker API," which, as the name suggests, allows you to select photos.

However, this API has a couple of issues:

1. You must do this from the client (i.e., the web browser, not the backend)
2. Only individual photos can be selected, not entire albums

The first item is, well, not ideal, but I could work around it. It's the second item which is a dead end. If we have to select every photo, it makes it very impractical. The whole reason photo frame was created was due to the lack of an automated way to see your photos with minimal effort on your part.

And to add insult to injury, they've also removed shared albums, meaning that even if we went through all of this, there's no way to access shared albums, which has been a popular way to let grandparents see their grandkids. 

The best part of the update they posted?

> If your app relies on accessing the user's entire library, you may need to re-evaluate your app or consider alternative approaches.

What alternative approaches? 🤦

# What do we do now?

I'm working on upgrading the frame to Python 3.x, since it's been a sticking point for some time. However, another item is that I'm going to develop support for Immich.app, as I'm no longer interested in paying $99/year to have my photos locked away while they train their AI on them and charge me for the privilege.

The other goal is to add support for additional photo albums that are less restrictive and still allow us to access our photos.

## Future versions

The upgrade will come with the caveat that the existing SD card image will be replaced; it's simply too old, and upgrading it in situ would be a significant undertaking with too many unknowns. I know this isn't ideal, but given the way most of us have used this software, this is a good time to clean house.

## What about iCloud Photos support?

Sadly, Apple's iCloud Photos will not be supported (by me, at least) since they don't have any public APIs. There are tools like iCloud Photos Downloader, so if anyone wants to write a service provider for it, I'd be happy to accept a pull request, but I'm neither an Apple user nor have the time to support such an endeavor. 

But I felt it important to call out since I know a lot of users use it (iCloud Photos, that is)

# Are you really going to do this?

Yes, I have multiple frames of my own, including one 24" one sitting prominently in my living room. Currently, it's cycling through old photos and Pexels.com photos. Not a good way to keep that spousal approval factor high 😉

