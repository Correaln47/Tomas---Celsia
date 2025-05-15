from flask import Flask, render_template, Response, jsonify, request # Añadir request
import cv2
import time
import threading
import os
import random
import numpy as np
import tflite_runtime.interpreter as tflite

app = Flask(__name__)

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

try:
    interpreter = tflite.Interpreter(model_path="emotion_model.tflite")
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    print("TFLite model input shape:", input_details[0]['shape'])
except Exception as e:
    print(f"Error al cargar el modelo TFLite: {e}")
    # Considerar salir o manejar el error de forma que la app no se rompa
    # sys.exit(1)


def predict_emotion_tflite(face_roi):
    if face_roi is None or face_roi.size == 0:
        print("Error: face_roi está vacío en predict_emotion_tflite")
        return "neutral"
    gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    try:
        h, w = input_details[0]['shape'][1:3]
        gray_face_resized = cv2.resize(gray_face, (w, h))
    except Exception as e:
        print("Error resizing face ROI:", e)
        return "neutral"
    
    gray_face_resized = gray_face_resized.astype("float32") / 255.0
    input_data = np.expand_dims(np.expand_dims(gray_face_resized, axis=-1), axis=0)
    
    try:
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        preds = interpreter.get_tensor(output_details[0]['index'])[0]
        emotion_index = np.argmax(preds)
        # print("Predicted probabilities:", preds, "-> Selected label:", emotion_labels[emotion_index]) # Comentado para reducir logs
        return emotion_labels[emotion_index]
    except Exception as e:
        print(f"Error durante la invocación del intérprete TFLite: {e}")
        return "neutral"


