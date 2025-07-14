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

### NUEVO: Definición de la ruta a la carpeta de imágenes del carrusel ###
CAROUSEL_IMG_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'carousel_images')

# --- INICIO DEL CÓDIGO ORIGINAL (SIN CAMBIOS) ---
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
    print("TFLite model loaded successfully. Input shape:", input_details[0]['shape']) # type: ignore
except Exception as e:
    print(f"CRITICAL ERROR: Failed to load TFLite model: {e}")
    interpreter = None

# --- FIN DEL CÓDIGO ORIGINAL (SIN CAMBIOS) ---

### NUEVO: Función para leer las imágenes del carrusel ###
def get_carousel_images():
    """
    Función que lee la carpeta de imágenes y devuelve una lista de URLs relativas.
    """
    if not os.path.exists(CAROUSEL_IMG_FOLDER):
        print(f"ADVERTENCIA: La carpeta del carrusel no existe en {CAROUSEL_IMG_FOLDER}")
        return []
    
    try:
        # Lista solo los archivos de imagen válidos y los ordena alfabéticamente
        files = sorted([
            f for f in os.listdir(CAROUSEL_IMG_FOLDER) 
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))
        ])
        
        # Crea las rutas relativas que usará el HTML.
        # El servidor de carga en el puerto 5002 servirá estos archivos.
        image_urls = [f"/static/carousel_images/{f}" for f in files]
        return image_urls
    except Exception as e:
        print(f"ERROR al leer la carpeta del carrusel: {e}")
        return []


# --- INICIO DEL CÓDIGO ORIGINAL (SIN CAMBIOS) ---
def predict_emotion_tflite(face_roi):
    """Predice la emoción de una ROI de cara usando el modelo TFLite."""
    global interpreter, input_details, output_details
    if interpreter is None:
        return "neutral"
    if face_roi is None or face_roi.size == 0:
        return "neutral"

    gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    try:
        h, w = input_details[0]['shape'][1:3] # type: ignore
        gray_face_resized = cv2.resize(gray_face, (w, h))
    except Exception as e:
        print(f"Error resizing face ROI: {e}")
        return "neutral"

    gray_face_resized = gray_face_resized.astype("float32") / 255.0
    input_data = np.expand_dims(np.expand_dims(gray_face_resized, axis=-1), axis=0)

    try:
        interpreter.set_tensor(input_details[0]['index'], input_data) # type: ignore
        interpreter.invoke()
        preds = interpreter.get_tensor(output_details[0]['index'])[0] # type: ignore
        return emotion_labels[np.argmax(preds)]
    except Exception as e:
        print(f"Error TFLite invocation: {e}")
        return "neutral"

def detection_loop():
    """Bucle principal para la detección de caras y emociones."""
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
            print("CRITICAL: Camera not accessible (VideoCapture.isOpened() is false).")
            # El resto del manejo de errores de la cámara se mantiene como en tu código original
            return
    except Exception as e_cap:
        print(f"CRITICAL ERROR initializing VideoCapture: {e_cap}")
        return

    detection_processing_interval = 0.1
    last_detection_time = time.time()

    print("Detection Loop: Starting frame processing.")
    while True:
        if forced_video_to_play or restart_requested:
            time.sleep(0.1)
            continue

        if cap is None or not cap.isOpened():
             print("Camera disconnected in loop. Attempting to re-open...")
             if cap: cap.release()
             cap = cv2.VideoCapture(0)
             if cap.isOpened():
                 cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                 cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                 print("Camera re-opened successfully.")
             else:
                 print("Failed to re-open camera. Waiting before next attempt.")
                 with frame_lock: current_frame = None
                 time.sleep(5)
                 continue

        ret, frame = cap.read()
        if not ret or frame is None:
            with frame_lock: current_frame = None
            time.sleep(0.1)
            continue

        current_time_loop = time.time()
        processed_frame_for_stream = frame.copy()

        if face_cascade is not None and not detection_complete and (current_time_loop - last_detection_time > detection_processing_interval):
            last_detection_time = current_time_loop
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
                    freq = {}
                    for _, e in emotion_buffer:
                         freq[e] = freq.get(e, 0) + 1
                    if freq:
                        dominant_emotion = max(freq, key=freq.get)
                        if freq[dominant_emotion] / len(emotion_buffer) >= threshold_ratio:
                            if not detection_complete:
                                print(f"Detection Loop: Emotion stabilized: {dominant_emotion}. Triggering interaction.")
                                detection_complete = True
                                detected_emotion = dominant_emotion
                                ret_snap, snap_jpeg = cv2.imencode('.jpg', frame)
                                if ret_snap:
                                     detected_snapshot = snap_jpeg.tobytes()
                                     print("Snapshot captured.")
                                else:
                                     print("Failed to capture snapshot.")
                        else:
                             last_emotion = dominant_emotion
                    else:
                        last_emotion = None
                else:
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
        else:
             with frame_lock: current_frame = None
        time.sleep(0.05)
    
    if cap:
        cap.release()

