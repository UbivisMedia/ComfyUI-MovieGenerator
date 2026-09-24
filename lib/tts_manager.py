"""
lib/tts_manager.py - Voiceover & Narration Engine for MovieGenerator

Provides high-quality non-diegetic speech generation (narrator voiceover, internal monologues)
using edge-tts and ComfyUI Kokoro-ONNX. Supports multi-track audio mixing and leveling.
"""

import os
import sys
import json
import asyncio
import subprocess
import shutil
import tempfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS_DIR = os.path.join(BASE_DIR, "Workflows")

# Available curated voices
VOICES_CATALOG = [
    # German Voices (edge-tts)
    {
        "id": "de-DE-ConradNeural",
        "name": "Conrad (DE - Doku / Trailer)",
        "lang": "de",
        "gender": "male",
        "engine": "edge_tts",
        "desc": "Tiefe, sonore Stimme für Dokumentationen, Film-Trailer und Erzähler."
    },
    {
        "id": "de-DE-KatjaNeural",
        "name": "Katja (DE - Erzählerin)",
        "lang": "de",
        "gender": "female",
        "engine": "edge_tts",
        "desc": "Warme, klare Erzählstimme für Voiceover und Hörbuch."
    },
    {
        "id": "de-DE-KillianNeural",
        "name": "Killian (DE - Dynamisch)",
        "lang": "de",
        "gender": "male",
        "engine": "edge_tts",
        "desc": "Prägnante, dynamische Stimme für Action, Thriller und moderne Szenen."
    },
    {
        "id": "de-DE-AmalaNeural",
        "name": "Amala (DE - Emotional)",
        "lang": "de",
        "gender": "female",
        "engine": "edge_tts",
        "desc": "Sanfte, emotionale Stimme für intime Monologe und ruhige Momente."
    },
    # English Voices (edge-tts)
    {
        "id": "en-US-ChristopherNeural",
        "name": "Christopher (US - Cinematic Storyteller)",
        "lang": "en",
        "gender": "male",
        "engine": "edge_tts",
        "desc": "Authoritative, resonant voice perfect for movie trailers and narration."
    },
    {
        "id": "en-US-JennyNeural",
        "name": "Jenny (US - Warm Narrator)",
        "lang": "en",
        "gender": "female",
        "engine": "edge_tts",
        "desc": "Clear, friendly, and engaging female voice for storytelling."
    },
    {
        "id": "en-GB-RyanNeural",
        "name": "Ryan (UK - British Documentary)",
        "lang": "en",
        "gender": "male",
        "engine": "edge_tts",
        "desc": "Distinguished British male narrator voice."
    },
    {
        "id": "en-GB-SoniaNeural",
        "name": "Sonia (UK - Elegant Narrator)",
        "lang": "en",
        "gender": "female",
        "engine": "edge_tts",
        "desc": "Poised, sophisticated British female narration."
    },
    # Kokoro ONNX Voices (ComfyUI)
    {
        "id": "am_michael",
        "name": "Michael (Kokoro - US Male)",
        "lang": "en",
        "gender": "male",
        "engine": "comfy_kokoro",
        "desc": "Natural, high-fidelity American male voice via local Kokoro ONNX."
    },
    {
        "id": "am_adam",
        "name": "Adam (Kokoro - US Male Deep)",
        "lang": "en",
        "gender": "male",
        "engine": "comfy_kokoro",
        "desc": "Deep, grounded American male voice via local Kokoro ONNX."
    },
    {
        "id": "af_sarah",
        "name": "Sarah (Kokoro - US Female)",
        "lang": "en",
        "gender": "female",
        "engine": "comfy_kokoro",
        "desc": "Clean, natural American female voice via local Kokoro ONNX."
    },
    {
        "id": "af_bella",
        "name": "Bella (Kokoro - US Female Soft)",
        "lang": "en",
        "gender": "female",
        "engine": "comfy_kokoro",
        "desc": "Soft, expressive American female voice via local Kokoro ONNX."
    },
    {
        "id": "bm_george",
        "name": "George (Kokoro - UK Male)",
        "lang": "en",
        "gender": "male",
        "engine": "comfy_kokoro",
        "desc": "Classic British male voice via local Kokoro ONNX."
    },
    {
        "id": "bf_emma",
        "name": "Emma (Kokoro - UK Female)",
        "lang": "en",
        "gender": "female",
        "engine": "comfy_kokoro",
        "desc": "Crisp British female narrator via local Kokoro ONNX."
    }
]


def get_available_voices():
    """Returns the list of configured voices."""
    return VOICES_CATALOG


def get_audio_duration(audio_path):
    """Measures audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 0.0


async def _generate_edge_tts(text, voice, temp_mp3_path):
    """Generates audio file via edge-tts."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(temp_mp3_path)


