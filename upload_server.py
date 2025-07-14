import os
import sys
import json ### NUEVO ###
from flask import Flask, request, render_template, redirect, url_for, flash, abort, jsonify
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
TEMPLATES_FOLDER = os.path.join(BASE_DIR, 'templates')

ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav'}
ALLOWED_CAROUSEL_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_EMOTION_FOLDERS = ["angry", "fear", "happy", "neutral", "no_face", "sad", "surprise"]

PORT = 5002

app = Flask(__name__, template_folder=TEMPLATES_FOLDER)
app.config['VIDEO_FOLDER'] = VIDEO_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER
app.config['CAROUSEL_FOLDER'] = CAROUSEL_FOLDER
app.secret_key = 'super secret key'


### NUEVO: Función para actualizar el archivo JSON del carrusel ###
def update_carousel_json():
    """Escanea la carpeta del carrusel y guarda la lista de imágenes en un archivo JSON."""
    try:
        carousel_folder_path = app.config['CAROUSEL_FOLDER']
        # Lista solo los archivos de imagen válidos y los ordena
        files = sorted([
            f for f in os.listdir(carousel_folder_path) 
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))
        ])
        
        # Crea las rutas relativas que usará el cliente
        image_urls = [f"/static/carousel_images/{f}" for f in files]
        
        # Define la ruta del archivo JSON de salida
        json_path = os.path.join(carousel_folder_path, 'carousel_data.json')
        
        # Escribe los datos en el archivo JSON
        with open(json_path, 'w') as f:
            json.dump({'images': image_urls}, f)
        
        logging.info(f"Archivo 'carousel_data.json' actualizado con {len(image_urls)} imágenes.")

    except Exception as e:
        logging.error(f"Error CRÍTICO al actualizar 'carousel_data.json': {e}")


# --- Asegurarse que las carpetas base existan ---
for folder in [VIDEO_FOLDER, AUDIO_FOLDER, CAROUSEL_FOLDER, TEMPLATES_FOLDER]:
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
        update_json_flag = False ### NUEVO ###

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
            update_json_flag = True ### NUEVO ###

        else:
            return jsonify({'error': 'Ningún archivo seleccionado o tipo de archivo no válido.'}), 400

        if file and allowed_file(file.filename, allowed_extensions):
            filename = secure_filename(file.filename)
            filepath = os.path.join(upload_folder, filename)
            try:
                file.save(filepath)
                
                ### MODIFICADO: Llama a la función de actualización si es una imagen del carrusel ###
                if update_json_flag:
                    update_carousel_json()
                    
                return jsonify({'status': 'success', 'message': f'{file_type} "{filename}" subido correctamente a {target_folder_relative_for_log}'}), 200
            except Exception as e:
                 return jsonify({'error': f'Error al guardar el archivo: {e}'}), 500
        elif file:
             return jsonify({'error': f'Tipo de archivo no permitido. Permitidas: {", ".join(allowed_extensions)}'}), 400

    video_files = sorted([f for f in os.listdir(app.config['VIDEO_FOLDER']) if os.path.isfile(os.path.join(app.config['VIDEO_FOLDER'], f))])
    carousel_images = sorted([f for f in os.listdir(app.config['CAROUSEL_FOLDER']) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))])
    
    audio_files_by_emotion = {}
    for emotion in ALLOWED_EMOTION_FOLDERS:
        emotion_folder_path = os.path.join(app.config['AUDIO_FOLDER'], emotion)
        if os.path.isdir(emotion_folder_path):
             audio_files_by_emotion[emotion] = sorted([f for f in os.listdir(emotion_folder_path) if os.path.isfile(os.path.join(emotion_folder_path, f))])

    return render_template('upload.html',
                           videos=video_files,
                           audio_files_by_emotion=audio_files_by_emotion,
                           allowed_emotions=ALLOWED_EMOTION_FOLDERS,
                           carousel_images=carousel_images)

@app.route('/delete/<type>/<subpath>/<path:filename>', methods=['POST'])
def delete_file(type, subpath, filename):
    filename = secure_filename(filename)
    base_folder = None
    update_json_flag = False ### NUEVO ###

    if type == 'video':
        base_folder = app.config['VIDEO_FOLDER']
    elif type == 'audio':
        base_folder = os.path.join(app.config['AUDIO_FOLDER'], secure_filename(subpath))
    elif type == 'carousel_image':
        base_folder = app.config['CAROUSEL_FOLDER']
        update_json_flag = True ### NUEVO ###
    else:
        abort(404)

    filepath = os.path.join(base_folder, filename)
    
    if not os.path.realpath(filepath).startswith(os.path.realpath(base_folder)):
        abort(403)

    if os.path.isfile(filepath):
        os.remove(filepath)
        flash(f'Archivo "{filename}" eliminado.', 'success')
        
        ### MODIFICADO: Llama a la función de actualización si se eliminó una imagen del carrusel ###
        if update_json_flag:
            update_carousel_json()
    else:
        flash(f'Error: El archivo "{filename}" no fue encontrado.', 'error')

    return redirect(url_for('upload_file'))

if __name__ == '__main__':
    # --- ### NUEVO: Asegurarse de que el JSON exista al arrancar ### ---
    update_carousel_json()
    # ---
    print(f"Servidor de carga y gestión iniciado en http://0.0.0.0:{PORT}")
    print(f" - Sirviendo desde: {STATIC_FOLDER}")
    app.run(host='0.0.0.0', port=PORT, debug=True, use_reloader=False)