detection_thread = threading.Thread(target=detection_loop, daemon=True)
detection_thread.start()

def gen_video():
    """Generador para el stream de video MJPEG."""
    global current_frame
    while True:
        with frame_lock:
            frame_to_send = current_frame
        if frame_to_send:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_to_send + b'\r\n')
        else:
             try:
                 placeholder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),"static","test.png")
                 with open(placeholder_path, "rb") as f: img_bytes = f.read()
                 yield (b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' + img_bytes + b'\r\n')
             except Exception as e:
                 print(f"gen_video: Error sending placeholder: {e}")
                 time.sleep(0.5)
        time.sleep(0.05)
# --- FIN DEL CÓDIGO ORIGINAL (SIN CAMBIOS) ---


### MODIFICADO: Esta es la ruta principal que ahora carga la lista de imágenes ###
@app.route('/')
def route_index():
    """Ruta principal que sirve la interfaz de interacción."""
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
    
    # 1. Llama a la nueva función para obtener la lista de imágenes.
    image_list = get_carousel_images()
    
    # 2. Pasa la lista directamente a la plantilla HTML.
    #    La plantilla podrá acceder a esta lista usando la variable 'image_files'.
    return render_template('index.html', image_files=image_list)


# --- INICIO DEL CÓDIGO ORIGINAL (SIN CAMBIOS) ---
@app.route('/video_feed')
def video_feed_route():
    """Ruta para el stream de video en vivo."""
    if face_cascade is None and interpreter is None:
        pass
    return Response(gen_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/detection_status')
def detection_status_route():
    """Ruta para que el frontend consulte el estado de detección."""
    global forced_video_to_play, detection_complete, detected_emotion, detected_snapshot, restart_requested

    status_data = {
        "detected": detection_complete,
        "emotion": detected_emotion,
        "restart_requested": restart_requested
    }
    video_to_send_now = forced_video_to_play
    if video_to_send_now:
        status_data["forced_video"] = video_to_send_now
        forced_video_to_play = None
    if restart_requested:
         restart_requested = False
    if detection_complete:
        detection_complete = False
    return jsonify(status_data)

@app.route('/snapshot')
def snapshot_route():
    """Ruta para obtener el snapshot cuando se detecta una emoción."""
    global detected_snapshot
    if detected_snapshot:
        return Response(detected_snapshot, mimetype='image/jpeg')
    else:
        try:
            placeholder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),"static","test.png")
            with open(placeholder_path, "rb") as f:
                return Response(f.read(), mimetype='image/jpeg')
        except Exception as e:
             return "No snapshot available or placeholder not found", 404

