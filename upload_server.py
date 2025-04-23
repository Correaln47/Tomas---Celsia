import os
import sys
from flask import Flask, request, render_template_string, redirect, url_for, flash, abort
from werkzeug.utils import secure_filename
import logging

# --- Configuración de Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuración de Rutas y Extensiones ---
try:
    # Obtiene la ruta del directorio donde se encuentra este script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
     # Si __file__ no está definido (p.ej. en intérprete interactivo), usa el directorio actual
     BASE_DIR = os.getcwd()
     logging.warning(f"__file__ no definido, usando directorio actual: {BASE_DIR}")


VIDEO_FOLDER = os.path.join(BASE_DIR, 'static', 'video')
AUDIO_FOLDER = os.path.join(BASE_DIR, 'static', 'audio') # Carpeta base para audio

ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav'}

PORT = 5002 # Puerto diferente para este servidor

app = Flask(__name__)
# Usar rutas absolutas para las carpetas de configuración
app.config['VIDEO_FOLDER'] = VIDEO_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER
app.secret_key = 'super secret key' # Necesario para usar flash messages

# --- Asegurarse que las carpetas de subida existan ---
for folder in [VIDEO_FOLDER, AUDIO_FOLDER]:
    if not os.path.exists(folder):
        try:
            os.makedirs(folder)
            logging.info(f"Carpeta creada en: {folder}")
        except OSError as e:
            logging.error(f"Error al crear la carpeta {folder}: {e}")
            # Podrías decidir terminar el script si no se puede crear la carpeta
            # sys.exit(f"No se pudo crear la carpeta necesaria: {folder}")
    else:
        logging.info(f"Usando carpeta existente: {folder}")


