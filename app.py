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
detection_complete = False # Flag para indicar si una emoción estable ha sido detectada
detected_emotion = "neutral"
detected_snapshot = None # Para guardar el frame cuando se detecta una emoción
last_emotion = None # Para mostrar la emoción actual antes de estabilizar
emotion_start_time = None
emotion_buffer = [] # Buffer para almacenar las últimas emociones detectadas
buffer_window = 4 # Ventana de tiempo en segundos para el buffer de emociones
threshold_ratio = 0.6 # Ratio mínimo de la emoción dominante en el buffer para considerarla estable
min_count = 5 # Cantidad mínima de detecciones en el buffer para considerar la estabilización
forced_video_to_play = None # Guarda el nombre del video a forzar desde la interfaz de control

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haascade_frontalface_default.xml")
emotion_labels = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

interpreter = None
input_details = None
output_details = None

try:
    # Asegúrate de que el archivo 'emotion_model.tflite' esté en la misma carpeta que app.py
    # O proporciona la ruta completa/correcta si está en otro lugar
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emotion_model.tflite")
    interpreter = tflite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    print("TFLite model loaded successfully. Input shape:", input_details[0]['shape']) # type: ignore
except Exception as e:
    print(f"CRITICAL ERROR: Failed to load TFLite model: {e}")
    interpreter = None # Asegurar que es None si falla

