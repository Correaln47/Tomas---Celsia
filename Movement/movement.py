from flask import Flask, request, jsonify, render_template
from gpiozero import PWMLED, LED
from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory()
app = Flask(__name__)

# Motor A (left)
FWD_A = 17   # PWM: controls speed for motor A
REV_A = 27   # Digital: direction flag for motor A

# Motor B (right)
FWD_B = 10   # PWM: controls speed for motor B
REV_B = 9    # Digital: direction flag for motor B

# Create motor objects:
motorA_fwd = PWMLED(FWD_A, pin_factory=factory)
motorA_rev = LED(REV_A, pin_factory=factory)
motorB_fwd = PWMLED(FWD_B, pin_factory=factory)
motorB_rev = LED(REV_B, pin_factory=factory)

# Configurable maximum throttle (0 to 1) to easily change the maximum duty cycle
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
    # Get joystick values:
    x = float(data.get("x", 0))
    y = float(data.get("y", 0))
    
    # Compute differential drive values:
    left = y + x
    right = y - x
    
    # Normalize values to [-1, 1] if necessary:
    max_val = max(abs(left), abs(right), 1)
    left /= max_val
    right /= max_val
    
    # Now scale the PWM values by MAX_THROTTLE:
    left_pwm = abs(left) * MAX_THROTTLE
    right_pwm = abs(right) * MAX_THROTTLE
    
    # Stop previous outputs:
    stop_all()
    
    # Debug prints:
    print(f"Joystick: x={x:.2f}, y={y:.2f} | Differential: left={left:.2f}, right={right:.2f}")
    print(f"Applied PWM (after throttle scaling): left={left_pwm:.2f}, right={right_pwm:.2f}")
    
    # Set Motor A (Left)
    if left >= 0:
        motorA_rev.off()  # forward mode
        motorA_fwd.value = left_pwm
        print(f"Motor A: FORWARD with PWM = {left_pwm:.2f}")
    else:
        motorA_rev.on()  # reverse flag active
        motorA_fwd.value = left_pwm
        print(f"Motor A: REVERSE with PWM = {left_pwm:.2f}")
    
    # Set Motor B (Right)
    if right >= 0:
        motorB_rev.off()  # forward mode
        motorB_fwd.value = right_pwm
        print(f"Motor B: FORWARD with PWM = {right_pwm:.2f}")
    else:
        motorB_rev.on()  # reverse flag active
        motorB_fwd.value = right_pwm
        print(f"Motor B: REVERSE with PWM = {right_pwm:.2f}")
    
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
