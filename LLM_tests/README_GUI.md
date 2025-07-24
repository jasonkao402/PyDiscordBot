# Schedule Generator Flask GUI

A web-based GUI for the Schedule Generator project that provides an interactive dashboard to manage AI-powered daily schedules.

## Features

- **Real-time Schedule Viewing**: View current time and active tasks
- **AI Schedule Generation**: Generate new schedules with customizable character settings
- **Mind Injection**: Interact with the AI by injecting thoughts and getting responses
- **Simulation Control**: Start/stop/step through schedule simulation
- **WebSocket Updates**: Real-time updates via Socket.IO
- **Responsive Design**: Bootstrap-based responsive interface

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure you have the required configuration files:
   - `acc/config.toml` (Ollama configuration)
   - `schedule_20250724.json` (sample schedule file)

## Quick Start

### Option 1: Use the batch file (Windows)
```bash
start_gui.bat
```

### Option 2: Run manually
```bash
python flask_app.py
```

Then open your browser to: http://127.0.0.1:5000

## Usage

### Dashboard Overview
The dashboard is divided into two main sections:

#### Left Panel - Controls
- **Character Settings**: Configure the AI character's name, personality, and behavior
- **Schedule Controls**: Load existing schedules or generate new ones
- **Simulation Controls**: Start/stop/step through time simulation
- **Current Status**: View current time and active task
- **Mind Injection**: Send thoughts to the AI and get responses

#### Right Panel - Schedule Display
- **Today's Schedule**: Complete list of scheduled events
- **Time Visualization**: Start/end times and duration for each event
- **Interactive Elements**: Hover effects and visual feedback

### Key Functions

1. **Load Schedule**: Load an existing schedule from a JSON file
2. **Generate New Schedule**: Create a new AI-generated schedule based on character settings
3. **Start Simulation**: Begin automatic time progression (90-minute steps every 5 seconds)
4. **Step Simulation**: Manually advance time by 90 minutes
5. **Mind Injection**: Send a thought to the AI and get a contextual response

### Real-time Features
- Live time updates during simulation
- Real-time task changes
- WebSocket-based communication
- Connection status indicator

## Configuration

The app uses the same configuration as the original ScheduleGenerator:
- Ollama API settings from `acc/config.toml`
- Character settings can be modified through the web interface
- Schedule files in JSON format

## API Endpoints

- `GET /` - Main dashboard
- `GET /api/schedule/current` - Get current status
- `GET /api/schedule/today` - Get full schedule
- `POST /api/schedule/load` - Load schedule from file
- `POST /api/schedule/generate` - Generate new schedule
- `POST /api/mind/inject` - Send mind injection to AI
- `POST /api/simulation/start` - Start simulation
- `POST /api/simulation/stop` - Stop simulation
- `POST /api/simulation/step` - Advance simulation

## WebSocket Events

- `connect/disconnect` - Connection status
- `time_update` - Real-time schedule updates

## Troubleshooting

1. **Connection Issues**: Make sure Ollama is running and accessible
2. **Schedule Not Loading**: Check that the schedule JSON file exists and is valid
3. **AI Not Responding**: Verify Ollama API configuration in `config.toml`
4. **Browser Issues**: Try refreshing the page or clearing browser cache

## Development

The Flask app is structured as follows:
- `flask_app.py` - Main Flask application with API routes
- `templates/dashboard.html` - Web interface
- `ScheduleGenerator.py` - Core schedule management (imported)
- `ollama_api.py` - Ollama API integration (imported)

To modify the interface, edit the HTML template. To add new features, extend the Flask routes and corresponding JavaScript functions.
