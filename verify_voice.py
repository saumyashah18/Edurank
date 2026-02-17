
import sys
import os

print("Verifying Voice Chat Dependencies...")

try:
    print("1. Checking OpenAI Whisper...")
    import whisper
    print("   ✅ Whisper imported successfully")
except ImportError as e:
    print(f"   ❌ Whisper import failed: {e}")

try:
    print("2. Checking gTTS...")
    from gtts import gTTS
    print("   ✅ gTTS imported successfully")
except ImportError as e:
    print(f"   ❌ gTTS import failed: {e}")

try:
    print("3. Checking Pydub...")
    from pydub import AudioSegment
    print("   ✅ Pydub imported successfully")
except ImportError as e:
    print(f"   ❌ Pydub import failed: {e}")

try:
    print("4. Checking FFmpeg (via pydub)...")
    from pydub.utils import which
    if which("ffmpeg"):
         print(f"   ✅ FFmpeg found at: {which('ffmpeg')}")
    else:
         print("   ❌ FFmpeg NOT found in PATH")
except ImportError:
    pass

try:
    print("5. Checking Math Normalizer...")
    from backend.utils.math_normalizer import normalize_math_speech
    res = normalize_math_speech("x squared")
    if res == "x²":
        print(f"   ✅ Math Normalizer working: 'x squared' -> '{res}'")
    else:
        print(f"   ❌ Math Normalizer error: Expected 'x²' got '{res}'")
except ImportError as e:
    print(f"   ❌ Math Normalizer import failed: {e}")
    
print("\nVerification Complete.")