def detection_loop():
    global current_frame, detection_complete, detected_emotion, detected_snapshot
    global last_emotion, emotion_start_time, emotion_buffer, forced_video_to_play

    cap = None
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Camera not accessible")
            # Cargar imagen de fallback si la cámara no está disponible
            try:
                fallback_img = cv2.imread("static/test.png") # Asegúrate que esta imagen exista
                if fallback_img is not None:
                    ret, jpeg = cv2.imencode('.jpg', fallback_img)
                    if ret:
                        with frame_lock:
                            current_frame = jpeg.tobytes()
                else:
                    print("Fallback image static/test.png no encontrada.")
            except Exception as e_fallback:
                print(f"Error cargando fallback image: {e_fallback}")
            return
    except Exception as e_cap:
        print(f"Error inicializando VideoCapture: {e_cap}")
        return


    while True:
        # Si hay un video forzado, la detección se pausa temporalmente en el lado del cliente (script.js)
        # Aquí podríamos añadir una lógica para que el hilo de detección "duerma" si hay un video forzado,
        # pero es más simple manejarlo del lado del cliente que controla el flujo principal.
        # Sin embargo, es importante que `detection_complete` se ponga a False cuando se pide un video forzado.

        if forced_video_to_play: # Si hay un video forzado, no procesamos nuevos frames para detección
            time.sleep(0.5) # Esperamos un poco
            # El reseteo de detection_complete se hace en la ruta /play_specific_video
            continue

        ret, frame = cap.read()
        if not ret:
            print("detection_loop: Failed to read frame")
            time.sleep(0.1)
            continue

        processed_frame = frame.copy()
        
        if not detection_complete: # Solo detectar si no hemos completado una detección o no hay video forzado
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100)) # Aumentar minSize
            except Exception as e:
                print("detection_loop: Error during face detection:", e)
                faces = []

            if len(faces) > 0:
                (x, y, w, h) = faces[0]
                cv2.rectangle(processed_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                
                face_roi = frame[y:y+h, x:x+w]
                if face_roi.size == 0: # Chequeo adicional
                    # print("Face ROI is empty, skipping prediction") # Comentado para reducir logs
                    emotion = last_emotion if last_emotion else "neutral"
                else:
                    emotion = predict_emotion_tflite(face_roi)
                
                # print("detection_loop: Detected emotion:", emotion) # Comentado para reducir logs

                current_time = time.time()
                emotion_buffer.append((current_time, emotion))
                emotion_buffer = [(t, e) for (t, e) in emotion_buffer if current_time - t <= buffer_window]

                if len(emotion_buffer) >= min_count:
                    freq = {}
                    for (_, e) in emotion_buffer:
                        freq[e] = freq.get(e, 0) + 1
                    
                    if freq: # Asegurarse que el diccionario no esté vacío
                        dominant_emotion = max(freq, key=freq.get)
                        ratio = freq[dominant_emotion] / len(emotion_buffer)
                        # print(f"Buffer: {len(emotion_buffer)}, Dom: {dominant_emotion}, Ratio: {ratio:.2f}") # Comentado

                        if ratio >= threshold_ratio:
                            detection_complete = True
                            detected_emotion = dominant_emotion
                            # Tomar snapshot del frame original, no del procesado con el recuadro de emoción previa
                            ret2, snapshot_jpeg = cv2.imencode('.jpg', frame) 
                            if ret2:
                                detected_snapshot = snapshot_jpeg.tobytes()
                            print("detection_loop: Detection complete with emotion:", dominant_emotion)
                        else:
                            last_emotion = dominant_emotion # Actualizar para mostrar emoción actual inestable
                    else: # Si freq está vacío (raro si emotion_buffer no lo está)
                        last_emotion = None
                else:
                    last_emotion = emotion # Actualizar para mostrar emoción actual inestable
                
                if last_emotion: # Mostrar la emoción (estable o inestable) en el frame
                     cv2.putText(processed_frame, last_emotion, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX,
                                0.9, (0, 255, 0), 2)
            else: # No se detectaron caras
                if not detection_complete: # Solo limpiar si no hay una detección ya completada
                    emotion_buffer = []
                    last_emotion = None
        
        # Codificar y enviar el frame procesado (con o sin overlays de detección)
        ret_jpeg, jpeg_frame = cv2.imencode('.jpg', processed_frame)
        if ret_jpeg:
            with frame_lock:
                current_frame = jpeg_frame.tobytes()
            # print("detection_loop: Updated frame") # Comentado
        else:
            print("detection_loop: Failed to encode frame")
        
        time.sleep(0.05) # Ajustar según sea necesario para el rendimiento

    if cap:
        cap.release()


detection_thread = threading.Thread(target=detection_loop, daemon=True)
detection_thread.start()


def gen_video():
    global current_frame
    while True:
        with frame_lock:
            frame_to_send = current_frame
        
        if frame_to_send is None:
            # Intentar cargar imagen de reserva si current_frame es None persistentemente
            try:
                with open("static/test.png", "rb") as f: # Asegúrate que esta imagen exista
                    fallback_frame = f.read()
                # print("gen_video: Enviando imagen de reserva") # Comentado
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + fallback_frame + b'\r\n')
            except Exception as e:
                # print(f"gen_video: Error loading fallback image: {e}") # Comentado
                # Enviar un frame vacío o un mensaje de error si la imagen de reserva falla
                error_frame_text = "Camara no disponible"
                img = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(img, error_frame_text, (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                ret, jpeg = cv2.imencode('.jpg', img)
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            time.sleep(0.1) # Esperar antes de reintentar
            continue
        
        try:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_to_send + b'\r\n')
        except Exception as e:
            print("gen_video: Error yielding frame:", e)
            # Podríamos intentar reconectar o simplemente esperar
            time.sleep(0.5) # Una pausa más larga si hay errores continuos
        
        time.sleep(0.05) # Sincronizar con la tasa de captura de detection_loop


@app.route('/')
def index():
    # Al cargar la página principal, nos aseguramos que no haya un video forzado pendiente de una sesión anterior.
    global forced_video_to_play
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
        # print(f"API /detection_status: Enviando forced_video: {video_to_send_now}") # Comentado
        forced_video_to_play = None # Resetear DESPUÉS de enviarlo para que el cliente lo reciba una vez
        
    return jsonify(status_data)

@app.route('/snapshot')
def snapshot():
    if detected_snapshot is not None:
        return Response(detected_snapshot, mimetype='image/jpeg')
    else:
        # Devolver una imagen placeholder si no hay snapshot
        try:
            with open("static/test.png", "rb") as f: # O una imagen específica de "no snapshot"
                placeholder = f.read()
            return Response(placeholder, mimetype='image/jpeg')
        except FileNotFoundError:
            return "No snapshot available and no placeholder found", 404


@app.route('/get_random_audio')
def get_random_audio():
    emotion_to_use = detected_emotion
    # Si la emoción detectada es "disgust" o "no_face" (si la tuvieras), usar audios neutrales
    if emotion_to_use in ["disgust", "no_face"]: # Ajusta esta lista según tus categorías de audio
        emotion_to_use = "neutral"
        
    folder = os.path.join(app.static_folder, "audio", emotion_to_use) # app.static_folder es 'static'
    try:
        if not os.path.exists(folder) or not os.path.isdir(folder):
             # Fallback a neutral si la carpeta de la emoción no existe
            print(f"Carpeta de audio para '{emotion_to_use}' no encontrada, usando 'neutral'.")
            folder = os.path.join(app.static_folder, "audio", "neutral")
            if not os.path.exists(folder) or not os.path.isdir(folder):
                print(f"Carpeta de audio 'neutral' tampoco encontrada.")
                return jsonify({'error': f'No audio folder found for {emotion_to_use} or neutral'}), 404

        files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(('.mp3', '.wav', '.ogg'))]
        if not files:
            # Fallback a neutral si no hay archivos en la carpeta de la emoción
            print(f"No hay archivos de audio en '{emotion_to_use}', intentando 'neutral'.")
            folder = os.path.join(app.static_folder, "audio", "neutral")
            if not os.path.exists(folder) or not os.path.isdir(folder):
                 return jsonify({'error': 'No audio files in emotion folder and neutral folder not found'}), 404
            files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(('.mp3', '.wav', '.ogg'))]
            if not files:
                print(f"No hay archivos de audio tampoco en 'neutral'.")
                return jsonify({'error': 'No audio files found for emotion or neutral fallback'}), 404
        
        file = random.choice(files)
        # Usar la emoción original para construir la URL si el fallback fue solo por carpeta no encontrada pero la emoción existe
        audio_url_emotion_part = emotion_to_use if os.path.exists(os.path.join(app.static_folder, "audio", emotion_to_use)) else "neutral"
        audio_url = os.path.join('/static', "audio", audio_url_emotion_part, file)
        # print(f"Serving audio: {audio_url}") # Comentado
        return jsonify({'audio_url': audio_url})
    except Exception as e:
        print(f"Error en get_random_audio: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/get_random_video')
def get_random_video():
    folder = os.path.join(app.static_folder, "video")
    try:
        if not os.path.exists(folder) or not os.path.isdir(folder):
            return jsonify({'error': 'Video folder not found'}), 404
            
        files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(('.mp4', '.webm', '.mov', '.avi'))]
        if not files:
            return jsonify({'error': 'No video files found in folder'}), 404
        
        file = random.choice(files)
        video_url = os.path.join('/static', "video", file)
        # print(f"Serving video: {video_url}") # Comentado
        return jsonify({'video_url': video_url})
    except Exception as e:
        print(f"Error en get_random_video: {e}")
        return jsonify({'error': str(e)}), 500

