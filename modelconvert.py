import tensorflow as tf

# Load the pre-trained Keras model
model = tf.keras.models.load_model("emotion_model.h5", compile=False)

# Convert the model to TFLite
converter = tf.lite.TFLiteConverter.from_keras_model(model)
# Optionally, you can set optimization options:
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

# Save the TFLite model to a file
with open("emotion_model.tflite", "wb") as f:
    f.write(tflite_model)

print("Conversion complete! TFLite model saved as emotion_model.tflite")
