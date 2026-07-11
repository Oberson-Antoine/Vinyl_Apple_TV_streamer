import io
import wave


def pcm_to_wav_bytes(pcm: bytes, *, channels: int, sample_width: int, framerate: int) -> bytes:
    """Wraps raw PCM16 bytes in a minimal WAV container using the stdlib `wave`
    module — no ffmpeg/pydub needed. Used to build the short snippet handed to
    ShazamIO."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(framerate)
        wav_file.writeframes(pcm)
    return buffer.getvalue()
