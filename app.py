from flask import Flask, render_template, Response, jsonify, request
from flask_cors import CORS
import cv2
import time
import threading
import os
import random
import numpy as np
import tflite_runtime.interpreter as tflite
import sys

app = Flask(__name__)
CORS(app)

frame_lock = threading.Lock()
current_frame = None
detection_complete = False
detected_emotion = "neutral"
detected_snapshot = None
last_emotion = None
emotion_start_time = None
emotion_buffer = []
buffer_window = 4
threshold_ratio = 0.6
min_count = 5 # Reducir si la detección tarda mucho en estabilizarse, ej. 5
forced_video_to_play = None

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
emotion_labels = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

interpreter = None
input_details = None
output_details = None

try:
    interpreter = tflite.Interpreter(model_path="emotion_model.tflite")
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    print("TFLite model loaded successfully. Input shape:", input_details[0]['shape']) # type: ignore
except Exception as e:
    print(f"CRITICAL ERROR: Failed to load TFLite model: {e}")
    interpreter = None # Asegurar que es None si falla

def predict_emotion_tflite(face_roi):
    global interpreter, input_details, output_details
    if interpreter is None: return "neutral"
    if face_roi is None or face_roi.size == 0: return "neutral"
    gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    try:
        h, w = input_details[0]['shape'][1:3] # type: ignore
        gray_face_resized = cv2.resize(gray_face, (w, h))
    except Exception as e:
        print(f"Error resizing face ROI: {e}"); return "neutral"
    gray_face_resized = gray_face_resized.astype("float32") / 255.0
    input_data = np.expand_dims(np.expand_dims(gray_face_resized, axis=-1), axis=0)
    try:
        interpreter.set_tensor(input_details[0]['index'], input_data) # type: ignore
        interpreter.invoke()
        preds = interpreter.get_tensor(output_details[0]['index'])[0] # type: ignore
        return emotion_labels[np.argmax(preds)]
    except Exception as e:
        print(f"Error TFLite invocation: {e}"); return "neutral"

def detection_loop():
    global current_frame, detection_complete, detected_emotion, detected_snapshot
    global last_emotion, emotion_start_time, emotion_buffer, forced_video_to_play
    cap = None
    print("Detection Loop: Initializing camera...")
    try:
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            # Reducir resolución para mejorar rendimiento
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            print(f"Camera initialized. Resolution: {cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")
        else:
            print("CRITICAL: Camera not accessible.")
            # Intentar cargar fallback si la cámara falla persistentemente
            try:
                 fallback_img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "test.png")
                 fallback_img = cv2.imread(fallback_img_path)
                 if fallback_img is not None:
                     ret_fb, jpeg_fb = cv2.imencode('.jpg', fallback_img)
                     if ret_fb:
                         with frame_lock: current_frame = jpeg_fb.tobytes()
            except: pass # Ignorar errores de fallback aquí para no detener el hilo
            return # Salir si la cámara no se abre
    except Exception as e_cap:
        print(f"CRITICAL ERROR initializing VideoCapture: {e_cap}"); return

    detection_processing_interval = 0.05 # Procesar detección cada 200ms (5 FPS)
    last_detection_time = time.time()

    while True:
        if forced_video_to_play:
            time.sleep(0.1); continue # Chequeo más frecuente si hay video forzado

        if not cap.isOpened(): # Si la cámara se desconecta
             print("Camera disconnected in loop. Attempting to re-open...")
             cap.release()
             cap = cv2.VideoCapture(0)
             if cap.isOpened():
                 cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                 cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                 print("Camera re-opened.")
             else:
                 print("Failed to re-open camera. Pausing detection attempts.")
                 time.sleep(5) # Esperar 5 segundos antes de reintentar
                 continue

        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.1); continue

        current_time_loop = time.time()
        processed_frame_for_stream = frame.copy() # Copia para el stream

        if not detection_complete and (current_time_loop - last_detection_time > detection_processing_interval):
            last_detection_time = current_time_loop
            # Procesamiento de detección (puede ser una copia diferente si se modifica mucho)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60)) # Ajustar params

            if len(faces) > 0:
                (x, y, w, h) = faces[0]
                cv2.rectangle(processed_frame_for_stream, (x, y), (x+w, y+h), (0, 255, 0), 2) # Dibujar en la copia del stream
                face_roi = frame[y:y+h, x:x+w]
                emotion = predict_emotion_tflite(face_roi)
                
                emotion_buffer.append((time.time(), emotion))
                emotion_buffer = [(t, e) for (t, e) in emotion_buffer if time.time() - t <= buffer_window]

                if len(emotion_buffer) >= min_count:
                    freq = {e: emotion_buffer.count(e) for _, e in emotion_buffer} # Forma más simple de contar
                    if freq:
                        dominant_emotion = max(freq, key=freq.get)
                        if freq[dominant_emotion] / len(emotion_buffer) >= threshold_ratio:
                            if not detection_complete: # Solo una vez
                                print(f"Detection Loop: Emotion stabilized: {dominant_emotion}")
                                detection_complete = True
                                detected_emotion = dominant_emotion
                                ret_snap, snap_jpeg = cv2.imencode('.jpg', frame) # Snapshot del frame original
                                if ret_snap: detected_snapshot = snap_jpeg.tobytes()
                        else: last_emotion = dominant_emotion
                    else: last_emotion = None # Si el buffer se vació o algo raro
                else: last_emotion = emotion
                
                if last_emotion and not detection_complete:
                     cv2.putText(processed_frame_for_stream, last_emotion, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else: # No faces
                if not detection_complete: emotion_buffer.clear(); last_emotion = None
        
        ret_jpeg, jpeg_frame = cv2.imencode('.jpg', processed_frame_for_stream)
        if ret_jpeg:
            with frame_lock: current_frame = jpeg_frame.tobytes()
        
        time.sleep(0.05) # Controla la tasa de actualización del frame para gen_video (~20 FPS)
    if cap: cap.release()

print("Starting detection thread...")
detection_thread = threading.Thread(target=detection_loop, daemon=True)
detection_thread.start()

def gen_video():
    global current_frame
    while True:
        with frame_lock: frame_to_send = current_frame
        if frame_to_send:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_to_send + b'\r\n')
        else: # Si no hay frame, enviar placeholder o esperar
             try: # Enviar fallback
                 fallback_img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "test.png")
                 with open(fallback_img_path, "rb") as f: img_bytes = f.read()
                 yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + img_bytes + b'\r\n')
             except: pass # Ignorar si el fallback falla
             time.sleep(0.1) # Esperar un poco más si no hay frames
        time.sleep(0.05) # Stream a ~20 FPS

