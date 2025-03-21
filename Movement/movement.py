from flask import Flask, request, jsonify, render_template
from gpiozero import PWMLED, LED
from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory()
app = Flask(__name__)

# Motor A (left)
FWD_A = 17   # PWM: controls speed (duty cycle) for Motor A
REV_A = 27   # Digital: sets direction flag (reverse) for Motor A

# Motor B (right)
FWD_B = 10   # PWM: controls speed (duty cycle) for Motor B
REV_B = 9    # Digital: sets direction flag (reverse) for Motor B

motorA_fwd = PWMLED(FWD_A, pin_factory=factory)
motorA_rev = LED(REV_A, pin_factory=factory)
motorB_fwd = PWMLED(FWD_B, pin_factory=factory)
motorB_rev = LED(REV_B, pin_factory=factory)

# Configurable maximum throttle (0 to 1).
# A PWM value of 1.0 corresponds to a 100% duty cycle (i.e. 3.3V output).
MAX_THROTTLE = 0.3

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
    # Expecting joystick values (assumed in the range [-1, 1])
    x = float(data.get("x", 0))
    y = float(data.get("y", 0))
    
    # Differential mixing: standard equation.
    # left = y + x, right = y - x.
    left  = y + x
    right = y - x

    # Clamp the values so they stay within [-1, 1].
    left  = max(min(left, 1), -1)
    right = max(min(right, 1), -1)
    
    # Debug: print the joystick input and computed differential values.
    print(f"Joystick input: x={x:.2f}, y={y:.2f}")
    print(f"Computed values: left={left:.2f}, right={right:.2f}")
    
    # Stop previous outputs before applying new commands.
    stop_all()
    
    # For Motor A (left):
    if left >= 0:
        # Forward mode: reverse flag off, PWM = left * MAX_THROTTLE.
        motorA_rev.off()
        motorA_fwd.value = left * MAX_THROTTLE
        print(f"Motor A: FORWARD, PWM = {left * MAX_THROTTLE:.2f}")
    else:
        # Reverse mode: reverse flag on, PWM = |left| * MAX_THROTTLE.
        motorA_rev.on()
        motorA_fwd.value = abs(left) * MAX_THROTTLE
        print(f"Motor A: REVERSE, PWM = {abs(left) * MAX_THROTTLE:.2f}")
    
    # For Motor B (right):
    if right >= 0:
        motorB_rev.off()
        motorB_fwd.value = right * MAX_THROTTLE
        print(f"Motor B: FORWARD, PWM = {right * MAX_THROTTLE:.2f}")
    else:
        motorB_rev.on()
        motorB_fwd.value = abs(right) * MAX_THROTTLE
        print(f"Motor B: REVERSE, PWM = {abs(right) * MAX_THROTTLE:.2f}")
    
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
