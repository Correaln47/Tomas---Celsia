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

# --- Configuración de la Detección de Emociones ---
EMOTION_CONFIRMATION_TIME = 1.5  # Segundos que una emoción debe ser detectada consistentemente para ser válida.

# -- Estado de la aplicación --
frame_lock = threading.Lock()
current_frame = None
detection_complete = False
detected_emotion = "neutral"
predete_emotion = "neutral"

looping_videos = False
looping_videos_camera = False

detected_snapshot = None
forced_video_to_play = None
restart_requested = False

# --- Estado para el proceso de confirmación de emoción ---
confirming_emotion = None
emotion_confirmation_start_time = None

# --- Configuración del evento especial ---
special_event_config = {
    "enabled": False,
    "min_time": 120,
    "max_time": 180,
    "initial_delay": 23500, # Este es el valor que cambiaste
    "move_duration": 450,
    "delay_between": 400
}
special_event_thread = None
special_event_timer_event = threading.Event()

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

# --- Lógica de la Aplicación ---
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
    global current_frame, detection_complete, detected_emotion, detected_snapshot, forced_video_to_play, restart_requested
    global confirming_emotion, emotion_confirmation_start_time
    
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
                
                current_emotion_reading = predict_emotion_tflite(frame[y:y+h, x:x+w])

                if current_emotion_reading == confirming_emotion:
                    if time.time() - emotion_confirmation_start_time >= EMOTION_CONFIRMATION_TIME:
                        print(f"DETECTION: Emotion '{confirming_emotion}' confirmed for {EMOTION_CONFIRMATION_TIME}s.")
                        detection_complete = True
                        detected_emotion = confirming_emotion
                        _, snap_jpeg = cv2.imencode('.jpg', frame)
                        detected_snapshot = snap_jpeg.tobytes()
                        confirming_emotion = None
                        emotion_confirmation_start_time = None
                else:
                    print(f"DETECTION: New candidate emotion: '{current_emotion_reading}'. Starting timer...")
                    confirming_emotion = current_emotion_reading
                    emotion_confirmation_start_time = time.time()
            else:
                if confirming_emotion is not None:
                    print("DETECTION: Face lost. Resetting confirmation state.")
                confirming_emotion = None
                emotion_confirmation_start_time = None
        
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

def special_event_scheduler():
    global forced_video_to_play, special_event_config, special_event_timer_event
    while True:
        special_event_timer_event.clear()
        
        if special_event_config["enabled"]:
            min_t, max_t = special_event_config["min_time"], special_event_config["max_time"]
            delay = random.uniform(min_t, max_t)
            print(f"SCHEDULER: Special event armed. Next trigger in ~{delay:.0f} seconds.")
            
            interrupted = special_event_timer_event.wait(timeout=delay)
            if interrupted:
                print("SCHEDULER: Config changed, restarting timer.")
                continue
            
            if special_event_config["enabled"] and forced_video_to_play is None:
                print("SCHEDULER: Triggering special event!")
                forced_video_to_play = "special/event.mp4"
                try:
                    # ### CAMBIO 1 ###
                    # Ahora se envía la configuración de movimiento al servidor de movimiento.
                    event_movement_params = {
                        "initial_delay": special_event_config.get("initial_delay"),
                        "move_duration": special_event_config.get("move_duration"),
                        "delay_between": special_event_config.get("delay_between")
                    }
                    requests.post(
                        f"{MOVEMENT_SERVER_URL}/trigger_special_event_movement",
                        json=event_movement_params
                    )
                except requests.exceptions.RequestException as e:
                    print(f"SCHEDULER ERROR: Could not contact movement server: {e}")
            elif forced_video_to_play is not None:
                print("SCHEDULER: Skipping event, another interaction is active.")
        else:
            time.sleep(5)

