import os
import sys
import json
from flask import Flask, request, render_template, redirect, url_for, flash, abort, jsonify, send_from_directory # MODIFICADO
from werkzeug.utils import secure_filename
import logging

# --- Configuración de Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuración de Rutas y Extensiones ---
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()
    logging.warning(f"__file__ no definido, usando directorio actual: {BASE_DIR}")

STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
VIDEO_FOLDER = os.path.join(STATIC_FOLDER, 'video')
AUDIO_FOLDER = os.path.join(STATIC_FOLDER, 'audio')
CAROUSEL_FOLDER = os.path.join(STATIC_FOLDER, 'carousel_images')
SPECIAL_FOLDER = os.path.join(STATIC_FOLDER, 'special') ### NUEVO ###
CAMERA_VIDEO_FOLDER = os.path.join(STATIC_FOLDER, 'video_upload') ### NUEVO ###
TEMPLATES_FOLDER = os.path.join(BASE_DIR, 'templates')

ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav'}
ALLOWED_CAROUSEL_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_EMOTION_FOLDERS = ["angry", "fear", "happy", "neutral", "no_face", "sad", "surprise"]
SPECIAL_EVENT_FILENAME = 'event.mp4' ### NUEVO ###

PORT = 5002

app = Flask(__name__, template_folder=TEMPLATES_FOLDER)
app.config['VIDEO_FOLDER'] = VIDEO_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER
app.config['CAROUSEL_FOLDER'] = CAROUSEL_FOLDER
app.config['SPECIAL_FOLDER'] = SPECIAL_FOLDER ### NUEVO ###
app.config['CAMERA_VIDEO_FOLDER'] = CAMERA_VIDEO_FOLDER ### NUEVO ###
app.secret_key = 'super secret key'


def update_carousel_json():
    """Escanea la carpeta del carrusel y guarda la lista de imágenes en un archivo JSON."""
    try:
        carousel_folder_path = app.config['CAROUSEL_FOLDER']
        files = sorted([
            f for f in os.listdir(carousel_folder_path) 
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))
        ])
        
        image_urls = [f"/static/carousel_images/{f}" for f in files]
        json_path = os.path.join(carousel_folder_path, 'carousel_data.json')
        
        with open(json_path, 'w') as f:
            json.dump({'images': image_urls}, f)
        
        logging.info(f"Archivo 'carousel_data.json' actualizado con {len(image_urls)} imágenes.")

    except Exception as e:
        logging.error(f"Error CRÍTICO al actualizar 'carousel_data.json': {e}")


# --- Asegurarse que las carpetas base existan ---
### MODIFICADO ###
for folder in [VIDEO_FOLDER, AUDIO_FOLDER, CAROUSEL_FOLDER, SPECIAL_FOLDER, CAMERA_VIDEO_FOLDER, TEMPLATES_FOLDER]:
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
            logging.info(f"Carpeta creada en: {folder}")
        except OSError as e:
            logging.error(f"Error al crear la carpeta {folder}: {e}")
    else:
        logging.info(f"Usando carpeta existente: {folder}")

for emotion in ALLOWED_EMOTION_FOLDERS:
    emotion_folder_path = os.path.join(AUDIO_FOLDER, emotion)
    if not os.path.exists(emotion_folder_path):
        os.makedirs(emotion_folder_path)

