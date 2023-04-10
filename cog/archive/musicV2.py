import discord
from discord.ext import commands

import asyncio
from itertools import islice
import sys
import traceback
from cog.music_tool.SongData import *

class VoiceConnectionError(commands.CommandError):
    """Custom Exception class for connection errors."""

class InvalidVoiceChannel(VoiceConnectionError):
    """Exception for cases of invalid Voice Channels."""

class Musicv2(commands.Cog):
    """Music related commands."""

    __slots__ = ('bot', 'loader', 'players')

    def __init__(self, bot):
        self.bot = bot
        self.loader = Loader()
        self.players = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
        except KeyError:
            pass

    async def __local_check(self, ctx):
        """A local check which applies to all commands in this cog."""
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def __error(self, ctx, error):
        """A local error handler for all errors arising from commands in this cog."""
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send('This command can not be used in Private Messages.')
            except discord.HTTPException:
                pass
        elif isinstance(error, InvalidVoiceChannel):
            await ctx.send('Error connecting to Voice Channel. '
                           'Please make sure you are in a valid channel or provide me with one')

        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    def get_player(self, ctx):
        """Retrieve the guild player, or generate one."""
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = GuildMusicPlayer(ctx)
            self.players[ctx.guild.id] = player

        return player

    @commands.command(name='connect', aliases=['join'])
    async def connect_(self, ctx, *, channel: discord.VoiceChannel=None):
        """Connect to voice.
        Parameters
        ------------
        channel: discord.VoiceChannel [Optional]
            The channel to connect to. If a channel is not specified, an attempt to join the voice channel you are in
            will be made.
        This command also handles moving the bot to different channels.
        """
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                raise InvalidVoiceChannel('No channel to join. Please either specify a valid channel or join one.')

        vc = ctx.voice_client

        if vc:
            if vc.channel.id == channel.id:
                return
            try:
                await vc.move_to(channel)
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Moving to channel: <{channel}> timed out.')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'Connecting to channel: <{channel}> timed out.')

        await ctx.send(f'Connected to: **{channel}**', delete_after=20)

    @commands.command(name='play', aliases=['yt', 'push'])
    async def play_(self, ctx, *, search: str):
        """Request a song and add it to the queue."""
        

        vc = ctx.voice_client

        if not vc:
            await ctx.invoke(self.connect_)

        gplayer = self.get_player(ctx)
        if 'playlist?list=' in search:
            await ctx.trigger_typing()
            # (0 -> title, 1 -> weburl)
            strmList = await self.loader.load_playlist(search)
            for entry in strmList:
                await gplayer.sngQueue.put(await self.loader.load_song(f"https://www.youtube.com/watch?v={entry[1]}"))
            await ctx.invoke(self.queue_info)

        else:
            strmSong = await self.loader.load_song(search)
            await ctx.send(f'**{strmSong.title}** now in queue!')
            await gplayer.sngQueue.put(strmSong)
        '''
        strmSong = await self.loader.load_local_song(search)
        await ctx.send(f'**{strmSong.title}** now in queue!')
        await gplayer.sngQueue.put(strmSong)
        '''
    @commands.command(name='pause')
    async def pause_(self, ctx):
        """Pause the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_playing():
            return await ctx.send('I am not currently playing anything!', delete_after=20)
        elif vc.is_paused():
            return

        vc.pause()
        await ctx.send(f'**`{ctx.author}`**: Paused the song!')

    @commands.command(name='resume')
    async def resume_(self, ctx):
        """Resume the currently paused song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!', delete_after=20)
        elif not vc.is_paused():
            return

        vc.resume()
        await ctx.send(f'**`{ctx.author}`**: Resumed the song!')

    @commands.command(name='skip', aliases=['pop'])
    async def skip_(self, ctx):
        """Skip the song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!', delete_after=20)

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        vc.stop()
        await ctx.send(f'**`{ctx.author}`**: Skipped the song!')

    @commands.command(name='queue', aliases=['q', 'playlist'])
    async def queue_info(self, ctx):
        """Retrieve a basic queue of upcoming songs."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!', delete_after=20)

        player = self.get_player(ctx)
        if player.sngQueue.empty():
            return await ctx.send('There are currently no more queued songs.')

        # Grab up to 5 entries from the queue...
        upcoming = list(islice(player.sngQueue._queue, 0, 10))

        fmt = '\n'.join(f'`{i.title} | request by - {ctx.author}\n`' for i in upcoming)
        embed = discord.Embed(title=f'Upcoming - Next {len(upcoming)}', description=fmt)

        await ctx.send(embed=embed)

    @commands.command(name='now_playing', aliases=['np', 'current', 'currentsong', 'playing'])
    async def now_playing_(self, ctx):
        """Display information about the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!', delete_after=20)

        player = self.get_player(ctx)

        await ctx.send(f'**Now Playing:** `{vc.source.title}`requested by `{vc.source.requester}`')

    @commands.command(name='volume', aliases=['vol'])
    async def change_volume(self, ctx, *, vol: int):
        """Change the player volume.
        Parameters
        ------------
        volume: float or int [Required]
            The volume to set the player to in percentage. This must be between 1 and 100.
        """
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently connected to voice!', delete_after=20)

        if not 0 < vol < 101:
            return await ctx.send('Please enter a value between 1 and 100.')

        player = self.get_player(ctx)

        if vc.source:
            vc.source.volume = vol // 100

        player.volume = vol // 100
        await ctx.send(f'**`{ctx.author}`**: Set the volume to **{vol}%**')

    @commands.command(name='stop')
    async def stop_(self, ctx):
        """Stop the currently playing song and destroy the player.
        !Warning!
            This will destroy the player assigned to your guild, also deleting any queued songs and settings.
        """
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            return await ctx.send('I am not currently playing anything!', delete_after=20)

        await self.cleanup(ctx.guild)

    @commands.command(name='setlist')
    async def setlist_(self, ctx):

        player = self.get_player(ctx)
        qlen = 0
        with open('./songData/answer.txt', mode='r', encoding='utf-8-sig') as ans_file:
            acc_data = ans_file.read().splitlines()
            q = [set(e.split()) for e in acc_data]
            qlen = len(q)
            player.ans_que.extend(q)

        await ctx.send(f"loaded {qlen} answers")

    @commands.command(name='noans')
    async def noans_(self, ctx):
        player = self.get_player(ctx)
        if not player.ans_que:
            print('queue empty')
            return await ctx.send('queue empty')

        tmp = player.ans_que.popleft()
        await ctx.send(f'The answer was {tmp}')
            

    @commands.command(name = 'quiz', aliases=['qz'])
    async def _quiz(self, ctx, *args):
        '''make a quiz'''
        player = self.get_player(ctx)
        args = set(args)
        if not args:
            print("Answer cannot be none")
            return await ctx.send(f"Answer cannot be none")
            
        player.ans_que.append(args)
        await ctx.send(f"preview ans = {args}")
        print(f"preview ans = {args}")

    @commands.command(name = 'guess', aliases=['gs'])
    async def _guess(self, ctx, *args):
        '''guess the answer'''

        #await ctx.send(f'**`{ctx.author}`**: guessed {"  ".join(args)}')
        player = self.get_player(ctx)
        if not player.ans_que:
            print('queue empty')
            return await ctx.send('queue empty')
        elif not args:
            return await ctx.send('隨便猜也好嘛(´・ω・`)', delete_after=20)
        elif len(args) > 1:
            await ctx.send('一次只能猜一個(´・ω・`)，只看第一個囉', delete_after=20)
        args = args[0].lower()
        
        print("corr ans : ", player.ans_que[0], "your ans : ", args)

        if args in player.ans_que[0]:
            await ctx.send(f'**`{ctx.author}`** guessed {args}: Correct, next!')
            player.ans_que.popleft()
        else:
            await ctx.send(f'**`{ctx.author}`** guessed {args}: Wrong~ Try again?')

    @commands.command(name = 'ans_queue', aliases=['aq'])
    async def _ans_queue(self, ctx):
        """get answer queue"""
        player = self.get_player(ctx)
        if not player.ans_que:
            print('queue empty')
            return await ctx.send('queue empty')

        upcoming = list(islice(player.ans_que, 0, 10))
        print(*upcoming, sep = '\n')
        fmt = '\n'.join(str(i) for i in upcoming)

        await ctx.send(embed=discord.Embed(title=f'Next {len(upcoming)} Answer', description=fmt))
    

def setup(bot):
    bot.add_cog(Musicv2(bot))
