from flask import Flask, request, jsonify, render_template
from gpiozero import LED
from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory()
app = Flask(__name__)

# Motor A (left)
DIR1 = 17  # Forward
DIR2 = 27  # Reverse

# Motor B (right)
DIR3 = 10  # Forward
DIR4 = 9   # Reverse

motorA_fwd = LED(DIR1, pin_factory=factory)
motorA_rev = LED(DIR2, pin_factory=factory)
motorB_fwd = LED(DIR3, pin_factory=factory)
motorB_rev = LED(DIR4, pin_factory=factory)

def stop_all():
    motorA_fwd.off()
    motorA_rev.off()
    motorB_fwd.off()
    motorB_rev.off()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/drive", methods=["POST"])
def drive():
    data = request.json
    x = float(data.get("x", 0))
    y = float(data.get("y", 0))

    stop_all()

    left = y + x
    right = y - x

    # Normalize
    max_val = max(abs(left), abs(right), 1)
    left /= max_val
    right /= max_val

    # Motor A
    if left > 0:
        motorA_fwd.on()
    elif left < 0:
        motorA_rev.on()

    # Motor B
    if right > 0:
        motorB_fwd.on()
    elif right < 0:
        motorB_rev.on()

    return jsonify({"left": left, "right": right})

@app.route("/stop", methods=["POST"])
def stop():
    stop_all()
    return jsonify({"status": "stopped"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