def allowed_file(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

# --- Plantilla HTML para el formulario y listados ---
HTML_TEMPLATE = """
<!doctype html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Gestionar Archivos de Tomas</title>
    <style>
        body { font-family: sans-serif; padding: 20px; line-height: 1.6; }
        h1, h2 { border-bottom: 1px solid #ccc; padding-bottom: 5px; }
        .upload-section { margin-bottom: 20px; padding: 15px; border: 1px solid #eee; border-radius: 5px; }
        .file-list { list-style: none; padding-left: 0; }
        .file-list li { margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; padding: 5px; border-bottom: 1px dotted #eee; }
        .file-list form { display: inline; margin-left: 10px; }
        .file-list button { background-color: #f44336; color: white; border: none; padding: 3px 8px; border-radius: 3px; cursor: pointer; font-size: 0.9em; }
        .file-list button:hover { background-color: #da190b; }
        .flash { padding: 10px; margin-bottom: 15px; border-radius: 4px; }
        .flash.success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .flash.error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
</head>
<body>
    <h1>Gestionar Archivos Multimedia de Tomas</h1>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="flash {{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <div class="upload-section">
        <h2>Subir Nuevo Video</h2>
        <form method=post enctype=multipart/form-data>
          <input type=file name=video accept="video/*">
          <input type=submit value="Subir Video">
        </form>
    </div>

    <div class="upload-section">
        <h2>Subir Nuevo Audio</h2>
        <form method=post enctype=multipart/form-data>
          <input type=file name=audio accept="audio/*">
          <input type=submit value="Subir Audio">
        </form>
    </div>

    <hr>

    <div>
        <h2>Videos Actuales (en static/video):</h2>
        {% if videos %}
            <ul class="file-list">
            {% for filename in videos %}
                <li>
                    <span>{{ filename }}</span>
                    <form method=post action="{{ url_for('delete_file', type='video', filename=filename) }}" onsubmit="return confirm('¿Estás seguro de que quieres eliminar este video?');">
                        <button type=submit>Eliminar</button>
                    </form>
                </li>
            {% endfor %}
            </ul>
        {% else %}
            <p>No hay videos aún.</p>
        {% endif %}
    </div>

    <div>
        <h2>Audios Actuales (en static/audio):</h2>
         <p><i>Nota: Por ahora, no se exploran subcarpetas de emociones aquí.</i></p>
        {% if audios %}
            <ul class="file-list">
            {% for filename in audios %}
                 <li>
                    <span>{{ filename }}</span>
                    <form method=post action="{{ url_for('delete_file', type='audio', filename=filename) }}" onsubmit="return confirm('¿Estás seguro de que quieres eliminar este audio?');">
                        <button type=submit>Eliminar</button>
                    </form>
                </li>
            {% endfor %}
            </ul>
        {% else %}
            <p>No hay audios aún.</p>
        {% endif %}
    </div>

</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        file = None
        upload_folder = None
        allowed_extensions = None
        file_type = None

        if 'video' in request.files and request.files['video'].filename != '':
            file = request.files['video']
            upload_folder = app.config['VIDEO_FOLDER']
            allowed_extensions = ALLOWED_VIDEO_EXTENSIONS
            file_type = "Video"
            target_folder_relative_for_log = os.path.relpath(upload_folder, BASE_DIR) # Para logs más cortos
        elif 'audio' in request.files and request.files['audio'].filename != '':
            file = request.files['audio']
            upload_folder = app.config['AUDIO_FOLDER'] # Sube a la carpeta base de audio por ahora
            allowed_extensions = ALLOWED_AUDIO_EXTENSIONS
            file_type = "Audio"
            # --- Opcional: Lógica para subcarpetas de emoción ---
            # emotion_subfolder = request.form.get('emotion')
            # if emotion_subfolder:
            #     upload_folder = os.path.join(upload_folder, secure_filename(emotion_subfolder))
            #     # Crear subcarpeta si no existe
            #     if not os.path.exists(upload_folder):
            #         try:
            #             os.makedirs(upload_folder)
            #             logging.info(f"Subcarpeta de audio creada: {upload_folder}")
            #         except OSError as e:
            #             logging.error(f"Error al crear subcarpeta de audio {upload_folder}: {e}")
            #             flash(f"Error al crear subcarpeta para emoción '{emotion_subfolder}'", "error")
            #             return redirect(request.url)
            # ----------------------------------------------------
            target_folder_relative_for_log = os.path.relpath(upload_folder, BASE_DIR) # Para logs más cortos

        if not file:
            flash('Ningún archivo seleccionado o enviado.', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename, allowed_extensions):
            filename = secure_filename(file.filename)
            # Asegurar que la carpeta de destino final exista (importante si hay subcarpetas)
            if not os.path.exists(upload_folder):
                 try:
                     os.makedirs(upload_folder)
                     logging.info(f"Carpeta de destino creada: {upload_folder}")
                 except OSError as e:
                     logging.error(f"Error al crear carpeta de destino {upload_folder}: {e}")
                     flash(f"Error interno al preparar carpeta de destino.", "error")
                     return redirect(request.url)

            filepath = os.path.join(upload_folder, filename)

            try:
                file.save(filepath)
                flash(f'{file_type} "{filename}" subido correctamente a {target_folder_relative_for_log}', 'success')
                logging.info(f"{file_type} guardado en: {filepath}")
                return redirect(url_for('upload_file')) # Redirige a GET
            except Exception as e:
                 flash(f'Error al guardar el archivo: {e}', 'error')
                 logging.error(f"Error guardando archivo {filepath}: {e}")
                 return redirect(request.url)
        else:
             flash(f'Tipo de archivo no permitido para {file_type}.', 'error')
             return redirect(request.url)

    # Método GET: Mostrar el formulario y la lista de archivos
    try:
        # Listar videos
        video_files = [f for f in os.listdir(app.config['VIDEO_FOLDER']) if os.path.isfile(os.path.join(app.config['VIDEO_FOLDER'], f))]
    except Exception as e:
        logging.error(f"Error al listar videos en {app.config['VIDEO_FOLDER']}: {e}")
        video_files = []

    try:
         # Listar audios (solo de la carpeta base por ahora)
         # TODO: Si se implementan subcarpetas, habría que listarlas recursivamente o cambiar la lógica.
        audio_files = [f for f in os.listdir(app.config['AUDIO_FOLDER']) if os.path.isfile(os.path.join(app.config['AUDIO_FOLDER'], f))]
    except Exception as e:
        logging.error(f"Error al listar audios en {app.config['AUDIO_FOLDER']}: {e}")
        audio_files = []

    return render_template_string(HTML_TEMPLATE, videos=sorted(video_files), audios=sorted(audio_files))


@app.route('/delete/<type>/<path:filename>', methods=['POST'])
def delete_file(type, filename):
    # Sanitizar filename por si acaso, aunque venga de url_for
    filename = secure_filename(filename)

    if type == 'video':
        base_folder = app.config['VIDEO_FOLDER']
    elif type == 'audio':
        base_folder = app.config['AUDIO_FOLDER']
        # Si se usaran subcarpetas, habría que determinar la ruta completa aquí
        # de forma segura, posiblemente necesitando más info en la URL o formulario.
    else:
        abort(404) # Tipo no reconocido

    filepath = os.path.join(base_folder, filename)
    # --- Comprobación de seguridad CRUCIAL ---
    # Verificar que la ruta resultante esté DENTRO de la carpeta base esperada
    # para evitar ataques de Path Traversal (ej. filename = ../../otro_archivo)
    common_path = os.path.commonpath([os.path.abspath(base_folder), os.path.abspath(filepath)])
    if os.path.abspath(base_folder) != common_path:
        logging.warning(f"Intento de eliminación fuera de la carpeta permitida: {filepath}")
        flash('Error: Intento de acceso a ruta no válida.', 'error')
        abort(403) # Forbidden

    try:
        if os.path.isfile(filepath):
            os.remove(filepath)
            flash(f'Archivo "{filename}" eliminado correctamente.', 'success')
            logging.info(f"Archivo eliminado: {filepath}")
        else:
            flash(f'Error: El archivo "{filename}" no fue encontrado.', 'error')
            logging.warning(f"Intento de eliminar archivo no existente: {filepath}")
    except Exception as e:
        flash(f'Error al eliminar el archivo "{filename}": {e}', 'error')
        logging.error(f"Error eliminando archivo {filepath}: {e}")

    return redirect(url_for('upload_file'))


if __name__ == '__main__':
    print(f"Servidor de carga y gestión iniciado en http://0.0.0.0:{PORT}")
    print(f" - Sirviendo videos desde: {VIDEO_FOLDER}")
    print(f" - Sirviendo audios desde: {AUDIO_FOLDER}")
    # Debug=False es más seguro para un servicio que corre siempre
    app.run(host='0.0.0.0', port=PORT, debug=False)