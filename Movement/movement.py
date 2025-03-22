from flask import Flask, request, jsonify, render_template
from gpiozero import PWMLED, LED
from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory()
app = Flask(__name__)

# Motor A (left)
FWD_A = 18   # Hardware PWM for speed control
REV_A = 27   # Digital: reverse flag

# Motor B (right)
FWD_B = 19   # Hardware PWM for speed control
REV_B = 9    # Digital: reverse flag

motorA_fwd = PWMLED(FWD_A, pin_factory=factory)
motorA_rev = LED(REV_A, pin_factory=factory)
motorB_fwd = PWMLED(FWD_B, pin_factory=factory)
motorB_rev = LED(REV_B, pin_factory=factory)

# Global variables for current PWM values (for smoothing)
current_left_pwm = 0.0
current_right_pwm = 0.0

# Maximum change in PWM per update (adjust to control acceleration rate)
ACCEL_LIMIT = 0.1

def stop_all():
    global current_left_pwm, current_right_pwm
    motorA_fwd.value = 0
    motorA_rev.off()
    motorB_fwd.value = 0
    motorB_rev.off()
    current_left_pwm = 0.0
    current_right_pwm = 0.0

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/drive", methods=["POST"])
def drive():
    global current_left_pwm, current_right_pwm
    data = request.json
    # Joystick values expected to be in [-1, 1]
    x = float(data.get("x", 0))
    y = float(data.get("y", 0))
    # Additional throttle multiplier from interface (0 to 1)
    throttle_multiplier = float(data.get("throttle", 1))
    
    # Differential mixing: up = forward, down = reverse.
    # Full up (y=1,x=0) → left=1 and right=1 (both motors forward at max speed).
    # Full down (y=-1) → left=-1 and right=-1 (both motors reverse at max speed).
    # Right: (x positive) → one motor forward, the other reverse.
    left  = y + x
    right = y - x

    # Clamp to [-1, 1]
    left  = max(min(left, 1), -1)
    right = max(min(right, 1), -1)
    
    # Compute target PWM values (absolute value times throttle multiplier)
    target_left_pwm = abs(left) * throttle_multiplier
    target_right_pwm = abs(right) * throttle_multiplier
    
    # Ramp (smooth) changes in the left PWM value:
    if target_left_pwm > current_left_pwm:
        current_left_pwm = min(current_left_pwm + ACCEL_LIMIT, target_left_pwm)
    else:
        current_left_pwm = max(current_left_pwm - ACCEL_LIMIT, target_left_pwm)
    
    # Ramp (smooth) changes in the right PWM value:
    if target_right_pwm > current_right_pwm:
        current_right_pwm = min(current_right_pwm + ACCEL_LIMIT, target_right_pwm)
    else:
        current_right_pwm = max(current_right_pwm - ACCEL_LIMIT, target_right_pwm)
    
    # Debug prints to show values in the console:
    print(f"Joystick: x={x:.2f}, y={y:.2f}, throttle_multiplier={throttle_multiplier:.2f}")
    print(f"Differential: left={left:.2f}, right={right:.2f}")
    print(f"Target PWM: left={target_left_pwm:.2f}, right={target_right_pwm:.2f}")
    print(f"Smoothed PWM: left={current_left_pwm:.2f}, right={current_right_pwm:.2f}")
    
    # Set Motor A (Left)
    if left >= 0:
        motorA_rev.off()  # forward mode
        motorA_fwd.value = current_left_pwm
        print(f"Motor A: FORWARD, PWM = {current_left_pwm:.2f}")
    else:
        motorA_rev.on()   # reverse mode
        motorA_fwd.value = current_left_pwm
        print(f"Motor A: REVERSE, PWM = {current_left_pwm:.2f}")
    
    # Set Motor B (Right)
    if right >= 0:
        motorB_rev.off()  # forward mode
        motorB_fwd.value = current_right_pwm
        print(f"Motor B: FORWARD, PWM = {current_right_pwm:.2f}")
    else:
        motorB_rev.on()   # reverse mode
        motorB_fwd.value = current_right_pwm
        print(f"Motor B: REVERSE, PWM = {current_right_pwm:.2f}")
    
    return jsonify({
        "left": left,
        "right": right,
        "target_left_pwm": target_left_pwm,
        "target_right_pwm": target_right_pwm,
        "smoothed_left_pwm": current_left_pwm,
        "smoothed_right_pwm": current_right_pwm,
        "motorA_rev": motorA_rev.is_active,
        "motorB_rev": motorB_rev.is_active,
    })

@app.route("/stop", methods=["POST"])
def stop():
    stop_all()
    print("STOPPED")
    return jsonify({"status": "stopped"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
