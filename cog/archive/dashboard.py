from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_socketio import SocketIO, emit
from collections import deque
from discord.ext import commands

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-nya'  # Replace in production
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,  # 僅在 HTTPS 使用
    SESSION_COOKIE_SAMESITE='Lax'
)
socketio = SocketIO(app)
features = {
    'feature1': True,
    'feature2': False,
    'feature3': True
}
socketio.run(app, debug=True)

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/toggle_feature', methods=['POST'])
def toggle_feature():
    feature = request.json.get('feature')
    if feature in features:
        features[feature] = not features[feature]
        socketio.emit('feature_update', features)
        return jsonify({'status': 'success', 'features': features})
    return jsonify({'status': 'error', 'message': 'Invalid feature'}), 400

def run_flask():
    socketio.run(app)
    
class dashboard(commands.Cog):
    __slots__ = ('bot')

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
async def setup(bot:commands.Bot):
    # localRead()
    await bot.add_cog(dashboard(bot))
    
async def teardown(bot):
    pass

