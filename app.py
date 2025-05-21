import os
import time
from flask import Flask, render_template, Response, request, jsonify, url_for, redirect # redirect puede ser útil
from flask_socketio import SocketIO, emit
import cv2
import face_recognition
import numpy as np
import threading
from werkzeug.utils import secure_filename
from gtts import gTTS
import pygame
from mutagen.mp3 import MP3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui' # ¡Cambia esto en producción!
app.config['UPLOAD_FOLDER'] = 'static/known_faces'
app.config['AUDIO_FOLDER'] = 'static/audio'
app.config['VIDEO_FOLDER'] = 'static/videos' # Aunque no se use activamente, es bueno tenerla definida
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'} # Solo estas extensiones para caras

socketio = SocketIO(app, async_mode='threading')

# Crear carpetas si no existen
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['AUDIO_FOLDER'], exist_ok=True)
os.makedirs(app.config['VIDEO_FOLDER'], exist_ok=True)

try:
    pygame.mixer.init()
except pygame.error as e:
    print(f"Advertencia: No se pudo inicializar pygame.mixer: {e}.")

# Variables globales
known_face_encodings = []
known_face_names = []
camera_active = False
recognition_active = True # Iniciar con reconocimiento activo por defecto
last_recognized_name = None
recognition_cooldown = 10 # Segundos
last_recognition_time = {}
current_expression = "neutral"
recognition_thread = None # Para mantener una referencia al hilo

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
        if allowed_file(filename): # Usa la función allowed_file para consistencia
            name = os.path.splitext(filename)[0] # El nombre es el nombre del archivo sin extensión
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                face_image = face_recognition.load_image_file(image_path)
                face_encodings_list = face_recognition.face_encodings(face_image)
                if face_encodings_list:
                    known_face_encodings.append(face_encodings_list[0])
                    known_face_names.append(name)
                    print(f"Cara cargada: {name}")
                else:
                    print(f"No se encontró cara en el archivo: {filename}")
            except Exception as e:
                print(f"Error cargando imagen {filename}: {e}")
    print(f"Total de caras conocidas cargadas: {len(known_face_names)}")

def generate_audio_greeting(name):
    text = f"Hola {name}, qué alegría verte."
    safe_name = "".join(c if c.isalnum() else "_" for c in name) # Nombre seguro para archivo
    audio_filename = f"greeting_{safe_name}.mp3"
    audio_path_server = os.path.join(app.config['AUDIO_FOLDER'], audio_filename)
    audio_path_client = url_for('static', filename=f'audio/{audio_filename}') # No necesita _external=True aquí

    if not os.path.exists(audio_path_server):
        try:
            tts = gTTS(text=text, lang='es', slow=False)
            tts.save(audio_path_server)
        except Exception as e:
            print(f"Error generando audio para {name}: {e}")
            return None, 0
    try:
        audio_info = MP3(audio_path_server)
        duration = audio_info.info.length
        return audio_path_client, duration
    except Exception as e:
        print(f"Error obteniendo duración del audio para {audio_path_server}: {e}")
        return audio_path_client, 5 # Duración por defecto si falla

def face_recognition_thread_func():
    global camera_active, recognition_active, last_recognized_name, current_expression, last_recognition_time
    
    print("Intentando abrir la cámara...")
    video_capture = cv2.VideoCapture(0)
    if not video_capture.isOpened(): video_capture = cv2.VideoCapture(-1)
    if not video_capture.isOpened(): video_capture = cv2.VideoCapture(1)
        
    if not video_capture.isOpened():
        print("Error Crítico: No se pudo abrir ninguna cámara.")
        camera_active = False
        return

    print("Cámara abierta exitosamente.")
    camera_active = True
    print("Hilo de reconocimiento facial iniciado.")
    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    process_this_frame = True

    while camera_active:
        if not recognition_active:
            ret, frame = video_capture.read()
            if ret:
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                frame_bytes = buffer.tobytes()
                socketio.emit('video_frame', {'image': frame_bytes})
            else:
                print("Error capturando frame (reconocimiento pausado). Reintentando cámara.")
                video_capture.release(); video_capture = cv2.VideoCapture(0)
                if not video_capture.isOpened(): camera_active = False; break 
            socketio.sleep(0.1)
            continue

        ret, frame = video_capture.read()
        if not ret:
            print("Error al capturar frame. Reintentando cámara.")
            video_capture.release(); video_capture = cv2.VideoCapture(0)
            if not video_capture.isOpened(): camera_active = False; break 
            socketio.sleep(0.1)
            continue

        if process_this_frame:
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            for face_encoding in face_encodings: 
                if not known_face_encodings: break
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.58)
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
                    audio_path, audio_duration = generate_audio_greeting(name)
                    if audio_path and audio_duration > 0:
                        socketio.emit('recognized_face', {
                            'name': name,
                            'message': f'Hola {name}, bienvenido!',
                            'audio_path': audio_path,
                            'audio_duration': audio_duration
                        })
                        current_expression = "happy"
                        socketio.emit('expression', {'expression': current_expression})
                    else:
                        print(f"No se pudo generar audio para {name}.")
                    break 
        process_this_frame = not process_this_frame
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        frame_bytes = buffer.tobytes()
        socketio.emit('video_frame', {'image': frame_bytes})
        socketio.sleep(0.03)

    if video_capture.isOpened(): video_capture.release()
    cv2.destroyAllWindows()
    print("Hilo de reconocimiento facial detenido.")
    camera_active = False

