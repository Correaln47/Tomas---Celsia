from flask import Flask, render_template, Response, jsonify, request
from flask_cors import CORS # Importar CORS
import cv2
import time
import threading
import os
import random
import numpy as np
import tflite_runtime.interpreter as tflite
import sys # Importar sys para manejo de errores críticos

app = Flask(__name__)
CORS(app) # Habilitar CORS para todas las rutas y orígenes

# --- Global state and thread lock ---
frame_lock = threading.Lock()
current_frame = None    # The live, JPEG-encoded frame with overlays

detection_complete = False   # Set to True when a stable emotion is detected
detected_emotion = "neutral"   # The detected emotion (e.g. "neutral")
detected_snapshot = None       # The frozen snapshot (for interaction phase)

# For stable emotion detection
last_emotion = None
emotion_start_time = None

emotion_buffer = []  # list of tuples (timestamp, emotion)
buffer_window = 4    # time window in seconds
threshold_ratio = 0.6  # require % or more of detections to be the same emotion
min_count = 7

# --- Nueva variable global para video forzado ---
forced_video_to_play = None

# --- Load face detector and TFLite emotion model ---
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
emotion_labels = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

# Variable para el intérprete TFLite
interpreter = None
input_details = None
output_details = None

try:
    interpreter = tflite.Interpreter(model_path="emotion_model.tflite")
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    print("TFLite model input shape:", input_details[0]['shape'])
except Exception as e:
    print(f"CRITICAL ERROR: Failed to load TFLite model: {e}")
    print("The application might not function correctly regarding emotion detection.")
    # Considerar si la aplicación debe detenerse si el modelo no carga:
    # sys.exit("Exiting due to model load failure.")


def predict_emotion_tflite(face_roi):
    global interpreter, input_details, output_details # Acceder a las variables globales

    if interpreter is None:
        print("Error: TFLite interpreter not loaded.")
        return "neutral"
        
    if face_roi is None or face_roi.size == 0:
        # print("Error: face_roi está vacío en predict_emotion_tflite") # Comentado para reducir logs
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
        emotion_index = np.argmax(preds)
        # print("Predicted probabilities:", preds, "-> Selected label:", emotion_labels[emotion_index]) # Comentado
        return emotion_labels[emotion_index]
    except Exception as e:
        print(f"Error during TFLite interpreter invocation: {e}")
        return "neutral"