def predict_emotion_tflite(face_roi):
    """Predice la emoción de una ROI de cara usando el modelo TFLite."""
    global interpreter, input_details, output_details
    if interpreter is None:
        # Si el modelo no cargó, siempre devuelve neutral
        return "neutral"
    if face_roi is None or face_roi.size == 0:
        return "neutral"

    # Preprocesar la imagen para el modelo
    gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    try:
        # El modelo espera una imagen de 48x48 (basado en los detalles de entrada del manifest)
        h, w = input_details[0]['shape'][1:3] # type: ignore
        gray_face_resized = cv2.resize(gray_face, (w, h))
    except Exception as e:
        print(f"Error resizing face ROI: {e}")
        return "neutral"

    # Normalizar y añadir dimensiones para el input del modelo
    gray_face_resized = gray_face_resized.astype("float32") / 255.0
    # Expandir dimensiones: (batch_size, height, width, channels)
    input_data = np.expand_dims(np.expand_dims(gray_face_resized, axis=-1), axis=0)

    try:
        # Ejecutar inferencia
        interpreter.set_tensor(input_details[0]['index'], input_data) # type: ignore
        interpreter.invoke()
        preds = interpreter.get_tensor(output_details[0]['index'])[0] # type: ignore

        # Obtener la emoción con la mayor probabilidad
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
        # Intenta abrir la cámara (0 es típicamente la cámara predeterminada)
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            # Reducir resolución para mejorar rendimiento en RPi
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
                         with frame_lock:
                             current_frame = jpeg_fb.tobytes()
                 else:
                     print("Fallback image not found.")
            except Exception as e_fb:
                print(f"Error loading fallback image: {e_fb}")
            return # Salir del hilo si la cámara no se abre
    except Exception as e_cap:
        print(f"CRITICAL ERROR initializing VideoCapture: {e_cap}")
        return # Salir del hilo en caso de excepción

    # Intervalo para procesar la detección (para no sobrecargar la CPU)
    detection_processing_interval = 0.1 # Procesar detección cada 100ms (10 FPS)
    last_detection_time = time.time()

    print("Detection Loop: Starting frame processing.")
    while True:
        # Si hay un video forzado reproduciéndose, la detección se pausa o ignora
        # El frontend maneja la reproducción del video forzado
        if forced_video_to_play:
            # Podrías opcionalmente mostrar un frame estático o negro aquí
            # para el stream si no quieres congelar el último frame de la cámara
            # Por ahora, simplemente espera para no consumir CPU innecesariamente
            time.sleep(0.1)
            continue

        # Si la cámara se desconecta inesperadamente durante el bucle
        if cap is None or not cap.isOpened():
             print("Camera disconnected in loop. Attempting to re-open...")
             if cap: cap.release() # Liberar recurso si existe
             cap = cv2.VideoCapture(0)
             if cap.isOpened():
                 cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                 cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                 print("Camera re-opened successfully.")
             else:
                 print("Failed to re-open camera. Waiting before next attempt.")
                 with frame_lock: current_frame = None # Limpiar frame para indicar problema
                 time.sleep(5) # Esperar 5 segundos antes de reintentar
                 continue # Ir a la siguiente iteración del bucle

        ret, frame = cap.read() # Capturar un frame
        if not ret or frame is None:
            # Si no se puede leer el frame, esperar un poco y continuar
            print("Failed to read frame from camera.")
            with frame_lock: current_frame = None # Limpiar frame
            time.sleep(0.1)
            continue

        current_time_loop = time.time()
        processed_frame_for_stream = frame.copy() # Copia para el stream de video

        # Procesar detección solo si no está completa y ha pasado el intervalo
        if not detection_complete and (current_time_loop - last_detection_time > detection_processing_interval):
            last_detection_time = current_time_loop

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Ajusta scaleFactor y minNeighbors si la detección es lenta o inconsistente
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)) # Ajustar params

            if len(faces) > 0:
                # Solo considera la primera cara detectada
                (x, y, w, h) = faces[0]

                # Dibujar recuadro en la copia que se usará para el stream
                cv2.rectangle(processed_frame_for_stream, (x, y), (x+w, y+h), (0, 255, 0), 2)

                # Extraer la región de interés (ROI) de la cara del frame original
                face_roi = frame[y:y+h, x:x+w]

                # Predecir la emoción usando el modelo TFLite
                emotion = predict_emotion_tflite(face_roi)

                # --- Lógica del Buffer de Emociones para Estabilización ---
                # Añadir la detección actual al buffer con timestamp
                emotion_buffer.append((time.time(), emotion))

                # Eliminar detecciones viejas del buffer
                emotion_buffer = [(t, e) for (t, e) in emotion_buffer if time.time() - t <= buffer_window]

                # Verificar si hay suficientes detecciones para intentar estabilizar
                if len(emotion_buffer) >= min_count:
                    # Contar la frecuencia de cada emoción en el buffer
                    freq = {}
                    for _, e in emotion_buffer:
                         freq[e] = freq.get(e, 0) + 1

                    if freq: # Asegurarse de que el diccionario no esté vacío
                        # Encontrar la emoción dominante
                        dominant_emotion = max(freq, key=freq.get)

                        # Verificar si la emoción dominante cumple el umbral de ratio
                        if freq[dominant_emotion] / len(emotion_buffer) >= threshold_ratio:
                            # Si la detección se ha estabilizado y no habíamos completado antes
                            if not detection_complete:
                                print(f"Detection Loop: Emotion stabilized: {dominant_emotion}. Triggering interaction.")
                                detection_complete = True # Marcar detección como completa
                                detected_emotion = dominant_emotion # Guardar la emoción final
                                # Guardar un snapshot del frame cuando la detección se completa
                                ret_snap, snap_jpeg = cv2.imencode('.jpg', frame) # Snapshot del frame original
                                if ret_snap:
                                     detected_snapshot = snap_jpeg.tobytes()
                                     print("Snapshot captured.")
                                else:
                                     print("Failed to capture snapshot.")
                        else:
                             # Si no se estabilizó, pero hay una emoción dominante actual
                             last_emotion = dominant_emotion
                             # print(f"Detection Loop: Current dominant (unstable): {last_emotion}") # Descomentar para depurar
                    else:
                        last_emotion = None # Buffer vacío o error, reset last_emotion
                        # print("Detection Loop: Emotion buffer empty/error.") # Descomentar para depurar
                else:
                    # Si el buffer aún no tiene suficientes elementos, usar la última detección
                    last_emotion = emotion
                    # print(f"Detection Loop: Buffer too small ({len(emotion_buffer)}), current: {last_emotion}") # Descomentar para depurar

                # Dibujar la emoción actual (estable o no) en la copia del stream
                if last_emotion:
                     cv2.putText(processed_frame_for_stream, last_emotion, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            else: # No faces detected
                # Si no hay caras, resetear el buffer y el estado si la detección no está completa
                if not detection_complete:
                    emotion_buffer.clear()
                    last_emotion = "no_face" # O simplemente None, según prefieras mostrar
                    # print("Detection Loop: No face detected.") # Descomentar para depurar
                # Si ya se detectó una emoción estable, no resetear hasta que se reinicie la interacción

        # Codificar el frame procesado (con recuadro y emoción) para el stream de video
        ret_jpeg, jpeg_frame = cv2.imencode('.jpg', processed_frame_for_stream)
        if ret_jpeg:
            with frame_lock:
                current_frame = jpeg_frame.tobytes()
        else:
             print("Failed to encode frame for stream.")
             with frame_lock: current_frame = None # Limpiar frame

        # Pequeña pausa para controlar la tasa de frames del stream
        # y reducir el uso de CPU si es necesario
        time.sleep(0.05) # Aproximadamente 20 FPS para el stream

    # Limpieza al salir del bucle (aunque con daemon=True esto rara vez se ejecuta)
    if cap:
        cap.release()
    print("Detection Loop: Camera released.")


print("Starting detection thread...")
# Iniciar el hilo de detección. daemon=True permite que el hilo se cierre cuando el programa principal finaliza.
detection_thread = threading.Thread(target=detection_loop, daemon=True)
detection_thread.start()

def gen_video():
    """Generador para el stream de video MJPEG."""
    global current_frame
    # Asegurarse de que haya un frame inicial para evitar errores al inicio
    # Puedes cargar un frame placeholder aquí si prefieres
    while True:
        # Obtener el frame actual de forma segura
        with frame_lock:
            frame_to_send = current_frame

        if frame_to_send:
            # Enviar el frame codificado en formato MJPEG
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_to_send + b'\r\n')
        else:
            # Si no hay frame (ej. cámara desconectada), puedes enviar un placeholder
             try:
                 placeholder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),"static","test.png")
                 with open(placeholder_path, "rb") as f: img_bytes = f.read()
                 yield (b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' + img_bytes + b'\r\n')
             except:
                 # Si el placeholder falla, esperar un poco
                 time.sleep(0.5) # Esperar más si no hay nada que enviar


        # Controlar la tasa de frames enviados en el stream
        time.sleep(0.05) # Envía frames a ~20 FPS

@app.route('/')
def route_index():
    """Ruta principal que sirve la interfaz de interacción."""
    global forced_video_to_play, detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_start_time, emotion_buffer
    print("Route /: Resetting state for new session.")
    # Resetear el estado al cargar la página principal
    detection_complete = False
    detected_emotion = "neutral"
    detected_snapshot = None
    last_emotion = None
    emotion_start_time = None
    emotion_buffer.clear()
    forced_video_to_play = None # Asegurar que no haya video forzado al inicio de la interacción

    return render_template('index.html')

@app.route('/video_feed')
def video_feed_route():
    """Ruta para el stream de video en vivo."""
    return Response(gen_video(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/detection_status')
def detection_status_route():
    """Ruta para que el frontend consulte el estado de detección."""
    global forced_video_to_play, detection_complete, detected_emotion, detected_snapshot

    status_data = {
        "detected": detection_complete,
        "emotion": detected_emotion,
        # No envíamos el snapshot aquí directamente, se pide por separado si detected es True
    }

    # Si hay un video forzado pendiente, lo enviamos en este status check
    video_to_send_now = forced_video_to_play
    if video_to_send_now:
        status_data["forced_video"] = video_to_send_now
        print(f"API /detection_status: Sending forced_video: {video_to_send_now} & resetting flag.")
        forced_video_to_play = None # Resetear la bandera después de enviarla

    # Después de enviar el estado de detección completa/emoción,
    # reiniciamos las variables relevantes para permitir una nueva detección.
    # Esto ocurre DESPUÉS de que el frontend haya tenido la oportunidad de leer el estado.
    # La lógica en el frontend (`script.js`) es la que decide qué hacer con este estado.
    if detection_complete:
        print(f"API /detection_status: Detection complete state sent. Resetting detection_complete.")
        detection_complete = False # Permitir una nueva detección
        # detected_emotion se mantiene hasta la próxima detección estable o reinicio completo
        # detected_snapshot se mantiene hasta la próxima detección estable o reinicio completo
        # emotion_buffer.clear() # Opcional: podrías querer limpiar el buffer aquí también

    return jsonify(status_data)

@app.route('/snapshot')
def snapshot_route():
    """Ruta para obtener el snapshot cuando se detecta una emoción."""
    global detected_snapshot
    if detected_snapshot:
        return Response(detected_snapshot, mimetype='image/jpeg')
    else:
        # Si no hay snapshot (aún no se ha detectado emoción o ya se usó), enviar un placeholder
        try:
            placeholder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),"static","test.png")
            with open(placeholder_path, "rb") as f:
                return Response(f.read(), mimetype='image/jpeg')
        except:
            return "No snapshot available or placeholder not found", 404 # O un error más amigable

@app.route('/get_random_audio')
def get_random_audio_route():
    """Ruta para obtener un archivo de audio aleatorio basado en la emoción detectada."""
    global detected_emotion
    # Mapear emociones detectadas a carpetas de audio existentes
    # Si la emoción detectada no tiene una carpeta específica, usar "neutral"
    emotion_folder_name = detected_emotion if detected_emotion in ["angry", "fear", "happy", "neutral", "sad", "surprise"] else "neutral"

    audio_folder_path = os.path.join(app.static_folder, "audio", emotion_folder_name) # type: ignore
    # Asegurarse de que la ruta estática se resuelva correctamente
    abs_audio_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), audio_folder_path)

    print(f"Attempting to get audio from: {abs_audio_folder_path} for emotion: {detected_emotion}")

    if not os.path.exists(abs_audio_folder_path):
        print(f"Audio folder not found: {abs_audio_folder_path}. Trying 'neutral' fallback.")
        # Fallback a la carpeta neutral si la carpeta de la emoción no existe
        emotion_folder_name = "neutral"
        audio_folder_path = os.path.join(app.static_folder, "audio", emotion_folder_name) # type: ignore
        abs_audio_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), audio_folder_path)
        if not os.path.exists(abs_audio_folder_path):
             print(f"Neutral audio folder not found either: {abs_audio_folder_path}")
             return jsonify({'error': 'Audio folder not found'}), 404


    try:
        # Listar archivos de audio (mp3, wav, ogg) en la carpeta
        files = [f for f in os.listdir(abs_audio_folder_path) if f.lower().endswith(('.mp3', '.wav', '.ogg'))]
        if not files:
            print(f"No audio files found in {abs_audio_folder_path}")
            return jsonify({'error': 'No audio files in folder'}), 404

        # Seleccionar un archivo aleatorio
        selected_file = random.choice(files)
        audio_url = f"/static/audio/{emotion_folder_name}/{selected_file}"
        print(f"Selected random audio: {audio_url}")
        return jsonify({'audio_url': audio_url})

    except Exception as e:
        print(f"Error get_random_audio: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_random_video')
def get_random_video_route():
    """Ruta para obtener un archivo de video aleatorio para la interacción."""
    video_folder_path = os.path.join(app.static_folder, "video") # type: ignore
    # Asegurarse de que la ruta estática se resuelva correctamente
    abs_video_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), video_folder_path)

    print(f"Attempting to get random video from: {abs_video_folder_path}")

    if not os.path.exists(abs_video_folder_path):
        print(f"Video folder not found: {abs_video_folder_path}")
        return jsonify({'error': 'Video folder not found'}), 404

    try:
        # Listar archivos de video (mp4, webm, mov, avi) en la carpeta
        files = [f for f in os.listdir(abs_video_folder_path) if f.lower().endswith(('.mp4', '.webm', '.mov', '.avi'))]
        if not files:
            print(f"No video files found in {abs_video_folder_path}")
            return jsonify({'error': 'No video files in folder'}), 404

        # Seleccionar un archivo aleatorio
        selected_file = random.choice(files)
        video_url = f"/static/video/{selected_file}"
        print(f"Selected random video: {video_url}")
        return jsonify({'video_url': video_url})

    except Exception as e:
        print(f"Error get_random_video: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/list_videos')
def list_videos_route():
    """Ruta para listar los videos disponibles (usado por la interfaz de control)."""
    video_folder_path = os.path.join(app.static_folder, "video") # type: ignore
    # Asegurarse de que la ruta estática se resuelva correctamente
    abs_video_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), video_folder_path)

    if not os.path.exists(abs_video_folder_path):
        return jsonify({'error': 'Video folder not found on server.'}), 404

    try:
        video_files = sorted([f for f in os.listdir(abs_video_folder_path) if f.lower().endswith(('.mp4', '.webm', '.mov', '.avi'))])
        print(f"API /list_videos: Found videos: {video_files}")
        return jsonify({'videos': video_files})
    except Exception as e:
        print(f"Error /list_videos: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/play_specific_video', methods=['POST'])
def play_specific_video_route():
    """Ruta para forzar la reproducción de un video específico (usado por la interfaz de control)."""
    global forced_video_to_play, detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_buffer

    data = request.json
    if not data or 'video_file' not in data:
        print("API /play_specific_video: Invalid request - missing video_file.")
        return jsonify({'error': 'Invalid request'}), 400

    video_file = data.get('video_file')
    # Validar que el nombre de archivo sea seguro y exista
    safe_video_file = os.path.basename(video_file) # Usar solo el nombre del archivo para seguridad
    abs_video_path = os.path.join(app.static_folder, "video", safe_video_file) # type: ignore
    # Asegurarse de que la ruta estática se resuelva correctamente
    full_abs_video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), abs_video_path)


    if not os.path.isfile(full_abs_video_path):
        print(f"API /play_specific_video: Video file not found: {full_abs_video_path}")
        return jsonify({'error': f'Video "{safe_video_file}" not found.'}), 404

    print(f"API /play_specific_video: Request to force play: {safe_video_file}")

    # Resetear el estado de detección e interacción
    detection_complete = False
    detected_emotion = "neutral"
    detected_snapshot = None
    last_emotion = None
    emotion_buffer.clear()
    forced_video_to_play = safe_video_file # Establecer el video forzado

    print(f"API /play_specific_video: forced_video_to_play SET TO: {forced_video_to_play}")

    return jsonify({'status': 'ok', 'message': f'Request to play {safe_video_file} received. Main interface should switch to video.'})

@app.route('/restart')
def restart_route():
    """Ruta para reiniciar el estado de la aplicación principal (usado por la interfaz de control)."""
    global detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_buffer, forced_video_to_play

    print("API /restart: Received restart request. Resetting application state.")

    # Resetear todas las variables de estado relevante
    detection_complete = False
    detected_emotion = "neutral"
    detected_snapshot = None
    last_emotion = None
    emotion_buffer.clear() # Limpiar el buffer de emociones
    forced_video_to_play = None # Asegurarse de que no haya video forzado

    print("API /restart: Application state reset.")

    return jsonify({"status": "restarted", "message": "Application state has been reset."})


if __name__ == '__main__':
    print("Flask app starting (performance changes)...")
    # Usa debug=False en producción/autostart para mejor rendimiento y estabilidad
    # use_reloader=False es importante para evitar que el hilo de detección se duplique
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)