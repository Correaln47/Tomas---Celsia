import os
import time
from flask import Flask, render_template, Response, request, jsonify, url_for
from flask_socketio import SocketIO, emit
import cv2
import face_recognition
import numpy as np
import threading
from werkzeug.utils import secure_filename # Para el manejo de nombres de archivo
from gtts import gTTS # Para Text-to-Speech
import pygame # Para reproducir audio (aunque el cliente lo maneja ahora, se mantiene por si acaso)
from mutagen.mp3 import MP3 # Para obtener la duración del audio

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!' # ¡Cambia esto en producción!
app.config['UPLOAD_FOLDER'] = 'static/known_faces'
app.config['AUDIO_FOLDER'] = 'static/audio' # Carpeta para audios generados
app.config['VIDEO_FOLDER'] = 'static/videos' # Carpeta para videos
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}
socketio = SocketIO(app, async_mode='threading')

# Asegurarse de que las carpetas existen
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['AUDIO_FOLDER'], exist_ok=True)
os.makedirs(app.config['VIDEO_FOLDER'], exist_ok=True) # Crear carpeta de videos también

# Inicializar Pygame Mixer (una sola vez, por si se usa en el servidor)
try:
    pygame.mixer.init()
except pygame.error as e:
    print(f"Advertencia: No se pudo inicializar pygame.mixer: {e}. La reproducción de audio en el servidor podría no funcionar.")


# Variables globales para el manejo de rostros y cámara
known_face_encodings = []
known_face_names = []
camera_active = False
recognition_active = True  # Controla si el reconocimiento está activo al inicio
last_recognized_name = None
recognition_cooldown = 10 # Segundos de cooldown para no repetir el saludo inmediatamente
last_recognition_time = {} # Diccionario para rastrear el último tiempo de reconocimiento por nombre

# Simulación de estados de ánimo
current_expression = "neutral"

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def load_known_faces():
    global known_face_encodings, known_face_names
    known_face_encodings = []
    known_face_names = []
    print(f"Cargando caras desde: {app.config['UPLOAD_FOLDER']}")
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        print(f"Error: La carpeta de caras conocidas no existe: {app.config['UPLOAD_FOLDER']}")
        return

    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if allowed_file(filename):
            name = os.path.splitext(filename)[0]
            # Reemplazar guiones bajos con espacios para nombres más amigables si es necesario
            # name = name.replace('_', ' ')
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                face_image = face_recognition.load_image_file(image_path)
                face_encodings_list = face_recognition.face_encodings(face_image)
                if face_encodings_list:
                    known_face_encodings.append(face_encodings_list[0])
                    known_face_names.append(name)
                    print(f"Cara cargada: {name}")
                else:
                    print(f"No se encontró cara en {filename}")
            except Exception as e:
                print(f"Error cargando imagen {filename}: {e}")
    print(f"Total de caras conocidas cargadas: {len(known_face_names)}")

def generate_audio_greeting(name):
    """Genera un archivo de audio de saludo y devuelve su ruta y duración."""
    text = f"Hola {name}, qué alegría verte." # Mensaje de saludo personalizado
    # Crear un nombre de archivo seguro para el audio
    safe_name = "".join(c if c.isalnum() else "_" for c in name)
    audio_filename = f"greeting_{safe_name}.mp3"
    audio_path_server = os.path.join(app.config['AUDIO_FOLDER'], audio_filename)
    # Generar la URL para el cliente
    audio_path_client = url_for('static', filename=f'audio/{audio_filename}', _external=False)


    if not os.path.exists(audio_path_server):
        try:
            print(f"Generando audio para: {name} en {audio_path_server}")
            tts = gTTS(text=text, lang='es', slow=False)
            tts.save(audio_path_server)
            print(f"Audio generado: {audio_path_server}")
        except Exception as e:
            print(f"Error generando audio para {name}: {e}")
            return None, 0

    try:
        audio_info = MP3(audio_path_server)
        duration = audio_info.info.length
        return audio_path_client, duration
    except Exception as e:
        print(f"Error obteniendo duración del audio para {audio_path_server}: {e}")
        # Devolver la ruta del cliente incluso si la duración falla, con una duración por defecto
        return audio_path_client, 5 # Duración por defecto de 5 segundos si falla la lectura

