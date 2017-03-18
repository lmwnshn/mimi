"""
Gets recent tracks from last.fm and loads their youtube links into VLC.
"""

import argparse
import datetime
import json
import telnetlib
import time
import lxml.html

import requests


class VLCrc:
    """
    Connect to VLC via its rc interface through telnet.
    """

    def __init__(self, server, port):
        self.server = server
        self.port = port
        self.telnet = telnetlib.Telnet(self.server, self.port)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.telnet.close()
        self.telnet = None

    def enqueue(self, youtube_url):
        """
        Adds youtube_url to VLC's playlist.
        """
        message = 'enqueue {url}\n'.format(url=youtube_url)
        self.telnet.write(message.encode('ascii'))


class Scrobbler:
    """
    Connect to last.fm audioscrobbler API.
    """

    def __init__(self, user, lastfm_key):
        self.user = user
        self.lastfm_key = lastfm_key

    def get_tracks(self, last_ts, limit):
        """
        Return up to limit tracks since last_ts (UNIX time).
        """
        recenttracks = {
            'method': 'user.getrecenttracks',
            'user': self.user,
            'api_key': self.lastfm_key,
            'format': 'json',
            'from': last_ts,
            'limit': limit
        }

        scrobblerapi2 = r'http://ws.audioscrobbler.com/2.0/'
        req = requests.post(scrobblerapi2, params=recenttracks)
        tracks = req.json()['recenttracks']['track']
        return tracks


class YoutubeLinker:
    """
    Obtain youtube video links.
    """

    def __init__(self, youtube_key=None):
        self.youtube_key = youtube_key

    def _get_from_lastfm(self, track):
        lastfm_url = track['url']
        req = requests.get(lastfm_url)

        tree = lxml.html.fromstring(req.content)
        links = tree.xpath('(//@data-youtube-url)[last()]')

        if len(links) == 0:
            return None
        else:
            return links[0]

    def _get_from_youtube(self, track):
        if self.youtube_key is None:
            return None

        track_name = track['name']
        track_author = track['artist']['#text']

        max_results = 5
        # youtube is usually good about returning relevant results
        # within the top 5, if it exists

        query = '{name} {author}'.format(name=track_name, author=track_author)

        params = {
            'part': 'snippet',
            'q': query,
            'key': self.youtube_key,
            'maxResults': max_results
        }

        ytsearchapi3 = r'https://www.googleapis.com/youtube/v3/search'
        req = requests.get(ytsearchapi3, params)

        video_url = r'https://www.youtube.com/watch?v={video_id}'

        i = 0
        while i < max_results:
            ith_result = req.json()['items'][i]['id']
            if 'videoId' in ith_result:
                video_id = ith_result['videoId']
                video_url = video_url.format(video_id=video_id)
                break
            else:
                i = i + 1
        else:
            video_url = None

        return video_url

    def get_youtube_url(self, track):
        """
        Return youtube_url for a last.fm track object. May return None.

        It first tries last.fm to see if there is a youtube video already,
        otherwise it makes a search API call to Youtube.
        """
        url = self._get_from_lastfm(track)
        url = self._get_from_youtube(track) if url is None else url

        return url


def _load_config():
    """
    Return contents of local file config.json as a dictionary.

    Expected from config.json:
    host: the server on which VLC's rc interface is running
          (note that the rc interface is insecure and should not be exposed,
           it is recommended that host is always 127.0.0.1,
           this option is here so you can shoot yourself in the foot
           if you want to)
    port: the port on which VLC's rc interface is running
    lastfm_key: api key for last.fm
    youtube_key: api key for Youtube Data API
    active_window_min: window in minutes for user recently active
    awake_min: time in minutes before we poll last.fm for update (fast)
    asleep_min: time in minutes before we poll last.fm for update (slow)
    """
    with open('config.json', 'r') as jsonfile:
        config = json.load(jsonfile)

    return config


def _time_hms(datetime_obj):
    """
    Return datetime_obj formatted as HH:MM:SS.
    """
    return '{time:%H:%M:%S}'.format(time=datetime_obj)


def load_tracks(tracks, last_ts, vlcrc, youtube_linker, verbose=False):
    """
    Load the youtube URL of every track into VLC,
    returning UNIX time of the latest track.
    """
    if len(tracks) == 0:
        return last_ts

    # we add one to prevent obtaining the same last video again
    last_ts = int(tracks[0]['date']['uts']) + 1

    # we reverse tracks here to have our playlist
    # match the last.fm play order, playing towards the present
    for track in reversed(tracks):
        youtube_url = youtube_linker.get_youtube_url(track)
        if youtube_url is None:
            continue

        vlcrc.enqueue(youtube_url)

        if verbose:
            track_name = track['name']
            video_id = youtube_url[youtube_url.find('?v=')+3:]
            print('[{id}] Loaded {name}'.format(name=track_name, id=video_id))

    return last_ts


def main():
    """
    Magic.
    """

    parser = argparse.ArgumentParser(
        description=("Loads youtube links for a last.fm user's"
                     "recent tracks into VLC.")
    )
    parser.add_argument(
        'limit', metavar='limit', type=int, nargs='?',
        const=25, default=25, help='number of tracks to load'
    )
    parser.add_argument(
        'user', metavar='user', type=str,
        help='last.fm user to load'
    )

    args = parser.parse_args()
    limit = args.limit
    lfm_user = args.user

    config = _load_config()
    host = config['host']
    port = config['port']
    lfm_key = config['lastfm_key']
    yt_key = config['youtube_key']
    active_window_s = 60 * int(config['active_window_min'])
    awake_s = 60 * int(config['awake_min'])
    asleep_s = 60 * int(config['asleep_min'])
    last_ts = 0

    scrobbler = Scrobbler(lfm_user, lfm_key)
    linker = YoutubeLinker(yt_key)

    while True:
        with VLCrc(host, port) as vlcrc:
            tracks = scrobbler.get_tracks(last_ts, limit)
            last_ts = load_tracks(tracks, last_ts, vlcrc,
                                  linker, verbose=True)
            last_ts_dt = datetime.datetime.fromtimestamp(last_ts)

            now = datetime.datetime.now()
            print(_time_hms(now), "| last played:", _time_hms(last_ts_dt))

            recently_active = now.timestamp() - last_ts < active_window_s

            if recently_active:
                wake_time = now + datetime.timedelta(seconds=awake_s)
                print('[ACTIVE] next update @', _time_hms(wake_time))
                time.sleep(awake_s)
            else:
                wake_time = now + datetime.timedelta(seconds=asleep_s)
                print('[ASLEEP] next update @', _time_hms(wake_time))
                time.sleep(asleep_s)


if __name__ == "__main__":
    main()
