"""
AI Engine & Analytics Logic
Handles data processing, statistical analysis, and recovery predictions.
Separated from app.py to keep the main application clean.
"""
import random
import time
from datetime import datetime, timedelta

class AIEngine:
    
    @staticmethod
    def get_detailed_analytics(sessions):
        """
        Processes session history for the Analytics graphs.
        Returns history array and exercise distribution stats.
        """
        history = []
        exercise_counts = {}
        total_acc_sum = 0
        count_acc = 0

        for s in sessions:
            reps = s.get('total_reps', 0)
            errors = s.get('total_errors', 0)
            # Fallback to 'Freestyle' if exercise name missing
            exercise = s.get('exercise', 'Freestyle') 
            
            # Calculate Accuracy per session
            acc = 100
            if reps > 0:
                acc = max(0, 100 - int((errors / reps) * 20))
            
            # History Data for Line Charts
            # Convert timestamp to date obj safely if needed, or use stored date string
            # We use the stored 'date' string "YYYY-MM-DD" for display
            date_str = s.get('date', 'Unknown')
            
            history.append({
                'date': date_str,
                'date_short': date_str[5:] if len(date_str) >= 10 else date_str, # "MM-DD"
                'reps': reps,
                'accuracy': acc,
                'duration': s.get('duration', 0)
            })
            
            # Exercise Aggregation
            if exercise in exercise_counts:
                exercise_counts[exercise] += reps
            else:
                exercise_counts[exercise] = reps
                
            if reps > 0:
                total_acc_sum += acc
                count_acc += 1

        # Format exercise stats for Bar Chart
        exercise_stats = [{'name': k, 'total_reps': v} for k, v in exercise_counts.items()]
        
        avg_accuracy = round(total_acc_sum / count_acc) if count_acc > 0 else 100

        return {
            'history': history,
            'exercise_stats': exercise_stats,
            'average_accuracy': avg_accuracy
        }

    @staticmethod
    def get_recovery_prediction(sessions):
        """
        Generates AI predictions for ROM, Asymmetry, and Recommendations.
        """
        if not sessions:
            return None

        # 1. COMPLIANCE & STREAK
        dates = [s['date'] for s in sessions]
        today = datetime.now().date()
        
        # Calculate simple streak (consecutive days backward from today)
        date_set = set(dates)
        
        # Simple loop to count backwards from today
        loop_date = today
        current_streak = 0
        
        # Check if streak is active (trained today or yesterday)
        if loop_date.strftime("%Y-%m-%d") not in date_set:
             # Check yesterday
             yesterday = loop_date - timedelta(days=1)
             if yesterday.strftime("%Y-%m-%d") in date_set:
                 loop_date = yesterday # Start counting from yesterday
             else:
                 # Streak broken
                 pass

        while loop_date.strftime("%Y-%m-%d") in date_set:
            current_streak += 1
            loop_date -= timedelta(days=1)
        
        # Weekly Adherence (Last 7 days)
        last_7_days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        days_trained = sum(1 for d in last_7_days if d in date_set)
        adherence = int((days_trained / 7) * 100)

        # 2. ASYMMETRY (Right vs Left)
        total_right = sum(s.get('right_reps', 0) for s in sessions)
        total_left = sum(s.get('left_reps', 0) for s in sessions)
        total_limb = total_right + total_left
        asymmetry = 0
        if total_limb > 0:
            asymmetry = abs(total_right - total_left) / total_limb * 100

        # 3. AI DERIVED METRICS (Simulating ROM & Consistency based on Accuracy)
        # We infer that higher accuracy = better ROM & Stability
        recent_sessions = sessions[-5:]
        rom_progress = []
        stability_score = 0
        
        for s in recent_sessions:
            # Re-calc accuracy for internal use
            reps = s.get('total_reps', 1) or 1
            acc = max(0, 100 - int((s.get('total_errors', 0) / reps) * 20))
            
            # Simulate ROM increasing with accuracy (Medical logic: better control = better range)
            base_rom = 85 + (acc * 0.5)  # Range ~85 to ~135 degrees
            # Add slight randomness for organic data look
            rom_val = min(145, max(60, int(base_rom + random.uniform(-5, 5))))
            
            date_label = s.get('date', 'Unknown')
            rom_progress.append({
                'date': date_label[5:] if len(date_label) >= 10 else date_label, 
                'rom': rom_val
            })
            
            stability_score += acc
            
        avg_stability = int(stability_score / len(recent_sessions)) if recent_sessions else 0

        # 4. RECOMMENDATIONS ENGINE
        recommendations = []
        
        # Asymmetry Rule
        if asymmetry > 15:
            weaker = "Left" if total_right > total_left else "Right"
            recommendations.append(f"Imbalance detected: Your {weaker} side is lagging by {int(asymmetry)}%. Focus on unilateral exercises.")
        
        # Stability Rule
        if avg_stability < 70:
            recommendations.append("Stability Score Low: Slow down your rep tempo to improve motor control.")
        elif avg_stability > 90:
            recommendations.append("Excellent Stability: You are ready to increase resistance or weight.")
        
        # Compliance Rule
        if adherence < 50:
            recommendations.append("Consistency Alert: Try to train at least 4 days a week for optimal recovery.")

        # 5. HOTSPOTS SIMULATION (In a real app, this would come from the specific joint errors)
        # For now, we simulate hotspots based on stability
        severity = 100 - avg_stability
        # Ensure values are safe integers
        hotspots = {
            'shoulder': int(severity * random.uniform(0.5, 1.0)),
            'elbow': int(severity * random.uniform(0.2, 0.6)),
            'hip': int(severity * random.uniform(0.1, 0.4))
        }

        return {
            'rom_chart': rom_progress,
            'asymmetry': {
                'right': total_right, 
                'left': total_left, 
                'score': int(asymmetry)
            },
            'stability_score': avg_stability,
            'compliance': {
                'streak': current_streak, 
                'weekly_adherence': adherence, 
                'days_trained': days_trained
            },
            'recommendations': recommendations,
            'hotspots': hotspots
        }