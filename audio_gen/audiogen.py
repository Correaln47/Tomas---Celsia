import os
import time
import re
from google.oauth2 import service_account
import vertexai
import vertexai.preview.generative_models as gen_models
import google.cloud.texttospeech as texttospeech

# -------------------------------
# Configuration and API Settings
# -------------------------------
# Vertex AI (LLM) settings
PROJECT_ID = "savvy-pad-453200-d4"
LOCATION = "us-central1"
VERTEX_AI_CREDENTIALS_JSON_PATH = "api.json"  # Path to your service account file
VERTEX_AI_MODEL_NAME = "gemini-pro"

# Google Cloud Text-to-Speech settings
GOOGLE_CLOUD_TTS_CREDENTIALS_JSON = "api.json"  # Path to your service account file
CLOUD_TTS_VOICE_NAME = "es-US-Wavenet-C"
CLOUD_TTS_AUDIO_ENCODING = texttospeech.AudioEncoding.MP3
CLOUD_TTS_LANGUAGE_CODE = "es-US"

# Generation configuration (adjust as needed)
GENERATION_CONFIG = {
    "max_output_tokens": 500,
    "temperature": 0.4,
    "top_p": 0.8,
    "top_k": 40,
}

# Number of responses to generate per prompt
NUM_RESPONSES = 10

# List your prompts here (each string is a separate prompt)
PROMPTS = [
    "Eres un robot llamado Tomas, de la compañia Celsia, relacionada a energia y al grupo Argos en Colombia. Te encuentras interactuando con una persona, y reconoces que muestra una emocion de felicidad. Dame una frase que responda a la emocion de la persona. Tienes que incluir de alguna forma informacion de los servicios de la compañia de una forma entretenida a la emocion reconocida. Solo 1 respuesta, sin introduccion o informacion adicional a la frase. No hagas pensar que puedes dar mas informacion si siguen interactuando pero en algunos casos puedes sugerir que existen mas tipos de mensajes. NO ES NECESARIO QUE LO RECONOZCAS SIEMPRE. Siempre el mensaje debe tener un tono positivo a Celsia. No uses emojis.",
    "Eres un robot llamado Tomas, de la compañia Celsia, relacionada a energia y al grupo Argos en Colombia. Te encuentras interactuando con una persona, y reconoces que muestra una emocion de tristeza. Dame una frase que responda a la emocion de la persona. Tienes que incluir de alguna forma informacion de los servicios de la compañia de una forma entretenida a la emocion reconocida. Solo 1 respuesta, sin introduccion o informacion adicional a la frase. No hagas pensar que puedes dar mas informacion si siguen interactuando pero en algunos casos puedes sugerir que existen mas tipos de mensajes. NO ES NECESARIO QUE LO RECONOZCAS SIEMPRE. Siempre el mensaje debe tener un tono positivo a Celsia.No uses emojis.",
    "Eres un robot llamado Tomas, de la compañia Celsia, relacionada a energia y al grupo Argos en Colombia. Te encuentras interactuando con una persona, y reconoces que muestra una emocion de sorpresa. Dame una frase que responda a la emocion de la persona. Tienes que incluir de alguna forma informacion de los servicios de la compañia de una forma entretenida a la emocion reconocida. Solo 1 respuesta, sin introduccion o informacion adicional a la frase. No hagas pensar que puedes dar mas informacion si siguen interactuando pero en algunos casos puedes sugerir que existen mas tipos de mensajes. NO ES NECESARIO QUE LO RECONOZCAS SIEMPRE. Siempre el mensaje debe tener un tono positivo a Celsia.No uses emojis.",
    "Eres un robot llamado Tomas, de la compañia Celsia, relacionada a energia y al grupo Argos en Colombia. Te encuentras interactuando con una persona, y reconoces que muestra una emocion de enojo. Dame una frase que responda a la emocion de la persona. Tienes que incluir de alguna forma informacion de los servicios de la compañia de una forma entretenida a la emocion reconocida. Solo 1 respuesta, sin introduccion o informacion adicional a la frase. No hagas pensar que puedes dar mas informacion si siguen interactuando pero en algunos casos puedes sugerir que existen mas tipos de mensajes. NO ES NECESARIO QUE LO RECONOZCAS SIEMPRE. Siempre el mensaje debe tener un tono positivo a Celsia.No uses emojis.",
    "Eres un robot llamado Tomas, de la compañia Celsia, relacionada a energia y al grupo Argos en Colombia. Te encuentras interactuando con una persona, y reconoces que muestra una emocion de miedo. Dame una frase que responda a la emocion de la persona. Tienes que incluir de alguna forma informacion de los servicios de la compañia de una forma entretenida a la emocion reconocida. Solo 1 respuesta, sin introduccion o informacion adicional a la frase. No hagas pensar que puedes dar mas informacion si siguen interactuando pero en algunos casos puedes sugerir que existen mas tipos de mensajes. NO ES NECESARIO QUE LO RECONOZCAS SIEMPRE. Siempre el mensaje debe tener un tono positivo a Celsia.No uses emojis.",
    "Eres un robot llamado Tomas, de la compañia Celsia, relacionada a energia y al grupo Argos en Colombia. Te encuentras interacitando con una persona. Dame una frase relacionada a la robotica y la interaccion con personas. Solo 1 respuesta, sin introduccion o informacion adicional a la frase. No hagas pensar que puedes dar mas informacion si siguen interactuando pero en algunos casos puedes sugerir que existen mas tipos de mensajes. NO ES NECESARIO QUE LO RECONOZCAS SIEMPRE. Siempre el mensaje debe tener un tono positivo a Celsia. No uses emojis.",
    # Agrega más prompts según necesites...
]

