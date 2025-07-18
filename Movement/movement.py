from flask import Flask, request, jsonify, render_template
from gpiozero import LED
from gpiozero.pins.pigpio import PiGPIOFactory
import time
import threading
import subprocess
import re

factory = PiGPIOFactory()
app = Flask(__name__)

# --- Configuración de Pines GPIO ---
FWD_A = 18
REV_A = 27
FWD_B = 19
REV_B = 9

motorA_fwd = LED(FWD_A, pin_factory=factory)
motorA_rev = LED(REV_A, pin_factory=factory)
motorB_fwd = LED(FWD_B, pin_factory=factory)
motorB_rev = LED(REV_B, pin_factory=factory)

# --- Configuración del evento especial (Ahora solo son valores por defecto/fallback) ---
special_event_config = {
    "enabled": False,
    "initial_delay": 1000,
    "move_duration": 500,
    "delay_between": 500
}

# --- Funciones para el Control de Volumen ---

def get_system_volume():
    """
    Obtiene el volumen actual del sistema usando 'amixer'.
    Devuelve: El nivel de volumen (0-100) o None si hay un error.
    """
    try:
        result = subprocess.run(
            ["amixer", "sget", "Master"],
            capture_output=True,
            text=True,
            check=True
        )
        match = re.search(r"\[(\d{1,3})%\]", result.stdout)
        if match:
            return int(match.group(1))
        print("ERROR: No se pudo encontrar el porcentaje de volumen en la salida de amixer.")
        return None
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR al obtener el volumen del sistema: {e}")
        return None

def set_system_volume(volume):
    """
    Establece el volumen del sistema usando 'amixer'.
    Args: volume (int): El nivel de volumen deseado (0-100).
    """
    if not 0 <= volume <= 100:
        print(f"ERROR: El volumen debe estar entre 0 y 100. Se recibió: {volume}")
        return False
    try:
        subprocess.run(
            ["amixer", "-M", "sset", "Master", f"{volume}%"],
            check=True,
            capture_output=True
        )
        print(f"Volumen del sistema establecido en: {volume}%")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR al establecer el volumen del sistema: {e}")
        return False

# --- Funciones de Control de Movimiento ---

def stop_all():
    motorA_fwd.off()
    motorA_rev.off()
    motorB_fwd.off()
    motorB_rev.off()
    print("MOTORES DETENIDOS")

def turn_left():
    motorA_rev.off()
    motorA_fwd.on()
    motorB_rev.off()
    motorB_fwd.on()
    print("Moviendo hacia ADELANTE")

def turn_right():
    motorA_rev.on()
    motorA_fwd.on()
    motorB_rev.on()
    motorB_fwd.on()
    print("Moviendo hacia ATRÁS")

def move_backward():
    motorA_rev.on()
    motorA_fwd.on()
    motorB_rev.off()
    motorB_fwd.on()
    print("Girando a la IZQUIERDA")

def move_forward():
    motorA_rev.off()
    motorA_fwd.on()
    motorB_rev.on()
    motorB_fwd.on()
    print("Girando a la DERECHA")

# --- ### CAMBIO 1: La función ahora recibe la configuración como parámetro ### ---
def run_special_event_movement(config):
    print(f"--- INICIANDO SECUENCIA DE MOVIMIENTO ESPECIAL CON CONFIG: {config} ---")
    
    # Usa la configuración recibida, no la global
    initial_delay_s = config["initial_delay"] / 1000.0
    move_duration_s = config["move_duration"] / 1000.0
    delay_between_s = config["delay_between"] / 1000.0
    
    time.sleep(initial_delay_s)
    
    moves = [
        ("atrás", move_backward),
        ("adelante", move_forward),
        ("izquierda", turn_left),
        ("derecha", turn_right)
    ]
    
    for i, (name, move_func) in enumerate(moves):
        move_func()
        time.sleep(move_duration_s)
        stop_all()
        if i < len(moves) - 1:
            time.sleep(delay_between_s)
            
    print("--- FIN DE SECUENCIA DE MOVIMIENTO ESPECIAL ---")

# --- Rutas Flask ---

@app.route("/")
def index():
    return render_template("index.html")

# --- Rutas para el Control de Volumen ---
@app.route("/get_volume", methods=["GET"])
def get_volume_route():
    volume = get_system_volume()
    if volume is not None:
        return jsonify({"status": "ok", "volume": volume})
    else:
        return jsonify({"status": "error", "message": "No se pudo obtener el volumen."}), 500

@app.route("/set_volume", methods=["POST"])
def set_volume_route():
    data = request.json
    volume = data.get("volume")
    if volume is None:
        return jsonify({"status": "error", "message": "Falta el parámetro de volumen."}), 400
    
    if set_system_volume(int(volume)):
        return jsonify({"status": "ok", "message": f"Volumen establecido en {volume}%."})
    else:
        return jsonify({"status": "error", "message": "No se pudo establecer el volumen."}), 500

# --- Rutas de Control de Movimiento y Eventos ---
@app.route("/control", methods=["POST"])
def control():
    data = request.json
    command = data.get("command")
    if command == "forward":
        turn_left()
    elif command == "backward":
        turn_right()
    elif command == "left":
        move_backward()
    elif command == "right":
        move_forward()
    else:
        stop_all()
        return jsonify({"status": "error", "message": "Comando no reconocido"}), 400
    return jsonify({"status": "ok", "command": command})

@app.route("/stop", methods=["POST"])
def stop_command():
    stop_all()
    return jsonify({"status": "stopped"})

@app.route("/config_special_event", methods=["POST"])
def config_special_event():
    global special_event_config
    data = request.json
    special_event_config.update(data)
    print(f"Configuración de movimiento PREDETERMINADA actualizada por app.py: {special_event_config}")
    return jsonify({"status": "ok", "message": "Configuración de movimiento guardada."})

# --- ### CAMBIO 2: La ruta ahora lee la configuración de la petición ### ---
@app.route("/trigger_special_event_movement", methods=["POST"])
def trigger_special_event_movement():
    # Obtiene la configuración enviada desde app.py. Si no se envía nada, usa los valores por defecto.
    data = request.json or {}
    current_config = {
        "initial_delay": data.get("initial_delay", special_event_config["initial_delay"]),
        "move_duration": data.get("move_duration", special_event_config["move_duration"]),
        "delay_between": data.get("delay_between", special_event_config["delay_between"])
    }
    
    # Pasa la configuración recibida a la función de movimiento
    thread = threading.Thread(target=run_special_event_movement, args=(current_config,))
    thread.start()
    return jsonify({"status": "ok", "message": "Secuencia de movimiento especial iniciada con config específica."})

# --- Inicio de la Aplicación ---
if __name__ == "__main__":
    try:
        stop_all()
        app.run(host="0.0.0.0", port=5001)
    finally:
        stop_all()
        motorA_fwd.close()
        motorA_rev.close()
        motorB_fwd.close()
        motorB_rev.close()
        print("GPIO limpiado.")