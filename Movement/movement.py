from flask import Flask, request, jsonify, render_template
from gpiozero import PWMLED, LED
from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory()
app = Flask(__name__)

# Use hardware PWM pins for stable PWM signal.
# Motor A (left)
FWD_A = 18   # Hardware PWM pin for motor A speed control
REV_A = 27   # Digital: sets motor A direction (reverse flag)

# Motor B (right)
FWD_B = 19   # Hardware PWM pin for motor B speed control
REV_B = 9    # Digital: sets motor B direction (reverse flag)

motorA_fwd = PWMLED(FWD_A, pin_factory=factory)
motorA_rev = LED(REV_A, pin_factory=factory)
motorB_fwd = PWMLED(FWD_B, pin_factory=factory)
motorB_rev = LED(REV_B, pin_factory=factory)

# Configurable maximum throttle (e.g., 0.3 means max PWM duty cycle of 30%)
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
    # Get joystick values (expected range: [-1, 1])
    x = float(data.get("x", 0))
    y = float(data.get("y", 0))
    
    # Differential mixing:
    # Pushing joystick up (y=1) yields both motors = 1 (max forward).
    # Pushing down (y=-1) yields both motors = -1 (max reverse).
    # Pushing right (x positive) makes one motor forward and the other reverse.
    left  = y + x
    right = y - x

    # Clamp values to [-1, 1]
    left  = max(min(left, 1), -1)
    right = max(min(right, 1), -1)
    
    # Debug prints for checking values:
    print(f"Joystick: x={x:.2f}, y={y:.2f}")
    print(f"Differential values: left={left:.2f}, right={right:.2f}")
    
    # Stop previous outputs
    stop_all()
    
    # Motor A (Left):
    if left >= 0:
        motorA_rev.off()  # forward mode
        motorA_fwd.value = left * MAX_THROTTLE
        print(f"Motor A: FORWARD, PWM = {left * MAX_THROTTLE:.2f}")
    else:
        motorA_rev.on()   # reverse mode
        motorA_fwd.value = abs(left) * MAX_THROTTLE
        print(f"Motor A: REVERSE, PWM = {abs(left) * MAX_THROTTLE:.2f}")
    
    # Motor B (Right):
    if right >= 0:
        motorB_rev.off()  # forward mode
        motorB_fwd.value = right * MAX_THROTTLE
        print(f"Motor B: FORWARD, PWM = {right * MAX_THROTTLE:.2f}")
    else:
        motorB_rev.on()   # reverse mode
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
