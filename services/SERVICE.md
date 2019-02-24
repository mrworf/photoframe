# How to develop a service for photoframe

Always prefix your service's filename with `svc_` and place it in this folder, or the photoframe software
will not detect and add your service.

## Step 1: Inherit from BaseService

This class provides a lot of the plumbing needed to plugin a new service that can provide photos for the frame.
All the OAuth work is hidden away and all the configuration is magically saved as needed.

Key things to get this working is:
- Call the __init__ of the parent
- Override preSetup and/or postSetup depending on your needs
- If you need OAuth
  - Override getOAuthScope to describe what you need
  - Override getOAuthMessage to help inform the user what they need to upload
- If you need authentication
  - Override getAuthenticationFields to describe what fields you need
  - Override validateAuthentication to make sure you got what you needed

## Step 2: Keywords

Once authentication and oauth has passed (if requested), the service is considered ready for use.

Each service has the option to simply state that it doesn't use keywords (override needKeywords and return false).
This will still allow the user to add it, but there won't be an option to provide any keywords. It can also only show up ONCE.

If keywords are allowed, the service may be provided with one or more SETS of keywords, this allows a service to be used multiple
times but with different sets of keywords. Photoframe makes the service responsible for keeping track of what's shown and what's not

Keywords is also a very loosly defined concept. It's simply a string, meaning the service can use it as it sees fit, which is why
it's always a good idea to override helpKeywords() to give the user some hints as to how it works. Service can also override
validateKeywords to do any validation it needs to a string before it's added to the service.

## Step 3: Heavy lifting

Once a service is in use, it's responsible for providing content on-demand. This is done by overriding the prepareNextItem.
This function shall return a key/value map with "mimetype" set to what you provided (for example, image/jpeg)
and an error key which shall be None unless you failed, at which point it should contain a useful error message.
There is a third key called "source" which can be set to an URL which would take the user to the source content, like for example
a google photos link to the real photo. This is only visible from within the web UI and is there to help users understand why
it showed up. If it cannot be provided, simply leave this key set to None or empty string.

A service is required to automatically deciding which keywords to use (from user provided list) when preparing the next image.
The selection of image should be random and preferably it remembers which it has shown before so it can avoid showing the same
image twice.

### Helpers

The BaseService does provide a bunch of helpful features to make it "easier" to do things like downloading files and/or
tracking if you've already shown a specific item.

#### self.requestUrl(url, destination=filename, params=http-query)

Use this to download items http(s) items. If OAuth was used, then the function will make the request using OAuth.

If destination isn't specified, the content will be passed as a return value consisting of ["status": http status code, "content" : raw data]
, if it's set, the content field will be None.

Params allows for http query parameters to be passed to the server. This is a key/value map.

#### self.memoryRemember(itemId, keywords=None)

This allows you to remember an item you've prepared. Keywords allows you to do this per keyword instead of globally
Returns true if this was new, if this already was seen, returns False

#### self.memorySeen(itemId, keywords=None)

Returns true/false if this has been seen. Keywords allows you to do this per keyword instead of globally

#### self.memoryForget(keywords=None)

Clears the memory of seen items. Keywords allows you to do this per keyword instead of globally

