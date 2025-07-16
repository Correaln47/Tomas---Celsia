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
import requests

app = Flask(__name__)
CORS(app)

# --- Configuración y Estado ---
MOVEMENT_SERVER_URL = "http://localhost:5001"
CAROUSEL_IMG_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'carousel_images')

# -- Estado de la aplicación --
frame_lock = threading.Lock()
current_frame = None
detection_complete = False
detected_emotion = "neutral"
detected_snapshot = None
last_emotion = None
emotion_buffer = []
forced_video_to_play = None
restart_requested = False
# Se elimina el estado de 'emotion_start_time' que no se usaba

# --- NUEVO: Configuración centralizada del evento especial (con valores por defecto) ---
special_event_config = {
    "enabled": False,
    "min_time": 120,          # en segundos
    "max_time": 180,          # en segundos
    "initial_delay": 1000,    # en ms
    "move_duration": 500,     # en ms
    "delay_between": 500      # en ms
}
# --- NUEVO: Herramientas para controlar el hilo del temporizador del evento ---
special_event_thread = None
special_event_timer_event = threading.Event() # Para reiniciar el temporizador si la config cambia

# --- Carga de Modelos ---
try:
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if face_cascade.empty():
        print("CRITICAL ERROR: Cascade Classifier not loaded.")
except Exception as e:
    print(f"CRITICAL ERROR loading Cascade Classifier: {e}")
    face_cascade = None

emotion_labels = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
interpreter = None
try:
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emotion_model.tflite")
    interpreter = tflite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    print("TFLite model loaded successfully.")
except Exception as e:
    print(f"CRITICAL ERROR: Failed to load TFLite model: {e}")
    interpreter = None

# --- Funciones de Lógica de la Aplicación (sin cambios) ---
def get_carousel_images():
    if not os.path.exists(CAROUSEL_IMG_FOLDER): return []
    try:
        files = sorted([f for f in os.listdir(CAROUSEL_IMG_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))])
        return [f"/static/carousel_images/{f}" for f in files]
    except Exception as e:
        print(f"ERROR al leer la carpeta del carrusel: {e}")
        return []

def predict_emotion_tflite(face_roi):
    if interpreter is None or face_roi is None or face_roi.size == 0: return "neutral"
    gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    h, w = input_details[0]['shape'][1:3]
    gray_face_resized = cv2.resize(gray_face, (w, h))
    input_data = np.expand_dims(np.expand_dims(gray_face_resized.astype("float32") / 255.0, axis=-1), axis=0)
    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()
    preds = interpreter.get_tensor(output_details[0]['index'])[0]
    return emotion_labels[np.argmax(preds)]

def detection_loop():
    global current_frame, detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_buffer, forced_video_to_play
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("CRITICAL: Camera not accessible.")
        return
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    
    while True:
        if forced_video_to_play or restart_requested:
            time.sleep(0.1)
            continue
        
        ret, frame = cap.read()
        if not ret:
            with frame_lock: current_frame = None
            time.sleep(1)
            continue

        processed_frame = frame.copy()
        if not detection_complete:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
            if len(faces) > 0:
                (x, y, w, h) = faces[0]
                cv2.rectangle(processed_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                emotion = predict_emotion_tflite(frame[y:y+h, x:x+w])
                emotion_buffer.append(emotion)
                if len(emotion_buffer) > 10: emotion_buffer.pop(0)
                
                dominant_emotion = max(set(emotion_buffer), key=emotion_buffer.count)
                if emotion_buffer.count(dominant_emotion) / len(emotion_buffer) >= 0.7:
                    if not detection_complete:
                        detection_complete, detected_emotion = True, dominant_emotion
                        _, snap_jpeg = cv2.imencode('.jpg', frame)
                        detected_snapshot = snap_jpeg.tobytes()
            else:
                emotion_buffer.clear()
        
        ret_jpeg, jpeg_frame = cv2.imencode('.jpg', processed_frame)
        if ret_jpeg:
            with frame_lock: current_frame = jpeg_frame.tobytes()
        time.sleep(0.05)

def gen_video():
    while True:
        with frame_lock:
            frame = current_frame
        if frame:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.05)

# --- NUEVO: Lógica del Temporizador del Evento Aleatorio ---
def special_event_scheduler():
    """Hilo que gestiona el temporizador y la activación del evento especial."""
    global forced_video_to_play, special_event_config, special_event_timer_event
    while True:
        # Reinicia la espera si la configuración cambia.
        special_event_timer_event.clear()
        
        if special_event_config["enabled"]:
            min_t, max_t = special_event_config["min_time"], special_event_config["max_time"]
            delay = random.uniform(min_t, max_t)
            print(f"SCHEDULER: Evento especial activado. Próxima ejecución en ~{delay:.0f} segundos.")
            
            # Espera el tiempo aleatorio. Se interrumpe si el evento se resetea.
            interrupted = special_event_timer_event.wait(timeout=delay)
            if interrupted:
                print("SCHEDULER: Configuración cambiada, reiniciando temporizador.")
                continue # Vuelve al inicio del bucle para recalcular el tiempo.
            
            # Si la espera no fue interrumpida y el evento sigue activo...
            if special_event_config["enabled"]:
                # Comprueba si hay alguna otra interacción en curso.
                # Esta es una comprobación simple, se puede hacer más robusta si es necesario.
                if forced_video_to_play is None:
                    print("SCHEDULER: ¡Activando evento especial!")
                    # 1. Fuerza la reproducción del video especial en el frontend.
                    #    Usamos un nombre de archivo único para evitar conflictos.
                    forced_video_to_play = "special/event.mp4"
                    # 2. Envía la orden de movimiento al servidor de movimiento.
                    try:
                        requests.post(f"{MOVEMENT_SERVER_URL}/trigger_special_event_movement")
                    except requests.exceptions.RequestException as e:
                        print(f"SCHEDULER ERROR: No se pudo contactar al servidor de movimiento: {e}")
                else:
                    print("SCHEDULER: Omitiendo evento, otra interacción está activa.")
        else:
            # Si el evento está desactivado, espera a que se active.
            time.sleep(5)

