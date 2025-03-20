from flask import Flask, render_template, Response, jsonify
import cv2, time, threading, os, random
import numpy as np
import tflite_runtime.interpreter as tflite

app = Flask(__name__)

# --- Global state and thread lock ---
frame_lock = threading.Lock()
current_frame = None    # The live, JPEG-encoded frame with overlays

detection_complete = False   # Set to True when a stable emotion is detected
detected_emotion = "neutral"   # The detected emotion (e.g. "neutral")
detected_snapshot = None       # The frozen snapshot (for interaction phase)

# For stable emotion detection
last_emotion = None
emotion_start_time = None

emotion_buffer = []  # list of tuples (timestamp, emotion)
buffer_window = 7    # time window in seconds
threshold_ratio = 0.7  # require 70% or more of detections to be the same emotion
min_count = 30  

# --- Load face detector and TFLite emotion model ---
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
emotion_labels = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

interpreter = tflite.Interpreter(model_path="emotion_model.tflite")
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()
print("TFLite model input shape:", input_details[0]['shape'])  # e.g. [1, 64, 64, 1]

def predict_emotion_tflite(face_roi):
    gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    try:
        h, w = input_details[0]['shape'][1:3]
        gray_face = cv2.resize(gray_face, (w, h))
    except Exception as e:
        print("Error resizing face ROI:", e)
        return "neutral"
    gray_face = gray_face.astype("float32") / 255.0
    input_data = np.expand_dims(np.expand_dims(gray_face, axis=-1), axis=0)
    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()
    preds = interpreter.get_tensor(output_details[0]['index'])[0]
    emotion_index = np.argmax(preds)
    print("Predicted probabilities:", preds, "-> Selected label:", emotion_labels[emotion_index])
    return emotion_labels[emotion_index]

def detection_loop():
    global current_frame, detection_complete, detected_emotion, detected_snapshot
    global last_emotion, emotion_start_time, emotion_buffer

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Camera not accessible")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            print("detection_loop: Failed to read frame")
            time.sleep(0.1)
            continue

        # Face detection: always process the frame to overlay the green box.
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        except Exception as e:
            print("detection_loop: Error during face detection:", e)
            faces = []

        if len(faces) > 0:
            (x, y, w, h) = faces[0]  # use the first detected face
            # Draw a green rectangle around the face
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            # Overlay the last detected emotion, if available
            if last_emotion:
                cv2.putText(frame, last_emotion, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX,
                            0.9, (0, 255, 0), 2)
            face_roi = frame[y:y+h, x:x+w]
            try:
                emotion = predict_emotion_tflite(face_roi)
            except Exception as e:
                print("detection_loop: Error during emotion prediction:", e)
                emotion = "neutral"
            print("detection_loop: Detected emotion:", emotion)

            # If stable detection isn't already complete, update the buffer.
            if not detection_complete:
                current_time = time.time()
                emotion_buffer.append((current_time, emotion))
                # Remove old entries
                emotion_buffer = [(t, e) for (t, e) in emotion_buffer if current_time - t <= buffer_window]
                if len(emotion_buffer) >= min_count:
                    freq = {}
                    for (_, e) in emotion_buffer:
                        freq[e] = freq.get(e, 0) + 1
                    dominant_emotion = max(freq, key=freq.get)
                    ratio = freq[dominant_emotion] / len(emotion_buffer)
                    print("detection_loop: Buffer size:", len(emotion_buffer), "Dominant emotion:", dominant_emotion, "Ratio:", ratio)
                    if ratio >= threshold_ratio:
                        detection_complete = True
                        detected_emotion = dominant_emotion
                        ret2, snapshot_jpeg = cv2.imencode('.jpg', frame)
                        if ret2:
                            detected_snapshot = snapshot_jpeg.tobytes()
                            # Optionally save snapshot for debugging:
                            with open("detected_snapshot.jpg", "wb") as f:
                                f.write(detected_snapshot)
                        print("detection_loop: Detection complete with emotion:", dominant_emotion)
                else:
                    last_emotion = emotion
        else:
            if not detection_complete:
                emotion_buffer = []
                last_emotion = None
                emotion_start_time = None

        # Always update the live feed with the frame (which now has overlays).
        ret2, jpeg = cv2.imencode('.jpg', frame)
        if ret2:
            with frame_lock:
                current_frame = jpeg.tobytes()
            print("detection_loop: Updated frame, length:", len(current_frame))
        else:
            print("detection_loop: Failed to encode frame")
        time.sleep(0.1)
    cap.release()


# Start the detection loop in a background thread.
detection_thread = threading.Thread(target=detection_loop, daemon=True)
detection_thread.start()

def gen_video():
    global current_frame
    while True:
        with frame_lock:
            frame_to_send = current_frame
        if frame_to_send is None:
            try:
                with open("static/test.jpg", "rb") as f:
                    fallback_frame = f.read()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + fallback_frame + b'\r\n')
            except Exception as e:
                print("gen_video: Error loading fallback image:", e)
            time.sleep(0.1)
            continue
        try:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_to_send + b'\r\n')
        except Exception as e:
            print("gen_video: Error yielding frame:", e)
        time.sleep(0.1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_video(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/detection_status')
def detection_status():
    return jsonify({"detected": detection_complete, "emotion": detected_emotion})

@app.route('/snapshot')
def snapshot():
    if detected_snapshot is not None:
        return Response(detected_snapshot, mimetype='image/jpeg')
    else:
        return "No snapshot available", 404

# --- Endpoints for Audio and Video for Interaction Phase ---
@app.route('/get_random_audio')
def get_random_audio():
    category = "emotion"
    emotion = detected_emotion
    folder = os.path.join("static", "audio", emotion)
    try:
        files = [f for f in os.listdir(folder) if f.endswith(('.mp3', '.wav'))]
        if not files:
            return jsonify({'error': 'No audio files found'}), 404
        file = random.choice(files)
        audio_url = os.path.join('/static', "audio", emotion, file)
        return jsonify({'audio_url': audio_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_random_video')
def get_random_video():
    folder = os.path.join("static", "video")
    try:
        files = [f for f in os.listdir(folder) if f.endswith(('.mp4', '.webm'))]
        if not files:
            return jsonify({'error': 'No video files found'}), 404
        file = random.choice(files)
        video_url = os.path.join('/static', "video", file)
        return jsonify({'video_url': video_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/restart')
def restart():
    global detection_complete, detected_emotion, detected_snapshot, last_emotion, emotion_start_time
    detection_complete = False
    detected_emotion = "neutral"
    detected_snapshot = None
    last_emotion = None
    emotion_start_time = None
    return jsonify({"status": "restarted"})

if __name__ == '__main__':
    # Disable reloader so globals are shared.
    app.run(host='0.0.0.0', debug=True, use_reloader=False)
