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

STATIC_FOLDER = os.path.join(BASE_DIR, 'static') # Carpeta estática base
VIDEO_FOLDER = os.path.join(STATIC_FOLDER, 'video')
AUDIO_FOLDER = os.path.join(STATIC_FOLDER, 'audio') # Carpeta base para audio
TEMPLATES_FOLDER = os.path.join(BASE_DIR, 'templates') # Nueva carpeta para templates

ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav'}
# Lista de subcarpetas de emociones permitidas para audio
ALLOWED_EMOTION_FOLDERS = ["angry", "fear", "happy", "neutral", "no_face", "sad", "surprise"]

PORT = 5002

app = Flask(__name__, template_folder=TEMPLATES_FOLDER) # Especificar la carpeta de templates
app.config['VIDEO_FOLDER'] = VIDEO_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER
app.secret_key = 'super secret key'

# --- Asegurarse que las carpetas base existan ---
for folder in [VIDEO_FOLDER, AUDIO_FOLDER, TEMPLATES_FOLDER]: # Añadir templates folder
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
            logging.info(f"Carpeta creada en: {folder}")
        except OSError as e:
            logging.error(f"Error al crear la carpeta {folder}: {e}")
            # Considerar terminar si no se puede crear
    else:
        logging.info(f"Usando carpeta existente: {folder}")


# --- Asegurarse que las subcarpetas de emociones existan ---
for emotion in ALLOWED_EMOTION_FOLDERS:
    emotion_folder_path = os.path.join(AUDIO_FOLDER, emotion)
    if not os.path.exists(emotion_folder_path):
        try:
            os.makedirs(emotion_folder_path)
            logging.info(f"Subcarpeta de emoción creada: {emotion_folder_path}")
        except OSError as e:
            logging.error(f"Error al crear subcarpeta de emoción {emotion_folder_path}: {e}")
            # Considerar terminar si no se puede crear