# --- Rutas Flask ---
@app.route('/')
def route_index():
    global forced_video_to_play, detection_complete, detected_emotion, detected_snapshot, emotion_buffer, restart_requested
    detection_complete, detected_emotion, detected_snapshot = False, "neutral", None
    emotion_buffer.clear()
    forced_video_to_play, restart_requested = None, False
    return render_template('index.html', image_files=get_carousel_images())

@app.route('/video_feed')
def video_feed_route():
    return Response(gen_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/detection_status')
def detection_status_route():
    global forced_video_to_play, detection_complete, detected_emotion, restart_requested
    status = {"detected": detection_complete, "emotion": detected_emotion, "restart_requested": restart_requested}
    if forced_video_to_play:
        status["forced_video"] = forced_video_to_play
        forced_video_to_play = None # Limpiar después de enviar
    if restart_requested: restart_requested = False
    if detection_complete: detection_complete = False
    return jsonify(status)

# --- Rutas de Archivos (sin cambios) ---
@app.route('/snapshot')
def snapshot_route():
    return Response(detected_snapshot, mimetype='image/jpeg') if detected_snapshot else ("No snapshot", 404)

@app.route('/get_random_audio')
def get_random_audio_route():
    emotion = detected_emotion if detected_emotion in emotion_labels else "neutral"
    path = os.path.join(app.static_folder, "audio", emotion)
    if not os.path.exists(path): path = os.path.join(app.static_folder, "audio", "neutral")
    files = [f for f in os.listdir(path) if f.lower().endswith('.mp3')]
    if not files: return jsonify({'error': 'No audio files'}), 404
    return jsonify({'audio_url': f"/static/audio/{os.path.basename(path)}/{random.choice(files)}"})

@app.route('/get_random_video')
def get_random_video_route():
    path = os.path.join(app.static_folder, "video")
    files = [f for f in os.listdir(path) if f.lower().endswith('.mp4')]
    if not files: return jsonify({'error': 'No video files'}), 404
    return jsonify({'video_url': f"/static/video/{random.choice(files)}"})

# --- Rutas de Control Externo ---
@app.route('/list_videos')
def list_videos_route():
    path = os.path.join(app.static_folder, "video")
    return jsonify({'videos': sorted([f for f in os.listdir(path) if f.lower().endswith('.mp4')])})

@app.route('/play_specific_video', methods=['POST'])
def play_specific_video_route():
    global forced_video_to_play
    forced_video_to_play = request.json.get('video_file')
    return jsonify({'status': 'ok'})

@app.route('/restart')
def restart_route():
    global restart_requested
    restart_requested = True
    return jsonify({"status": "restarted"})

# --- NUEVO: Rutas centralizadas para la configuración del evento ---
@app.route('/config_special_event', methods=['POST'])
def config_special_event():
    """Recibe la configuración COMPLETA desde la UI de movimiento."""
    global special_event_config, special_event_timer_event
    
    new_config = request.json
    special_event_config.update(new_config)
    
    print(f"CONFIG: Nueva configuración de evento recibida: {special_event_config}")

    # Reenviar la parte de movimiento al servidor de movimiento
    movement_config = {
        "enabled": new_config.get("enabled"),
        "initial_delay": new_config.get("initial_delay"),
        "move_duration": new_config.get("move_duration"),
        "delay_between": new_config.get("delay_between"),
    }
    try:
        requests.post(f"{MOVEMENT_SERVER_URL}/config_special_event", json=movement_config)
    except requests.exceptions.RequestException as e:
        print(f"CONFIG ERROR: No se pudo enviar la config a movement.py: {e}")
        return jsonify({"status": "error", "message": "Could not contact movement server"}), 503
        
    # Despertar al hilo del temporizador para que use la nueva configuración inmediatamente.
    special_event_timer_event.set()
    
    return jsonify({"status": "ok", "message": "Configuración actualizada."})

@app.route('/get_special_event_config', methods=['GET'])
def get_special_event_config():
    """Proporciona la configuración actual a la UI de movimiento."""
    return jsonify(special_event_config)

if __name__ == '__main__':
    # Iniciar el hilo de detección
    threading.Thread(target=detection_loop, daemon=True).start()
    
    # --- NUEVO: Iniciar el hilo del temporizador de eventos especiales ---
    special_event_thread = threading.Thread(target=special_event_scheduler, daemon=True)
    special_event_thread.start()
    
    print("Flask app starting... Main detection and event scheduler are running.")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)