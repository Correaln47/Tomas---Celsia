# movement.py modificado

from flask import Flask, request, jsonify, render_template
from gpiozero import LED  # Cambiado de PWMLED a LED
from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory()
app = Flask(__name__)

# --- Configuración de Pines GPIO ---
# Usamos LED para todos los pines, ya que solo necesitamos ON/OFF
# Motor A (Izquierdo)
FWD_A = 18   # Pin para mover hacia adelante (ahora es ON/OFF)
REV_A = 27   # Pin para habilitar reversa
# Motor B (Derecho)
FWD_B = 19   # Pin para mover hacia adelante (ahora es ON/OFF)
REV_B = 9    # Pin para habilitar reversa

motorA_fwd = LED(FWD_A, pin_factory=factory)
motorA_rev = LED(REV_A, pin_factory=factory)
motorB_fwd = LED(FWD_B, pin_factory=factory)
motorB_rev = LED(REV_B, pin_factory=factory)

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
    motorA_fwd.on() # Siempre a máxima velocidad (ON)
    motorB_rev.off()
    motorB_fwd.on() # Siempre a máxima velocidad (ON)
    print("Moviendo hacia ADELANTE")

def move_backward():
    """Mueve ambos motores hacia atrás."""
    motorA_rev.on()  # Habilita reversa
    motorA_fwd.on() # Siempre a máxima velocidad (ON)
    motorB_rev.on()  # Habilita reversa
    motorB_fwd.on() # Siempre a máxima velocidad (ON)
    print("Moviendo hacia ATRÁS")

def turn_left():
    """Gira a la izquierda (Motor A atrás, Motor B adelante)."""
    motorA_rev.on()  # Motor A en reversa
    motorA_fwd.on()
    motorB_rev.off() # Motor B hacia adelante
    motorB_fwd.on()
    print("Girando a la IZQUIERDA")

def turn_right():
    """Gira a la derecha (Motor A adelante, Motor B atrás)."""
    motorA_rev.off() # Motor A hacia adelante
    motorA_fwd.on()
    motorB_rev.on()  # Motor B en reversa
    motorB_fwd.on()
    print("Girando a la DERECHA")

# --- Rutas Flask ---

@app.route("/")
def index():
    """Sirve la página HTML de control."""
    return render_template("index.html")

@app.route("/control", methods=["POST"]) # Cambiado de /drive a /control
def control():
    """Recibe comandos de dirección y activa los motores."""
    data = request.json
    command = data.get("command")

    if command == "forward":
        turn_right()
    elif command == "backward":
        turn_left()
    elif command == "left":
        move_forward()
    elif command == "right":
        move_backward()
    elif command == "stop": # El stop también se puede manejar aquí si se prefiere
        stop_all()
    else:
        # Si el comando no es reconocido, detener por seguridad
        stop_all()
        return jsonify({"status": "error", "message": "Comando no reconocido"}), 400

    return jsonify({"status": "ok", "command": command})

@app.route("/stop", methods=["POST"])
def stop_command():
    """Ruta específica para detener los motores."""
    stop_all()
    return jsonify({"status": "stopped"})

# --- Inicio de la Aplicación ---
if __name__ == "__main__":
    try:
        stop_all() # Asegurarse de que los motores estén detenidos al iniciar
        app.run(host="0.0.0.0", port=5001)
    finally:
        # Limpieza de GPIO al cerrar la aplicación
        stop_all()
        motorA_fwd.close()
        motorA_rev.close()
        motorB_fwd.close()
        motorB_rev.close()
        print("GPIO limpiado.")