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
import requests # <--- NUEVO: Añadido para hacer peticiones HTTP

app = Flask(__name__)
CORS(app)

# --- NUEVO: URL del servidor de movimiento ---
MOVEMENT_SERVER_URL = "http://localhost:5001" 

### Definición de la ruta a la carpeta de imágenes del carrusel ###
CAROUSEL_IMG_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'carousel_images')

# --- Estado de la aplicación y configuración ---
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
min_count = 5
forced_video_to_play = None
restart_requested = False

# --- Carga de Modelos ---
try:
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if face_cascade.empty():
        print("CRITICAL ERROR: Cascade Classifier 'haarcascade_frontalface_default.xml' not loaded.")
except Exception as e:
    print(f"CRITICAL ERROR loading Cascade Classifier: {e}")
    face_cascade = None

emotion_labels = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
interpreter = None
input_details = None
output_details = None

try:
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emotion_model.tflite")
    interpreter = tflite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    print("TFLite model loaded successfully. Input shape:", input_details[0]['shape'])
except Exception as e:
    print(f"CRITICAL ERROR: Failed to load TFLite model: {e}")
    interpreter = None

### Función para leer las imágenes del carrusel ###
def get_carousel_images():
    if not os.path.exists(CAROUSEL_IMG_FOLDER):
        print(f"ADVERTENCIA: La carpeta del carrusel no existe en {CAROUSEL_IMG_FOLDER}")
        return []
    try:
        files = sorted([f for f in os.listdir(CAROUSEL_IMG_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))])
        image_urls = [f"/static/carousel_images/{f}" for f in files]
        return image_urls
    except Exception as e:
        print(f"ERROR al leer la carpeta del carrusel: {e}")
        return []

def predict_emotion_tflite(face_roi):
    global interpreter, input_details, output_details
    if interpreter is None or face_roi is None or face_roi.size == 0:
        return "neutral"
    
    gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    try:
        h, w = input_details[0]['shape'][1:3]
        gray_face_resized = cv2.resize(gray_face, (w, h))
    except Exception as e:
        print(f"Error resizing face ROI: {e}")
        return "neutral"

    gray_face_resized = gray_face_resized.astype("float32") / 255.0
    input_data = np.expand_dims(np.expand_dims(gray_face_resized, axis=-1), axis=0)

    try:
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        preds = interpreter.get_tensor(output_details[0]['index'])[0]
        return emotion_labels[np.argmax(preds)]
    except Exception as e:
        print(f"Error TFLite invocation: {e}")
        return "neutral"

def detection_loop():
    global current_frame, detection_complete, detected_emotion, detected_snapshot
    global last_emotion, emotion_start_time, emotion_buffer, forced_video_to_play

    cap = None
    print("Detection Loop: Initializing camera...")
    try:
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            print(f"Camera initialized. Resolution: {cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")
        else:
            print("CRITICAL: Camera not accessible.")
            return
    except Exception as e_cap:
        print(f"CRITICAL ERROR initializing VideoCapture: {e_cap}")
        return

    last_detection_time = time.time()
    print("Detection Loop: Starting frame processing.")
    while True:
        if forced_video_to_play or restart_requested:
            time.sleep(0.1)
            continue

        if not cap or not cap.isOpened():
            print("Camera disconnected. Attempting to re-open...")
            if cap: cap.release()
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            else:
                with frame_lock: current_frame = None
                time.sleep(5)
                continue

        ret, frame = cap.read()
        if not ret or frame is None:
            with frame_lock: current_frame = None
            time.sleep(0.1)
            continue
        
        processed_frame_for_stream = frame.copy()
        
        if face_cascade is not None and not detection_complete and (time.time() - last_detection_time > 0.1):
            last_detection_time = time.time()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

            if len(faces) > 0:
                (x, y, w, h) = faces[0]
                cv2.rectangle(processed_frame_for_stream, (x, y), (x+w, y+h), (0, 255, 0), 2)
                face_roi = frame[y:y+h, x:x+w]
                emotion = predict_emotion_tflite(face_roi)
                emotion_buffer.append((time.time(), emotion))
                emotion_buffer = [(t, e) for (t, e) in emotion_buffer if time.time() - t <= buffer_window]

                if len(emotion_buffer) >= min_count:
                    freq = {e: [tup[1] for tup in emotion_buffer].count(e) for e in set(tup[1] for tup in emotion_buffer)}
                    if freq:
                        dominant_emotion = max(freq, key=freq.get)
                        if freq[dominant_emotion] / len(emotion_buffer) >= threshold_ratio:
                            if not detection_complete:
                                print(f"Detection Loop: Emotion stabilized: {dominant_emotion}.")
                                detection_complete = True
                                detected_emotion = dominant_emotion
                                ret_snap, snap_jpeg = cv2.imencode('.jpg', frame)
                                if ret_snap:
                                    detected_snapshot = snap_jpeg.tobytes()
                
                last_emotion = emotion
                if last_emotion:
                    cv2.putText(processed_frame_for_stream, last_emotion, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                if not detection_complete:
                    emotion_buffer.clear()
                    last_emotion = "no_face"

        ret_jpeg, jpeg_frame = cv2.imencode('.jpg', processed_frame_for_stream)
        if ret_jpeg:
            with frame_lock:
                current_frame = jpeg_frame.tobytes()
        
        time.sleep(0.05)
    
    if cap:
        cap.release()

detection_thread = threading.Thread(target=detection_loop, daemon=True)
detection_thread.start()

def gen_video():
    global current_frame
    while True:
        with frame_lock:
            frame_to_send = current_frame
        if frame_to_send:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_to_send + b'\r\n')
        else:
            # Placeholder logic if no frame is available
            try:
                placeholder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),"static","test.png")
                with open(placeholder_path, "rb") as f:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + f.read() + b'\r\n')
            except Exception as e:
                time.sleep(0.5)
        time.sleep(0.05)


