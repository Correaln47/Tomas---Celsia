from flask import Flask, request, jsonify, render_template
from gpiozero import LED, PWMLED
from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory()
app = Flask(__name__)

# Pin setup (same as earlier)
DIR1 = 17; DIR2 = 27; THROTTLE1 = 22
DIR3 = 10; DIR4 = 9;  THROTTLE2 = 23

motorA_fwd = LED(DIR1, pin_factory=factory)
motorA_rev = LED(DIR2, pin_factory=factory)
motorA_pwm = PWMLED(THROTTLE1, pin_factory=factory)

motorB_fwd = LED(DIR3, pin_factory=factory)
motorB_rev = LED(DIR4, pin_factory=factory)
motorB_pwm = PWMLED(THROTTLE2, pin_factory=factory)

MAX_THROTTLE = 0.3

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/drive", methods=["POST"])
def drive():
    data = request.json
    x = float(data.get("x", 0))
    y = float(data.get("y", 0))

    motorA_fwd.off(); motorA_rev.off(); motorA_pwm.value = 0
    motorB_fwd.off(); motorB_rev.off(); motorB_pwm.value = 0

    throttle = min((x**2 + y**2)**0.5, 1.0) * MAX_THROTTLE
    left = y + x
    right = y - x
    max_val = max(abs(left), abs(right))
    if max_val > 1:
        left /= max_val
        right /= max_val

    if left > 0:
        motorA_fwd.on(); motorA_rev.off(); motorA_pwm.value = abs(left) * throttle
    elif left < 0:
        motorA_fwd.off(); motorA_rev.on(); motorA_pwm.value = abs(left) * throttle

    if right > 0:
        motorB_fwd.on(); motorB_rev.off(); motorB_pwm.value = abs(right) * throttle
    elif right < 0:
        motorB_fwd.off(); motorB_rev.on(); motorB_pwm.value = abs(right) * throttle

    return jsonify({"status": "driving", "throttle": throttle})

@app.route("/stop", methods=["POST"])
def stop():
    motorA_fwd.off(); motorA_rev.off(); motorA_pwm.value = 0
    motorB_fwd.off(); motorB_rev.off(); motorB_pwm.value = 0
    return jsonify({"status": "stopped"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