@app.route('/get_random_audio')
def get_random_audio_route():
    """Ruta para obtener un archivo de audio aleatorio basado en la emoción detectada."""
    global detected_emotion
    emotion_folder_name = detected_emotion if detected_emotion in ["angry", "fear", "happy", "neutral", "sad", "surprise"] else "neutral"
    audio_folder_path = os.path.join(app.static_folder, "audio", emotion_folder_name) # type: ignore
    abs_audio_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), audio_folder_path)

    if not os.path.exists(abs_audio_folder_path):
        emotion_folder_name = "neutral"
        audio_folder_path = os.path.join(app.static_folder, "audio", emotion_folder_name) # type: ignore
        abs_audio_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), audio_folder_path)
        if not os.path.exists(abs_audio_folder_path):
             return jsonify({'error': 'Audio folder not found'}), 404
    try:
        files = [f for f in os.listdir(abs_audio_folder_path) if f.lower().endswith(('.mp3', '.wav', '.ogg'))]
        if not files:
            return jsonify({'error': 'No audio files in folder'}), 404
        selected_file = random.choice(files)
        audio_url = f"/static/audio/{emotion_folder_name}/{selected_file}"
        return jsonify({'audio_url': audio_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_random_video')
def get_random_video_route():
    """Ruta para obtener un archivo de video aleatorio para la interacción."""
    video_folder_path = os.path.join(app.static_folder, "video") # type: ignore
    abs_video_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), video_folder_path)
    if not os.path.exists(abs_video_folder_path):
        return jsonify({'error': 'Video folder not found'}), 404
    try:
        files = [f for f in os.listdir(abs_video_folder_path) if f.lower().endswith(('.mp4', '.webm', '.mov', '.avi'))]
        if not files:
            return jsonify({'error': 'No video files in folder'}), 404
        selected_file = random.choice(files)
        video_url = f"/static/video/{selected_file}"
        return jsonify({'video_url': video_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/list_videos')
def list_videos_route():
    """Ruta para listar los videos disponibles (usado por la interfaz de control)."""
    video_folder_path = os.path.join(app.static_folder, "video") # type: ignore
    abs_video_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), video_folder_path)
    if not os.path.exists(abs_video_folder_path):
        return jsonify({'error': 'Video folder not found on server.'}), 404
    try:
        video_files = sorted([f for f in os.listdir(abs_video_folder_path) if f.lower().endswith(('.mp4', '.webm', '.mov', '.avi'))])
        return jsonify({'videos': video_files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/play_specific_video', methods=['POST'])
def play_specific_video_route():
    """Ruta para forzar la reproducción de un video específico (usado por la interfaz de control)."""
    global forced_video_to_play, detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_buffer, restart_requested
    data = request.json
    if not data or 'video_file' not in data:
        return jsonify({'error': 'Invalid request'}), 400
    video_file = data.get('video_file')
    safe_video_file = os.path.basename(video_file) # type: ignore
    abs_video_path = os.path.join(app.static_folder, "video", safe_video_file) # type: ignore
    full_abs_video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), abs_video_path)
    if not os.path.isfile(full_abs_video_path):
        return jsonify({'error': f'Video "{safe_video_file}" not found.'}), 404
    detection_complete = False
    detected_emotion = "neutral"
    detected_snapshot = None
    last_emotion = None
    emotion_buffer.clear()
    forced_video_to_play = safe_video_file
    restart_requested = False
    return jsonify({'status': 'ok', 'message': f'Request to play {safe_video_file} received. Main interface should switch to video.'})

@app.route('/restart')
def restart_route():
    """Ruta para reiniciar el estado de la aplicación principal (usado por la interfaz de control)."""
    global detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_buffer, forced_video_to_play, restart_requested
    detection_complete = False
    detected_emotion = "neutral"
    detected_snapshot = None
    last_emotion = None
    emotion_buffer.clear()
    forced_video_to_play = None
    restart_requested = True
    return jsonify({"status": "restarted", "message": "Application state has been reset. Restart flag set."})

if __name__ == '__main__':
    print("Flask app starting (performance changes)...")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)

# --- FIN DEL CÓDIGO ORIGINAL (SIN CAMBIOS) ---