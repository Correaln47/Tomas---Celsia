# movement.py modificado para control centralizado

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

# Almacenamiento local para la configuración de movimiento del evento.
# Esta configuración es ahora recibida desde app.py
special_event_config = {
    "enabled": False,
    "initial_delay": 1000,
    "move_duration": 500,
    "delay_between": 500
}

# --- Funciones de Control (SIN CAMBIOS, respetando la lógica del hardware) ---

def stop_all():
    """Detiene ambos motores."""
    motorA_fwd.off()
    motorA_rev.off()
    motorB_fwd.off()
    motorB_rev.off()
    print("MOTORES DETENIDOS")

def turn_left(): # ADELANTE (según la lógica del usuario)
    """Mueve ambos motores hacia adelante."""
    motorA_rev.off()
    motorA_fwd.on()
    motorB_rev.off()
    motorB_fwd.on()
    print("Moviendo hacia ADELANTE")

def turn_right(): # ATRÁS (según la lógica del usuario)
    """Mueve ambos motores hacia atrás."""
    motorA_rev.on()
    motorA_fwd.on()
    motorB_rev.on()
    motorB_fwd.on()
    print("Moviendo hacia ATRÁS")

def move_backward(): # IZQUIERDA (según la lógica del usuario)
    """Gira a la izquierda."""
    motorA_rev.on()
    motorA_fwd.on()
    motorB_rev.off()
    motorB_fwd.on()
    print("Girando a la IZQUIERDA")

def move_forward(): # DERECHA (según la lógica del usuario)
    """Gira a la derecha."""
    motorA_rev.off()
    motorA_fwd.on()
    motorB_rev.on()
    motorB_fwd.on()
    print("Girando a la DERECHA")

# --- Lógica de la secuencia de movimiento del evento (SIN CAMBIOS) ---
def run_special_event_movement():
    """Ejecuta la secuencia de movimientos en un hilo separado."""
    if not special_event_config["enabled"]:
        print("Movimiento de evento recibido, pero está desactivado.")
        return

    print("--- INICIANDO SECUENCIA DE MOVIMIENTO ESPECIAL ---")
    
    initial_delay_s = special_event_config["initial_delay"] / 1000.0
    move_duration_s = special_event_config["move_duration"] / 1000.0
    delay_between_s = special_event_config["delay_between"] / 1000.0
    
    time.sleep(initial_delay_s)
    
    # La secuencia de movimiento se mantiene con las funciones originales
    moves = [
        ("atrás", move_backward), # Llama a la función de giro izquierda
        ("adelante", move_forward),  # Llama a la función de giro derecha
        ("izquierda", turn_left),    # Llama a la función de avance
        ("derecha", turn_right)      # Llama a la función de retroceso
    ]
    
    for i, (name, move_func) in enumerate(moves):
        print(f"Evento especial: Moviendo '{name}' (función: {move_func.__name__})")
        move_func()
        time.sleep(move_duration_s)
        stop_all()
        if i < len(moves) - 1:
            time.sleep(delay_between_s)

    print("--- FIN DE SECUENCIA DE MOVIMIENTO ESPECIAL ---")

# --- Rutas Flask ---

@app.route("/control", methods=["POST"])
def control():
    """Recibe comandos de dirección y activa los motores (SIN CAMBIOS EN LA LÓGICA)."""
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
    """Ruta específica para detener los motores."""
    stop_all()
    return jsonify({"status": "stopped"})

# --- Rutas MODIFICADAS para el evento especial ---

@app.route("/config_special_event", methods=["POST"])
def config_special_event():
    """Recibe y guarda la configuración del evento especial desde app.py."""
    global special_event_config
    data = request.json
    special_event_config.update(data)
    print(f"Configuración de movimiento actualizada por app.py: {special_event_config}")
    return jsonify({"status": "ok", "message": "Configuración de movimiento guardada."})

@app.route("/trigger_special_event_movement", methods=["POST"])
def trigger_special_event_movement():
    """Activa la secuencia de movimiento (llamado por app.py)."""
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
        # Se elimina render_template de las importaciones ya que no se usa más
        app.run(host="0.0.0.0", port=5001)
    finally:
        stop_all()
        motorA_fwd.close()
        motorA_rev.close()
        motorB_fwd.close()
        motorB_rev.close()
        print("GPIO limpiado.")