@app.route('/')
def index():
    return render_template('index.html')

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
    elif not recognition_active:
        recognition_active = True
        # No es necesario recargar caras aquí si solo se está reactivando el flag
        return jsonify({'status': 'Reconocimiento reactivado'})
    return jsonify({'status': 'Reconocimiento ya activo o cámara iniciándose'})

@app.route('/stop_recognition', methods=['POST'])
def stop_recognition_route():
    global recognition_active, last_recognized_name
    if recognition_active:
        recognition_active = False
        last_recognized_name = None
        socketio.emit('expression', {'expression': 'neutral'})
        print("Reconocimiento pausado por el usuario.")
        return jsonify({'status': 'Reconocimiento pausado'})
    return jsonify({'status': 'El reconocimiento ya estaba pausado'})

# --- RUTA DE UPLOAD CORREGIDA Y UNIFICADA ---
@app.route('/upload', methods=['GET', 'POST'])  # Ahora maneja GET y POST
def upload_file():  # Nombre de función original: upload_file
    message = None
    message_type = None # Para el CSS del mensaje
    if request.method == 'POST':
        if 'file' not in request.files or 'name' not in request.form:
            message = 'Falta archivo o nombre en el formulario.'
            message_type = 'error'
            return render_template('upload.html', message=message, message_type=message_type)

        file = request.files['file']
        name_from_form = request.form['name'].strip() # Nombre que el usuario ingresa

        if not name_from_form:
            message = 'El nombre es requerido.'
            message_type = 'error'
            return render_template('upload.html', message=message, message_type=message_type)
        if file.filename == '':
            message = 'No se seleccionó ningún archivo.'
            message_type = 'error'
            return render_template('upload.html', message=message, message_type=message_type)

        if file and allowed_file(file.filename):
            try:
                # El nombre del archivo guardado será el 'name_from_form' con la extensión original.
                # Esto es mejor que forzar .jpg o usar file.filename directamente como nombre base.
                original_extension = os.path.splitext(file.filename)[1]
                # Usar name_from_form como base para el nombre del archivo
                # secure_filename se asegura de que el nombre sea seguro para el sistema de archivos.
                # Si name_from_form es "Juan Perez", el archivo podría ser "Juan_Perez.png"
                filename_to_save = secure_filename(name_from_form + original_extension)
                
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename_to_save)
                file.save(filepath)
                
                print(f"Archivo '{filepath}' subido y guardado.")
                load_known_faces() # ¡Importante! Recargar caras conocidas.
                
                message = f'Archivo {filename_to_save} subido exitosamente para {name_from_form}. Caras recargadas.'
                message_type = 'success'
            except Exception as e:
                print(f"Error guardando archivo: {str(e)}")
                message = f'Error guardando archivo: {str(e)}'
                message_type = 'error'
            # Siempre renderizar upload.html para mostrar el mensaje en la misma página
            return render_template('upload.html', message=message, message_type=message_type)
        else:
            message = 'Tipo de archivo no permitido. Solo se permiten: png, jpg, jpeg.'
            message_type = 'error'
            return render_template('upload.html', message=message, message_type=message_type)
    
    # Para GET request, simplemente mostrar el formulario de subida sin mensaje previo
    return render_template('upload.html', message=None, message_type=None)

@app.route('/shutdown', methods=['POST'])
def shutdown_server_route():
    print("Solicitud de apagado recibida.")
    global camera_active, recognition_active, recognition_thread
    recognition_active = False
    camera_active = False
    if recognition_thread and recognition_thread.is_alive():
        recognition_thread.join(timeout=2.0) # Esperar un poco a que el hilo termine
    
    socketio.emit('message', {'text': 'El servidor se está apagando.'}) # Avisar al cliente
    print("Servidor y procesos detenidos (simulado). El sistema operativo NO se apagará con este código.")
    # Para apagar realmente la RPi (¡CON MUCHO CUIDADO!):
    # os.system('sudo shutdown -h now')
    return jsonify(message="Comando de apagado procesado. El servidor Flask se detendrá (simulado).")


if __name__ == '__main__':
    print("Iniciando aplicación Flask...")
    load_known_faces() # Cargar caras al inicio
    
    # Iniciar el hilo de reconocimiento automáticamente
    if recognition_thread is None or not recognition_thread.is_alive():
        print("Iniciando hilo de reconocimiento al arrancar...")
        recognition_thread = threading.Thread(target=face_recognition_thread_func, daemon=True)
        recognition_thread.start()

    print(f"Servidor Flask-SocketIO escuchando en http://0.0.0.0:5000")
    # debug=False y use_reloader=False es importante para producción y para evitar que los hilos se inicien dos veces.
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    print("Aplicación Flask terminada.")