# --- Nuevas rutas para control de video desde la página de movimiento ---
@app.route('/list_videos')
def list_videos():
    video_folder = os.path.join(app.static_folder, "video")
    try:
        if not os.path.exists(video_folder) or not os.path.isdir(video_folder):
            print(f"Video folder {video_folder} not found for /list_videos")
            return jsonify({'error': 'Video folder not found'}), 404
        
        video_files = [f for f in os.listdir(video_folder) if os.path.isfile(os.path.join(video_folder, f)) and f.lower().endswith(('.mp4', '.webm', '.mov', '.avi'))]
        # print(f"Listing videos: {video_files}") # Comentado
        return jsonify({'videos': sorted(video_files)})
    except Exception as e:
        print(f"Error listing videos: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/play_specific_video', methods=['POST'])
def play_specific_video_route(): # Renombrado para evitar colisión de nombres si existiera
    global forced_video_to_play, detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_start_time, emotion_buffer
    
    data = request.json
    video_file = data.get('video_file')

    if not video_file:
        return jsonify({'error': 'No video_file provided'}), 400

    # Validar que el archivo de video existe
    # Ojo: app.static_folder es el nombre de la carpeta ('static'), no la ruta completa al iniciar.
    # Usar os.path.join(os.path.dirname(__file__), app.static_folder, "video", video_file) para una ruta más robusta si es necesario
    # o simplemente confiar en que el cliente envía nombres de archivo válidos obtenidos de /list_videos.
    
    # Una validación simple:
    path_to_video = os.path.join(app.static_folder, "video", video_file) # Esto es relativo para la URL, no para os.path.isfile directamente
                                                                         # A menos que Flask esté sirviendo desde el directorio actual.
                                                                         # Para verificar el archivo, mejor ruta absoluta:
    abs_video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), app.static_folder, "video", video_file)

    if not os.path.isfile(abs_video_path):
        print(f"Video file {abs_video_path} not found on server for /play_specific_video.")
        return jsonify({'error': f'Video file "{video_file}" not found on server.'}), 404

    print(f"API /play_specific_video: Solicitud para reproducir video específico: {video_file}")

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


    return jsonify({'status': 'ok', 'message': f'Solicitud para reproducir {video_file} recibida. La interfaz principal debería reaccionar.'})


@app.route('/restart')
def restart():
    global detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_start_time, emotion_buffer, forced_video_to_play
    print("API /restart: Reiniciando estado de la aplicación.")
    detection_complete = False
    detected_emotion = "neutral"
    detected_snapshot = None
    last_emotion = None
    emotion_start_time = None
    emotion_buffer.clear()
    forced_video_to_play = None # Muy importante resetear esto aquí también
    return jsonify({"status": "restarted"})


if __name__ == '__main__':
    # Deshabilitar el reloader explícitamente para producción si es necesario, 
    # aunque para desarrollo debug=True lo activa.
    # use_reloader=False es importante cuando se usan hilos y variables globales como aquí.
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)