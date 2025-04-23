from collections import deque
from discord.ext import commands, tasks
from flask_socketio import SocketIO

WINDOW_SIZE = 300  # seconds
UPDATE_INTERVAL = 10  # seconds
class personality(commands.Cog):
    __slots__ = ('bot')

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_counts = deque(maxlen=WINDOW_SIZE)
        self.command_counts = deque(maxlen=WINDOW_SIZE)
        self.internal_time = 0
        self.socketio = SocketIO()
    
    def init_app(self, app):
        self.socketio.init_app(app)
        # self.socketio.on_event('message', self.handle_message)
        # self.socketio.on_event('command', self.handle_command)
        self.update_metrics.start()
        
    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def update_metrics(self):
        # current_time = time.time()
        # Remove old entries
        while self.message_counts and self.internal_time - self.message_counts[0][0] > WINDOW_SIZE:
            self.message_counts.popleft()
        while self.command_counts and self.internal_time - self.command_counts[0][0] > WINDOW_SIZE:
            self.command_counts.popleft()
        # Calculate averages
        total_messages = sum(count for _, count in self.message_counts)
        total_commands = sum(count for _, count in self.command_counts)
        avg_messages_per_min = (total_messages / (WINDOW_SIZE / 60)) if self.message_counts else 0
        avg_commands_per_min = (total_commands / (WINDOW_SIZE / 60)) if self.command_counts else 0
        # Emit to clients
        self.socketio.emit('metrics_update', {
            'avg_messages_per_min': round(avg_messages_per_min, 2),
            'avg_commands_per_min': round(avg_commands_per_min, 2)
        })
        
async def setup(bot:commands.Bot):
    # localRead()
    await bot.add_cog(personality(bot))
    
async def teardown(bot):
    pass