def detection_loop():
    global current_frame, detection_complete, detected_emotion, detected_snapshot
    global last_emotion, emotion_start_time, emotion_buffer, forced_video_to_play

    cap = None
    print("Attempting to initialize camera...")
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("CRITICAL: Camera not accessible. detection_loop will not run effectively.")
            # Intentar cargar imagen de fallback si la cámara no está disponible
            try:
                fallback_img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "test.png")
                fallback_img = cv2.imread(fallback_img_path)
                if fallback_img is not None:
                    print(f"Loaded fallback image from {fallback_img_path}")
                    ret, jpeg = cv2.imencode('.jpg', fallback_img)
                    if ret:
                        with frame_lock:
                            current_frame = jpeg.tobytes()
                else:
                    print(f"Fallback image {fallback_img_path} not found.")
            except Exception as e_fallback:
                print(f"Error loading fallback image: {e_fallback}")
            return # Salir del loop de detección si la cámara falla al inicio
        else:
            print("Camera initialized successfully.")
    except Exception as e_cap:
        print(f"CRITICAL ERROR initializing VideoCapture: {e_cap}")
        return # Salir del loop

    while True:
        if forced_video_to_play:
            # print("Detection loop paused due to forced video.") # Comentado
            time.sleep(0.5)
            continue

        if not cap.isOpened(): # Verificar si la cámara sigue abierta
            print("Camera is not open in loop. Attempting to re-open...")
            cap.release() # Liberar por si acaso
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("Failed to re-open camera. detection_loop will pause.")
                time.sleep(5) # Esperar antes de reintentar
                continue # Volver al inicio del while para reintentar o manejar video forzado
            else:
                print("Camera re-opened successfully.")


        ret, frame = cap.read()
        if not ret or frame is None:
            print("detection_loop: Failed to read frame or frame is None.")
            time.sleep(0.1)
            continue

        processed_frame = frame.copy()
        
        if not detection_complete:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                # Ajustar parámetros para mejorar detección o rendimiento si es necesario
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
            except Exception as e:
                print(f"detection_loop: Error during face detection: {e}")
                faces = []

            if len(faces) > 0:
                (x, y, w, h) = faces[0]
                cv2.rectangle(processed_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                
                face_roi = frame[y:y+h, x:x+w]
                emotion = "neutral" # Default
                if face_roi.size == 0:
                    # print("Face ROI is empty, skipping prediction") # Comentado
                    emotion = last_emotion if last_emotion else "neutral"
                else:
                    emotion = predict_emotion_tflite(face_roi)
                
                current_time = time.time()
                emotion_buffer.append((current_time, emotion))
                emotion_buffer = [(t, e) for (t, e) in emotion_buffer if current_time - t <= buffer_window]

                if len(emotion_buffer) >= min_count:
                    freq = {}
                    for (_, e_val) in emotion_buffer: # Renombrar e a e_val para evitar conflicto con la 'e' de la excepción
                        freq[e_val] = freq.get(e_val, 0) + 1
                    
                    if freq:
                        dominant_emotion = max(freq, key=freq.get)
                        ratio = freq[dominant_emotion] / len(emotion_buffer)
                        # print(f"Buffer: {len(emotion_buffer)}, Dom: {dominant_emotion}, Ratio: {ratio:.2f}") # Comentado

                        if ratio >= threshold_ratio:
                            if not detection_complete: # Solo actualizar si no estaba ya completa (para evitar multiples snapshots)
                                print(f"detection_loop: Detection newly complete with emotion: {dominant_emotion}")
                                detection_complete = True
                                detected_emotion = dominant_emotion
                                ret2, snapshot_jpeg = cv2.imencode('.jpg', frame) 
                                if ret2:
                                    detected_snapshot = snapshot_jpeg.tobytes()
                        else:
                            last_emotion = dominant_emotion 
                    else:
                        last_emotion = None
                else:
                    last_emotion = emotion
                
                if last_emotion and not detection_complete: # Mostrar la emoción (estable o inestable) solo si la detección no está completa
                     cv2.putText(processed_frame, last_emotion, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX,
                                0.9, (0, 255, 0), 2)
            else: 
                if not detection_complete:
                    emotion_buffer = []
                    last_emotion = None
        
        ret_jpeg, jpeg_frame = cv2.imencode('.jpg', processed_frame)
        if ret_jpeg:
            with frame_lock:
                current_frame = jpeg_frame.tobytes()
        else:
            print("detection_loop: Failed to encode frame")
        
        time.sleep(0.03) # Ajustar ~30FPS, puede ser 0.05 para ~20FPS si hay problemas de CPU

    if cap:
        print("Releasing camera in detection_loop (end).")
        cap.release()


print("Starting detection thread...")
detection_thread = threading.Thread(target=detection_loop, daemon=True)
detection_thread.start()


def gen_video():
    global current_frame
    fallback_img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "test.png")
    error_img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "error_cam.png") # Crear esta imagen

    while True:
        with frame_lock:
            frame_to_send = current_frame
        
        if frame_to_send is None:
            error_message = "Esperando camara..."
            img_to_use_path = fallback_img_path
            
            # Intentar cargar imagen de reserva
            try:
                with open(img_to_use_path, "rb") as f:
                    img_bytes = f.read()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + img_bytes + b'\r\n')
            except Exception as e_img:
                # print(f"gen_video: Error loading image {img_to_use_path}: {e_img}") # Comentado
                # Fallback a un frame generado si la imagen de reserva también falla
                img = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(img, "ERROR CAM", (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                ret_err_jpeg, jpeg_err_frame = cv2.imencode('.jpg', img)
                if ret_err_jpeg:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg_err_frame.tobytes() + b'\r\n')
            time.sleep(0.2) # Esperar un poco más si no hay frame
            continue
        
        try:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_to_send + b'\r\n')
        except GeneratorExit:
            # print("gen_video: Client disconnected.") # Comentado
            return # Salir del generador si el cliente se desconecta
        except Exception as e_yield:
            print(f"gen_video: Error yielding frame: {e_yield}")
            time.sleep(0.5) 
        
        time.sleep(0.03) # Sincronizar con la tasa de captura de detection_loop