def generate_voiceover_stem(text, voice="de-DE-ConradNeural", output_wav_path=None, speed=1.0):
    """
    Synthesizes text into a clean 44.1kHz 16-bit stereo WAV voiceover stem.
    Returns (success: bool, path: str, duration: float, error: str).
    """
    if not text or not text.strip():
        return False, None, 0.0, "Empty voiceover text"

    clean_text = text.strip()
    voice_info = next((v for v in VOICES_CATALOG if v["id"] == voice), None)
    engine = voice_info["engine"] if voice_info else ("comfy_kokoro" if voice.startswith(("af_", "am_", "bf_", "bm_")) else "edge_tts")

    target_wav = output_wav_path
    if not target_wav:
        fd, target_wav = tempfile.mkstemp(suffix=".wav", prefix="vo_")
        os.close(fd)

    os.makedirs(os.path.dirname(os.path.abspath(target_wav)), exist_ok=True)

    # 1. ComfyUI Kokoro ONNX generation
    if engine == "comfy_kokoro":
        try:
            from lib.comfy_manager import (
                queue_prompt,
                get_history,
                get_image,
                get_server_address
            )
            wf_path = os.path.join(WORKFLOWS_DIR, "workflow_tts_kokoro.json")
            if not os.path.exists(wf_path):
                raise FileNotFoundError(f"Missing {wf_path}")

            with open(wf_path, "r", encoding="utf-8") as f:
                wf = json.load(f)

            # Update Kokoro TTS node
            if "1" in wf and "inputs" in wf["1"]:
                wf["1"]["inputs"]["text"] = clean_text
                wf["1"]["inputs"]["speaker"] = voice

            res = queue_prompt(wf, server_address=get_server_address())
            prompt_id = res.get("prompt_id")
            if not prompt_id:
                raise RuntimeError("Failed to queue Kokoro TTS prompt in ComfyUI")

            # Poll for completion
            import time
            max_wait = 45
            start_time = time.time()
            audio_bytes = None
            raw_filename = None

            while time.time() - start_time < max_wait:
                hist = get_history(prompt_id, server_address=get_server_address())
                if prompt_id in hist:
                    outputs = hist[prompt_id].get("outputs", {})
                    for nid in outputs:
                        if "audio" in outputs[nid]:
                            alist = outputs[nid]["audio"]
                            if alist:
                                ainfo = alist[0]
                                audio_bytes = get_image(
                                    ainfo["filename"],
                                    ainfo.get("subfolder", ""),
                                    ainfo.get("type", "output"),
                                    server_address=get_server_address()
                                )
                                raw_filename = ainfo["filename"]
                                break
                    if audio_bytes:
                        break
                time.sleep(1.0)

            if not audio_bytes:
                raise RuntimeError("Kokoro TTS ComfyUI did not return audio in time")

            # Write temp audio then convert to target wav with standardized sample rate
            temp_raw = target_wav + ".raw"
            with open(temp_raw, "wb") as rf:
                rf.write(audio_bytes)

            cmd = [
                "ffmpeg", "-y",
                "-i", temp_raw,
                "-ar", "44100",
                "-ac", "2",
                target_wav
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            if os.path.exists(temp_raw):
                os.remove(temp_raw)

            dur = get_audio_duration(target_wav)
            return True, target_wav, dur, None

        except Exception as e:
            # Fallback to edge_tts if Kokoro fails
            print(f"⚠️ Kokoro TTS via ComfyUI failed: {e}. Falling back to edge-tts.")
            fallback_voice = "en-US-ChristopherNeural" if "en" in voice else "de-DE-ConradNeural"
            return generate_voiceover_stem(clean_text, voice=fallback_voice, output_wav_path=target_wav, speed=speed)

    # 2. edge-tts generation (default / fallback)
    temp_mp3 = target_wav + ".mp3"
    try:
        asyncio.run(_generate_edge_tts(clean_text, voice, temp_mp3))

        # Convert to pristine 44.1kHz stereo WAV
        cmd = [
            "ffmpeg", "-y",
            "-i", temp_mp3,
            "-ar", "44100",
            "-ac", "2",
            target_wav
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        if os.path.exists(temp_mp3):
            os.remove(temp_mp3)

        dur = get_audio_duration(target_wav)
        return True, target_wav, dur, None
    except Exception as e:
        if os.path.exists(temp_mp3):
            try:
                os.remove(temp_mp3)
            except Exception:
                pass
        return False, None, 0.0, str(e)


def mix_voiceover_into_scene_clip(scene_video_path, vo_audio_path, output_video_path, vo_volume=1.0, foley_volume=0.85):
    """
    Mixes voiceover narration audio stem into an existing scene video clip.
    If scene has existing production audio, combines them cleanly with voiceover prominence.
    If scene has no audio, adds the voiceover as the sole audio track.
    Returns True on success, False otherwise.
    """
    if not os.path.exists(scene_video_path) or not os.path.exists(vo_audio_path):
        return False

    # Check if video has an audio stream
    has_audio = False
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            scene_video_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        has_audio = "audio" in res.stdout
    except Exception:
        has_audio = False

    vo_vol = max(0.1, min(2.0, float(vo_volume)))
    foley_vol = max(0.1, min(1.5, float(foley_volume)))

    if has_audio:
        filter_complex = (
            f"[0:a]volume={foley_vol:.2f},aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[prod];"
            f"[1:a]volume={vo_vol:.2f},aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[vo];"
            f"[prod][vo]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", scene_video_path,
            "-i", vo_audio_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "256k",
            output_video_path
        ]
    else:
        filter_complex = f"[1:a]volume={vo_vol:.2f},aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[aout]"
        cmd = [
            "ffmpeg", "-y",
            "-i", scene_video_path,
            "-i", vo_audio_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "256k",
            "-shortest",
            output_video_path
        ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except Exception as e:
        print(f"❌ Failed to mix voiceover into scene clip: {e}")
        return False
