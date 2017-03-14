# mimi
Continually loads [YouTube](https://www.youtube.com/) links for a [Last.fm](https://www.last.fm/) user's recent tracks into [VLC](http://www.videolan.org/vlc/).

## Details

For when you want to listen "live" to someone's scrobbles.

Why not the Last.fm built-in player? 

- The built-in player relies on people adding a YouTube video for each track. That's a non-trivial amount of work, especially when more than half of the track list is missing videos.

- Furthermore, Last.fm RSS feeds have been broken since [September 2015](https://twitter.com/lastfm/status/644113840855080961). To listen "live", you would need to make something anyway.

So this script calls the Last.fm API to get a user's recent tracks, and then for each track:

1. If Last.fm already has a YouTube video, load it into VLC
2. Otherwise call the YouTube Data API and load the first video result into VLC

The script repeats the above every X seconds, where X is determined by whether the user was recently active. (refreshing more often if they were, and less often otherwise)

## Usage
**Configuration:**  
1. VLC needs to have its [rc](https://wiki.videolan.org/documentation:modules/rc/) interface configured, preferably as an extra interface.
2. Fill in `config.json` with: host and port for VLC's rc interface, Last.fm user and API key, (optional but recommended) YouTube API key

**Once configured:**  
1. Start VLC.
2. `python mimi.py`

## Notes
- Currently, VLC 2.2.4 youtube.luac fails to extract the video URL for certain YouTube videos, resulting in a "VLC is unable to open the MRL ..." error. It is possible to just supply the video URL directly by using [pafy](https://pypi.python.org/pypi/pafy), but this results in an unreadable playlist. It would be cleaner to fix VLC than to band-aid around it here.
