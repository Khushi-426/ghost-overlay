"""
Flask application with API routes - OPTIMIZED & AGNOSTIC VERSION
Flask application - FULLY INTEGRATED DYNAMIC DASHBOARD VERSION
"""

from flask import Flask, Response, jsonify, request
import cv2
import mediapipe as mp
import numpy as np
import time
import json
import os
import random
import string
import requests
import certifi
from collections import deque
from datetime import datetime
from flask_cors import CORS
from dotenv import load_dotenv
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from flask_mail import Mail, Message
from flask_socketio import SocketIO, emit
from bson.objectid import ObjectId

# --- IMPORT CUSTOM AI MODULE (CRITICAL FOR ACCURACY) ---
from ai_engine import AIEngine
from constants import EXERCISE_PRESETS

# ----------------------------------------------------
# 0. CONFIGURATION
# ----------------------------------------------------
load_dotenv()

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ----------------------------------------------------
# 1. MAIL CONFIGURATION
# ----------------------------------------------------
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
mail = Mail(app)

# ----------------------------------------------------
# 2. DATABASE SETUP
# ----------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "physiocheck_db"

try:
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,
        tls=True,
        tlsCAFile=certifi.where(),
        tlsAllowInvalidCertificates=True,
    )
    client.admin.command("ping")
    db = client[DB_NAME]

    users_collection = db["users"]
    otp_collection = db["otps"]
    sessions_collection = db["sessions"]

    exercises_collection = db["exercises"]
    protocols_collection = db["protocols"]
    notifications_collection = db["notifications"]

    print(f"✅ Connected to MongoDB Cloud: {DB_NAME}")
except Exception as e:
    print(f"⚠️ DB Error: {e}")
    users_collection = None
    otp_collection = None
    sessions_collection = None
    notifications_collection = None

# ----------------------------------------------------
# 3. WORKOUT SESSION
# ----------------------------------------------------
workout_session = None

def init_session(exercise_name="Bicep Curl"):
    global workout_session
    from workout_session import WorkoutSession
    workout_session = WorkoutSession(exercise_name)

def generate_video_frames():
    from constants import WorkoutPhase
    if workout_session is None:
        return

    while workout_session.phase != WorkoutPhase.INACTIVE:
        frame, should_continue = workout_session.process_frame()
        if not should_continue or frame is None:
            break

        socketio.emit("workout_update", workout_session.get_state_dict())
        socketio.sleep(0.01)

        ret, buffer = cv2.imencode(".jpg", frame)
        if ret:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buffer.tobytes()
                + b"\r\n"
            )

# ----------------------------------------------------
# 4. EXERCISES (FRONTEND)
# ----------------------------------------------------
def _get_frontend_exercise_list():
    exercise_map = {
        "Bicep Curl": {"difficulty": "Beginner", "duration": "5 Mins"},
        "Knee Lift": {"difficulty": "Beginner", "duration": "5 Mins"},
        "Shoulder Press": {"difficulty": "Intermediate", "duration": "8 Mins"},
        "Squat": {"difficulty": "Intermediate", "duration": "10 Mins"},
        "Standing Row": {"difficulty": "Intermediate", "duration": "7 Mins"},
    }

    result = []
    for name in EXERCISE_PRESETS:
        result.append({
            "id": name.lower().replace(" ", "_"),
            "title": name,
            **exercise_map.get(name, {})
        })
    return result

# ----------------------------------------------------
# 5. SOCKET EVENTS
# ----------------------------------------------------
@socketio.on("connect")
def handle_connect():
    print("Client connected")

@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")

@socketio.on("stop_session")
def handle_stop_session(data):
    global workout_session
    if not workout_session:
        return

    data = data or {}
    email = data.get("email")
    exercise = data.get("exercise", "Freestyle")

    try:
        report = workout_session.get_final_report()
        workout_session.stop()

        if email and sessions_collection:
            r = report["summary"]["RIGHT"]
            l = report["summary"]["LEFT"]

            sessions_collection.insert_one({
                "email": email,
                "exercise": exercise,
                "timestamp": time.time(),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "total_reps": r["total_reps"] + l["total_reps"],
                "total_errors": r["error_count"] + l["error_count"],
            })

        emit("session_stopped", {"status": "success"})
    except Exception as e:
        print("Stop session error:", e)

