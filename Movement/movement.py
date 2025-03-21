from flask import Flask, request, jsonify, render_template
from gpiozero import PWMLED, LED
from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory()
app = Flask(__name__)

# Motor A (left)
DIR1 = 17  # Forward (PWM)
DIR2 = 27  # Reverse (ON/OFF)

# Motor B (right)
DIR3 = 10  # Forward (PWM)
DIR4 = 9   # Reverse (ON/OFF)

motorA_fwd = PWMLED(DIR1, pin_factory=factory)
motorA_rev = LED(DIR2, pin_factory=factory)
motorB_fwd = PWMLED(DIR3, pin_factory=factory)
motorB_rev = LED(DIR4, pin_factory=factory)

def stop_all():
    motorA_fwd.value = 0
    motorA_rev.off()
    motorB_fwd.value = 0
    motorB_rev.off()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/drive", methods=["POST"])
def drive():
    data = request.json
    x = float(data.get("x", 0))
    y = float(data.get("y", 0))

    # Differential drive
    left = y + x
    right = y - x

    # Normalize
    max_val = max(abs(left), abs(right), 1)
    left /= max_val
    right /= max_val

    # Stop everything before new motion
    stop_all()

    # Motor A (left)
    if left > 0:
        motorA_fwd.value = abs(left)
        print(f"Left motor FORWARD at {abs(left):.2f}")
    elif left < 0:
        motorA_rev.on()
        print(f"Left motor REVERSE")

    # Motor B (right)
    if right > 0:
        motorB_fwd.value = abs(right)
        print(f"Right motor FORWARD at {abs(right):.2f}")
    elif right < 0:
        motorB_rev.on()
        print(f"Right motor REVERSE")

    return jsonify({
        "left": left,
        "right": right,
        "motorA_fwd": motorA_fwd.value,
        "motorA_rev": motorA_rev.is_active,
        "motorB_fwd": motorB_fwd.value,
        "motorB_rev": motorB_rev.is_active,
    })

@app.route("/stop", methods=["POST"])
def stop():
    stop_all()
    print("STOPPED")
    return jsonify({"status": "stopped"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