@app.route('/')
def route_index():
    global forced_video_to_play, detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_start_time, emotion_buffer
    print("Route /: Resetting state for new session.")
    detection_complete = False; detected_emotion = "neutral"; detected_snapshot = None
    last_emotion = None; emotion_start_time = None; emotion_buffer.clear(); forced_video_to_play = None
    return render_template('index.html')

@app.route('/video_feed')
def video_feed_route(): return Response(gen_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/detection_status')
def detection_status_route():
    global forced_video_to_play, detection_complete, detected_emotion
    video_to_send_now = forced_video_to_play
    status_data = {"detected": detection_complete, "emotion": detected_emotion}
    if video_to_send_now:
        status_data["forced_video"] = video_to_send_now
        print(f"API /detection_status: Sending forced_video: {video_to_send_now} & resetting.")
        forced_video_to_play = None
    return jsonify(status_data)

@app.route('/snapshot')
def snapshot_route():
    global detected_snapshot
    if detected_snapshot: return Response(detected_snapshot, mimetype='image/jpeg')
    try:
        placeholder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),"static","test.png")
        with open(placeholder_path, "rb") as f: return Response(f.read(), mimetype='image/jpeg')
    except: return "No snapshot", 404

@app.route('/get_random_audio')
def get_random_audio_route():
    global detected_emotion
    emotion = detected_emotion if detected_emotion not in ["disgust", "no_face"] else "neutral"
    audio_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), app.static_folder, "audio", emotion)
    if not os.path.exists(audio_folder): # Fallback a neutral
        audio_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), app.static_folder, "audio", "neutral")
        emotion = "neutral" # Para construir la URL correctamente
    if not os.path.exists(audio_folder): return jsonify({'error': 'Audio folder not found'}), 404
    try:
        files = [f for f in os.listdir(audio_folder) if f.lower().endswith(('.mp3', '.wav', '.ogg'))]
        if not files: return jsonify({'error': 'No audio files in folder'}), 404
        return jsonify({'audio_url': f"/static/audio/{emotion}/{random.choice(files)}"})
    except Exception as e: print(f"Error get_random_audio: {e}"); return jsonify({'error': str(e)}), 500

@app.route('/get_random_video')
def get_random_video_route():
    video_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), app.static_folder, "video")
    if not os.path.exists(video_folder): return jsonify({'error': 'Video folder not found'}), 404
    try:
        files = [f for f in os.listdir(video_folder) if f.lower().endswith(('.mp4', '.webm', '.mov', '.avi'))]
        if not files: return jsonify({'error': 'No video files in folder'}), 404
        return jsonify({'video_url': f"/static/video/{random.choice(files)}"})
    except Exception as e: print(f"Error get_random_video: {e}"); return jsonify({'error': str(e)}), 500

@app.route('/list_videos')
def list_videos_route():
    video_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), app.static_folder, "video")
    if not os.path.exists(video_folder): return jsonify({'error': 'Video folder not found on server.'}), 404
    try:
        video_files = sorted([f for f in os.listdir(video_folder) if f.lower().endswith(('.mp4', '.webm', '.mov', '.avi'))])
        print(f"API /list_videos: Found videos: {video_files}")
        return jsonify({'videos': video_files})
    except Exception as e: print(f"Error /list_videos: {e}"); return jsonify({'error': str(e)}), 500

@app.route('/play_specific_video', methods=['POST'])
def play_specific_video_route():
    global forced_video_to_play, detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_buffer
    data = request.json
    if not data or 'video_file' not in data: return jsonify({'error': 'Invalid request'}), 400
    video_file = data.get('video_file')
    abs_video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), app.static_folder, "video", video_file) # type: ignore
    if not os.path.isfile(abs_video_path): return jsonify({'error': f'Video "{video_file}" not found.'}), 404
    print(f"API /play_specific_video: Request for: {video_file}")
    detection_complete = False; detected_emotion = "neutral"; detected_snapshot = None
    last_emotion = None; emotion_buffer.clear(); forced_video_to_play = video_file
    print(f"API /play_specific_video: forced_video_to_play SET TO: {forced_video_to_play}")
    return jsonify({'status': 'ok', 'message': f'Request to play {video_file} received.'})

@app.route('/restart')
def restart_route():
    global detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_buffer, forced_video_to_play
    print("API /restart: Resetting application state.")
    detection_complete = False; detected_emotion = "neutral"; detected_snapshot = None
    last_emotion = None; emotion_buffer.clear(); forced_video_to_play = None
    return jsonify({"status": "restarted"})

if __name__ == '__main__':
    print("Flask app starting (performance changes)...")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)