# ----------------------------------------------------
# 6. AUTH ROUTES
# ----------------------------------------------------
@app.route("/api/auth/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json(silent=True) or {}
    email = data.get("email")

    if users_collection.find_one({"email": email}):
        return jsonify({"error": "Email already registered"}), 400

    otp = "".join(random.choices(string.digits, k=6))
    otp_collection.update_one(
        {"email": email},
        {"$set": {"otp": otp, "created_at": time.time()}},
        upsert=True,
    )

    msg = Message("PhysioCheck OTP", sender=app.config["MAIL_USERNAME"], recipients=[email])
    msg.body = f"Your verification code is: {otp}"
    mail.send(msg)

    return jsonify({"message": "OTP sent"}), 200

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    user = users_collection.find_one({"email": data.get("email")})

    if user and bcrypt.check_password_hash(user["password"], data.get("password")):
        return jsonify({
            "email": user["email"],
            "role": user["role"],
            "name": user["name"]
        })

    return jsonify({"error": "Invalid credentials"}), 401

# ----------------------------------------------------
# 7. ANALYTICS (PATIENT)
# ----------------------------------------------------
@app.route("/api/user/analytics_detailed", methods=["POST"])
def analytics_detailed():
    data = request.get_json(silent=True) or {}
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email required"}), 400

    sessions = list(
        sessions_collection.find({"email": email}).sort("timestamp", -1)
    )

    if not sessions:
        return jsonify({"total_sessions": 0, "history": []})

    history = []
    total_acc = 0

    for s in sessions:
        reps = s.get("total_reps", 0)
        errors = s.get("total_errors", 0)
        acc = max(0, 100 - int((errors / max(reps, 1)) * 20))
        total_acc += acc

        history.append({
            "date": datetime.fromtimestamp(s["timestamp"]).strftime("%Y-%m-%d"),
            "exercise": s.get("exercise"),
            "reps": reps,
            "accuracy": acc
        })

    return jsonify({
        "total_sessions": len(sessions),
        "average_accuracy": total_acc // len(sessions),
        "history": history
    })

# ----------------------------------------------------
# 8. 🔴 THERAPIST ROUTES (FIXED)
# ----------------------------------------------------
@app.route("/api/therapist/patients", methods=["GET"])
def therapist_patients():
    if users_collection is None:
        return jsonify({"patients": []}), 200

    patients = list(users_collection.find(
        {"role": "patient"},
        {"_id": 0, "name": 1, "email": 1, "created_at": 1}
    ))

    enriched = []

    for p in patients:
        last = sessions_collection.find_one(
            {"email": p["email"]},
            sort=[("timestamp", -1)]
        )

        status = "Normal"
        if last:
            reps = last.get("total_reps", 0)
            errors = last.get("total_errors", 0)
            accuracy = max(0, 100 - int((errors / max(reps, 1)) * 20))

            if accuracy < 60:
                status = "High Risk"
            elif accuracy < 80:
                status = "Alert"

        enriched.append({
            "name": p.get("name", "Unknown"),
            "email": p["email"],
            "date_joined": datetime.fromtimestamp(
                p.get("created_at", time.time())
            ).strftime("%Y-%m-%d"),
            "status": status,
            "hasActiveProtocol": False
        })

    return jsonify({"patients": enriched}), 200

@app.route("/api/therapist/notifications", methods=["GET"])
def therapist_notifications():
    if notifications_collection is None:
        return jsonify([]), 200

    notifs = list(
        notifications_collection.find({}).sort("timestamp", -1).limit(10)
    )

    response = []
    for n in notifs:
        response.append({
            "id": str(n.get("_id")),
            "type": n.get("type", "Info"),
            "title": n.get("title", "System"),
            "message": n.get("message", ""),
            "time": n.get("time", "Recently")
        })

    return jsonify(response), 200

# ----------------------------------------------------
# 9. TRACKING + STREAM
# ----------------------------------------------------
@app.route("/start_tracking", methods=["POST"])
def start_tracking():
    global workout_session
    data = request.get_json(silent=True) or {}
    exercise = data.get("exercise", "Bicep Curl")

    if workout_session:
        workout_session.stop()

    init_session(exercise)
    workout_session.start()

    return jsonify({"status": "started", "exercise": exercise})

@app.route("/video_feed")
def video_feed():
    return Response(
        generate_video_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/report_data")
def report_data():
    if workout_session:
        return jsonify(workout_session.get_final_report())
    return jsonify({"error": "No session data"})

# ----------------------------------------------------
# 10. RUN
# ----------------------------------------------------
if __name__ == "__main__":
    init_session()
    socketio.run(app, host="0.0.0.0", port=5001, debug=True)