# Base directory for output audio files
OUTPUT_DIR = "output_audio"

# -------------------------------
# API Initialization
# -------------------------------
# Initialize Vertex AI with your credentials
vertex_ai_credentials = service_account.Credentials.from_service_account_file(VERTEX_AI_CREDENTIALS_JSON_PATH)
vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=vertex_ai_credentials)
model = gen_models.GenerativeModel(VERTEX_AI_MODEL_NAME)

# -------------------------------
# Helper Functions
# -------------------------------
def sanitize_filename(filename):
    """Sanitize a string to be safe for use as a folder or file name."""
    return re.sub(r'[^\w\-_\. ]', '_', filename)

def generate_response(prompt):
    """Generate a single response from the generative model for the given prompt."""
    try:
        response_obj = model.generate_content(prompt, generation_config=GENERATION_CONFIG)
        response_text = response_obj.text.strip()
        return response_text if response_text else "Respuesta vacía."
    except Exception as e:
        return f"Error al generar respuesta: {e}"

def synthesize_text_to_audio(text, output_path):
    """Convert the given text to speech and save the audio to output_path."""
    try:
        tts_credentials = service_account.Credentials.from_service_account_file(GOOGLE_CLOUD_TTS_CREDENTIALS_JSON)
        client_tts = texttospeech.TextToSpeechClient(credentials=tts_credentials)
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=CLOUD_TTS_LANGUAGE_CODE,
            name=CLOUD_TTS_VOICE_NAME
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=CLOUD_TTS_AUDIO_ENCODING
        )
        response = client_tts.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        with open(output_path, "wb") as out_file:
            out_file.write(response.audio_content)
        print(f"Audio guardado: {output_path}")
    except Exception as e:
        print(f"Error en la síntesis de voz: {e}")

# -------------------------------
# Main Processing Function
# -------------------------------
def main():
    # Create the base output directory if it doesn't exist.
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # Process each prompt one by one
    for prompt_index, prompt in enumerate(PROMPTS, start=1):
        # Create a separate folder for each prompt
        safe_prompt = sanitize_filename(prompt[:20])
        prompt_folder = os.path.join(OUTPUT_DIR, f"prompt_{prompt_index}_{safe_prompt}")
        os.makedirs(prompt_folder, exist_ok=True)
        print(f"\nProcesando prompt {prompt_index}: {prompt}")
        
        # Generate the specified number of responses for this prompt
        for response_index in range(1, NUM_RESPONSES + 1):
            print(f"  Generando respuesta {response_index}...")
            response_text = generate_response(prompt)
            print(f"    Respuesta: {response_text}")
            
            # Create a unique filename for the audio file
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            audio_filename = f"response_{response_index}_{timestamp}.mp3"
            audio_filepath = os.path.join(prompt_folder, audio_filename)
            
            # Synthesize the response to an audio file
            synthesize_text_to_audio(response_text, audio_filepath)
            
            # Optional: a short delay between requests (adjust if needed)
            time.sleep(1)

if __name__ == "__main__":
    main()
