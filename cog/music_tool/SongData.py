import asyncio
import youtube_dl
from youtube_dl.utils import DownloadError

class Song:
    '''song data object'''

    def __init__(self, title : str, url, source):
        self.title = title
        self.url = url
        self.source = source

class SongRequest:
    """Represents a song request from a user from a channel
    
    This is used internally by the GuildPlayer to track the songs being played.
    """

    def __init__(self, song, request_user, request_channel, *, loop=False):
        self.song = song
        self.request_user = request_user
        self.request_channel = request_channel
        self.loop = loop

    @property
    def title(self):
        return self.song.title

    @property
    def url(self):
        return self.song.url

    @property
    def source(self):
        return self.song.source
        
class Loader:
    '''Retrieves song data via youtube dl'''

    async def load_song(self, lookup : str):
        results = await self._load_from_url(lookup, noplaylist=True)
        title, source = results[0]
        return Song(title, lookup, source)

    async def load_playlist(self, lookup : str):
        results = await self._load_from_url(lookup)
        return [Song(title, lookup, source) for (title, source) in results]

    async def _load_from_url(self, url: str, *, noplaylist=False):
        '''Retrieves one or more songs for a url. If its a playlist, returns multiple
        The results are (title, source) pairs
        '''

        ydl = youtube_dl.YoutubeDL({
            'format': 'bestaudio/best',
            'noplaylist': noplaylist,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'logtostderr': False,
            'quiet': True
        })

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_songs, ydl, url)

    def _extract_songs(self, ydl: youtube_dl.YoutubeDL, url: str):
        info = ydl.extract_info(url, download=False)
        if not info:
            raise DownloadError('Data could not be retrieved')
            
        if '_type' in info and info['_type'] == 'playlist':
            entries = info['entries']
        else:
            entries = [info]

        results = [(e['title'], e['url']) for e in entries]
        return results