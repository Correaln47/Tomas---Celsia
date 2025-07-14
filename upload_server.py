import os
import sys
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
CAROUSEL_FOLDER = os.path.join(STATIC_FOLDER, 'carousel_images') # <--- NUEVA CARPETA
TEMPLATES_FOLDER = os.path.join(BASE_DIR, 'templates')

ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav'}
ALLOWED_CAROUSEL_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} # <--- NUEVAS EXTENSIONES
ALLOWED_EMOTION_FOLDERS = ["angry", "fear", "happy", "neutral", "no_face", "sad", "surprise"]

PORT = 5002

app = Flask(__name__, template_folder=TEMPLATES_FOLDER)
app.config['VIDEO_FOLDER'] = VIDEO_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER
app.config['CAROUSEL_FOLDER'] = CAROUSEL_FOLDER # <--- NUEVA CONFIGURACIÓN
app.secret_key = 'super secret key'

# --- Asegurarse que las carpetas base existan ---
for folder in [VIDEO_FOLDER, AUDIO_FOLDER, CAROUSEL_FOLDER, TEMPLATES_FOLDER]: # <--- AÑADIR NUEVA CARPETA AQUÍ
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
        try:
            os.makedirs(emotion_folder_path)
            logging.info(f"Subcarpeta de emoción creada: {emotion_folder_path}")
        except OSError as e:
            logging.error(f"Error al crear subcarpeta de emoción {emotion_folder_path}: {e}")

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
            emotion_folder_name = secure_filename(selected_emotion)
            upload_folder = os.path.join(app.config['AUDIO_FOLDER'], emotion_folder_name)
            allowed_extensions = ALLOWED_AUDIO_EXTENSIONS
            file_type = "Audio"
            target_folder_relative_for_log = os.path.relpath(upload_folder, STATIC_FOLDER)
            if not os.path.exists(upload_folder):
                 try:
                     os.makedirs(upload_folder)
                 except OSError as e:
                     return jsonify({"error": f"Error interno al preparar carpeta para emoción '{selected_emotion}'."}), 500
        
        # <--- INICIO: NUEVA LÓGICA PARA IMÁGENES DEL CARRUSEL ---
        elif 'carousel_image' in request.files and request.files['carousel_image'].filename != '':
            file = request.files['carousel_image']
            upload_folder = app.config['CAROUSEL_FOLDER']
            allowed_extensions = ALLOWED_CAROUSEL_EXTENSIONS
            file_type = "Imagen de Carrusel"
            target_folder_relative_for_log = os.path.relpath(upload_folder, STATIC_FOLDER)
        # <--- FIN: NUEVA LÓGICA ---

        else:
            error_message = 'Ningún archivo seleccionado o tipo de archivo no válido.'
            if 'video' in request.files or 'audio' in request.files or 'carousel_image' in request.files:
                 error_message = 'Ningún archivo seleccionado.'
            return jsonify({'error': error_message}), 400

        if file and allowed_file(file.filename, allowed_extensions):
            filename = secure_filename(file.filename)
            filepath = os.path.join(upload_folder, filename)
            try:
                abs_upload_folder = os.path.realpath(upload_folder)
                abs_filepath_candidate = os.path.realpath(filepath)
                if not os.path.isdir(abs_upload_folder) or not abs_filepath_candidate.startswith(abs_upload_folder):
                     return jsonify({'error': 'Ruta de archivo no permitida.'}), 400
                file.save(filepath)
                return jsonify({'status': 'success', 'message': f'{file_type} "{filename}" subido correctamente a {target_folder_relative_for_log}'}), 200
            except Exception as e:
                 return jsonify({'error': f'Error al guardar el archivo: {e}'}), 500
        elif file:
             return jsonify({'error': f'Tipo de archivo no permitido para {file_type}. Extensiones permitidas: {", ".join(allowed_extensions)}'}), 400

    # --- Método GET ---
    try:
        video_files = sorted([f for f in os.listdir(app.config['VIDEO_FOLDER']) if os.path.isfile(os.path.join(app.config['VIDEO_FOLDER'], f))])
    except Exception as e:
        video_files = []
        flash('Error al cargar la lista de videos.', 'error')

    audio_files_by_emotion = {}
    try:
        for emotion in ALLOWED_EMOTION_FOLDERS:
            emotion_folder_path = os.path.join(app.config['AUDIO_FOLDER'], emotion)
            if os.path.isdir(emotion_folder_path):
                 audio_files_by_emotion[emotion] = sorted([
                    f for f in os.listdir(emotion_folder_path)
                    if os.path.isfile(os.path.join(emotion_folder_path, f))
                ])
            else:
                 audio_files_by_emotion[emotion] = []
    except Exception as e:
        flash('Error al cargar la lista de audios.', 'error')
        
    # <--- INICIO: NUEVA LÓGICA PARA LISTAR IMÁGENES DEL CARRUSEL ---
    try:
        carousel_images = sorted([f for f in os.listdir(app.config['CAROUSEL_FOLDER']) if os.path.isfile(os.path.join(app.config['CAROUSEL_FOLDER'], f))])
    except Exception as e:
        carousel_images = []
        flash('Error al cargar la lista de imágenes del carrusel.', 'error')
    # <--- FIN: NUEVA LÓGICA ---

    return render_template('upload.html',
                           videos=video_files,
                           audio_files_by_emotion=audio_files_by_emotion,
                           allowed_emotions=ALLOWED_EMOTION_FOLDERS,
                           carousel_images=carousel_images) # <--- PASAR IMÁGENES A LA PLANTILLA

