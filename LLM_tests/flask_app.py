from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
import asyncio
import json
from datetime import datetime, timedelta
from ScheduleGenerator import ScheduleManager, Event, list_events, TIME_ZONE
import uuid
import concurrent.futures
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global schedule manager instance
schedule_manager = None
executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

def get_schedule_manager():
    global schedule_manager
    if schedule_manager is None:
        schedule_manager = ScheduleManager()
        schedule_manager.initialize()
    return schedule_manager

def run_async_in_thread(async_func):
    """Helper function to run async functions in a separate thread with proper event loop handling"""
    def wrapper():
        try:
            logger.info("Starting async operation in thread")
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(async_func)
                logger.info("Async operation completed successfully")
                return result
            finally:
                # Properly cleanup the loop
                try:
                    # Cancel all running tasks
                    pending = asyncio.all_tasks(loop)
                    if pending:
                        logger.info(f"Cancelling {len(pending)} pending tasks")
                        for task in pending:
                            task.cancel()
                        
                        # Wait for all tasks to complete cancellation
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                finally:
                    loop.close()
                    logger.info("Event loop closed")
        except Exception as e:
            logger.error(f"Error in async execution: {e}")
            raise e
    
    # Run in thread pool to avoid blocking
    logger.info("Submitting async operation to thread pool")
    future = executor.submit(wrapper)
    return future.result(timeout=30)  # 30 second timeout

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/schedule/current')
def get_current_schedule():
    """Get current schedule information"""
    try:
        sm = get_schedule_manager()
        current_task = sm.get_task_at(sm.internal_time)        
        return jsonify({
            'success': True,
            'current_time': sm.internal_time.strftime('%Y-%m-%d %H:%M'),
            'current_task': {
                'start_time': current_task.start_time.strftime('%H:%M'),
                'end_time': current_task.end_time.strftime('%H:%M'),
                'what_to_do': current_task.what_to_do,
                'interaction_target': current_task.interaction_target
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/schedule/today')
def get_today_schedule():
    """Get full today's schedule"""
    try:
        sm = get_schedule_manager()
        
        schedule_items = []
        for event in sm.today_todo_list:
            schedule_items.append({
                'start_time': event.start_time.strftime('%H:%M'),
                'end_time': event.end_time.strftime('%H:%M'),
                'what_to_do': event.what_to_do,
                'interaction_target': event.interaction_target,
                'duration_minutes': int(event.duration.total_seconds() / 60)
            })
        
        return jsonify({
            'success': True,
            'schedule': schedule_items,
            'total_events': len(schedule_items)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/schedule/load', methods=['POST'])
def load_schedule():
    """Load schedule from file"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.json
        else:
            data = request.form.to_dict()
        filename = data.get('filename', 'schedule_20250724.json')
        
        sm = get_schedule_manager()
        
        with open(filename, "r", encoding="utf8") as f:
            sm.today_schedule_text = f.read()
        
        sm.today_todo_list = sm.parse_schedule_text(sm.today_schedule_text)
        
        return jsonify({
            'success': True,
            'message': f'Schedule loaded from {filename}',
            'events_count': len(sm.today_todo_list)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/schedule/generate', methods=['POST'])
def generate_schedule():
    """Generate new schedule"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.json
        else:
            data = request.form.to_dict()
        name = data.get('name', '伊莉亞')
        personality = data.get('personality', '熟悉日本名古屋美食和景點的攝影師女孩')
        behavior = data.get('behavior', '擅長規劃旅遊行程')
        
        sm = get_schedule_manager()
        sm.initialize(name, personality, behavior)
        
        # Run async function using our helper
        run_async_in_thread(sm.spawn_schedule())
        
        # Parse the generated schedule
        sm.today_todo_list = sm.parse_schedule_text(sm.today_schedule_text)
        
        # Save to file
        filename = f"schedule_{sm.internal_time.strftime('%Y%m%d')}.json"
        with open(filename, "w", encoding='utf8') as f:
            f.write(sm.today_schedule_text)
        
        return jsonify({
            'success': True,
            'message': f'New schedule generated and saved to {filename}',
            'events_count': len(sm.today_todo_list)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/mind/inject', methods=['POST'])
def inject_mind():
    """Inject a thought and get AI response"""
    try:
        logger.info("Mind injection request received")
        # Handle both JSON and form data
        if request.is_json:
            data = request.json
        else:
            data = request.form.to_dict()
        mind_injection = data.get('mind_injection', '')
        
        sm = get_schedule_manager()
        
        # If no mind injection provided, use current event to generate narration
        if not mind_injection.strip():
            current_task = sm.get_task_at(sm.internal_time)
            mind_injection = f"我現在正在{current_task.what_to_do}，附近有{current_task.interaction_target}"
            is_auto_generated = True
            logger.info("Using auto-generated mind injection")
        else:
            is_auto_generated = False
            logger.info("Using user-provided mind injection")
        
        # Build status prompt
        status_prompt = sm.build_current_task_prompt(sm.internal_time, mind_injection)
        
        # Get AI response using our helper
        logger.info("Sending request to AI")
        status = run_async_in_thread(sm.react_to_task(status_prompt))
        logger.info("AI response received")
        
        return jsonify({
            'success': True,
            'response': status.message.content,
            'timestamp': sm.internal_time.strftime('%H:%M'),
            'mind_injection': mind_injection,
            'is_auto_generated': is_auto_generated
        })
    except Exception as e:
        logger.error(f"Error in mind injection: {e}")
        return jsonify({'success': False, 'error': str(e)})



@app.route('/api/simulation/step', methods=['POST', 'GET'])
def simulation_step():
    """Advance simulation by specified time interval"""
    try:
        logger.info("Simulation step requested")
        # Handle GET, JSON and form data
        if request.method == 'GET':
            data = request.args.to_dict()
        elif request.is_json:
            data = request.json or {}
        else:
            data = request.form.to_dict()
          # Get interval from request, default to 90 minutes
        interval_minutes = int(data.get('interval_minutes', 90))
        
        # Validate interval options (30min, 60min, 90min)
        valid_intervals = [30, 60, 90]
        if interval_minutes not in valid_intervals:
            return jsonify({
                'success': False, 
                'error': f'Invalid interval. Valid options: {valid_intervals} minutes (30min, 60min, 90min)'
            })
        
        sm = get_schedule_manager()
        oldtime = sm.internal_time
        
        # Advance time by specified interval
        sm.internal_time += timedelta(minutes=interval_minutes)
        logger.info(f"Time advanced from {oldtime.strftime('%H:%M')} to {sm.internal_time.strftime('%H:%M')} (+{interval_minutes} minutes)")
        
        # Check if we moved to next day
        if sm.internal_time.day != oldtime.day:
            sm.today_todo_list = sm.parse_schedule_text(sm.today_schedule_text)
            logger.info("Moved to next day, reloaded schedule")
        
        current = sm.get_task_at(sm.internal_time)
        
        # Emit update to all connected clients
        socketio.emit('time_update', {
            'current_time': sm.internal_time.strftime('%Y-%m-%d %H:%M'),
            'current_task': {
                'start_time': current.start_time.strftime('%H:%M'),
                'end_time': current.end_time.strftime('%H:%M'),
                'what_to_do': current.what_to_do,
                'interaction_target': current.interaction_target
            },
            'interval_minutes': interval_minutes        })
        logger.info("Time update emitted to clients")
        
        return jsonify({
            'success': True,
            'current_time': sm.internal_time.strftime('%Y-%m-%d %H:%M'),
            'current_task': str(current),
            'interval_minutes': interval_minutes,
            'available_intervals': {
                '30min': 30,
                '1hour': 60,
                '1.5hour': 90
            }
        })
    except Exception as e:
        logger.error(f"Error in simulation step: {e}")
        return jsonify({'success': False, 'error': str(e)})



@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('connected', {'data': 'Connected to ScheduleGenerator'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

@app.teardown_appcontext
def cleanup_executor(error):
    """Cleanup executor when app context tears down"""
    pass

if __name__ == '__main__':
    try:
        socketio.run(app, debug=True, host='127.0.0.1', port=5000)
    finally:
        # Cleanup executor on exit
        executor.shutdown(wait=True)