### RUTAS FLASK ###

@app.route('/')
def route_index():
    global forced_video_to_play, detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_start_time, emotion_buffer, restart_requested
    print("Route /: Resetting state for new session.")
    detection_complete = False
    detected_emotion = "neutral"
    detected_snapshot = None
    last_emotion = None
    emotion_start_time = None
    emotion_buffer.clear()
    forced_video_to_play = None
    restart_requested = False
    
    image_list = get_carousel_images()
    return render_template('index.html', image_files=image_list)

@app.route('/video_feed')
def video_feed_route():
    return Response(gen_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/detection_status')
def detection_status_route():
    global forced_video_to_play, detection_complete, detected_emotion, restart_requested
    status_data = {
        "detected": detection_complete,
        "emotion": detected_emotion,
        "restart_requested": restart_requested
    }
    if forced_video_to_play:
        status_data["forced_video"] = forced_video_to_play
        forced_video_to_play = None
    if restart_requested:
        restart_requested = False
    if detection_complete:
        detection_complete = False
    return jsonify(status_data)

@app.route('/snapshot')
def snapshot_route():
    if detected_snapshot:
        return Response(detected_snapshot, mimetype='image/jpeg')
    else:
        return "No snapshot available", 404

@app.route('/get_random_audio')
def get_random_audio_route():
    emotion_folder_name = detected_emotion if detected_emotion in emotion_labels else "neutral"
    audio_folder_path = os.path.join(app.static_folder, "audio", emotion_folder_name)
    
    if not os.path.exists(audio_folder_path):
        audio_folder_path = os.path.join(app.static_folder, "audio", "neutral")
        emotion_folder_name = "neutral"
        if not os.path.exists(audio_folder_path):
            return jsonify({'error': 'Default audio folder not found'}), 404

    try:
        files = [f for f in os.listdir(audio_folder_path) if f.lower().endswith(('.mp3', '.wav', '.ogg'))]
        if not files:
            return jsonify({'error': f'No audio files in folder for {emotion_folder_name}'}), 404
        selected_file = random.choice(files)
        audio_url = f"/static/audio/{emotion_folder_name}/{selected_file}"
        return jsonify({'audio_url': audio_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_random_video')
def get_random_video_route():
    video_folder_path = os.path.join(app.static_folder, "video")
    if not os.path.exists(video_folder_path):
        return jsonify({'error': 'Video folder not found'}), 404
    try:
        files = [f for f in os.listdir(video_folder_path) if f.lower().endswith(('.mp4', '.webm', '.mov'))]
        if not files:
            return jsonify({'error': 'No video files in folder'}), 404
        selected_file = random.choice(files)
        video_url = f"/static/video/{selected_file}"
        return jsonify({'video_url': video_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/list_videos')
def list_videos_route():
    video_folder_path = os.path.join(app.static_folder, "video")
    if not os.path.exists(video_folder_path):
        return jsonify({'error': 'Video folder not found'}), 404
    try:
        video_files = sorted([f for f in os.listdir(video_folder_path) if f.lower().endswith(('.mp4', '.webm', '.mov'))])
        return jsonify({'videos': video_files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/play_specific_video', methods=['POST'])
def play_specific_video_route():
    global forced_video_to_play
    data = request.json
    if not data or 'video_file' not in data:
        return jsonify({'error': 'Invalid request'}), 400
    
    video_file = os.path.basename(data['video_file'])
    abs_video_path = os.path.join(app.static_folder, "video", video_file)
    if not os.path.isfile(abs_video_path):
        return jsonify({'error': f'Video "{video_file}" not found.'}), 404
    
    forced_video_to_play = video_file
    return jsonify({'status': 'ok', 'message': f'Request to play {video_file} received.'})

@app.route('/restart')
def restart_route():
    global restart_requested
    restart_requested = True
    return jsonify({"status": "restarted"})


# --- NUEVA RUTA para comunicar el evento especial al servidor de movimiento ---
@app.route('/trigger_special_event', methods=['POST'])
def trigger_special_event():
    """
    Recibe el aviso del frontend y lo reenvía al servidor de movimiento
    para que inicie la secuencia de movimiento del evento especial.
    """
    try:
        print("APP.PY: Reenviando trigger de evento especial al servidor de movimiento...")
        response = requests.post(f"{MOVEMENT_SERVER_URL}/trigger_special_event_movement")
        
        # Comprobar la respuesta del servidor de movimiento
        if response.status_code == 200:
            print("APP.PY: Servidor de movimiento confirmó el inicio de la secuencia.")
            return jsonify({"status": "ok", "message": "Special event movement triggered."}), 200
        else:
            print(f"APP.PY: Error del servidor de movimiento - {response.status_code}: {response.text}")
            return jsonify({
                "status": "error", 
                "message": "Failed to trigger movement.", 
                "details": response.text
            }), response.status_code
            
    except requests.exceptions.RequestException as e:
        # Error si no se puede conectar al servidor de movimiento
        print(f"CRITICAL ERROR: No se pudo conectar al servidor de movimiento en {MOVEMENT_SERVER_URL}. Error: {e}")
        return jsonify({
            "status": "error", 
            "message": "Could not connect to the movement server."
        }), 503


if __name__ == '__main__':
    print("Flask app starting...")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)