from flask import Flask, request, jsonify, render_template
from gpiozero import PWMLED, LED
from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory()
app = Flask(__name__)

# Motor A (left)
FWD_A = 18   # PWM: controls speed for Motor A (hardware PWM)
REV_A = 27   # Digital: sets motor A direction (reverse)
# Motor B (right)
FWD_B = 19   # PWM: controls speed for Motor B (hardware PWM)
REV_B = 9    # Digital: sets motor B direction (reverse)

motorA_fwd = PWMLED(FWD_A, pin_factory=factory)
motorA_rev = LED(REV_A, pin_factory=factory)
motorB_fwd = PWMLED(FWD_B, pin_factory=factory)
motorB_rev = LED(REV_B, pin_factory=factory)

# Set max throttle to 0.9 (so PWM duty cycle is scaled by 0.9)
MAX_THROTTLE = 0.9

# Global variables to store current PWM magnitude for each motor
currentA = 0.0
currentB = 0.0

# Ramping rates
FAST_RATE = 0.1   # Fast ramping when accelerating (increasing PWM)
SLOW_RATE = 0.03  # Slow ramping when decelerating (reducing PWM)

def update_pwm(current, target, fast_rate, slow_rate):
    """
    Smoothly update the current PWM value toward the target.
    - When accelerating, increase quickly.
    - When decelerating to zero, decrease slowly.
    """
    if target > current:
        return min(current + fast_rate, target)
    elif target < current:
        # Use a slower deceleration when target is zero (gentle braking)
        if target == 0:
            return max(current - slow_rate, target)
        else:
            return max(current - fast_rate, target)
    return current

def stop_all():
    global currentA, currentB
    currentA = 0.0
    currentB = 0.0
    motorA_fwd.value = 0
    motorA_rev.off()
    motorB_fwd.value = 0
    motorB_rev.off()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/drive", methods=["POST"])
def drive():
    global currentA, currentB
    data = request.json
    # Read joystick values.
    # Invert the y-axis so that pushing up gives positive (forward) movement.
    x = float(data.get("x", 0))
    y = -float(data.get("y", 0))
    
    # Differential mixing: 
    # - Full up (y = 1, x = 0) -> left = 1, right = 1 (both forward)
    # - Full down (y = -1, x = 0) -> left = -1, right = -1 (both reverse)
    # - Pushing right (x positive) produces left > 0 and right < 0 (turn right)
    left  = y + x
    right = y - x

    # Clamp values to the range [-1, 1]
    left  = max(min(left, 1), -1)
    right = max(min(right, 1), -1)
    
    # Compute target PWM magnitudes (absolute values) scaled by MAX_THROTTLE
    targetA = abs(left) * MAX_THROTTLE
    targetB = abs(right) * MAX_THROTTLE
    
    # Update current PWM values using our ramping filter
    new_currentA = update_pwm(currentA, targetA, FAST_RATE, SLOW_RATE)
    new_currentB = update_pwm(currentB, targetB, FAST_RATE, SLOW_RATE)
    currentA, currentB = new_currentA, new_currentB
    
    # Debug prints
    print(f"Joystick: x={x:.2f}, y={y:.2f}")
    print(f"Differential: left={left:.2f}, right={right:.2f}")
    print(f"Targets: Motor A = {targetA:.2f}, Motor B = {targetB:.2f}")
    print(f"Ramped PWM: Motor A = {currentA:.2f}, Motor B = {currentB:.2f}")
    
    # Set Motor A (Left)
    if left >= 0:
        # Forward: disable reverse flag, apply PWM speed
        motorA_rev.off()
        motorA_fwd.value = currentA
        print(f"Motor A: FORWARD, PWM = {currentA:.2f}")
    else:
        # Reverse: enable reverse flag, apply PWM speed
        motorA_rev.on()
        motorA_fwd.value = currentA
        print(f"Motor A: REVERSE, PWM = {currentA:.2f}")
    
    # Set Motor B (Right)
    if right >= 0:
        motorB_rev.off()
        motorB_fwd.value = currentB
        print(f"Motor B: FORWARD, PWM = {currentB:.2f}")
    else:
        motorB_rev.on()
        motorB_fwd.value = currentB
        print(f"Motor B: REVERSE, PWM = {currentB:.2f}")
    
    return jsonify({
        "left": left,
        "right": right,
        "targetA": targetA,
        "targetB": targetB,
        "currentA": currentA,
        "currentB": currentB,
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