# --- Rutas Flask ---
@app.route('/')
def route_index():
    global forced_video_to_play, detection_complete, detected_emotion, detected_snapshot, restart_requested
    global confirming_emotion, emotion_confirmation_start_time
    
    detection_complete, detected_emotion, detected_snapshot = False, "happy", None
    forced_video_to_play, restart_requested = None, False
    confirming_emotion, emotion_confirmation_start_time = None, None
    
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
        forced_video_to_play = None
    if restart_requested: restart_requested = False
    if detection_complete: detection_complete = False
    return jsonify(status)

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
    
@app.route('/trigger_special_event_manually', methods=['POST'])
def trigger_special_event_manually_route():
    global forced_video_to_play
    if forced_video_to_play is not None:
        return jsonify({"status": "error", "message": "Otra interacción ya está en curso."}), 409
    print("MANUAL TRIGGER: ¡Activando evento especial manualmente!")
    forced_video_to_play = "special/event.mp4"
    try:
        # ### CAMBIO 2 ###
        # También se envía la configuración al activar el evento manualmente.
        event_movement_params = {
            "initial_delay": special_event_config.get("initial_delay"),
            "move_duration": special_event_config.get("move_duration"),
            "delay_between": special_event_config.get("delay_between")
        }
        requests.post(
            f"{MOVEMENT_SERVER_URL}/trigger_special_event_movement",
            json=event_movement_params
        )
    except requests.exceptions.RequestException as e:
        print(f"MANUAL TRIGGER ERROR: No se pudo contactar al servidor de movimiento: {e}")
        return jsonify({"status": "warning", "message": "Video triggered, but could not contact movement server."}), 503
    return jsonify({"status": "ok", "message": "Evento especial activado manualmente."})

@app.route('/config_special_event', methods=['POST'])
def config_special_event():
    global special_event_config, special_event_timer_event
    new_config = request.json
    special_event_config.update(new_config)
    print(f"CONFIG: Nueva configuración de evento recibida: {special_event_config}")
    # No es necesario enviar la configuración al servidor de movimiento aquí,
    # ya que se enviará en el momento de la activación del evento.
    special_event_timer_event.set() # Reinicia el temporizador del evento con la nueva config.
    return jsonify({"status": "ok", "message": "Configuración actualizada."})

@app.route('/get_special_event_config', methods=['GET'])
def get_special_event_config():
    return jsonify(special_event_config)


# --------------------- Cambio de cara predeterminada ---------
@app.route('/get_predete_emotion', methods=['GET'])
def get_predete_emotion_route():
    global predete_emotion
    return jsonify({"emotion": predete_emotion})

@app.route("/set_predete_emotion", methods=['POST'])
def set_predete_emotion():
    global predete_emotion
    predete_emotion = request.args.get('emotion')
    return jsonify({"emotion": predete_emotion})

#------------------------- Videos automáticos -----------------
@app.route('/set_video_loop_state', methods=['POST'])
def set_video_loop_state():
    global looping_videos
    state_param = request.args.get('state')
    looping_videos = state_param == 'true' if state_param is not None else False
    return jsonify({"looping": looping_videos})


@app.route('/get_video_loop_state', methods=['GET'])
def get_video_loop_state():
    return jsonify({"looping": looping_videos})


@app.route('/set_video_loop_camera_state', methods=['POST'])
def set_video_loop_camera_state():
    global looping_videos_camera
    state_param = request.args.get('state')
    looping_videos_camera = state_param == 'true' if state_param is not None else False
    return jsonify({"looping": looping_videos_camera})


@app.route('/get_video_loop_camera_state', methods=['GET'])
def get_video_loop_camera_state():
    return jsonify({"looping": looping_videos_camera})




if __name__ == '__main__':
    threading.Thread(target=detection_loop, daemon=True).start()
    special_event_thread = threading.Thread(target=special_event_scheduler, daemon=True)
    special_event_thread.start()
    print("Flask app starting... Main detection and event scheduler are running.")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)