import wave
import io

from app.audio.wav import pcm_to_wav_bytes


def test_pcm_to_wav_bytes_roundtrips_params_and_data():
    pcm = b"\x01\x00\x02\x00" * 100  # 100 frames of 2ch S16_LE
    wav_bytes = pcm_to_wav_bytes(pcm, channels=2, sample_width=2, framerate=44100)

    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        assert wav_file.getnchannels() == 2
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 44100
        assert wav_file.readframes(wav_file.getnframes()) == pcm
