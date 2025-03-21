from flask import Flask, request, jsonify, render_template
from gpiozero import PWMLED, LED
from gpiozero.pins.pigpio import PiGPIOFactory

factory = PiGPIOFactory()
app = Flask(__name__)

# Motor A (left)
FWD_A = 17   # PWM: sets speed
REV_A = 27   # Digital: sets reverse flag

# Motor B (right)
FWD_B = 10   # PWM: sets speed
REV_B = 9    # Digital: sets reverse flag

# Create our motor objects:
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
    x = float(data.get("x", 0))
    y = float(data.get("y", 0))

    # Compute differential values
    left  = y + x
    right = y - x

    # Normalize values so that maximum magnitude is 1
    max_val = max(abs(left), abs(right), 1)
    left  /= max_val
    right /= max_val

    # Stop previous commands
    stop_all()

    # Motor A (Left)
    if left >= 0:
        # Forward: set reverse flag off, PWM proportional to speed
        motorA_rev.off()
        motorA_fwd.value = abs(left)
        print(f"Motor A: FORWARD with PWM = {abs(left):.2f}")
    else:
        # Reverse: set reverse flag on, PWM proportional to speed
        motorA_rev.on()
        motorA_fwd.value = abs(left)
        print(f"Motor A: REVERSE with PWM = {abs(left):.2f}")

    # Motor B (Right)
    if right >= 0:
        motorB_rev.off()
        motorB_fwd.value = abs(right)
        print(f"Motor B: FORWARD with PWM = {abs(right):.2f}")
    else:
        motorB_rev.on()
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
