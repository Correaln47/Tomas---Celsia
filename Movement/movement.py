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
    # Get the joystick values from the web interface:
    x = float(data.get("x", 0))
    y = float(data.get("y", 0))
    
    # Compute differential drive values:
    left  = y + x
    right = y - x

    # Normalize values so that the maximum absolute value is 1
    max_val = max(abs(left), abs(right), 1)
    left  /= max_val
    right /= max_val

    # Debug prints:
    print(f"Received joystick values: x={x:.2f}, y={y:.2f}")
    print(f"Computed differential values: left={left:.2f}, right={right:.2f}")

    # Stop any previous commands:
    stop_all()

    # Set Motor A (Left)
    if left >= 0:
        motorA_rev.off()  # forward mode
        motorA_fwd.value = abs(left)
        print(f"Motor A: FORWARD with PWM = {abs(left):.2f}")
    else:
        motorA_rev.on()  # reverse flag active
        motorA_fwd.value = abs(left)
        print(f"Motor A: REVERSE with PWM = {abs(left):.2f}")

    # Set Motor B (Right)
    if right >= 0:
        motorB_rev.off()  # forward mode
        motorB_fwd.value = abs(right)
        print(f"Motor B: FORWARD with PWM = {abs(right):.2f}")
    else:
        motorB_rev.on()  # reverse flag active
        motorB_fwd.value = abs(right)
        print(f"Motor B: REVERSE with PWM = {abs(right):.2f}")

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