def allowed_file(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

# RUTA PRINCIPAL DE CARGA Y LISTADO
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # --- Manejo de Carga de Archivos (para solicitudes AJAX) ---
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
                # Devolver JSON con error para la solicitud AJAX
                logging.warning(f'Intento de subir audio con emoción inválida: "{selected_emotion}".')
                return jsonify({'error': f'Emoción seleccionada inválida: "{selected_emotion}".'}), 400

            # Construir ruta a la subcarpeta de emoción
            emotion_folder_name = secure_filename(selected_emotion) # Asegurar nombre carpeta
            upload_folder = os.path.join(app.config['AUDIO_FOLDER'], emotion_folder_name)
            allowed_extensions = ALLOWED_AUDIO_EXTENSIONS
            file_type = "Audio"
            target_folder_relative_for_log = os.path.relpath(upload_folder, STATIC_FOLDER)

            # Asegurar que la subcarpeta específica exista (aunque ya se hizo al inicio, por si acaso)
            if not os.path.exists(upload_folder):
                 try:
                     os.makedirs(upload_folder)
                     logging.info(f"Subcarpeta de audio creada al subir: {upload_folder}")
                 except OSError as e:
                     logging.error(f"Error al crear subcarpeta de audio {upload_folder}: {e}")
                     return jsonify({"error": f"Error interno al preparar carpeta para emoción '{selected_emotion}'."}), 500


        else:
            # Manejar el caso donde no se envió ni video ni audio válido (para AJAX)
            error_message = 'Ningún archivo seleccionado o tipo de archivo no válido.'
            if 'video' in request.files or 'audio' in request.files:
                 error_message = 'Ningún archivo seleccionado.'
            logging.warning(f"Intento de carga POST sin archivo válido. Mensaje: {error_message}")
            return jsonify({'error': error_message}), 400


        # Procesar el archivo seleccionado (si existe y es permitido)
        if file and allowed_file(file.filename, allowed_extensions):
            filename = secure_filename(file.filename)
            filepath = os.path.join(upload_folder, filename)

            try:
                # Comprobación de seguridad: No permitir rutas absolutas o travesías de directorio
                # Aunque secure_filename ayuda, una verificación extra no hace daño.
                # Realpath resuelve enlaces simbólicos, etc. Aseguramos que el destino esté dentro de la carpeta esperada.
                abs_upload_folder = os.path.realpath(upload_folder)
                abs_filepath_candidate = os.path.realpath(filepath)

                if not os.path.isdir(abs_upload_folder) or not abs_filepath_candidate.startswith(abs_upload_folder):
                     logging.warning(f"Intento de travesía de directorio detectado: {filename} -> {filepath} (Resuelto: {abs_filepath_candidate}, Carpeta destino: {abs_upload_folder})")
                     return jsonify({'error': 'Ruta de archivo no permitida.'}), 400


                file.save(filepath)
                logging.info(f"{file_type} guardado en: {filepath}")
                # Devolver JSON con éxito para la solicitud AJAX
                return jsonify({'status': 'success', 'message': f'{file_type} "{filename}" subido correctamente a {target_folder_relative_for_log}'}), 200
            except Exception as e:
                 logging.error(f"Error al guardar el archivo {filepath}: {e}")
                 return jsonify({'error': f'Error al guardar el archivo: {e}'}), 500
        elif file: # Si hay archivo pero la extensión no es válida
             logging.warning(f"Intento de subir archivo con extensión no permitida: {file.filename}")
             return jsonify({'error': f'Tipo de archivo no permitido para {file_type}. Extensiones permitidas: {", ".join(allowed_extensions)}'}), 400
        # El caso 'else' (no file) ya se cubrió antes


    # --- Método GET: Mostrar el formulario y la lista de archivos ---
    # Obtener la lista de videos
    try:
        video_files = sorted([f for f in os.listdir(app.config['VIDEO_FOLDER']) if os.path.isfile(os.path.join(app.config['VIDEO_FOLDER'], f))])
    except Exception as e:
        logging.error(f"Error al listar videos en {app.config['VIDEO_FOLDER']}: {e}")
        video_files = []
        # Añadir un flash message para informar al usuario si falla el listado GET
        flash('Error al cargar la lista de videos.', 'error')


    # Listar audios por carpeta de emoción
    audio_files_by_emotion = {}
    try:
        for emotion in ALLOWED_EMOTION_FOLDERS:
            emotion_folder_path = os.path.join(app.config['AUDIO_FOLDER'], emotion)
            if os.path.isdir(emotion_folder_path): # Verificar si existe la carpeta
                 audio_files_by_emotion[emotion] = sorted([
                    f for f in os.listdir(emotion_folder_path)
                    if os.path.isfile(os.path.join(emotion_folder_path, f))
                ])
            else:
                 # Si la carpeta no existe, registrarlo pero continuar
                 logging.warning(f"La subcarpeta de emoción '{emotion}' no existe en {app.config['AUDIO_FOLDER']}")
                 audio_files_by_emotion[emotion] = [] # Mostrarla vacía en la interfaz

    except Exception as e:
        logging.error(f"Error al listar audios en {app.config['AUDIO_FOLDER']}: {e}")
        # Dejar audio_files_by_emotion como esté (posiblemente vacío o parcial)
        # Añadir un flash message para informar al usuario si falla el listado GET
        flash('Error al cargar la lista de audios.', 'error')


    # Renderizar la plantilla HTML
    return render_template('upload.html',
                           videos=video_files,
                           audio_files_by_emotion=audio_files_by_emotion,
                           allowed_emotions=ALLOWED_EMOTION_FOLDERS)


# Ruta de eliminación modificada para manejar subpath (emoción para audio)
@app.route('/delete/<type>/<subpath>/<path:filename>', methods=['POST'])
def delete_file(type, subpath, filename):
    # Sanitizar nombre de archivo y subpath (emoción)
    filename = secure_filename(filename)
    # El subpath puede ser '_' para video o una emoción para audio
    if type == 'audio':
        subpath = secure_filename(subpath) # Asegura que el nombre de la emoción sea seguro
    elif type == 'video' and subpath != '_':
         # Si es video, el subpath debería ser el placeholder '_'
         logging.warning(f"Intento de eliminación de video con subpath inesperado: {subpath}")
         flash('Error: Ruta inválida para eliminar video.', 'error')
         abort(400) # Bad Request
    elif type != 'video' and type != 'audio':
         logging.warning(f"Intento de eliminación con tipo no válido: {type}")
         abort(404) # Not Found


    base_folder = None
    target_folder_relative_for_log = ""

    if type == 'video':
        base_folder = app.config['VIDEO_FOLDER']
        filepath = os.path.join(base_folder, filename)
        target_folder_relative_for_log = os.path.relpath(base_folder, STATIC_FOLDER)
    elif type == 'audio':
        # Para audio, subpath es la emoción
        if subpath not in ALLOWED_EMOTION_FOLDERS:
             logging.warning(f"Intento de eliminación en subcarpeta de audio no válida: {subpath}")
             flash('Error: Subcarpeta de emoción no válida.', 'error')
             abort(404) # Not Found

        base_folder = os.path.join(app.config['AUDIO_FOLDER'], subpath)
        filepath = os.path.join(base_folder, filename)
        target_folder_relative_for_log = os.path.relpath(base_folder, STATIC_FOLDER)

    # --- Comprobación de seguridad CRUCIAL ---
    # Verificar que la ruta resultante esté DENTRO de la carpeta base esperada
    try:
        abs_base = os.path.realpath(base_folder)
        abs_file = os.path.realpath(filepath)

        # Comprueba que la carpeta base exista y que el archivo esté dentro de ella
        if not os.path.isdir(abs_base) or os.path.commonpath([abs_base, abs_file]) != abs_base:
            logging.warning(f"Intento de eliminación fuera de la carpeta permitida o carpeta base no existe: {filepath} (Base resuelta: {abs_base}, Archivo resuelto: {abs_file})")
            flash('Error: Intento de acceso a ruta no válida o carpeta no encontrada.', 'error')
            # Usar 404 si la carpeta base no existe, 403 si está fuera del límite
            abort(404 if not os.path.isdir(abs_base) else 403)
    except Exception as e:
         logging.error(f"Error durante la validación de ruta para eliminar {filepath}: {e}")
         flash('Error interno al validar la ruta del archivo.', 'error')
         return redirect(url_for('upload_file'))


    # Proceder a eliminar si la ruta es válida
    try:
        if os.path.isfile(filepath):
            os.remove(filepath)
            flash(f'Archivo "{filename}" eliminado correctamente de {target_folder_relative_for_log}.', 'success')
            logging.info(f"Archivo eliminado: {filepath}")
        else:
            flash(f'Error: El archivo "{filename}" no fue encontrado en {target_folder_relative_for_log}.', 'error')
            logging.warning(f"Intento de eliminar archivo no existente: {filepath}")
    except Exception as e:
        flash(f'Error al eliminar el archivo "{filename}": {e}', 'error')
        logging.error(f"Error eliminando archivo {filepath}: {e}")

    # Redirigir de vuelta a la página principal (ahora manejada por la ruta '/')
    return redirect(url_for('upload_file'))


if __name__ == '__main__':
    print(f"Servidor de carga y gestión iniciado en http://0.0.0.0:{PORT}")
    print(f" - Sirviendo templates desde: {TEMPLATES_FOLDER}")
    print(f" - Sirviendo videos desde: {VIDEO_FOLDER}")
    print(f" - Sirviendo audios desde: {AUDIO_FOLDER} (con subcarpetas de emoción)")
    # Ejecutar con debug=True puede ser útil para desarrollo, pero cámbialo a False para producción/autostart
    # use_reloader=False puede ser necesario si tienes problemas con el reloader duplicando procesos
    app.run(host='0.0.0.0', port=PORT, debug=True, use_reloader=False)