from flask import Flask, request, jsonify, render_template
from gpiozero import PWMLED, LED
from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory()
app = Flask(__name__)

# Motor definitions:
# Motor A (left) – uses hardware PWM on FWD and a digital reverse flag.
FWD_A = 18   # PWM for speed control (hardware PWM pin)
REV_A = 27   # Digital reverse flag

# Motor B (right)
FWD_B = 19   # PWM for speed control (hardware PWM pin)
REV_B = 9    # Digital reverse flag

motorA_fwd = PWMLED(FWD_A, pin_factory=factory)
motorA_rev = LED(REV_A, pin_factory=factory)
motorB_fwd = PWMLED(FWD_B, pin_factory=factory)
motorB_rev = LED(REV_B, pin_factory=factory)

# Global variables for smoothing (current PWM values)
current_left_pwm = 0.0
current_right_pwm = 0.0

# Constants for deadzone and smoothing:
DEADZONE = 0.2       # If |x| is below this, treat x as 0.
SMOOTHING = 0.1      # Smoothing factor for acceleration (0.0 to 1.0)

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
    # Read joystick values (expected range -1 to 1)
    x = float(data.get("x", 0))
    y = float(data.get("y", 0))
    # Throttle multiplier from the slider (0 to 1)
    throttle_multiplier = float(data.get("throttle", 1))
    
    # Apply deadzone on steering (x axis)
    if abs(x) < DEADZONE:
        x = 0

    # Compute differential commands:
    # left_raw and right_raw are calculated from the joystick's y (forward/backward)
    # and x (steering). With a proper deadzone, a small x will yield:
    #   left_raw = y + x  ≈ y, and right_raw = y - x ≈ y.
    left_raw = y + x
    right_raw = y - x
    
    # Clamp values to [-1, 1]
    left_raw = max(min(left_raw, 1), -1)
    right_raw = max(min(right_raw, 1), -1)
    
    # Invert left motor command to compensate for wiring differences.
    # For example, if you push the joystick up (y=1, x=0) then:
    #   left_raw = 1, right_raw = 1.
    # But we want the left motor to actually run in reverse (to correct wiring),
    # so we define:
    left_cmd = -left_raw  
    right_cmd = right_raw
    
    # Determine target PWM (using throttle multiplier)
    target_left_pwm = abs(left_cmd) * throttle_multiplier
    target_right_pwm = abs(right_cmd) * throttle_multiplier
    
    # Smooth changes in PWM using exponential smoothing:
    current_left_pwm += SMOOTHING * (target_left_pwm - current_left_pwm)
    current_right_pwm += SMOOTHING * (target_right_pwm - current_right_pwm)
    
    # Debug prints:
    print(f"Joystick: x={x:.2f}, y={y:.2f}, throttle_multiplier={throttle_multiplier:.2f}")
    print(f"Raw: left_raw={left_raw:.2f}, right_raw={right_raw:.2f}")
    print(f"Adjusted: left_cmd={left_cmd:.2f}, right_cmd={right_cmd:.2f}")
    print(f"Target PWM: left={target_left_pwm:.2f}, right={target_right_pwm:.2f}")
    print(f"Smoothed PWM: left={current_left_pwm:.2f}, right={current_right_pwm:.2f}")
    
    # Set Motor A (Left)
    if left_cmd >= 0:
        # For left motor, a non-negative command means "forward" (which, because of inversion,
        # actually rotates the motor in the physically correct direction).
        motorA_rev.off()
        motorA_fwd.value = current_left_pwm
        print(f"Motor A: FORWARD, PWM = {current_left_pwm:.2f}")
    else:
        # Negative command: set reverse flag.
        motorA_rev.on()
        motorA_fwd.value = current_left_pwm
        print(f"Motor A: REVERSE, PWM = {current_left_pwm:.2f}")
    
    # Set Motor B (Right)
    if right_cmd >= 0:
        motorB_rev.off()
        motorB_fwd.value = current_right_pwm
        print(f"Motor B: FORWARD, PWM = {current_right_pwm:.2f}")
    else:
        motorB_rev.on()
        motorB_fwd.value = current_right_pwm
        print(f"Motor B: REVERSE, PWM = {current_right_pwm:.2f}")
    
    return jsonify({
        "left_cmd": left_cmd,
        "right_cmd": right_cmd,
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
    app.run(host="0.0.0.0", port=5000)
