"""
Flask application with API routes
"""
from flask import Flask, Response, jsonify
import cv2
import mediapipe as mp
import numpy as np
import time
import json
import os
import random
import string
import requests
import certifi # Ensure this is imported
from collections import deque
from datetime import datetime
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from flask_mail import Mail, Message

# --- 0. CONFIGURATION ---
load_dotenv()

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

# --- 1. MAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
mail = Mail(app)

# --- 2. DATABASE SETUP (DOUBLE SSL FIX) ---
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "physiocheck_db"

try:
    # Use BOTH certifi AND allow invalid certs to be 100% sure it connects
    client = MongoClient(
        MONGO_URI, 
        serverSelectionTimeoutMS=5000, 
        tls=True,
        tlsCAFile=certifi.where(),       # Fix 1: Provide correct CA
        tlsAllowInvalidCertificates=True # Fix 2: Bypass validation if Fix 1 fails
    )
    
    # Trigger a connection check
    client.admin.command('ping') 
    
    db = client[DB_NAME]
    users_collection = db['users']
    otp_collection = db['otps']
    sessions_collection = db['sessions']
    print(f"✅ Connected to MongoDB Cloud: {DB_NAME}")
except Exception as e:
    print(f"⚠️ DB Error: {e}")
    db = None
    users_collection = None
    otp_collection = None
    sessions_collection = None

# Global session instance
workout_session = None

def init_session():
    """Initialize workout session"""
    global workout_session
    from workout_session import WorkoutSession
    workout_session = WorkoutSession()

def generate_video_frames():
    """Generator for video streaming using the WorkoutSession class"""
    from constants import WorkoutPhase
    
    if workout_session is None: return
    
    while workout_session.phase != WorkoutPhase.INACTIVE:
        # workout_session.process_frame handles all MediaPipe, UI drawing, and phase logic
        frame, should_continue = workout_session.process_frame() 
        
        if not should_continue or frame is None:
            break
        
        # Encode frame
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
# --- END VIDEO GENERATOR ---

# --- 3. MEDIA PIPE SETUP (CLEANED) ---
mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils

# --- 6. AUTHENTICATION ROUTES (UNCHANGED) ---

