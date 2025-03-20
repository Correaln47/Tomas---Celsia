from flask import Flask, Response
import time

app = Flask(__name__)

def gen_test_video():
    # Read the static image from disk
    with open("static/test.png", "rb") as f:
        img = f.read()
    while True:
        # Yield the same image every time using the MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + img + b'\r\n')
        time.sleep(0.1)

@app.route('/video_feed')
def video_feed():
    return Response(gen_test_video(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(debug=True)
