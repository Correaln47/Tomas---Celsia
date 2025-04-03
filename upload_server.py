import os
from flask import Flask, request, render_template_string, redirect, url_for, flash
from werkzeug.utils import secure_filename

# --- Configuración ---
UPLOAD_FOLDER = os.path.join('static', 'video') # Ruta relativa a donde se ejecuta el script
ALLOWED_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi'} # Extensiones permitidas
PORT = 5002 # Puerto diferente para este servidor

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'super secret key' # Necesario para usar flash messages

# --- Asegurarse que la carpeta de subida exista ---
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Carpeta de subida creada en: {os.path.abspath(UPLOAD_FOLDER)}")
else:
    print(f"Usando carpeta de subida existente: {os.path.abspath(UPLOAD_FOLDER)}")


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Plantilla HTML simple para el formulario ---
# Usamos render_template_string para no necesitar un archivo .html separado
HTML_FORM = """
<!doctype html>
<title>Subir Nuevo Video</title>
<h1>Subir Nuevo Video para Tomas</h1>
{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    <ul>
    {% for category, message in messages %}
      <li class="{{ category }}">{{ message }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
<form method=post enctype=multipart/form-data>
  <input type=file name=video accept="video/*">
  <input type=submit value=Subir>
</form>
<hr>
<h2>Videos Actuales:</h2>
<ul>
  {% for filename in videos %}
    <li>{{ filename }}</li>
  {% else %}
    <li>No hay videos aún.</li>
  {% endfor %}
</ul>
<style>
    body { font-family: sans-serif; padding: 20px; }
    .success { color: green; }
    .error { color: red; }
    li { margin-bottom: 5px;}
</style>
"""

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Verificar si el post request tiene la parte del archivo
        if 'video' not in request.files:
            flash('No se encontró la parte del archivo', 'error')
            return redirect(request.url)
        file = request.files['video']
        # Si el usuario no selecciona archivo, el navegador
        # envía una parte vacía sin nombre de archivo
        if file.filename == '':
            flash('Ningún archivo seleccionado', 'error')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                file.save(filepath)
                flash(f'Video "{filename}" subido correctamente!', 'success')
                print(f"Video guardado en: {filepath}")
                 # Redirige a GET para mostrar la lista actualizada y limpiar el formulario
                return redirect(url_for('upload_file'))
            except Exception as e:
                 flash(f'Error al guardar el archivo: {e}', 'error')
                 print(f"Error guardando archivo: {e}")
                 return redirect(request.url) # Recarga con mensaje de error
        else:
             flash('Tipo de archivo no permitido. Usar mp4, webm, mov, avi.', 'error')
             return redirect(request.url)

    # Método GET: Mostrar el formulario y la lista de videos actuales
    try:
        current_videos = os.listdir(app.config['UPLOAD_FOLDER'])
        # Filtrar para mostrar solo archivos (no subdirectorios, si los hubiera)
        current_videos = [f for f in current_videos if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], f))]
    except FileNotFoundError:
        current_videos = [] # Si la carpeta no existe aún

    return render_template_string(HTML_FORM, videos=current_videos)

if __name__ == '__main__':
    print(f"Servidor de carga iniciado en http://0.0.0.0:{PORT}")
    # Ejecutar en la red local (0.0.0.0)
    # Debug=False es más seguro para un servicio que corre siempre
    app.run(host='0.0.0.0', port=PORT, debug=False)