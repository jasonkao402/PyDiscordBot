import asyncio
import youtube_dl
import collections
import discord
from youtube_dl.utils import DownloadError

ffmpeg_opts = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    'options': '-vn'
}

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

    async def load_local_song(self, lookup : str) -> Song:
        #results = await self._load_from_url(lookup, noplaylist=True)
        title, streamurl = lookup, lookup
        return Song(title, lookup, streamurl)

    async def load_song(self, lookup : str) -> Song:
        results = await self._load_from_url(lookup, noplaylist=True)
        title, streamurl = results[0]
        return Song(title, lookup, streamurl)

    async def load_playlist(self, lookup : str) -> list:
        return await self._load_from_url(lookup, isProc=False)
        '''
        r2 = []
        for k in results:
            r2 += await self._load_from_url(f"https://www.youtube.com/watch?v={k[1]}", noplaylist=True)
            print (r2[-1])
        
        return [Song(title, lookup, weburl) for (title, weburl) in results]
        '''

    async def _load_from_url(self, url: str, *, noplaylist=False, isProc=True):
        '''Retrieves one or more songs for a url. If its a playlist, returns multiple
        The results are (title, source) pairs
        '''

        ydl = youtube_dl.YoutubeDL({
            'format': 'bestaudio/best',
            'noplaylist': noplaylist,
            'default_search': 'ytsearch',
            'outtmpl': '/data/music/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        })

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._extract_songs, ydl, url, isProc)

    def _extract_songs(self, ydl: youtube_dl.YoutubeDL, url: str, isProc):
        info = ydl.extract_info(url, download=False, process=isProc)
        if not info:
            raise DownloadError('Data could not be retrieved')
        
        if '_type' in info and info['_type'] == 'playlist':
            entries = info['entries']
        else:
            entries = [info]
        results = [(e['title'], e['url']) for e in entries]
        return results

class GuildMusicPlayer:
    """A class which is assigned to each guild using the bot for Music.
    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    When the bot disconnects from the Voice it's instance will be destroyed.
    """

    __slots__ = ('bot', '_guild', '_channel', '_cog', 'sngQueue', 'toggleNext', 'np', 'volume', 'ans_que')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.sngQueue = asyncio.Queue()
        self.toggleNext = asyncio.Event()
        self.ans_que = collections.deque()
        self.np = None  # Now playing message
        self.volume = .2
        
        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.toggleNext.clear()
            s = await self.sngQueue.get()
            #self.np = await self._channel.send(f'Now Playing: {source.title}')
            print(f"trying to play {s.source}")
            self._guild.voice_client.play(
                discord.FFmpegPCMAudio(source=s.source, **ffmpeg_opts),
                after=lambda _: self.bot.loop.call_soon_threadsafe(self.toggleNext.set)
            )
            
            await self.toggleNext.wait()

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))