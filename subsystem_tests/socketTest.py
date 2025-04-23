from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
# app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('message')
def handle_message(msg):
    print(f'Received message: {msg}')
    emit('message', f'User: {msg}', broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)