@app.route('/')
def route_index(): # Renombrar para evitar conflicto con una variable 'index'
    global forced_video_to_play, detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_start_time, emotion_buffer
    print("Route /: Resetting state for new session.")
    # Reiniciar estado al cargar la página principal
    detection_complete = False
    detected_emotion = "neutral"
    detected_snapshot = None
    last_emotion = None
    emotion_start_time = None
    emotion_buffer.clear()
    forced_video_to_play = None
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_video(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/detection_status')
def detection_status():
    global forced_video_to_play, detection_complete, detected_emotion
    
    video_to_send_now = forced_video_to_play
    
    status_data = {"detected": detection_complete, "emotion": detected_emotion}
    if video_to_send_now:
        status_data["forced_video"] = video_to_send_now
        print(f"API /detection_status: Sending forced_video: {video_to_send_now} and resetting it on server.")
        forced_video_to_play = None # Resetear DESPUÉS de enviarlo
        
    return jsonify(status_data)

@app.route('/snapshot')
def snapshot():
    global detected_snapshot
    if detected_snapshot is not None:
        return Response(detected_snapshot, mimetype='image/jpeg')
    else:
        try:
            placeholder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "test.png")
            with open(placeholder_path, "rb") as f: 
                placeholder = f.read()
            return Response(placeholder, mimetype='image/jpeg')
        except FileNotFoundError:
            return "No snapshot available and no placeholder found", 404


@app.route('/get_random_audio')
def get_random_audio():
    global detected_emotion # Acceder a la variable global
    emotion_to_use = detected_emotion
    
    if emotion_to_use in ["disgust", "no_face"]: 
        emotion_to_use = "neutral"
    
    base_audio_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), app.static_folder, "audio")
    folder_path = os.path.join(base_audio_path, emotion_to_use)
    
    try:
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            print(f"Audio folder for '{emotion_to_use}' not found ({folder_path}), using 'neutral'.")
            folder_path = os.path.join(base_audio_path, "neutral")
            emotion_for_url = "neutral" # Usar neutral para la URL si la carpeta original no existe
            if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                print(f"Neutral audio folder also not found ({folder_path}).")
                return jsonify({'error': f'No audio folder found for {emotion_to_use} or neutral'}), 404
        else:
            emotion_for_url = emotion_to_use

        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and f.lower().endswith(('.mp3', '.wav', '.ogg'))]
        
        if not files: # Si la carpeta existe pero está vacía, intentar neutral
            print(f"No audio files in '{emotion_for_url}' folder ({folder_path}), trying 'neutral'.")
            folder_path = os.path.join(base_audio_path, "neutral")
            emotion_for_url = "neutral"
            if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                 return jsonify({'error': 'Emotion audio folder empty and neutral folder not found'}), 404
            files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and f.lower().endswith(('.mp3', '.wav', '.ogg'))]
            if not files:
                print(f"No audio files in neutral folder either.")
                return jsonify({'error': 'No audio files found for emotion or neutral fallback'}), 404
        
        file_choice = random.choice(files)
        audio_url = f"/static/audio/{emotion_for_url}/{file_choice}" # Construir URL relativa
        # print(f"Serving audio: {audio_url}") # Comentado
        return jsonify({'audio_url': audio_url})
    except Exception as e_audio:
        print(f"Error in get_random_audio: {e_audio}")
        return jsonify({'error': str(e_audio)}), 500