def face_recognition_thread_func():
    global camera_active, recognition_active, last_recognized_name, current_expression, last_recognition_time
    
    print("Intentando abrir la cámara...")
    video_capture = cv2.VideoCapture(0) # Intenta con el índice 0 por defecto
    
    # Intentar con otros índices si el 0 falla (común en sistemas con múltiples cámaras o virtuales)
    if not video_capture.isOpened():
        print("Cámara 0 no disponible, intentando con índice -1...")
        video_capture = cv2.VideoCapture(-1) # A veces -1 funciona
    if not video_capture.isOpened():
        print("Cámara -1 no disponible, intentando con índice 1...")
        video_capture = cv2.VideoCapture(1)
        
    if not video_capture.isOpened():
        print("Error Crítico: No se pudo abrir ninguna cámara.")
        camera_active = False
        return

    print("Cámara abierta exitosamente.")
    camera_active = True
    print("Hilo de reconocimiento facial iniciado.")

    # Ajustar resolución para mejorar rendimiento si es necesario
    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    # Ajustar FPS si es posible y necesario (no todos los drivers lo soportan bien)
    # video_capture.set(cv2.CAP_PROP_FPS, 15)


    process_this_frame = True # Para procesar frames alternos y ahorrar CPU

    while camera_active:
        if not recognition_active:
            # Aunque el reconocimiento esté pausado, seguimos enviando frames para el stream
            ret, frame = video_capture.read()
            if ret:
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70]) # Comprimir un poco
                frame_bytes = buffer.tobytes()
                socketio.emit('video_frame', {'image': frame_bytes})
            else:
                print("Error capturando frame mientras el reconocimiento está pausado.")
                # Intentar reabrir la cámara si falla la captura
                video_capture.release()
                video_capture = cv2.VideoCapture(0) # o el índice que funcionó
                if not video_capture.isOpened():
                    print("Error Crítico: Se perdió la conexión con la cámara y no se pudo reabrir.")
                    camera_active = False # Terminar el hilo si no se puede recuperar la cámara
                    break 
            socketio.sleep(0.1) # Pausa más larga si solo se hace streaming
            continue

        ret, frame = video_capture.read()
        if not ret:
            print("Error al capturar frame de la cámara.")
            # Intentar reabrir la cámara si falla la captura
            video_capture.release()
            video_capture = cv2.VideoCapture(0) # o el índice que funcionó
            if not video_capture.isOpened():
                print("Error Crítico: Se perdió la conexión con la cámara y no se pudo reabrir.")
                camera_active = False # Terminar el hilo si no se puede recuperar la cámara
                break 
            socketio.sleep(0.1) # Pequeña pausa antes de reintentar
            continue

        # Procesar solo frames alternos para ahorrar recursos
        if process_this_frame:
            # Reducir el tamaño del frame para un reconocimiento más rápido
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25) # Reducir a 1/4
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(rgb_small_frame, model="hog") # 'hog' es más rápido que 'cnn'
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            # current_recognized_in_frame = None # Para saber si alguien fue reconocido en este frame

            for face_encoding, face_location in zip(face_encodings, face_locations):
                if not known_face_encodings: # Si no hay caras cargadas, no hacer nada
                    break

                matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.58) # Ajustar tolerancia
                name = "Desconocido"

                face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    if matches[best_match_index]:
                        name = known_face_names[best_match_index]

                current_time = time.time()
                if name != "Desconocido" and \
                   (name != last_recognized_name or \
                    (current_time - last_recognition_time.get(name, 0)) > recognition_cooldown):
                    
                    last_recognized_name = name
                    last_recognition_time[name] = current_time
                    # current_recognized_in_frame = name
                    print(f"Cara reconocida: {name}")

                    audio_path, audio_duration = generate_audio_greeting(name)
                    if audio_path and audio_duration > 0:
                        socketio.emit('recognized_face', {
                            'name': name,
                            'message': f'Hola {name}, bienvenido!',
                            'audio_path': audio_path,
                            'audio_duration': audio_duration
                        })
                        current_expression = "happy" # O alguna expresión relevante
                        socketio.emit('expression', {'expression': current_expression})

                        # Opcional: reproducir un video después del saludo
                        # video_filename_for_user = f"video_{name}.mp4" # Asume que tienes videos nombrados así
                        # video_path_for_user = os.path.join(app.config['VIDEO_FOLDER'], video_filename_for_user)
                        # if os.path.exists(video_path_for_user):
                        #    socketio.sleep(audio_duration + 0.5) # Esperar a que termine el audio
                        #    video_url = url_for('static', filename=f'videos/{video_filename_for_user}')
                        #    socketio.emit('play_video', {'video_path': video_url})

                    else:
                        print(f"No se pudo generar audio para {name}, no se emite evento recognized_face.")
                    break # Procesar solo la primera cara reconocida y que cumpla el cooldown

        process_this_frame = not process_this_frame # Alternar

        # Dibujar recuadros en el frame original (escalando las coordenadas)
        # for (top, right, bottom, left) in face_locations:
        #     top *= 4
        #     right *= 4
        #     bottom *= 4
        #     left *= 4
        #     cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
        #     # cv2.putText(frame, name_to_display_on_frame, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)

        # Transmitir el frame de video
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70]) # Comprimir un poco
        frame_bytes = buffer.tobytes()
        socketio.emit('video_frame', {'image': frame_bytes})

        socketio.sleep(0.03) # Ajustar según sea necesario (aprox 30 FPS si el procesamiento es rápido)

    video_capture.release()
    cv2.destroyAllWindows() # Asegurarse de liberar ventanas si se crearon
    print("Hilo de reconocimiento facial detenido.")
    camera_active = False

