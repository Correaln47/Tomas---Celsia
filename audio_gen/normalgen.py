import os
import time
import re
from google.oauth2 import service_account
import google.cloud.texttospeech as texttospeech

# -------------------------------
# Configuration and API Settings
# -------------------------------
GOOGLE_CLOUD_TTS_CREDENTIALS_JSON = "api.json"
CLOUD_TTS_VOICE_NAME = "es-US-Wavenet-C"
CLOUD_TTS_AUDIO_ENCODING = texttospeech.AudioEncoding.MP3
CLOUD_TTS_LANGUAGE_CODE = "es-US"
OUTPUT_DIR = "output_audio_exacto"

# ----------------------------------------------------
# TEXTO EXACTO QUE QUIERES CONVERTIR A AUDIO
# ----------------------------------------------------
FRASES_PARA_GENERAR = [
    "¡Hola! Soy Tomas, para poder reconocer tu emoción de forma correcta y compartirte informacion sobre Celsia, posiciónate a 1 metro de distancia alfrente de mi, y mírame a los ojos."
]

# -------------------------------
# API Initialization
# -------------------------------
try:
    tts_credentials = service_account.Credentials.from_service_account_file(GOOGLE_CLOUD_TTS_CREDENTIALS_JSON)
    client_tts = texttospeech.TextToSpeechClient(credentials=tts_credentials)
except Exception as e:
    print(f"Error Crítico: No se pudieron cargar las credenciales desde '{GOOGLE_CLOUD_TTS_CREDENTIALS_JSON}'. Verifica el archivo.")
    print(f"   Detalle: {e}")
    exit()

# -------------------------------
# Helper Functions
# -------------------------------
def sanitize_foldername(text):
    """Sanitize a string to be safe for use as a folder name by taking the first few words."""
    words = re.findall(r'\b\w+\b', text)
    # Une las primeras 4 palabras o menos si la frase es más corta
    num_words = min(len(words), 4)
    safe_name = "_".join(words[:num_words])
    return re.sub(r'[^\w_]', '', safe_name) # Limpieza final por si acaso

def synthesize_text_to_audio(text, output_path):
    """
    Convierte texto a audio, verificando que la respuesta de la API sea válida.
    """
    # Verificación 1: Asegurarse de que el texto no esté vacío.
    if not text.strip():
        print("Advertencia: Se intentó sintetizar un texto vacío. Omitiendo.")
        return

    try:
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

        # Verificación 2: La más importante. Revisa si la API devolvió contenido de audio.
        if response and response.audio_content:
            with open(output_path, "wb") as out_file:
                out_file.write(response.audio_content)
            print(f"Audio guardado correctamente: {output_path}")
        else:
            # Si response.audio_content está vacío, aquí está el problema.
            print(f"Error: La API de Google no devolvió contenido de audio para el texto.")
            print(f"   Texto: '{text[:80]}...'")
            print(f"   Posibles causas: API no habilitada, problemas de facturación o permisos insuficientes en Google Cloud.")

    except Exception as e:
        print(f"Error durante la síntesis de voz: {e}")

# -------------------------------
# Main Processing Function
# -------------------------------
def main():
    """Processes each exact phrase and converts it to an audio file."""
    # Create the base output directory if it doesn't exist.
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # Process each exact phrase from the list
    for index, frase_texto in enumerate(FRASES_PARA_GENERAR, start=1):
        # Create a separate folder for each phrase
        folder_name = sanitize_foldername(frase_texto)
        frase_folder = os.path.join(OUTPUT_DIR, f"frase_{index}_{folder_name}")
        os.makedirs(frase_folder, exist_ok=True)
        
        print(f"\nProcesando frase {index}: '{frase_texto}'")
        
        # Create a unique filename for the audio file
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        audio_filename = f"audio_{index}_{timestamp}.mp3"
        audio_filepath = os.path.join(frase_folder, audio_filename)
        
        # Synthesize the text to an audio file
        synthesize_text_to_audio(frase_texto, audio_filepath)
        
        # Optional: a short delay between requests
        time.sleep(1)

if __name__ == "__main__":
    main()