@app.route('/get_random_video')
def get_random_video():
    video_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), app.static_folder, "video")
    try:
        if not os.path.exists(video_dir_path) or not os.path.isdir(video_dir_path):
            print(f"Video folder {video_dir_path} not found for /get_random_video")
            return jsonify({'error': 'Video folder not found'}), 404
            
        files = [f for f in os.listdir(video_dir_path) if os.path.isfile(os.path.join(video_dir_path, f)) and f.lower().endswith(('.mp4', '.webm', '.mov', '.avi'))]
        if not files:
            print(f"No video files found in {video_dir_path}")
            return jsonify({'error': 'No video files found in folder'}), 404
        
        file_choice = random.choice(files)
        video_url = f"/static/video/{file_choice}" # Construir URL relativa
        # print(f"Serving video: {video_url}") # Comentado
        return jsonify({'video_url': video_url})
    except Exception as e_video:
        print(f"Error in get_random_video: {e_video}")
        return jsonify({'error': str(e_video)}), 500

# --- Nuevas rutas para control de video desde la página de movimiento ---
@app.route('/list_videos')
def list_videos_route(): # Renombrar
    video_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), app.static_folder, "video")
    try:
        if not os.path.exists(video_dir_path) or not os.path.isdir(video_dir_path):
            print(f"Video folder {video_dir_path} not found for /list_videos")
            return jsonify({'error': 'Video folder not found on server.'}), 404
        
        video_files = [f for f in os.listdir(video_dir_path) if os.path.isfile(os.path.join(video_dir_path, f)) and f.lower().endswith(('.mp4', '.webm', '.mov', '.avi'))]
        print(f"API /list_videos: Found videos: {video_files}")
        return jsonify({'videos': sorted(video_files)})
    except Exception as e_list:
        print(f"Error in /list_videos: {e_list}")
        return jsonify({'error': f'Server error listing videos: {str(e_list)}'}), 500

@app.route('/play_specific_video', methods=['POST'])
def play_specific_video_route():
    global forced_video_to_play, detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_start_time, emotion_buffer
    
    data = request.json
    if not data or 'video_file' not in data:
        return jsonify({'error': 'Invalid request: No video_file provided in JSON body.'}), 400
        
    video_file = data.get('video_file')
    if not video_file: # Chequeo extra por si el valor es None o vacío
        return jsonify({'error': 'Invalid request: video_file is empty.'}), 400

    abs_video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), app.static_folder, "video", video_file)

    if not os.path.isfile(abs_video_path):
        print(f"API /play_specific_video: Video file {abs_video_path} not found on server.")
        return jsonify({'error': f'Video file "{video_file}" not found on server.'}), 404

    print(f"API /play_specific_video: Request to play specific video: {video_file}")

    # 1. Reiniciar estado de detección para prepararse para el video
    detection_complete = False
    detected_emotion = "neutral" 
    detected_snapshot = None
    last_emotion = None
    emotion_start_time = None
    emotion_buffer.clear() 

    # 2. Establecer el video forzado
    forced_video_to_play = video_file 
    print(f"API /play_specific_video: forced_video_to_play SET TO: {forced_video_to_play}")

    return jsonify({'status': 'ok', 'message': f'Request to play {video_file} received. Main interface should react.'})


@app.route('/restart')
def restart_route(): # Renombrar
    global detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_start_time, emotion_buffer, forced_video_to_play
    print("API /restart: Resetting application state.")
    detection_complete = False
    detected_emotion = "neutral"
    detected_snapshot = None
    last_emotion = None
    emotion_start_time = None
    emotion_buffer.clear()
    forced_video_to_play = None 
    return jsonify({"status": "restarted"})


if __name__ == '__main__':
    print("Flask application starting...")
    # Recordatorio: use_reloader=False es importante para evitar que los hilos se inicien dos veces
    # y para mantener la consistencia de las variables globales en desarrollo.
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)