@app.route('/')
def index():
    return render_template('index.html')

recognition_thread = None

@app.route('/start_recognition', methods=['POST'])
def start_recognition_route():
    global recognition_active, camera_active, recognition_thread
    if not camera_active:
        recognition_active = True
        load_known_faces()
        if recognition_thread is None or not recognition_thread.is_alive():
            recognition_thread = threading.Thread(target=face_recognition_thread_func, daemon=True)
            recognition_thread.start()
            return jsonify({'status': 'Hilo de reconocimiento iniciado'})
        else:
            return jsonify({'status': 'El hilo de reconocimiento ya está activo pero la cámara no lo estaba. Intentando reactivar.'})
    elif not recognition_active:
        recognition_active = True
        load_known_faces() # Recargar por si acaso
        return jsonify({'status': 'Reconocimiento reactivado'})
    return jsonify({'status': 'Reconocimiento ya activo o la cámara se está iniciando'})


@app.route('/stop_recognition', methods=['POST'])
def stop_recognition_route():
    global recognition_active, last_recognized_name
    if recognition_active:
        recognition_active = False
        last_recognized_name = None # Resetear el último nombre reconocido
        socketio.emit('expression', {'expression': 'neutral'}) # Resetear expresión en el cliente
        print("Reconocimiento pausado por el usuario.")
        return jsonify({'status': 'Reconocimiento pausado'})
    return jsonify({'status': 'El reconocimiento ya estaba pausado'})


