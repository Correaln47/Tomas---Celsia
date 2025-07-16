# movement.py modificado

from flask import Flask, request, jsonify, render_template
from gpiozero import LED
from gpiozero.pins.pigpio import PiGPIOFactory
import time
import threading

factory = PiGPIOFactory()
app = Flask(__name__)

# --- Configuración de Pines GPIO ---
# Motor A (Izquierdo)
FWD_A = 18
REV_A = 27
# Motor B (Derecho)
FWD_B = 19
REV_B = 9

motorA_fwd = LED(FWD_A, pin_factory=factory)
motorA_rev = LED(REV_A, pin_factory=factory)
motorB_fwd = LED(FWD_B, pin_factory=factory)
motorB_rev = LED(REV_B, pin_factory=factory)

# --- NUEVO: Almacenamiento de la configuración del evento especial ---
special_event_config = {
    "enabled": False,
    "initial_delay": 1000,  # en ms
    "move_duration": 500,   # en ms
    "delay_between": 500    # en ms
}

# --- Funciones de Control ---

def stop_all():
    """Detiene ambos motores."""
    motorA_fwd.off()
    motorA_rev.off()
    motorB_fwd.off()
    motorB_rev.off()
    print("MOTORES DETENIDOS")

def move_forward():
    """Mueve ambos motores hacia adelante."""
    motorA_rev.off()
    motorA_fwd.on()
    motorB_rev.off()
    motorB_fwd.on()
    print("Moviendo hacia ADELANTE")

def move_backward():
    """Mueve ambos motores hacia atrás."""
    motorA_rev.on()
    motorA_fwd.on()
    motorB_rev.on()
    motorB_fwd.on()
    print("Moviendo hacia ATRÁS")

def turn_left():
    """Gira a la izquierda (Motor A atrás, Motor B adelante)."""
    motorA_rev.on()
    motorA_fwd.on()
    motorB_rev.off()
    motorB_fwd.on()
    print("Girando a la IZQUIERDA")

def turn_right():
    """Gira a la derecha (Motor A adelante, Motor B atrás)."""
    motorA_rev.off()
    motorA_fwd.on()
    motorB_rev.on()
    motorB_fwd.on()
    print("Girando a la DERECHA")

# --- NUEVO: Lógica para la secuencia de movimiento del evento especial ---
def run_special_event_movement():
    """Ejecuta la secuencia de movimientos en un hilo separado."""
    if not special_event_config["enabled"]:
        print("Evento especial de movimiento recibido, pero está desactivado.")
        return

    print("--- INICIANDO SECUENCIA DE MOVIMIENTO ESPECIAL ---")
    
    # Convertir milisegundos a segundos para time.sleep()
    initial_delay_s = special_event_config["initial_delay"] / 1000.0
    move_duration_s = special_event_config["move_duration"] / 1000.0
    delay_between_s = special_event_config["delay_between"] / 1000.0
    
    time.sleep(initial_delay_s)
    
    # Secuencia de movimientos
    moves = [
        ("atrás", move_backward),
        ("adelante", move_forward),
        ("izquierda", turn_left),
        ("derecha", turn_right)
    ]
    
    for i, (name, move_func) in enumerate(moves):
        print(f"Evento especial: Moviendo hacia {name}")
        move_func()
        time.sleep(move_duration_s)
        stop_all()
        # No esperar después del último movimiento
        if i < len(moves) - 1:
            time.sleep(delay_between_s)

    print("--- FIN DE SECUENCIA DE MOVIMIENTO ESPECIAL ---")

# --- Rutas Flask ---

@app.route("/")
def index():
    """Sirve la página HTML de control."""
    return render_template("index.html")

@app.route("/control", methods=["POST"])
def control():
    """Recibe comandos de dirección y activa los motores. Lógica CORREGIDA."""
    data = request.json
    command = data.get("command")

    # Lógica de movimiento corregida para que coincida con los botones
    if command == "forward":
        move_forward()
    elif command == "backward":
        move_backward()
    elif command == "left":
        turn_left()
    elif command == "right":
        turn_right()
    else:
        stop_all()
        return jsonify({"status": "error", "message": "Comando no reconocido"}), 400

    return jsonify({"status": "ok", "command": command})

@app.route("/stop", methods=["POST"])
def stop_command():
    """Ruta específica para detener los motores."""
    stop_all()
    return jsonify({"status": "stopped"})

# --- NUEVO: Rutas para manejar la configuración del evento especial ---

@app.route("/config_special_event", methods=["POST"])
def config_special_event():
    """Recibe y guarda la configuración del evento especial desde la interfaz."""
    global special_event_config
    data = request.json
    
    # Actualizar configuración con validación básica
    special_event_config["enabled"] = bool(data.get("enabled", False))
    special_event_config["initial_delay"] = int(data.get("initial_delay", 1000))
    special_event_config["move_duration"] = int(data.get("move_duration", 500))
    special_event_config["delay_between"] = int(data.get("delay_between", 500))
    
    print(f"Configuración de evento especial actualizada: {special_event_config}")
    return jsonify({"status": "ok", "message": "Configuración guardada."})

@app.route("/get_special_event_config", methods=["GET"])
def get_special_event_config():
    """Devuelve la configuración actual a la interfaz."""
    return jsonify(special_event_config)

@app.route("/trigger_special_event_movement", methods=["POST"])
def trigger_special_event_movement():
    """Activa la secuencia de movimiento si está habilitada."""
    if special_event_config["enabled"]:
        thread = threading.Thread(target=run_special_event_movement)
        thread.start()
        return jsonify({"status": "ok", "message": "Secuencia de movimiento especial iniciada."})
    else:
        return jsonify({"status": "disabled", "message": "El evento especial está desactivado."})


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