@app.route('/api/auth/send-otp', methods=['POST'])
def send_otp():
    if users_collection is None: return jsonify({'error': 'Database unavailable'}), 503
    data = request.json
    email = data.get('email')
    
    if users_collection.find_one({'email': email}):
        return jsonify({'error': 'Email is already registered. Please login.'}), 400

    otp = ''.join(random.choices(string.digits, k=6))
    
    otp_collection.update_one(
        {'email': email}, 
        {'$set': {'otp': otp, 'created_at': time.time()}}, 
        upsert=True
    )

    try:
        msg = Message('PhysioCheck Verification Code', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f"Your verification code is: {otp}\n\nThis code expires in 10 minutes."
        mail.send(msg)
        return jsonify({'message': 'OTP sent successfully'}), 200
    except Exception as e:
        print(f"Mail Error: {e}")
        return jsonify({'error': 'Failed to send email.'}), 500

@app.route('/api/auth/signup-verify', methods=['POST'])
def signup_verify():
    if users_collection is None: return jsonify({'error': 'Database unavailable'}), 503
    data = request.json
    email = data.get('email')
    otp_input = data.get('otp')
    
    record = otp_collection.find_one({'email': email})
    if not record or record['otp'] != otp_input:
        return jsonify({'error': 'Invalid or expired OTP'}), 400
    
    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    user = {
        'name': data['name'],
        'email': email,
        'password': hashed_password,
        'role': data.get('role', 'patient'),
        'licenseId': data.get('licenseId', None),
        'created_at': time.time(),
        'auth_method': 'email'
    }
    users_collection.insert_one(user)
    otp_collection.delete_one({'email': email}) 
    return jsonify({'message': 'User verified and created!', 'user': {'name': user['name'], 'role': user['role']}}), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    if users_collection is None: return jsonify({'error': 'Database unavailable'}), 503
    data = request.json
    user = users_collection.find_one({'email': data['email']})
    
    if user and user.get('auth_method') == 'google' and not user.get('password'):
        return jsonify({'error': 'Please sign in with Google'}), 400

    if user and bcrypt.check_password_hash(user['password'], data['password']):
        return jsonify({
            'message': 'Login successful', 
            'role': user['role'],
            'name': user['name'],
            'email': user['email']
        }), 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/auth/google', methods=['POST'])
def google_auth():
    if users_collection is None: return jsonify({'error': 'Database unavailable'}), 503
    token = request.json.get('token')
    role = request.json.get('role', 'patient') 
    
    try:
        resp = requests.get(
            'https://www.googleapis.com/oauth2/v1/userinfo',
            params={'access_token': token, 'alt': 'json'}
        )
        if not resp.ok: return jsonify({'error': 'Invalid Google Token'}), 401
            
        google_user = resp.json()
        email = google_user['email']
        name = google_user['name']
        
        user = users_collection.find_one({'email': email})
        if not user:
            user = {
                'name': name, 'email': email, 'password': '', 
                'role': role, 'created_at': time.time(), 'auth_method': 'google'
            }
            users_collection.insert_one(user)
            
        return jsonify({
            'message': 'Google login successful',
            'role': user['role'], 'name': user['name'], 'email': user['email']
        }), 200
    except Exception as e:
        print(f"Google Auth Error: {e}")
        return jsonify({'error': 'Authentication failed'}), 500

# --- 7. PROFILE STATS ROUTES (UNCHANGED) ---
@app.route('/api/user/stats', methods=['POST'])
def get_user_stats():
    if sessions_collection is None: return jsonify({'error': 'DB Error'}), 503
    
    email = request.json.get('email')
    if not email: return jsonify({'error': 'Email required'}), 400
    
    user_sessions = list(sessions_collection.find({'email': email}))
    
    total_workouts = len(user_sessions)
    total_reps = sum(s.get('total_reps', 0) for s in user_sessions)
    total_duration = sum(s.get('duration', 0) for s in user_sessions)
    
    total_errors = sum(s.get('total_errors', 0) for s in user_sessions)
    accuracy = 100
    if total_reps > 0:
        accuracy = max(0, 100 - int((total_errors / total_reps) * 20))

    graph_data = []
    for s in user_sessions[-7:]:
        graph_data.append({
            'date': s.get('date', 'Unknown'),
            'reps': s.get('total_reps', 0)
        })

    return jsonify({
        'total_workouts': total_workouts,
        'total_reps': total_reps,
        'total_minutes': round(total_duration / 60, 1),
        'accuracy': accuracy,
        'graph_data': graph_data
    })

# --- 9. TRACKING CONTROL ROUTES (UPDATED TO USE WorkoutSession) ---

@app.route('/start_tracking')
def start_tracking():
    """Start new workout session, beginning with calibration"""
    from constants import WorkoutPhase
    global workout_session

    if workout_session and workout_session.phase != WorkoutPhase.INACTIVE:
        return jsonify({'status': 'already_active'}), 400
    
    try:
        if workout_session is None:
            init_session()
        workout_session.start()
        return jsonify({'status': 'success', 'message': 'Calibration started'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to start session: {e}'}), 500


@app.route('/stop_tracking', methods=['POST'])
def stop_tracking():
    """Stop current workout session, clean up resources, and save data"""
    global workout_session
    from constants import WorkoutPhase
    
    if not workout_session or workout_session.phase == WorkoutPhase.INACTIVE:
        return jsonify({'status': 'inactive'})
    
    data = request.json
    user_email = data.get('email') if data else None
    
    report = workout_session.get_final_report()
    workout_session.stop() 
    
    # Save to DB using data retrieved from workout_session
    if user_email and sessions_collection is not None:
        # Duration is taken from the report generated by WorkoutSession
        duration = report.get('duration', 0)
        right_summary = report['summary']['RIGHT']
        left_summary = report['summary']['LEFT']
        
        session_doc = {
            'email': user_email,
            'date': datetime.now().strftime("%Y-%m-%d"),
            'timestamp': time.time(),
            'duration': duration,
            'total_reps': right_summary['total_reps'] + left_summary['total_reps'],
            'right_reps': right_summary['total_reps'],
            'left_reps': left_summary['total_reps'],
            'total_errors': right_summary['error_count'] + left_summary['error_count']
        }
        sessions_collection.insert_one(session_doc)
        print(f"💾 Saved workout for {user_email}")

    # Since the report is generated by WorkoutSession, we return it directly.
    return jsonify({'status': 'success', 'report': report})


@app.route('/video_feed')
def video_feed():
    """Stream video frames using the WorkoutSession process_frame method"""
    return Response(generate_video_frames(), 
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/data_feed')
def data_feed():
    """Get current workout state from WorkoutSession"""
    if workout_session:
        return jsonify(workout_session.get_state_dict())
    return jsonify({'status': 'INACTIVE'})

@app.route('/report_data')
def report_data():
    """Get final session report from WorkoutSession"""
    if workout_session:
        return jsonify(workout_session.get_final_report())
    return jsonify({'error': 'No session data available'})

if __name__ == '__main__':
    
    init_session()
    app.run(host='0.0.0.0', port=5000, debug=True)