@app.route('/upload', methods=['GET', 'POST'])
def upload_file_route():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No hay parte de archivo en la solicitud'}), 400
        file = request.files['file']
        name = request.form.get('name', '').strip()

        if not name:
            return jsonify({'error': 'El nombre es requerido'}), 400
        if file.filename == '':
            return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
        if file and allowed_file(file.filename):
            # Usar el nombre proporcionado para el archivo, limpiándolo
            # Es buena idea hacer el nombre más seguro para archivos
            base, ext = os.path.splitext(file.filename)
            filename = secure_filename(name + ext) # secure_filename para el nombre completo
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                file.save(filepath)
                print(f"Archivo {filename} guardado para {name}.")
                # Recargar las caras conocidas después de una nueva subida
                load_known_faces()
                return jsonify({'success': f'Archivo {filename} subido exitosamente para {name}. Caras recargadas.'}), 200
            except Exception as e:
                return jsonify({'error': f'Error guardando archivo: {str(e)}'}), 500
        else:
            return jsonify({'error': 'Tipo de archivo no permitido'}), 400
    # Para GET request, mostrar el formulario de subida
    return render_template('upload.html')

@app.route('/shutdown', methods=['POST'])
def shutdown_server_route():
    print("Solicitud de apagado recibida.")
    global camera_active, recognition_active, recognition_thread
    
    recognition_active = False # Detener el bucle de reconocimiento
    camera_active = False      # Señal para que el hilo de la cámara termine

    if recognition_thread and recognition_thread.is_alive():
        print("Esperando a que el hilo de reconocimiento termine...")
        recognition_thread.join(timeout=2.0) # Esperar hasta 2 segundos
        if recognition_thread.is_alive():
            print("Advertencia: El hilo de reconocimiento no terminó a tiempo.")

    # Emitir un mensaje al cliente
    socketio.emit('message', {'text': 'El servidor se está apagando.'})
    print("Servidor y procesos detenidos (simulado).")

    # Comando de apagado del sistema (¡USAR CON EXTREMO CUIDADO!)
    # Esto apagará la Raspberry Pi. Asegúrate de que es lo que quieres.
    # DESCOMENTA SOLO SI ESTÁS SEGURO Y HAS PROBADO TODO.
    # try:
    #     print("Intentando apagar el sistema operativo...")
    #     os.system('sudo shutdown -h now')
    # except Exception as e:
    #     print(f"Error al intentar ejecutar el comando de apagado del sistema: {e}")
    #     return jsonify(message=f"Comando de apagado enviado, pero hubo un error al ejecutarlo en el SO: {e}"), 500

    # Para desarrollo, es mejor solo detener el servidor Flask si es posible,
    # pero con `socketio.run` esto es más complejo. La forma más segura es
    # que el script termine y el gestor de procesos (systemd, supervisor) no lo reinicie.
    
    # Una forma de intentar detener el servidor Werkzeug (funciona en modo debug)
    # func = request.environ.get('werkzeug.server.shutdown')
    # if func is None:
    #    print('No se pudo obtener la función de apagado de Werkzeug. El servidor podría no detenerse limpiamente.')
    # else:
    #    func()
    
    # Para un apagado más robusto, se podría enviar una señal al propio proceso
    # import signal
    # os.kill(os.getpid(), signal.SIGINT) # Envía una interrupción, como Ctrl+C

    return jsonify(message="Comando de apagado procesado. El sistema debería apagarse en breve (actualmente solo detiene los hilos internos de la app).")


if __name__ == '__main__':
    print("Iniciando aplicación Flask...")
    load_known_faces() # Cargar caras al inicio

    # Iniciar el hilo de reconocimiento automáticamente al arrancar la app
    if recognition_thread is None or not recognition_thread.is_alive():
        print("Iniciando hilo de reconocimiento al arrancar...")
        recognition_thread = threading.Thread(target=face_recognition_thread_func, daemon=True)
        recognition_thread.start()
    else:
        print("El hilo de reconocimiento ya estaba activo (inesperado al inicio).")


    print(f"Servidor Flask-SocketIO escuchando en http://0.0.0.0:5000")
    # Usar debug=False para producción para evitar que los hilos se inicien dos veces y por rendimiento.
    # allow_unsafe_werkzeug=True es necesario para usar `request.environ.get('werkzeug.server.shutdown')`
    # si se decide usar esa vía para el apagado, pero es mejor manejarlo externamente.
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    print("Aplicación Flask terminada.")