def allowed_file(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = None
        upload_folder = None
        allowed_extensions = None
        file_type = None
        target_folder_relative_for_log = ""
        update_json_flag = False

        if 'video' in request.files and request.files['video'].filename != '':
            file = request.files['video']
            upload_folder = app.config['VIDEO_FOLDER']
            allowed_extensions = ALLOWED_VIDEO_EXTENSIONS
            file_type = "Video"
            target_folder_relative_for_log = os.path.relpath(upload_folder, STATIC_FOLDER)

        elif 'audio' in request.files and request.files['audio'].filename != '':
            file = request.files['audio']
            selected_emotion = request.form.get('emotion')
            if not selected_emotion or selected_emotion not in ALLOWED_EMOTION_FOLDERS:
                return jsonify({'error': f'Emoción seleccionada inválida: "{selected_emotion}".'}), 400
            upload_folder = os.path.join(app.config['AUDIO_FOLDER'], secure_filename(selected_emotion))
            allowed_extensions = ALLOWED_AUDIO_EXTENSIONS
            file_type = "Audio"
            target_folder_relative_for_log = os.path.relpath(upload_folder, STATIC_FOLDER)
        
        elif 'carousel_image' in request.files and request.files['carousel_image'].filename != '':
            file = request.files['carousel_image']
            upload_folder = app.config['CAROUSEL_FOLDER']
            allowed_extensions = ALLOWED_CAROUSEL_EXTENSIONS
            file_type = "Imagen de Carrusel"
            target_folder_relative_for_log = os.path.relpath(upload_folder, STATIC_FOLDER)
            update_json_flag = True
        
        ### NUEVO: Bloque para manejar la subida de videos de cámara ###
        elif 'camera_video' in request.files and request.files['camera_video'].filename != '':
            file = request.files['camera_video']
            upload_folder = app.config['CAMERA_VIDEO_FOLDER']
            allowed_extensions = ALLOWED_VIDEO_EXTENSIONS
            file_type = "Video de Cámara"
            target_folder_relative_for_log = os.path.relpath(upload_folder, STATIC_FOLDER)
        
        ### NUEVO: Bloque para manejar la subida del video del evento especial ###
        elif 'special_event' in request.files and request.files['special_event'].filename != '':
            file = request.files['special_event']
            upload_folder = app.config['SPECIAL_FOLDER']
            allowed_extensions = ALLOWED_VIDEO_EXTENSIONS
            file_type = "Video de Evento Especial"
            target_folder_relative_for_log = os.path.relpath(upload_folder, STATIC_FOLDER)

            # Forzar el nombre del archivo y eliminar cualquier otro archivo en la carpeta
            filename = SPECIAL_EVENT_FILENAME
            for f in os.listdir(upload_folder):
                os.remove(os.path.join(upload_folder, f))
            
            filepath = os.path.join(upload_folder, filename)
            try:
                file.save(filepath)
                return jsonify({'status': 'success', 'message': f'{file_type} actualizado correctamente.'}), 200
            except Exception as e:
                return jsonify({'error': f'Error al guardar el archivo de evento: {e}'}), 500

        else:
            return jsonify({'error': 'Ningún archivo seleccionado o tipo de archivo no válido.'}), 400

        if file and allowed_file(file.filename, allowed_extensions):
            filename = secure_filename(file.filename)
            filepath = os.path.join(upload_folder, filename)
            try:
                file.save(filepath)
                
                if update_json_flag:
                    update_carousel_json()
                    
                return jsonify({'status': 'success', 'message': f'{file_type} "{filename}" subido correctamente a {target_folder_relative_for_log}'}), 200
            except Exception as e:
                return jsonify({'error': f'Error al guardar el archivo: {e}'}), 500
        elif file:
            return jsonify({'error': f'Tipo de archivo no permitido. Permitidas: {", ".join(allowed_extensions)}'}), 400

    video_files = sorted([f for f in os.listdir(app.config['VIDEO_FOLDER']) if os.path.isfile(os.path.join(app.config['VIDEO_FOLDER'], f))])
    carousel_images = sorted([f for f in os.listdir(app.config['CAROUSEL_FOLDER']) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))])
    
    ### NUEVO: Listar archivo de evento especial ###
    special_event_file = None
    if os.path.exists(os.path.join(app.config['SPECIAL_FOLDER'], SPECIAL_EVENT_FILENAME)):
        special_event_file = SPECIAL_EVENT_FILENAME
    
    ### NUEVO: Listar videos de cámara ###
    camera_videos = sorted([f for f in os.listdir(app.config['CAMERA_VIDEO_FOLDER']) if f.lower().endswith('.mp4')])

    audio_files_by_emotion = {}
    for emotion in ALLOWED_EMOTION_FOLDERS:
        emotion_folder_path = os.path.join(app.config['AUDIO_FOLDER'], emotion)
        if os.path.isdir(emotion_folder_path):
            audio_files_by_emotion[emotion] = sorted([f for f in os.listdir(emotion_folder_path) if os.path.isfile(os.path.join(emotion_folder_path, f))])

    ### MODIFICADO: Añade 'special_event_file' y 'camera_videos' al render_template ###
    return render_template('upload.html',
                           videos=video_files,
                           audio_files_by_emotion=audio_files_by_emotion,
                           allowed_emotions=ALLOWED_EMOTION_FOLDERS,
                           carousel_images=carousel_images,
                           camera_videos=camera_videos,
                           special_event_file=special_event_file)

@app.route('/delete/<type>/<subpath>/<path:filename>', methods=['POST'])
def delete_file(type, subpath, filename):
    filename = secure_filename(filename)
    base_folder = None
    update_json_flag = False

    if type == 'video':
        base_folder = app.config['VIDEO_FOLDER']
    elif type == 'audio':
        base_folder = os.path.join(app.config['AUDIO_FOLDER'], secure_filename(subpath))
    elif type == 'carousel_image':
        base_folder = app.config['CAROUSEL_FOLDER']
        update_json_flag = True
    ### NUEVO: Manejo de eliminación para videos de cámara ###
    elif type == 'camera_video':
        base_folder = app.config['CAMERA_VIDEO_FOLDER']
    ### NUEVO: Manejo de eliminación para el archivo de evento especial ###
    elif type == 'special_event':
        base_folder = app.config['SPECIAL_FOLDER']
    else:
        abort(404)

    filepath = os.path.join(base_folder, filename)
    
    # Comprobación de seguridad para evitar ataques de path traversal
    if not os.path.realpath(filepath).startswith(os.path.realpath(base_folder)):
        abort(403)

    if os.path.isfile(filepath):
        os.remove(filepath)
        flash(f'Archivo "{filename}" eliminado.', 'success')
        
        if update_json_flag:
            update_carousel_json()
    else:
        flash(f'Error: El archivo "{filename}" no fue encontrado.', 'error')

    return redirect(url_for('upload_file'))

### NUEVO: Ruta para descargar archivos ###
@app.route('/download/<type>/<subpath>/<path:filename>')
def download_file(type, subpath, filename):
    filename = secure_filename(filename)
    directory = None

    if type == 'video':
        directory = app.config['VIDEO_FOLDER']
    elif type == 'audio':
        directory = os.path.join(app.config['AUDIO_FOLDER'], secure_filename(subpath))
    elif type == 'carousel_image':
        directory = app.config['CAROUSEL_FOLDER']
    elif type == 'camera_video':
        directory = app.config['CAMERA_VIDEO_FOLDER']
    elif type == 'special_event':
        directory = app.config['SPECIAL_FOLDER']
    else:
        return abort(404)

    # Comprobación de seguridad
    if not os.path.realpath(os.path.join(directory, filename)).startswith(os.path.realpath(directory)):
        abort(403)

    return send_from_directory(directory, filename, as_attachment=True)

if __name__ == '__main__':
    update_carousel_json()
    print(f"Servidor de carga y gestión iniciado en http://0.0.0.0:{PORT}")
    print(f" - Sirviendo desde: {STATIC_FOLDER}")
    app.run(host='0.0.0.0', port=PORT, debug=True, use_reloader=False)