@app.route('/delete/<type>/<subpath>/<path:filename>', methods=['POST'])
def delete_file(type, subpath, filename):
    filename = secure_filename(filename)
    base_folder = None
    target_folder_relative_for_log = ""

    if type == 'video':
        if subpath != '_': abort(400)
        base_folder = app.config['VIDEO_FOLDER']
        target_folder_relative_for_log = os.path.relpath(base_folder, STATIC_FOLDER)
    elif type == 'audio':
        subpath = secure_filename(subpath)
        if subpath not in ALLOWED_EMOTION_FOLDERS: abort(404)
        base_folder = os.path.join(app.config['AUDIO_FOLDER'], subpath)
        target_folder_relative_for_log = os.path.relpath(base_folder, STATIC_FOLDER)
    # <--- INICIO: NUEVA LÓGICA PARA ELIMINAR IMÁGENES DEL CARRUSEL ---
    elif type == 'carousel_image':
        if subpath != '_': abort(400)
        base_folder = app.config['CAROUSEL_FOLDER']
        target_folder_relative_for_log = os.path.relpath(base_folder, STATIC_FOLDER)
    # <--- FIN: NUEVA LÓGICA ---
    else:
        abort(404)

    filepath = os.path.join(base_folder, filename)
    
    try:
        abs_base = os.path.realpath(base_folder)
        abs_file = os.path.realpath(filepath)
        if not os.path.isdir(abs_base) or os.path.commonpath([abs_base, abs_file]) != abs_base:
            abort(404 if not os.path.isdir(abs_base) else 403)
    except Exception as e:
         flash('Error interno al validar la ruta del archivo.', 'error')
         return redirect(url_for('upload_file'))

    try:
        if os.path.isfile(filepath):
            os.remove(filepath)
            flash(f'Archivo "{filename}" eliminado correctamente de {target_folder_relative_for_log}.', 'success')
        else:
            flash(f'Error: El archivo "{filename}" no fue encontrado en {target_folder_relative_for_log}.', 'error')
    except Exception as e:
        flash(f'Error al eliminar el archivo "{filename}": {e}', 'error')

    return redirect(url_for('upload_file'))
    
# <--- INICIO: NUEVA RUTA PARA OBTENER LA LISTA DE IMÁGENES DEL CARRUSEL ---
@app.route('/list_carousel_images')
def list_carousel_images():
    try:
        carousel_folder_path = app.config['CAROUSEL_FOLDER']
        files = [f for f in os.listdir(carousel_folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        # Devolver la lista de URLs completas
        image_urls = [f"/static/carousel_images/{f}" for f in sorted(files)]
        return jsonify({'images': image_urls})
    except Exception as e:
        logging.error(f"Error al listar imágenes del carrusel: {e}")
        return jsonify({'error': 'No se pudieron listar las imágenes del carrusel'}), 500
# <--- FIN: NUEVA RUTA ---

if __name__ == '__main__':
    print(f"Servidor de carga y gestión iniciado en http://0.0.0.0:{PORT}")
    print(f" - Sirviendo templates desde: {TEMPLATES_FOLDER}")
    print(f" - Sirviendo videos desde: {VIDEO_FOLDER}")
    print(f" - Sirviendo audios desde: {AUDIO_FOLDER}")
    print(f" - Sirviendo imágenes de carrusel desde: {CAROUSEL_FOLDER}") # <--- NUEVO MENSAJE
    app.run(host='0.0.0.0', port=PORT, debug=True, use_reloader=False)