import os
import tempfile
import requests
from gtts import gTTS
import pyttsx3
from ..utils.math_normalizer import normalize_math_speech

# Support for multiple STT options
try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

class VoiceService:
    def __init__(self):
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.stt_lang = os.getenv("STT_LANGUAGE", "en-US")
        self.tts_lang = os.getenv("TTS_LANGUAGE", "en")
        self.whisper_model_name = os.getenv("WHISPER_MODEL", "base")
        
        self.groq_client = None
        self._local_whisper_model = None

        if self.groq_key and Groq:
            try:
                self.groq_client = Groq(api_key=self.groq_key)
                print("[VoiceService] STT Mode: Groq (Cloud)")
            except Exception as e:
                print(f"[VoiceService] Error initializing Groq: {e}")
                self.groq_client = None

        if not self.groq_client:
            if WhisperModel:
                print(f"[VoiceService] STT Mode: faster-whisper (Local) | Model: {self.whisper_model_name}")
            else:
                print("[VoiceService] WARNING: No STT engine available. Install 'groq' or 'faster-whisper'.")

    def _get_local_whisper(self):
        """Lazily load the faster-whisper model."""
        if not self._local_whisper_model and WhisperModel:
            print(f"Loading faster-whisper model: {self.whisper_model_name}...")
            # Using CPU by default as requested
            self._local_whisper_model = WhisperModel(
                self.whisper_model_name,
                device="cpu",
                compute_type="int8"
            )
        return self._local_whisper_model

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe audio to text with math normalization.
        Uses Groq if available, otherwise falls back to faster-whisper.
        """
        try:
            text = ""
            if self.groq_client:
                # Option A: Groq (fast, cloud)
                with open(audio_path, "rb") as f:
                    result = self.groq_client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=f,
                        language=self.stt_lang.split('-')[0] # Groq prefers ISO 639-1
                    )
                    text = result.text
            elif WhisperModel:
                # Option B: faster-whisper (local)
                model = self._get_local_whisper()
                segments, _ = model.transcribe(
                    audio_path,
                    language=self.stt_lang.split('-')[0]
                )
                text = " ".join(s.text.strip() for s in segments)
            
            if not text:
                return ""
                
            normalized = normalize_math_speech(text)
            print(f"DEBUG STT: '{text}' -> '{normalized}'")
            return normalized
        except Exception as e:
            print(f"Error in transcription: {e}")
            return ""

    def synthesize(self, text: str) -> str:
        """
        Convert text to speech with offline fallback.
        gTTS is primary, pyttsx3 is fallback.
        """
        if not text:
            return ""

        # Use an appropriate language setting
        lang = os.getenv("TTS_LANGUAGE", "en")
        
        try:
            # Option A: gTTS (Standard cloud-based)
            tts = gTTS(text=text, lang=lang)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            tmp_path = tmp.name
            tmp.close()
            tts.save(tmp_path)
            return tmp_path
        except Exception as e:
            print(f"gTTS failed, falling back to pyttsx3: {e}")
            try:
                # Option B: pyttsx3 (Standard offline fallback)
                engine = pyttsx3.init()
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                tmp_path = tmp.name
                tmp.close()
                engine.save_to_file(text, tmp_path)
                engine.runAndWait()
                return tmp_path
            except Exception as e2:
                print(f"Critical Error: Both TTS engines failed: {e2}")
                return ""

    def process_audio_file(self, file_path: str) -> str:
        """
        Placeholder for audio pre-processing logic (WebM -> WAV conversion).
        Keep existing entry point as requested.
        """
        return file_path

# Global instance
voice_service = VoiceService()
