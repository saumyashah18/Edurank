import os
import whisper
from gtts import gTTS
import tempfile
from ..utils.math_normalizer import normalize_math_speech

class VoiceService:
    def __init__(self):
        self.stt_model = None

    def _load_model(self):
        if not self.stt_model:
            print("Loading Whisper model (lazy)...")
            self.stt_model = whisper.load_model("base")
            print("Whisper model loaded.")

    def transcribe(self, audio_path: str) -> str:
        """
        Convert speech to text using Whisper.
        """
        try:
            self._load_model()
            
            # Whisper handles various formats
            result = self.stt_model.transcribe(audio_path)
            text = result["text"].strip()
            
            # Normalize math expressions
            normalized_text = normalize_math_speech(text)
            
            print(f"DEBUG: Transcribed: '{text}' -> Normalized: '{normalized_text}'")
            return normalized_text
        except Exception as e:
            print(f"Error in transcription: {e}")
            return ""

    def synthesize(self, text: str, output_path: str = None) -> str:
        """
        Convert text to speech using gTTS.
        Returns the path to the generated audio file.
        """
        try:
            if not text:
                return None
                
            if not output_path:
                fd, output_path = tempfile.mkstemp(suffix=".mp3")
                os.close(fd)
            
            # gTTS is online-based (Google Translate TTS)
            # For offline, we would use pyttsx3 or piper
            # Using gTTS as requested for simplicity/quality balance
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(output_path)
            
            return output_path
        except Exception as e:
            print(f"Error in synthesis: {e}")
            return None

    def process_audio_file(self, file_path: str) -> str:
        """
        Helper to ensure audio is in a format Whisper likes (ffmpeg required).
        """
        return file_path

# Global instance
voice_service = VoiceService()
