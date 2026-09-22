import json
import urllib.request
import time
import random
import sys
import os
import re
import shutil
import subprocess
import io
from PIL import Image, PngImagePlugin

# Force UTF-8 encoding in Windows terminal (prevents UnicodeEncodeErrors with emojis)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from localization import t, init_localization, set_language, get_current_language
from catalog_builder import build_or_update_catalog
from version import __version__

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRESETS_DIR = os.path.join(BASE_DIR, "Presets")
WORKFLOWS_DIR = os.path.join(BASE_DIR, "Workflows")
PROJECTS_DIR = os.path.join(BASE_DIR, "Projects")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "language": "auto",
    "export_webm": True,
    "comfyui": {
        "server_address": "127.0.0.1:8188",
        "models_dir": "",
        "models_search_paths": [
            "../ComfyUI/models",
            "../ComfyUI_windows_portable/ComfyUI/models"
        ]
    },
    "minimax_i2v": {
        "unet_name": "MiniMax H3\\base model\\minimaxH3INT8INT4_flREF2VAPruned.safetensors",
        "turbo_lora": "MiniMax H3\\tool\\minimax_h3_fl2v_lightx2v_turbo_8step_v1.0_resized_avg_rank_24_bf16.safetensors",
        "turbo_strength": 1.0,
        "steps": 8,
        "clip_name": "minimaxH3INT8INT4_fl2vaINT8Pruned_txt.safetensors",
        "video_vae_name": "minimax_h3_video_vae_int8_convrot.safetensors",
        "audio_vae_name": "minimax_h3_audio_vae_fp32.safetensors"
    },
    "music_studio": {
        "enabled": False,
        "checkpoint": "Other\\base model\\ace_step_v1_3.5b.safetensors",
        "steps": 40,
        "cfg": 4.0,
        "volume": 0.20,
        "ducking": True
    },
    "lm_studio": {
        "url": "http://127.0.0.1:1234/v1/chat/completions",
        "model_name": "gemma-4-e4b-uncensored-hauhaucs-aggressive",
        "temperature": 0.7
    }
}

def find_music_checkpoints(models_dir):
    """Finds audio/music checkpoints (e.g. ACE-Step, Stable Audio) in models/checkpoints."""
    found = []
    if not models_dir or not os.path.exists(models_dir):
        return found
    base = os.path.join(models_dir, "checkpoints")
    if not os.path.exists(base):
        return found
    for root, _, files in os.walk(base):
        for f in files:
            if f.endswith((".safetensors", ".gguf", ".sft", ".ckpt")):
                rel_p = os.path.relpath(os.path.join(root, f), base)
                rp_lower = rel_p.lower()
                if any(kw in rp_lower for kw in ["ace", "music", "audio", "sound"]):
                    if rel_p not in found:
                        found.append(rel_p)
    return sorted(found)

def get_video_duration(video_path):
    """Returns duration of video in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return None

def has_audio_stream(video_path):
    """Returns True if the video file contains an audio stream."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return "audio" in res.stdout
    except Exception:
        return False

def mix_soundtrack_into_movie(video_path, audio_path, output_path, volume=0.20, ducking=True, ducking_threshold=0.08):
    """Mixes generated background music into the movie without replacing or drowning speech/foley."""
    vol = max(0.05, min(1.0, float(volume)))
    if ducking:
        filter_complex = (
            f"[1:a]volume={vol:.2f}[bgm];"
            f"[bgm][0:a]sidechaincompress=threshold={ducking_threshold:.2f}:ratio=4:attack=150:release=800[ducked];"
            f"[0:a][ducked]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
    else:
        filter_complex = (
            f"[1:a]volume={vol:.2f}[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "320k",
        output_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except Exception as e:
        fallback_cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "320k",
            output_path
        ]
        try:
            subprocess.run(fallback_cmd, check=True, capture_output=True, text=True)
            return True
        except Exception as fe:
            print(f"   ❌ FFmpeg Audio-Mix Fehler: {fe}")
            return False

def generate_movie_soundtrack(wf_music_template, prompt_tags, duration_seconds, checkpoint=None, steps=40, cfg=4.0, seed=None):
    """Executes ComfyUI audio workflow to generate an instrumental soundtrack."""
    wf = json.loads(json.dumps(wf_music_template))
    
    if checkpoint and "40" in wf and "inputs" in wf["40"]:
        wf["40"]["inputs"]["ckpt_name"] = checkpoint
        
    dur = max(5.0, min(360.0, float(duration_seconds)))
    if "17" in wf and "inputs" in wf["17"]:
        wf["17"]["inputs"]["seconds"] = round(dur, 1)
        
    if "14" in wf and "inputs" in wf["14"]:
        wf["14"]["inputs"]["tags"] = prompt_tags
        wf["14"]["inputs"]["lyrics"] = "[instrumental]"
        
    audio_seed = seed if seed is not None else random.randint(1, 999999999999999)
    if "3" in wf and "inputs" in wf["3"]:
        wf["3"]["inputs"]["seed"] = audio_seed
        wf["3"]["inputs"]["steps"] = int(steps)
        wf["3"]["inputs"]["cfg"] = float(cfg)
        
    res = queue_prompt(wf)
    prompt_id = res['prompt_id']
    
    while True:
        history = get_history(prompt_id)
        if prompt_id in history:
            prompt_info = history[prompt_id]
            status_info = prompt_info.get("status", {})
            if status_info.get("status_str") == "error":
                err_msg = "Unknown ComfyUI error"
                for msg in status_info.get("messages", []):
                    if msg[0] == "execution_error":
                        err_msg = msg[1].get("exception_message", str(msg[1]))
                raise RuntimeError(f"ComfyUI Music Error: {err_msg}")
                
            outputs = prompt_info.get('outputs', {})
            for node_id in outputs:
                if 'audio' in outputs[node_id]:
                    audio_list = outputs[node_id]['audio']
                    if audio_list:
                        aud_info = audio_list[0]
                        aud_data = get_image(aud_info['filename'], aud_info['subfolder'], aud_info['type'])
                        return aud_data, aud_info['filename']
            break
        time.sleep(2)
    return None, None

def build_scenes_timeline(scenes):
    """Builds a chronological scene timeline with timestamps for music scoring."""
    if not scenes or not isinstance(scenes, list):
        return "", 0
    lines = []
    current_sec = 0.0
    for idx, s in enumerate(scenes, start=1):
        if not isinstance(s, dict):
            continue
        try:
            dur = float(s.get("duration", s.get("dauer", 6)) or 6)
        except (ValueError, TypeError):
            dur = 6.0
        
        start_min, start_sec = divmod(int(current_sec), 60)
        end_time = current_sec + dur
        end_min, end_sec = divmod(int(end_time), 60)
        time_tag = f"[{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}]"
        
        seq = (s.get("sequence") or s.get("sequenz") or f"Szene {idx}").strip()
        loc = (s.get("location") or s.get("ort") or "").strip()
        idea = (s.get("idea") or s.get("prompt") or s.get("handlung") or "").strip()
        # Clean idea from tags like <Subject 1>, {variables} etc.
        clean_idea = re.sub(r'<Subject \d+>\s*(?:\([^)]*\))?', '', idea)
        clean_idea = re.sub(r'\{[^}]+\}', '', clean_idea)
        clean_idea = re.sub(r'\s+', ' ', clean_idea).strip()
        if len(clean_idea) > 100:
            clean_idea = clean_idea[:97] + "..."
            
        soundscape = (s.get("soundscape") or s.get("geraeusche") or "").strip()
        
        entry = f"- {time_tag} Szene {idx} ({seq}"
        if loc:
            entry += f", {loc}"
        entry += f"): {clean_idea}"
        if soundscape:
            entry += f" [SFX: {soundscape}]"
        lines.append(entry)
        current_sec = end_time

    return "\n".join(lines), int(current_sec)

def ask_lm_studio_music_tags(title, description, scenes=None, url=None, model=None):
    """Generates chronologically synchronized musical progression tags via LM Studio."""
    lms_cfg = SETTINGS.get("lm_studio", {})
    endpoint = url or lms_cfg.get("url", "http://127.0.0.1:1234/v1/chat/completions")
    model_name = model or lms_cfg.get("model_name", "")
    
    timeline_str, total_sec = build_scenes_timeline(scenes) if scenes else ("", 0)
    
    if timeline_str and len(scenes) > 1:
        system_prompt = (
            "You are an expert cinematic film composer.\n"
            "Compose a time-synchronized, progression-based instrumental soundtrack prompt for AI music generation (ACE-Step).\n"
            "Match the narrative progression and emotional arc of the scenes using timestamp segments.\n"
            "Strictly instrumental (no vocals, no singing).\n"
            "Format: Output 3-5 comma-separated segments with timestamps matching the timeline, e.g.:\n"
            "[00:00-00:07] intro motif with light rhythm, [00:07-00:19] playful swelling melody, [00:19-00:29] emotional cello climax, [00:29-00:35] mellow outro, instrumental\n"
            "Output ONLY the prompt text. No explanations."
        )
        user_prompt = (
            f"Film Title: {title}\n"
            f"Story Premise: {description}\n"
            f"Total Duration: {total_sec}s\n"
            f"Scene Timeline:\n{timeline_str}"
        )
        max_tokens = 200
    else:
        system_prompt = (
            "You are an expert cinematic film composer and soundtrack supervisor.\n"
            "Generate a comma-separated list of 5-8 English descriptive tags defining the musical genre, instruments, tempo, and mood for a cinematic instrumental background soundtrack.\n"
            "The soundtrack MUST be strictly instrumental (no singing, no lyrics, no vocals).\n"
            "Output ONLY the comma-separated tags (e.g. 'cinematic acoustic guitar, warm pads, gentle ocean breeze, light percussion, romantic chill vibe, instrumental'). No other text."
        )
        user_prompt = f"Movie Title: {title}\nStory Premise: {description}"
        max_tokens = 120
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.5,
        "max_tokens": max_tokens
    }
    
    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            msg = data['choices'][0]['message']
            raw_text = (msg.get('content') or msg.get('reasoning_content') or '').strip()
            tags = re.sub(r'[\'"`*]', '', raw_text).strip()
            if "prompt:" in tags.lower():
                tags = tags.split(":", 1)[1].strip()
            if not tags:
                raise ValueError("Empty response from LM Studio")
            if "instrumental" not in tags.lower():
                tags += ", instrumental"
            return tags
    except Exception as e:
        print(f"⚠️ LM Studio Music Tags Warning: {e}")
        if timeline_str:
            return f"[00:00-00:07] warm acoustic guitar, soft ocean pads, [00:07-00:19] joyful strings, light percussion, [00:19-{total_sec:02d}] emotional climax, gentle sunset resolution, instrumental"
        return "cinematic ambient soundtrack, acoustic guitar, warm pads, gentle tempo, emotional, instrumental"

def find_minimax_unets(models_dir):
    """Finds Minimax diffusion models in models/diffusion_models and models/unet."""
    found = []
    if not models_dir or not os.path.exists(models_dir):
        return found
    for sub in ["diffusion_models", "unet"]:
        base = os.path.join(models_dir, sub)
        if not os.path.exists(base):
            continue
        for root, _, files in os.walk(base):
            for f in files:
                if f.endswith((".safetensors", ".gguf", ".sft", ".pt")):
                    rel_p = os.path.relpath(os.path.join(root, f), base)
                    rp_lower = rel_p.lower()
                    if ("minimax" in rp_lower or "h3" in rp_lower) and "music" not in rp_lower:
                        if rel_p not in found:
                            found.append(rel_p)
    return sorted(found)

def find_minimax_turbo_loras(models_dir):
    """Finds Minimax Turbo/LightX2V LoRAs in models/loras."""
    found = []
    if not models_dir or not os.path.exists(models_dir):
        return found
    base = os.path.join(models_dir, "loras")
    if not os.path.exists(base):
        return found
    for root, _, files in os.walk(base):
        for f in files:
            if f.endswith((".safetensors", ".gguf", ".sft", ".pt")):
                rel_p = os.path.relpath(os.path.join(root, f), base)
                rp_lower = rel_p.lower()
                if "minimax" in rp_lower and any(kw in rp_lower for kw in ["turbo", "lightx2v", "taomate"]):
                    if rel_p not in found:
                        found.append(rel_p)
    return sorted(found)

def detect_steps_from_lora_name(lora_name, default=8):
    """Heuristically detects recommended step count from LoRA filename."""
    if not lora_name:
        return default
    m = re.search(r'(\d+)\s*step', lora_name, re.IGNORECASE)
    if m:
        try:
            val = int(m.group(1))
            if 1 <= val <= 50:
                return val
        except ValueError:
            pass
    if "taomate" in lora_name.lower():
        return 3
    if "4step" in lora_name.lower():
        return 4
    if "8step" in lora_name.lower():
        return 8
    return default

def configure_minimax_interactive(models_dir=None, current_cfg=None):
    """Interactively guides the user through selecting Minimax diffusion model, Turbo LoRA, and steps."""
    if not models_dir:
        models_dir = get_comfy_models_dir()
    
    current_cfg = current_cfg or {}
    cur_unet = current_cfg.get("unet_name", "MiniMax H3\\base model\\minimaxH3INT8INT4_flREF2VAPruned.safetensors")
    cur_turbo = current_cfg.get("turbo_lora", "MiniMax H3\\tool\\minimax_h3_fl2v_lightx2v_turbo_8step_v1.0_resized_avg_rank_24_bf16.safetensors")
    cur_steps = current_cfg.get("steps", 8)
    cur_strength = current_cfg.get("turbo_strength", 1.0)

    print(t("wizard_minimax_header"))
    
    # 1. UNET / Diffusion Model selection
    unets = find_minimax_unets(models_dir)
    chosen_unet = cur_unet
    if unets:
        print(t("wizard_minimax_unets_found"))
        default_idx = 1
        for idx, u in enumerate(unets, 1):
            marker = ""
            if u == cur_unet or os.path.basename(u) == os.path.basename(cur_unet):
                default_idx = idx
                marker = " [aktiv / current]"
            print(f"     [{idx}] {u}{marker}")
        try:
            choice = input(t("wizard_minimax_select_unet", count=len(unets), default=unets[default_idx-1], default_idx=default_idx)).strip()
        except (EOFError, KeyboardInterrupt):
            choice = ""
        if choice.isdigit() and 1 <= int(choice) <= len(unets):
            chosen_unet = unets[int(choice) - 1]
        elif choice in unets:
            chosen_unet = choice
        elif not choice:
            chosen_unet = unets[default_idx - 1]
        else:
            chosen_unet = choice
    else:
        try:
            choice = input(t("wizard_minimax_unet_manual", default=cur_unet)).strip()
        except (EOFError, KeyboardInterrupt):
            choice = ""
        chosen_unet = choice if choice else cur_unet

    # 2. Turbo LoRA selection
    loras = find_minimax_turbo_loras(models_dir)
    chosen_turbo = cur_turbo
    if loras:
        print(t("wizard_minimax_loras_found"))
        default_idx = 1
        for idx, l in enumerate(loras, 1):
            marker = ""
            if l == cur_turbo or os.path.basename(l) == os.path.basename(cur_turbo):
                default_idx = idx
                marker = " [aktiv / current]"
            det_steps = detect_steps_from_lora_name(l)
            print(f"     [{idx}] {l} ({det_steps} Steps){marker}")
        try:
            choice = input(t("wizard_minimax_select_lora", count=len(loras), default=loras[default_idx-1], default_idx=default_idx)).strip()
        except (EOFError, KeyboardInterrupt):
            choice = ""
        if choice.isdigit() and 1 <= int(choice) <= len(loras):
            chosen_turbo = loras[int(choice) - 1]
        elif choice in loras:
            chosen_turbo = choice
        elif not choice:
            chosen_turbo = loras[default_idx - 1]
        else:
            chosen_turbo = choice
    else:
        try:
            choice = input(t("wizard_minimax_lora_manual", default=cur_turbo)).strip()
        except (EOFError, KeyboardInterrupt):
            choice = ""
        chosen_turbo = choice if choice else cur_turbo

    # 3. Sampling Steps
    auto_steps = detect_steps_from_lora_name(chosen_turbo, default=cur_steps)
    try:
        steps_input = input(t("wizard_minimax_steps_prompt", default=auto_steps)).strip()
    except (EOFError, KeyboardInterrupt):
        steps_input = ""
    chosen_steps = int(steps_input) if steps_input.isdigit() and 1 <= int(steps_input) <= 50 else auto_steps

    # 4. Turbo LoRA Strength
    try:
        strength_input = input(t("wizard_minimax_strength_prompt", default=cur_strength)).strip()
    except (EOFError, KeyboardInterrupt):
        strength_input = ""
    try:
        chosen_strength = float(strength_input) if strength_input else cur_strength
    except ValueError:
        chosen_strength = cur_strength

    result = {
        "unet_name": chosen_unet,
        "turbo_lora": chosen_turbo,
        "turbo_strength": chosen_strength,
        "steps": chosen_steps,
        "clip_name": current_cfg.get("clip_name", "minimaxH3INT8INT4_fl2vaINT8Pruned_txt.safetensors"),
        "video_vae_name": current_cfg.get("video_vae_name", "minimax_h3_video_vae_int8_convrot.safetensors"),
        "audio_vae_name": current_cfg.get("audio_vae_name", "minimax_h3_audio_vae_fp32.safetensors")
    }
    return result

def fetch_lm_studio_models(api_url):
    """Attempts to retrieve available models from LM Studio /v1/models."""
    try:
        m = re.match(r'^(https?://[^/]+(?:/v1)?)', api_url)
        if m:
            base_prefix = m.group(1)
            if not base_prefix.endswith('/v1'):
                models_url = f"{base_prefix}/v1/models"
            else:
                models_url = f"{base_prefix}/models"
        else:
            models_url = "http://127.0.0.1:1234/v1/models"

        req = urllib.request.Request(models_url, headers={"User-Agent": "MovieGenerator"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models_list = []
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    mid = item.get("id")
                    if mid and mid not in models_list:
                        models_list.append(mid)
            return models_list
    except Exception:
        return []

def deep_merge_settings(user_cfg, default_cfg):
    """Recursively merges default_cfg into user_cfg for any missing keys."""
    added_keys = []
    def _merge(target, source, path=""):
        for k, v in source.items():
            curr_path = f"{path}.{k}" if path else k
            if k not in target:
                target[k] = v
                added_keys.append(curr_path)
            elif isinstance(v, dict) and isinstance(target.get(k), dict):
                _merge(target[k], v, curr_path)
    
    result = dict(user_cfg)
    _merge(result, default_cfg)
    return result, added_keys

def interactive_setup_wizard():
    """Interactively guides the user through setting up settings.json."""
    print(t("wizard_welcome"))

    # 1. Language
    cur_lang = get_current_language()
    default_lang = "auto"
    try:
        lang_input = input(t("wizard_lang_prompt", default=default_lang)).strip().lower()
    except (EOFError, KeyboardInterrupt):
        lang_input = ""
    chosen_lang = lang_input if lang_input in ("de", "en", "auto") else default_lang
    if chosen_lang != "auto":
        set_language(chosen_lang)

    # 2. ComfyUI Server Address
    default_server = "127.0.0.1:8188"
    try:
        server_input = input(t("wizard_comfyui_server_prompt", default=default_server)).strip()
    except (EOFError, KeyboardInterrupt):
        server_input = ""
    chosen_server = server_input if server_input else default_server

    # 3. ComfyUI Models Directory
    default_models_dir = ""
    for candidate in ["../ComfyUI/models", "../ComfyUI_windows_portable/ComfyUI/models", "D:\\ComfyUI_windows_portable\\ComfyUI\\models"]:
        if os.path.exists(candidate):
            default_models_dir = candidate
            break
    try:
        models_input = input(t("wizard_models_dir_prompt", default=default_models_dir)).strip()
    except (EOFError, KeyboardInterrupt):
        models_input = ""
    chosen_models_dir = models_input if models_input else default_models_dir

    # 4. LM Studio API URL
    default_lms_url = "http://127.0.0.1:1234/v1/chat/completions"
    try:
        lms_url_input = input(t("wizard_lms_url_prompt", default=default_lms_url)).strip()
    except (EOFError, KeyboardInterrupt):
        lms_url_input = ""
    chosen_lms_url = lms_url_input if lms_url_input else default_lms_url

    # Query models from LM Studio
    print(t("wizard_lms_querying_models"))
    available_models = fetch_lm_studio_models(chosen_lms_url)
    chat_models = [m for m in available_models if "embedding" not in m.lower()]
    default_model_name = "gemma-4-e4b-uncensored-hauhaucs-aggressive"

    chosen_model_name = default_model_name
    if chat_models:
        print(t("wizard_lms_models_found"))
        default_idx = 1
        for idx, m_id in enumerate(chat_models, 1):
            if m_id == default_model_name:
                default_idx = idx
            marker = " (empfohlen / recommended)" if default_model_name in m_id else ""
            print(f"     [{idx}] {m_id}{marker}")
        
        try:
            m_choice = input(t("wizard_lms_select_model", count=len(chat_models), default=chat_models[default_idx-1], default_idx=default_idx)).strip()
        except (EOFError, KeyboardInterrupt):
            m_choice = ""
        
        if m_choice.isdigit() and 1 <= int(m_choice) <= len(chat_models):
            chosen_model_name = chat_models[int(m_choice) - 1]
        elif m_choice in chat_models:
            chosen_model_name = m_choice
        elif not m_choice:
            chosen_model_name = chat_models[default_idx - 1]
        else:
            chosen_model_name = m_choice
    else:
        try:
            m_choice = input(t("wizard_lms_no_models_fallback", default=default_model_name)).strip()
        except (EOFError, KeyboardInterrupt):
            m_choice = ""
        chosen_model_name = m_choice if m_choice else default_model_name

    # 5. Minimax I2V Configuration
    chosen_minimax = configure_minimax_interactive(chosen_models_dir)

    # 6. WebM Export
    default_webm = "j" if get_current_language() == "de" else "y"
    try:
        webm_input = input(t("wizard_webm_prompt", default=default_webm)).strip().lower()
    except (EOFError, KeyboardInterrupt):
        webm_input = ""
    chosen_webm = True
    if webm_input in ("n", "no", "nein", "false", "0"):
        chosen_webm = False

    new_settings = {
        "language": chosen_lang,
        "comfyui": {
            "server_address": chosen_server,
            "models_dir": chosen_models_dir,
            "models_search_paths": [
                "../ComfyUI/models",
                "../ComfyUI_windows_portable/ComfyUI/models"
            ]
        },
        "minimax_i2v": chosen_minimax,
        "export_webm": chosen_webm,
        "lm_studio": {
            "url": chosen_lms_url,
            "model_name": chosen_model_name,
            "temperature": 0.7
        }
    }

    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as sf:
            json.dump(new_settings, sf, indent=2, ensure_ascii=False)
        print(t("wizard_saved"))
    except Exception as e:
        print(f"⚠️ Konnte settings.json nicht speichern: {e}")

    # 7. Model & LoRA Catalog Scan (t2i_presets.json)
    target_presets_path = os.path.join(PRESETS_DIR, "t2i_presets.json")
    if chosen_models_dir and os.path.exists(chosen_models_dir):
        default_scan = "j" if get_current_language() == "de" else "y"
        try:
            scan_input = input(t("wizard_scan_catalog_prompt", default=default_scan)).strip().lower()
        except (EOFError, KeyboardInterrupt):
            scan_input = ""
        do_scan = False if scan_input in ("n", "no", "nein", "false", "0") else True
        if do_scan:
            default_nsfw = "j" if get_current_language() == "de" else "y"
            try:
                nsfw_input = input(t("wizard_filter_nsfw_prompt", default=default_nsfw)).strip().lower()
            except (EOFError, KeyboardInterrupt):
                nsfw_input = ""
            filter_nsfw = False if nsfw_input in ("n", "no", "nein", "false", "0") else True
            print(t("catalog_scan_start", dir=chosen_models_dir))
            try:
                stats = build_or_update_catalog(chosen_models_dir, presets_path=target_presets_path, filter_nsfw=filter_nsfw)
                print(t("catalog_scan_completed", total_loras=stats["total_loras"], new_loras=stats["new_loras"], total_models=stats["total_presets"]))
            except Exception as scan_err:
                print(f"⚠️ Katalog-Scan Fehler: {scan_err}")

    return new_settings

def load_settings():
    """Loads configuration from settings.json with interactive first-run wizard and auto-healing."""
    defaults = json.loads(json.dumps(DEFAULT_SETTINGS))
    
    if not os.path.exists(SETTINGS_FILE):
        if sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
            return interactive_setup_wizard()
        else:
            try:
                with open(SETTINGS_FILE, "w", encoding="utf-8") as sf:
                    json.dump(defaults, sf, indent=2, ensure_ascii=False)
            except Exception:
                pass
            return defaults

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as sf:
            cfg = json.load(sf)
    except Exception as e:
        print(f"⚠️ Fehler beim Lesen von settings.json: {e}")
        return defaults

    if not isinstance(cfg, dict):
        cfg = {}

    # Auto-migrate / auto-heal missing keys
    merged_cfg, added_keys = deep_merge_settings(cfg, defaults)
    if added_keys:
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as sf:
                json.dump(merged_cfg, sf, indent=2, ensure_ascii=False)
            print(t("settings_migrated_notice", keys=", ".join(added_keys)))
        except Exception:
            pass

    return merged_cfg

SETTINGS = load_settings()
SERVER_ADDRESS = SETTINGS["comfyui"]["server_address"]
LM_STUDIO_URL = SETTINGS["lm_studio"]["url"]
LLM_MODEL_NAME = SETTINGS["lm_studio"]["model_name"]
LLM_TEMPERATURE = SETTINGS["lm_studio"].get("temperature", 0.7)

def load_prompt_template(filename, default_text=""):
    """Loads a prompt template from the prompts folder or falls back to default_text."""
    filepath = os.path.join(PROMPTS_DIR, filename)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as pf:
                return pf.read()
        except Exception:
            pass
    return default_text

def format_prompt_template(template_str, **kwargs):
    """Replaces placeholders {key} in the template safely without formatting exceptions."""
    result = template_str
    for key, val in kwargs.items():
        result = result.replace(f"{{{key}}}", str(val))
    return result

def find_file(filename, search_dirs):
    """Searches for a file in the specified directories and returns the first existing path."""
    for folder in search_dirs:
        full_path = os.path.join(folder, filename)
        if os.path.exists(full_path):
            return full_path
    return os.path.join(search_dirs[0], filename)

def lms_load():
    print(t("lms_loading", model=LLM_MODEL_NAME))
    try:
        subprocess.run(["lms", "load", LLM_MODEL_NAME], check=True, capture_output=True)
        print(t("lms_loaded"))
    except Exception as e:
        print(t("lms_load_error", error=e))

def lms_unload():
    print(t("lms_unloading"))
    try:
        subprocess.run(["lms", "unload", "--all"], check=False, capture_output=True)
        print(t("lms_unloaded"))
    except Exception as e:
        print(t("lms_unload_error", error=e))

def free_comfyui_memory(unload_models=False, free_memory=True):
    """Frees ComfyUI memory/VRAM cache via its /free endpoint."""
    try:
        data = json.dumps({"unload_models": unload_models, "free_memory": free_memory}).encode("utf-8")
        req = urllib.request.Request(
            f"http://{SERVER_ADDRESS}/free",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=5)
        print(t("vram_cleanup"))
    except Exception:
        pass

def queue_prompt(prompt_workflow):
    p = {"prompt": prompt_workflow, "client_id": "master_regisseur"}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{SERVER_ADDRESS}/prompt", data=data)
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        print(f"   ❌ HTTPError from ComfyUI ({e.code}): {err_body}")
        raise

def get_history(prompt_id):
    try:
        req = urllib.request.Request(f"http://{SERVER_ADDRESS}/history/{prompt_id}")
        return json.loads(urllib.request.urlopen(req).read())
    except Exception:
        return {}

def get_image(filename, subfolder, folder_type):
    url = f"http://{SERVER_ADDRESS}/view?filename={filename}&subfolder={subfolder}&type={folder_type}"
    req = urllib.request.Request(url)
    return urllib.request.urlopen(req).read()

def upload_file(file_data, filename, content_type="image/png"):
    """Uploads an image/video to ComfyUI and returns the actual assigned filename."""
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="overwrite"\r\n\r\n'
        f'true\r\n'
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f'Content-Type: {content_type}\r\n\r\n'
    ).encode('utf-8') + file_data + f'\r\n--{boundary}--\r\n'.encode('utf-8')
    
    req = urllib.request.Request(f"http://{SERVER_ADDRESS}/upload/image", data=body)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    response = urllib.request.urlopen(req).read()
    return json.loads(response)["name"]

def save_image_with_metadata(img_bytes, target_path, prompt_workflow=None, a1111_params_text=""):
    """Saves a PNG image with embedded ComfyUI workflow JSON and A1111/Civitai parameters text."""
    try:
        image = Image.open(io.BytesIO(img_bytes))
        png_info = PngImagePlugin.PngInfo()
        if prompt_workflow:
            png_info.add_text("prompt", json.dumps(prompt_workflow, ensure_ascii=False))
        if a1111_params_text:
            png_info.add_text("parameters", a1111_params_text)
        image.save(target_path, "PNG", pnginfo=png_info)
    except Exception:
        with open(target_path, "wb") as f:
            f.write(img_bytes)

def inject_video_metadata(video_path, title, description, prompt_workflow_dict=None):
    """Injects Civitai-compatible metadata tags into an MP4 file using FFmpeg."""
    temp_path = video_path + "_meta_temp.mp4"
    try:
        comment_str = json.dumps(prompt_workflow_dict, ensure_ascii=False) if prompt_workflow_dict else ""
        meta_cmd = [
            "ffmpeg", "-y", "-i", video_path, "-c", "copy",
            "-metadata", f"title={title}",
            "-metadata", "artist=MovieGenerator AI Studio",
            "-metadata", f"description={description}"
        ]
        if comment_str:
            meta_cmd.extend(["-metadata", f"comment={comment_str}"])
        meta_cmd.append(temp_path)
        subprocess.run(meta_cmd, check=True, capture_output=True)
        if os.path.exists(temp_path):
            shutil.move(temp_path, video_path)
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

def extract_last_frame(video_path):
    """Extracts the last frame of a video as PNG bytes (via FFmpeg or OpenCV)."""
    if not video_path or not os.path.exists(video_path):
        return None

    # 1. FFmpeg (system-installed, fast and requires no external cv2 pip package)
    try:
        temp_png = video_path + "_last_frame_temp.png"
        cmd = ["ffmpeg", "-y", "-sseof", "-0.1", "-i", video_path, "-frames:v", "1", "-q:v", "2", temp_png]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if os.path.exists(temp_png):
            with open(temp_png, "rb") as f:
                data = f.read()
            os.remove(temp_png)
            return data
    except Exception:
        pass

    # 2. Fallback via OpenCV (dynamically imported if installed)
    try:
        import importlib
        cv2 = importlib.import_module("cv2")
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total_frames - 1))
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                _, buf = cv2.imencode(".png", frame)
                return buf.tobytes()
    except Exception:
        pass

    return None

def extract_video_frame(video_path, time_offset="00:00:01.000"):
    """Extracts a frame at a specific timestamp from a video as PNG bytes."""
    if not video_path or not os.path.exists(video_path):
        return None
    try:
        temp_png = video_path + "_frame_temp.png"
        cmd = ["ffmpeg", "-y", "-ss", str(time_offset), "-i", video_path, "-frames:v", "1", "-q:v", "2", temp_png]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if os.path.exists(temp_png):
            with open(temp_png, "rb") as f:
                data = f.read()
            os.remove(temp_png)
            return data
    except Exception:
        pass
    # Fallback to beginning of video (0s)
    try:
        temp_png = video_path + "_frame_start_temp.png"
        cmd = ["ffmpeg", "-y", "-ss", "00:00:00.000", "-i", video_path, "-frames:v", "1", "-q:v", "2", temp_png]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if os.path.exists(temp_png):
            with open(temp_png, "rb") as f:
                data = f.read()
            os.remove(temp_png)
            return data
    except Exception:
        pass
    return None

def create_preview_image_with_metadata(video_path, preview_png_path, a1111_params_text="", prompt_workflow=None, time_offset="00:00:01.000"):
    """Extracts a frame from a video and saves it as a PNG with Civitai-compatible metadata (parameters & prompt)."""
    frame_bytes = extract_video_frame(video_path, time_offset=time_offset)
    if not frame_bytes:
        frame_bytes = extract_last_frame(video_path)
    if not frame_bytes:
        return False
    try:
        save_image_with_metadata(frame_bytes, preview_png_path, prompt_workflow=prompt_workflow, a1111_params_text=a1111_params_text)
        return os.path.exists(preview_png_path)
    except Exception:
        return False

_CIVITAI_META_CACHE = {}

def get_comfy_models_dir():
    """
    Resolves the ComfyUI models directory without hardcoded drive paths.
    Checks:
    1. 'models_dir' configured in settings.json (absolute or relative to BASE_DIR)
    2. 'models_search_paths' list configured in settings.json
    3. Dynamic portable candidates relative to MovieGenerator (e.g. sibling ComfyUI folder)
    """
    comfy_cfg = SETTINGS.get("comfyui", {})

    # 1. Configured direct models_dir
    models_dir = comfy_cfg.get("models_dir")
    if models_dir and isinstance(models_dir, str) and models_dir.strip():
        m_path = models_dir.strip()
        resolved = m_path if os.path.isabs(m_path) else os.path.abspath(os.path.join(BASE_DIR, m_path))
        if os.path.exists(resolved) and os.path.isdir(resolved):
            return resolved

    # 2. Configured search paths list from settings.json
    search_paths = comfy_cfg.get("models_search_paths", [])
    if isinstance(search_paths, str):
        search_paths = [search_paths]

    # 3. Dynamic portable candidates relative to MovieGenerator
    portable_fallbacks = [
        os.path.join(BASE_DIR, "..", "ComfyUI", "models"),
        os.path.join(BASE_DIR, "..", "ComfyUI_windows_portable", "ComfyUI", "models"),
        os.path.join(BASE_DIR, "models"),
    ]

    all_candidates = list(search_paths) + portable_fallbacks
    for c in all_candidates:
        if not isinstance(c, str) or not c.strip():
            continue
        c_clean = c.strip()
        resolved = c_clean if os.path.isabs(c_clean) else os.path.abspath(os.path.join(BASE_DIR, c_clean))
        if os.path.exists(resolved) and os.path.isdir(resolved):
            return resolved

    return None

def find_civitai_metadata(model_filename_or_path, subfolder=None):
    """
    Finds and loads the .metadata.json file corresponding to a model/lora.
    Caches the results to avoid repeated disk walks.
    """
    if not model_filename_or_path:
        return None
        
    cache_key = (model_filename_or_path, subfolder)
    if cache_key in _CIVITAI_META_CACHE:
        return _CIVITAI_META_CACHE[cache_key]

    models_dir = get_comfy_models_dir()
    if not models_dir:
        return None

    target_base = os.path.splitext(os.path.basename(model_filename_or_path))[0].lower()
    
    search_dirs = []
    if subfolder:
        sf_path = os.path.join(models_dir, subfolder)
        if os.path.exists(sf_path):
            search_dirs.append(sf_path)
    search_dirs.extend([
        os.path.join(models_dir, "diffusion_models"),
        os.path.join(models_dir, "loras"),
        os.path.join(models_dir, "checkpoints")
    ])

    seen_dirs = set()
    best_partial = None
    for s_dir in search_dirs:
        if s_dir in seen_dirs or not os.path.exists(s_dir):
            continue
        seen_dirs.add(s_dir)
        for root, _, files in os.walk(s_dir):
            for f in files:
                if f.endswith(".metadata.json"):
                    f_base = f[:-14].lower()  # strip .metadata.json
                    if f_base == target_base:
                        meta_file = os.path.join(root, f)
                        try:
                            with open(meta_file, "r", encoding="utf-8") as jf:
                                data = json.load(jf)
                                _CIVITAI_META_CACHE[cache_key] = data
                                return data
                        except Exception:
                            pass
                    elif (target_base in f_base or f_base in target_base) and not best_partial:
                        best_partial = os.path.join(root, f)

    if best_partial:
        try:
            with open(best_partial, "r", encoding="utf-8") as jf:
                data = json.load(jf)
                _CIVITAI_META_CACHE[cache_key] = data
                return data
        except Exception:
            pass

    _CIVITAI_META_CACHE[cache_key] = None
    return None

def build_civitai_resource_metadata(model_path=None, loras_list=None):
    """
    Builds Civitai resources JSON and hash mappings from local .metadata.json files.
    """
    civitai_resources = []
    lora_hashes = []
    model_hash = None

    if model_path:
        meta = find_civitai_metadata(model_path, "diffusion_models") or find_civitai_metadata(model_path, "checkpoints")
        if meta:
            civ = meta.get("civitai", {})
            v_id = civ.get("id") or civ.get("modelVersionId")
            if v_id:
                civitai_resources.append({
                    "type": "checkpoint" if "lora" not in str(meta.get("sub_type", "")).lower() else "lora",
                    "modelVersionId": v_id,
                    "modelName": meta.get("model_name") or civ.get("name", "Checkpoint")
                })
            sha = meta.get("sha256")
            if sha:
                model_hash = sha[:10]

    if loras_list:
        for lora in loras_list:
            meta = find_civitai_metadata(lora, "loras")
            name_clean = os.path.splitext(os.path.basename(lora))[0]
            if meta:
                civ = meta.get("civitai", {})
                v_id = civ.get("id") or civ.get("modelVersionId")
                if v_id:
                    civitai_resources.append({
                        "type": "lora",
                        "modelVersionId": v_id,
                        "modelName": meta.get("model_name") or civ.get("name", name_clean),
                        "weight": 1.0
                    })
    # Deduplicate resources by modelVersionId
    seen_res = set()
    dedup_resources = []
    for r in civitai_resources:
        rid = r.get("modelVersionId")
        if rid and rid not in seen_res:
            seen_res.add(rid)
            dedup_resources.append(r)
        elif not rid:
            dedup_resources.append(r)

    # Deduplicate lora hashes
    seen_hashes = set()
    dedup_lora_hashes = []
    for lh in lora_hashes:
        if lh not in seen_hashes:
            seen_hashes.add(lh)
            dedup_lora_hashes.append(lh)

    return {
        "civitai_resources": dedup_resources,
        "model_hash": model_hash,
        "lora_hashes": dedup_lora_hashes
    }

def get_workflow_sampling_params(wf):
    """
    Extracts steps, sampler, scheduler, cfg, and seed from ComfyUI workflow.
    Defaults to Minimax H3 standard settings (8 steps, er_sde, beta, CFG 1.0).
    """
    steps = 8
    sampler = "er_sde"
    scheduler = "beta"
    cfg = 1.0
    seed = 42

    if not wf or not isinstance(wf, dict):
        return steps, sampler, scheduler, cfg, seed

    for nid, node in wf.items():
        if not isinstance(node, dict):
            continue
        ctype = node.get("class_type", "")
        inputs = node.get("inputs", {})
        meta_title = str(node.get("_meta", {}).get("title", "")).lower()

        if ctype == "KSamplerSelect":
            sampler = inputs.get("sampler_name", sampler)
        elif ctype == "BasicScheduler":
            scheduler = inputs.get("scheduler", scheduler)
            st = inputs.get("steps")
            if isinstance(st, (int, float)):
                steps = int(st)
            elif isinstance(st, list) and len(st) > 0:
                ref_id = str(st[0])
                if ref_id in wf and "value" in wf[ref_id].get("inputs", {}):
                    steps = int(wf[ref_id]["inputs"]["value"])
        elif ctype == "INTConstant" and ("step" in meta_title or "schritt" in meta_title):
            if "value" in inputs:
                steps = int(inputs["value"])
        elif ctype in ("KSampler", "KSamplerAdvanced"):
            if "steps" in inputs:
                steps = int(inputs["steps"])
            if "sampler_name" in inputs:
                sampler = inputs["sampler_name"]
            if "scheduler" in inputs:
                scheduler = inputs["scheduler"]
            if "cfg" in inputs:
                cfg = float(inputs["cfg"])
            if "seed" in inputs:
                seed = inputs["seed"]
        elif ctype == "RandomNoise":
            ns = inputs.get("noise_seed")
            if isinstance(ns, (int, float)):
                seed = int(ns)
            elif isinstance(ns, list) and len(ns) > 0:
                ref_id = str(ns[0])
                if ref_id in wf and "seed" in wf[ref_id].get("inputs", {}):
                    seed = wf[ref_id]["inputs"]["seed"]
                elif ref_id in wf and "value" in wf[ref_id].get("inputs", {}):
                    seed = wf[ref_id]["inputs"]["value"]
        elif "seed" in inputs and isinstance(inputs["seed"], (int, float)):
            seed = inputs["seed"]

    return steps, sampler, scheduler, cfg, seed

def interpolate_variables(text, variables):
    """Replaces {variable_name} in text with its current value from variables dictionary (whitespace & case tolerant)."""
    if not text or not variables:
        return text
    result = text
    # Exact replacement
    for key, val in variables.items():
        result = result.replace(f"{{{key}}}", str(val))
    # Case-insensitive & whitespace-tolerant replacement (e.g. { celina_top })
    for key, val in variables.items():
        pattern = re.compile(rf"\{{\s*{re.escape(key)}\s*\}}", re.IGNORECASE)
        result = pattern.sub(str(val), result)
    return result


def get_character_first_scene(char, scenes_list):
    """
    Determines the first scene number where a character appears.
    Checks char['first_scene'] / char['erste_szene'] / char['first_appearance'].
    If not specified, automatically scans scenes_list for references to this character.
    Returns 1-based scene id (int).
    """
    if not isinstance(char, dict):
        return 1

    # 1. Explicit user/screenplay configuration
    for key in ["first_scene", "erste_szene", "first_appearance", "auftritt", "erster_auftritt"]:
        val = char.get(key)
        if val is not None and str(val).strip():
            try:
                scene_num = int(val)
                if scene_num > 0:
                    return scene_num
            except (ValueError, TypeError):
                pass

    if not scenes_list:
        return 1

    char_id = char.get("id")
    char_name = (char.get("name") or "").strip()
    char_name_lower = char_name.lower()
    clean_char_name = re.sub(r"[^a-zA-Z0-9]", "", char_name_lower)

    # 2. Search scenes sequentially for first appearance
    for idx, scene in enumerate(scenes_list):
        s_id = scene.get("id", idx + 1)
        try:
            s_id_int = int(s_id)
        except (ValueError, TypeError):
            s_id_int = idx + 1

        # Check scene['characters'] / scene['charaktere'] / scene['actors']
        scene_chars = (
            scene.get("characters") or 
            scene.get("charaktere") or 
            scene.get("actors") or 
            scene.get("darsteller") or 
            []
        )
        if isinstance(scene_chars, list):
            for sc in scene_chars:
                if sc is None:
                    continue
                # Match by ID: 1, "1", "<Subject 1>"
                if char_id is not None:
                    if sc == char_id or str(sc).strip() == str(char_id):
                        return s_id_int
                    sub_match = re.search(r"<Subject\s*(\d+)>", str(sc), re.IGNORECASE)
                    if sub_match and int(sub_match.group(1)) == int(char_id):
                        return s_id_int

                # Match by Name: e.g. "Team_2_Sophie", "<Subject 9> (Team_2_Sophie)", "Sophie"
                sc_str = str(sc).strip().lower()
                if char_name_lower and (char_name_lower in sc_str or sc_str in char_name_lower):
                    return s_id_int
                sc_clean = re.sub(r"[^a-zA-Z0-9]", "", sc_str)
                if clean_char_name and (clean_char_name in sc_clean or sc_clean in clean_char_name):
                    return s_id_int

        # Check idea / prompt text for <Subject {id}> or character name
        text = (scene.get("idea") or scene.get("idee") or scene.get("prompt") or "")
        if char_id is not None and f"<Subject {char_id}>" in text:
            return s_id_int
        if char_name and len(char_name) >= 3:
            if re.search(r"\b" + re.escape(char_name) + r"\b", text, re.IGNORECASE):
                return s_id_int

    first_s_id = scenes_list[0].get("id", 1) if scenes_list else 1
    try:
        return int(first_s_id)
    except (ValueError, TypeError):
        return 1


def get_variables_for_scene(screenplay, target_scene_id=1):
    """
    Computes the cumulative state of screenplay variables up to and including target_scene_id.
    Starts with root variables + initial character outfits, then sequentially applies
    scene-level variable updates (variables_update / set_variables) for each scene
    up to target_scene_id.
    """
    vars_state = {}
    root_vars = screenplay.get("variablen") or screenplay.get("variables") or {}
    if isinstance(root_vars, dict):
        vars_state.update(root_vars)

    characters_list = screenplay.get("charaktere") or screenplay.get("characters") or []
    for c in characters_list:
        c_name = c.get("name", "").strip()
        c_outfit = c.get("outfit") or c.get("kleidung") or c.get("status") or c.get("wardrobe")
        if c_outfit and c_name:
            var_key = f"outfit_{re.sub(r'[^a-zA-Z0-9]', '_', c_name.lower())}"
            if var_key not in vars_state:
                vars_state[var_key] = str(c_outfit)

    if target_scene_id is None or target_scene_id <= 0:
        return vars_state

    scenes_list = screenplay.get("szenen") or screenplay.get("scenes") or []
    for idx, scene in enumerate(scenes_list):
        s_id = scene.get("id", idx + 1)
        try:
            s_id_int = int(s_id)
        except (ValueError, TypeError):
            s_id_int = idx + 1

        if s_id_int > target_scene_id:
            break

        scene_var_updates = (
            scene.get("variablen_update") or 
            scene.get("variables_update") or 
            scene.get("set_variables") or 
            scene.get("variablen") or 
            scene.get("variables") or 
            {}
        )
        if isinstance(scene_var_updates, dict) and scene_var_updates:
            vars_state.update(scene_var_updates)

    return vars_state


def ask_lm_studio_character(char, screenplay, preset_name, preset, active_variables=None):
    """Invokes LM Studio to generate the optimal T2I character casting prompt."""
    char_name = char.get("name", "Character")
    existing_prompt = char.get("prompt") or char.get("beschreibung") or char.get("rolle") or char.get("idee") or char.get("description") or ""

    # Interpolate active variables (e.g. {celina_top}) in character prompt / description
    if active_variables:
        existing_prompt = interpolate_variables(existing_prompt, active_variables)
    elif screenplay:
        root_vars = screenplay.get("variablen") or screenplay.get("variables") or {}
        if root_vars:
            existing_prompt = interpolate_variables(existing_prompt, root_vars)

    # Check for optional reference character link (bilingual support)
    ref_char_val = (
        char.get("reference_id") or 
        char.get("referenz_id") or 
        char.get("reference_character") or 
        char.get("referenz_charakter") or
        char.get("parent_character")
    )
    if ref_char_val is not None:
        chars_list = screenplay.get("charaktere") or screenplay.get("characters") or []
        ref_name = None
        for c in chars_list:
            if str(c.get("id")) == str(ref_char_val) or str(c.get("name", "")).strip().lower() == str(ref_char_val).strip().lower():
                ref_name = c.get("name")
                break
        ref_display = f"#{ref_char_val} ('{ref_name}')" if ref_name else f"#{ref_char_val}"
        ref_notes = (
            f"\n\n[CHARACTER IDENTITY CONTINUITY]:\n"
            f"This character is an alternate style version, age progression, or costume variation of reference character {ref_display}. "
            f"CRITICAL: Maintain the recognizable identity (facial bone structure, hair style/color, eye color) while translating into the requested target style/age."
        )
        existing_prompt = (existing_prompt + ref_notes).strip()
    
    # Short scenes overview for narrative context (bilingual support)
    sc_list = screenplay.get("szenen") or screenplay.get("scenes") or []
    scenes_overview = "\n".join([f"- Szene {s.get('id', idx+1)}: {s.get('idee') or s.get('idea') or s.get('prompt', '')}" for idx, s in enumerate(sc_list)])
    model_desc = preset.get("beschreibung", preset_name) if preset else preset_name
    
    default_instruction = """You are an expert AI prompt engineer for image generation models (Stable Diffusion / SDXL / Pony / Anima / CyberRealistic).
Create a single, highly detailed, visually compelling English prompt for the character casting sheet of '{char_name}'.

SCREENPLAY STORY & SCENES:
{szenen_uebersicht}

TARGET IMAGE MODEL:
'{preset_name}' ({model_desc})

CHARACTER INFORMATION:
Name: {char_name}
Original description/notes: {existing_prompt}

GUIDELINES:
1. Write the prompt entirely in English as a comma-separated list of descriptive visual tags and phrases.
2. Adapt the style to the target model:
   - If realistic/photorealistic (e.g. cyberrealistic, krea): focus on photographic terms, skin texture, natural lighting, camera angle, realistic clothing, subtle expressions.
   - If anime/stylized (e.g. catpony, turbo): focus on clean anime aesthetics, expressive eyes, hair details, stylized outfit.
3. Keep it consistent with the overall movie atmosphere and the character's role in the screenplay.
4. Always frame it as a clean solo character casting shot: full body shot or medium shot, solid or simple background (e.g. simple background, standing, soft studio lighting), so it works perfectly as an actor reference for video generation.
5. Return ONLY the final prompt text. Do NOT include markdown formatting, bolding, explanations, or quotes."""

    template = load_prompt_template("character_casting.txt", default_instruction)
    instruction = format_prompt_template(
        template,
        char_name=char_name,
        szenen_uebersicht=scenes_overview,
        preset_name=preset_name,
        model_desc=model_desc,
        existing_prompt=existing_prompt
    )

    data = {
        "model": LLM_MODEL_NAME,
        "messages": [
            {"role": "user", "content": instruction}
        ],
        "temperature": LLM_TEMPERATURE
    }

    try:
        req = urllib.request.Request(LM_STUDIO_URL, data=json.dumps(data).encode('utf-8'))
        req.add_header('Content-Type', 'application/json')
        response = json.loads(urllib.request.urlopen(req).read())
        content = response['choices'][0]['message']['content'].strip()
        content = re.sub(r'^```[a-zA-Z]*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
        content = content.strip('"\n ')
        return content
    except Exception as e:
        print(t("char_prompt_error", error=e))
        return existing_prompt


def format_state_instruction(characters, active_variables=None, character_states=None):
    """Formats active character wardrobe and environment variables into instructions for the LLM."""
    lines = []
    
    # 1. Check per-character outfits and states
    for i, char in enumerate(characters):
        c_name = char.get("name", f"actor_{i+1}")
        state_parts = []
        
        # Check character_states dictionary passed for this scene
        if character_states and c_name in character_states:
            c_val = character_states[c_name]
            if isinstance(c_val, dict):
                for k, v in c_val.items():
                    state_parts.append(f"{k}: {v}")
            else:
                state_parts.append(str(c_val))
                
        # Also check active_variables for keys associated with this character (e.g. outfit_chloe, chloe_outfit)
        if active_variables:
            clean_name = re.sub(r'[^a-zA-Z0-9]', '', c_name.lower())
            for vk, vv in active_variables.items():
                clean_vk = re.sub(r'[^a-zA-Z0-9]', '', vk.lower())
                if clean_name and clean_name in clean_vk:
                    entry = f"{vk}: {vv}"
                    if entry not in state_parts and str(vv) not in state_parts:
                        state_parts.append(entry)
                        
        if state_parts:
            lines.append(f"- {c_name} (<Subject {i+1}>): {', '.join(state_parts)}")
            
    # 2. Add remaining general scene/environment variables
    if active_variables:
        char_names_clean = [re.sub(r'[^a-zA-Z0-9]', '', c.get("name", "").lower()) for c in characters]
        general_vars = []
        for vk, vv in active_variables.items():
            clean_vk = re.sub(r'[^a-zA-Z0-9]', '', vk.lower())
            if not any(cn in clean_vk for cn in char_names_clean if cn):
                general_vars.append(f"{vk} = '{vv}'")
        if general_vars:
            lines.append(f"- Active Story Variables: {', '.join(general_vars)}")
            
    if lines:
        return "\n".join(lines)
    return "None (All characters appear in their standard reference wardrobe/appearance)."

def get_available_scene_loras(t2i_presets):
    """Returns a dictionary of MiniMax H3 compatible scene LoRAs."""
    if not t2i_presets:
        return {}
    lora_presets = t2i_presets.get("lora_presets", {})
    available = {}
    excluded = {"mmh3_fl2v_lightx2v_turbo", "mmh3_turbo_ckpt850", "mmh3_turbo_4step"}
    for k, v in lora_presets.items():
        if k in excluded:
            continue
        compat = v.get("kompatible_modelle", [])
        lname = v.get("lora_name", "").lower()
        if any(m in compat for m in ["minimax_h3", "minimax_h3_video"]) or "minimax" in lname or "mmh3" in k:
            available[k] = v
    return available

def format_available_scene_loras(available_loras):
    """Formats available scene LoRAs into bullet points for the LLM prompt."""
    if not available_loras:
        return "None available."
    lines = []
    for k, v in sorted(available_loras.items()):
        desc = v.get("beschreibung", "")
        trig = v.get("trigger_words", "")
        trig_str = f" [triggers: {trig}]" if trig else ""
        lines.append(f"- {k}: {desc}{trig_str}")
    return "\n".join(lines)

def resolve_scene_characters(scene, characters_list):
    """
    Resolves the list of character objects active in a specific scene.
    Looks for scene-level 'charaktere', 'characters', 'cast', or 'actors'.
    Falls back to checking mentions in 'idee', 'idea', or 'prompt'.
    Defaults to characters_list if no specific characters are identified.
    """
    if not characters_list:
        return []

    char_map = {}
    for idx, c in enumerate(characters_list):
        c_id = str(c.get("id", idx + 1))
        char_map[c_id] = c
        if c.get("name"):
            char_map[c.get("name").strip().lower()] = c

    raw_chars = (
        scene.get("charaktere") or 
        scene.get("characters") or 
        scene.get("cast") or 
        scene.get("actors")
    )

    if raw_chars:
        if isinstance(raw_chars, str):
            raw_list = [x.strip() for x in raw_chars.split(",") if x.strip()]
        elif isinstance(raw_chars, list):
            raw_list = raw_chars
        else:
            raw_list = [raw_chars]

        resolved = []
        for item in raw_list:
            if isinstance(item, dict):
                k = str(item.get("id") or item.get("name") or "").strip().lower()
                c_obj = char_map.get(k) or item
                if c_obj not in resolved:
                    resolved.append(c_obj)
            else:
                k = str(item).strip().lower()
                if k in char_map:
                    if char_map[k] not in resolved:
                        resolved.append(char_map[k])
                else:
                    for c_name_key, c_obj in char_map.items():
                        if k == c_name_key or k in c_name_key:
                            if c_obj not in resolved:
                                resolved.append(c_obj)
                            break
        if resolved:
            return resolved

    # Fallback: Check mentions in idea / prompt
    text_corpus = (
        str(scene.get("idee") or "") + " " + 
        str(scene.get("idea") or "") + " " + 
        str(scene.get("prompt") or "")
    ).lower()

    mentioned = []
    for idx, c in enumerate(characters_list):
        c_name = str(c.get("name", "")).strip().lower()
        c_id = str(c.get("id", idx + 1))
        if c_name and c_name in text_corpus:
            if c not in mentioned:
                mentioned.append(c)
        elif f"<picture {c_id}>" in text_corpus or f"<subject {c_id}>" in text_corpus:
            if c not in mentioned:
                mentioned.append(c)

    if mentioned:
        return mentioned

    return list(characters_list)

def ask_lm_studio(
    idea,
    characters,
    use_previous_scene=False,
    direct_continuation=False,
    active_variables=None,
    character_states=None,
    previous_shot_context=None,
    same_scene=False,
    sequence_info=None,
    t2i_presets=None
):
    print(t("scene_elaborating", idea=idea))
    
    char_definitions = ""
    for i, char in enumerate(characters):
        char_definitions += f"<Subject {i+1}> is the character in <Picture {i+1}> ({char['name']}).\n"

    continuity_rules = []
    
    # 1. Sequence & Location setting
    if sequence_info and (sequence_info.get("sequence") or sequence_info.get("location")):
        seq_val = sequence_info.get("sequence") or ""
        loc_val = sequence_info.get("location") or ""
        desc_parts = []
        if loc_val:
            desc_parts.append(f"Location: {loc_val}")
        if seq_val:
            desc_parts.append(f"Scene Group/Sequence: {seq_val}")
        continuity_rules.append(f"- SETTING: {', '.join(desc_parts)}")

    # 2. Previous shot context to prevent redundant actions and maintain physical posture
    if previous_shot_context:
        prev_id = previous_shot_context.get("id", "?")
        prev_summary = previous_shot_context.get("summary", "").strip()
        is_same_seq = previous_shot_context.get("same_sequence", False)
        is_same_scene = previous_shot_context.get("same_scene", False) or same_scene

        if is_same_seq or is_same_scene or direct_continuation or use_previous_scene:
            continuity_rules.append(
                f"- PRECEDING SHOT #{prev_id} ACTION: \"{prev_summary}\"\n"
                "- PHYSICAL CONTINUITY (CRITICAL):\n"
                f"  * Characters are ALREADY in the physical posture, position, and proximity established at the end of Shot #{prev_id}.\n"
                "  * DO NOT REPEAT ACTIONS: Never have characters walk up again, sit down again, or reach across if they already completed that action in the preceding shot!\n"
                "  * MANDATORY STARTING WORD: In 'detailed_description' under [Shot 1], you MUST explicitly begin by describing characters 'ALREADY' in their posture (e.g. '[Shot 1]: A medium close-up frames Chloe and Liam as they are ALREADY seated closely opposite each other at the table...', '[Shot 1]: A profile shot shows both characters ALREADY embracing intimately...').\n"
                "  * If this shot changes the camera angle or perspective (e.g. from wide shot to close-up, or over-the-shoulder), frame the new angle smoothly without resetting posture or moving characters back apart."
            )

    if direct_continuation:
        matchcut_snippet = load_prompt_template(
            "continuity_matchcut.txt",
            "CRITICAL CONTINUITY: This scene is a DIRECT SEAMLESS CONTINUATION (match cut) starting from the exact final frame of the previous scene. The action and character motion must immediately pick up where the previous scene ended without resetting posture or changing camera angle abruptly."
        )
        continuity_rules.append(f"- MATCH CUT: {matchcut_snippet.strip()}")

    if use_previous_scene:
        env_snippet = load_prompt_template(
            "continuity_environment.txt",
            "The user wants to keep the continuity from the previous scene. You MUST include '<Video 1> establishes the environment' in your detailed description so the model knows to use the previous video as a reference for the location/setting."
        )
        continuity_rules.append(f"- ENVIRONMENT: {env_snippet.strip()}")

    continuity_instruction = "\n".join(continuity_rules) if continuity_rules else "Independent shot. Standard scene staging."
    video_instruction = f"\n\nIMPORTANT CONTINUITY INSTRUCTIONS:\n{continuity_instruction}" if continuity_rules else ""
    state_instruction = format_state_instruction(characters, active_variables, character_states)
    
    avail_loras_dict = get_available_scene_loras(t2i_presets)
    avail_loras_text = format_available_scene_loras(avail_loras_dict)

    default_minimax_instruction = """You are an expert prompt engineer for the Minimax video generation model.
You will receive a short scene idea in German or English. Translate/expand it into this EXACT format.
Also, estimate how many seconds this shot should take based on the action (between 3 and 15) and write it at the very end as DURATION: X.

CRITICAL AUDIO REQUIREMENT:
- Absolutely NO non-diegetic background music, soundtrack, or score! The individual scenes will be spliced together, so inconsistent music ruins the final movie.
- Under 'overall_soundscape:', describe ONLY realistic diegetic ambient sounds, natural environment foley (footsteps, breathing, cloth rustle, room acoustics), and character speech/dialogue if any.
- Under 'non_diegetic_music:', ALWAYS write: None

CRITICAL CHARACTER WARDROBE & STATE CONTINUITY:
{state_instruction}
- Visual Identity vs. Clothing: The reference image (<Picture X>) establishes the character's facial features and identity. However, their CLOTHING and CURRENT STATE in this scene MUST strictly match the active state listed above!
- When a character's state specifies a wardrobe change (e.g. apron removed, topless, shirtless, nude, wearing different clothes, wet hair), you MUST explicitly describe them in their current clothing state in [Shot 1], explicitly stating their current outfit so Minimax overrides what was in <Picture X>.
- MANDATORY SUBJECT TAGGING: In 'detailed_description' under [Shot 1], you MUST refer to characters exclusively by their tag '<Subject X>' (e.g. '<Subject 1>') alongside their action, NEVER solely by their character name. Minimax models rely on '<Subject X>' to bind the description to '<Picture X>'.
- CRITICAL VISUAL STYLE: State the visual medium clearly in [Shot 1]: If live-action, specify 'photorealistic 35mm cinematic film footage, real life camera shot, hyperrealistic textures'. If animated/anime, specify 'cel-shaded vibrant anime style, expressive animation aesthetics'.

CRITICAL SCENE & SHOT CONTINUITY:
{continuity_instruction}

AVAILABLE SCENE LORAS (MiniMax H3):
{available_loras}
If this specific shot features motion, visual styles, combat, or intimate actions that match any of the LoRAs above, select 0 to 2 matching LoRA keys (e.g. 'mmh3_combat_v2' for martial arts, 'mmh3_nafasp_natural' for talking/facial motion, 'mmh3_poly_perfect' for close-up detail, or 'None').

FORMAT TO FOLLOW STRICTLY:
subject_definitions:
{char_definitions}

summary:
[reference generation] <1 sentence summary of the action in English>

detailed_description:
[Shot 1]: A medium shot frames ... Detailed cinematic description of the action in English.{video_instruction}

overall_soundscape:
<Realistic diegetic environmental noise, foley, and spoken dialogue if any. Strictly NO background music>

non_diegetic_music:
None

DURATION: <number>
LORAS: <comma-separated list of selected lora keys, or None>

Here is the scene idea:
{idee}"""

    minimax_template = load_prompt_template("minimax_scene.txt", default_minimax_instruction)
    instruction = format_prompt_template(
        minimax_template,
        char_definitions=char_definitions.strip(),
        continuity_instruction=continuity_instruction,
        video_instruction=video_instruction,
        state_instruction=state_instruction,
        available_loras=avail_loras_text,
        idee=idea
    )

    data = {
        "model": LLM_MODEL_NAME,
        "messages": [
            {"role": "user", "content": instruction}
        ],
        "temperature": LLM_TEMPERATURE
    }
    
    try:
        req = urllib.request.Request(LM_STUDIO_URL, data=json.dumps(data).encode('utf-8'))
        req.add_header('Content-Type', 'application/json')
        response = json.loads(urllib.request.urlopen(req).read())
        content = response['choices'][0]['message']['content']
        
        duration = 5 
        match = re.search(r'DURATION:\s*(\d+)', content, re.IGNORECASE)
        if match:
            duration = int(match.group(1))
            duration = max(3, min(10, duration)) 
            content = re.sub(r'DURATION:\s*\d+', '', content, flags=re.IGNORECASE).strip()

        # Parse selected LoRAs
        selected_loras = []
        lora_match = re.search(r'LORAS:\s*([^\n]+)', content, re.IGNORECASE)
        if lora_match:
            raw_loras = lora_match.group(1).strip()
            content = re.sub(r'LORAS:\s*[^\n]+', '', content, flags=re.IGNORECASE).strip()
            if raw_loras.lower() not in ["none", "n/a", "no", "null", ""]:
                for item in re.split(r'[,;\s]+', raw_loras):
                    clean_item = item.strip().strip("'\"`")
                    if not clean_item or clean_item.lower() in ["none", "and", "or"]:
                        continue
                    matched_key = None
                    if clean_item in avail_loras_dict:
                        matched_key = clean_item
                    else:
                        for ak in avail_loras_dict:
                            if clean_item.lower() == ak.lower():
                                matched_key = ak
                                break
                    if matched_key and matched_key not in selected_loras:
                        selected_loras.append(matched_key)

        if selected_loras:
            print(t("scene_loras_chosen", loras=", ".join(selected_loras)))

        # Strictly ensure non_diegetic_music is set to None and no background music is generated
        if "non_diegetic_music:" in content.lower():
            content = re.sub(r'non_diegetic_music:\s*.*', 'non_diegetic_music:\nNone', content, flags=re.IGNORECASE)
        else:
            content += "\n\nnon_diegetic_music:\nNone"

        if "overall_soundscape:" not in content.lower():
            content += "\n\noverall_soundscape:\nRealistic ambient environment sounds, subtle foley, and natural breathing. Strictly no music."
            
        return content, duration, selected_loras
    except Exception as e:
        print(t("lms_scene_error", error=e))
        state_fallback = f"\n[Active Wardrobe & State: {state_instruction}]" if active_variables or character_states else ""
        return (
            f"subject_definitions:\n{char_definitions.strip()}\n\n"
            f"summary:\n[reference generation] {idea}\n\n"
            f"detailed_description:\n[Shot 1]: {idea}{state_fallback}\n\n"
            f"overall_soundscape:\nNatural ambient room sounds, diegetic foley effects, and speech. Strictly no background music.\n\n"
            f"non_diegetic_music:\nNone",
            5,
            []
        )

def build_minimax_api_prompt(prompt_text, characters=None, scene_data=None):
    """Ensures the final prompt submitted to ComfyUI node 138 has the full Minimax template envelope:
    subject_definitions, summary, detailed_description, overall_soundscape, and non_diegetic_music: None.
    If prompt_text already has the full envelope, it is returned intact with subject_definitions ensured."""
    if not prompt_text:
        return ""

    p_lower = prompt_text.lower()

    # If already has full envelope (summary, detailed_description, and non_diegetic_music)
    if "detailed_description:" in p_lower and "summary:" in p_lower and "non_diegetic_music:" in p_lower:
        if "subject_definitions:" not in p_lower and characters:
            char_defs = ""
            for i, char in enumerate(characters):
                c_name = char.get("name") if isinstance(char, dict) else str(char)
                char_defs += f"<Subject {i+1}> is the character in <Picture {i+1}> ({c_name}).\n"
            return f"subject_definitions:\n{char_defs.strip()}\n\n{prompt_text.strip()}"
        return prompt_text.strip()

    # Assemble subject definitions
    char_defs = ""
    chars_to_use = characters or (scene_data.get("characters") if scene_data else None) or []
    for i, char in enumerate(chars_to_use):
        c_name = char.get("name") if isinstance(char, dict) else str(char)
        char_defs += f"<Subject {i+1}> is the character in <Picture {i+1}> ({c_name}).\n"

    # Extract summary
    summary = ""
    if scene_data and scene_data.get("summary"):
        summary = str(scene_data["summary"]).strip()
    if not summary:
        clean_first = re.sub(r'^\[Shot \d+\]:?\s*', '', prompt_text.strip())
        sentences = [s.strip() for s in re.split(r'[.!?\n]', clean_first) if s.strip()]
        summary = sentences[0] if sentences else clean_first[:100]

    # Clean detailed description
    detailed = prompt_text.strip()
    if not detailed.lower().startswith("[shot"):
        detailed = f"[Shot 1]: {detailed}"

    # Extract soundscape
    soundscape = ""
    if scene_data and scene_data.get("soundscape"):
        soundscape = str(scene_data["soundscape"]).strip()
    elif scene_data and scene_data.get("overall_soundscape"):
        soundscape = str(scene_data["overall_soundscape"]).strip()
    if not soundscape:
        soundscape = "Realistic ambient environment sounds, foley, and natural breathing. Strictly no music."

    parts = []
    if char_defs.strip():
        parts.append(f"subject_definitions:\n{char_defs.strip()}")
    parts.append(f"summary:\n{summary}")
    parts.append(f"detailed_description:\n{detailed}")
    parts.append(f"overall_soundscape:\n{soundscape}")
    parts.append("non_diegetic_music:\nNone")

    return "\n\n".join(parts)


def assemble_movie(scenes_dir, movie_dir, movie_name, screenplay=None, prepared_scenes=None, wf_i2v=None, t2i_presets=None):
    """Concatenates all generated scene clips into the final movie using FFmpeg with embedded Civitai metadata."""
    list_path = os.path.join(scenes_dir, "ffmpeg_list.txt")
    
    # Sort scenes correctly by numerical index: Szene_01.mp4, Szene_02.mp4, ...
    def scene_sort_key(filename):
        m = re.search(r'(\d+)', filename)
        return int(m.group(1)) if m else 999999

    scene_files = sorted([f for f in os.listdir(scenes_dir) if f.startswith("Szene_") and f.endswith(".mp4")], key=scene_sort_key)
    
    if not scene_files:
        print(t("cutting_no_scenes"))
        return

    print(t("cutting_start"))
    with open(list_path, "w", encoding="utf-8") as lf:
        for scene in scene_files:
            lf.write(f"file '{scene}'\n")
            
    final_video_path = os.path.abspath(os.path.join(movie_dir, f"{movie_name}_FINAL.mp4"))

    # Build Civitai-compatible metadata summary
    movie_title = (screenplay.get("titel") or screenplay.get("title") or movie_name) if screenplay else movie_name
    movie_desc = (screenplay.get("beschreibung") or screenplay.get("description") or "") if screenplay else ""

    civitai_summary = [f"Title: {movie_title}"]
    if movie_desc:
        civitai_summary.append(f"Description: {movie_desc}")
    civitai_summary.append("Generator: MovieGenerator AI Studio (ComfyUI Minimax I2V + T2I Casting)")

    lora_tags = []
    lora_presets_dict = t2i_presets.get("lora_presets", {}) if t2i_presets else {}
    if screenplay and (screenplay.get("charaktere") or screenplay.get("characters")):
        chars_list = screenplay.get("charaktere") or screenplay.get("characters")
        civitai_summary.append("\nCast & Models:")
        for c in chars_list:
            c_name = c.get("name", "Unknown")
            c_model = c.get("modell") or c.get("preset") or c.get("model") or "default"
            c_loras = c.get("loras") or c.get("lora") or []
            if isinstance(c_loras, list):
                lora_str = ", ".join([str(x.get("name") if isinstance(x, dict) else x) for x in c_loras])
                for x in c_loras:
                    lname = x.get("name") if isinstance(x, dict) else x
                    if lname in lora_presets_dict:
                        real_f = os.path.basename(lora_presets_dict[lname]["lora_name"]).replace(".safetensors", "")
                        tag = f"<lora:{real_f}:1.0>"
                    else:
                        tag = f"<lora:{lname}:1.0>"
                    if tag not in lora_tags:
                        lora_tags.append(tag)
            else:
                lora_str = str(c_loras)
                if lora_str in lora_presets_dict:
                    real_f = os.path.basename(lora_presets_dict[lora_str]["lora_name"]).replace(".safetensors", "")
                    tag = f"<lora:{real_f}:1.0>"
                else:
                    tag = f"<lora:{lora_str}:1.0>"
                if tag not in lora_tags:
                    lora_tags.append(tag)
            civitai_summary.append(f"- {c_name} (Model: {c_model}" + (f", LoRAs: {lora_str}" if lora_str else "") + ")")

    root_vars = screenplay.get("variablen") or screenplay.get("variables") or {} if screenplay else {}
    if prepared_scenes:
        civitai_summary.append("\nScenes & Storyboard:")
        for idx, s in enumerate(prepared_scenes):
            s_id = s.get("id", idx + 1)
            s_id_str = f"{int(s_id):02d}" if str(s_id).isdigit() else str(s_id)
            s_dur = s.get("dauer") or s.get("dauer_sekunden") or s.get("duration") or 5
            s_cont_parts = []
            if s.get("direkter_anschluss") or s.get("direct_continuation") or s.get("match_cut"):
                s_cont_parts.append("[Match Cut]")
            elif s.get("gleiche_szene") or s.get("same_scene") or s.get("angle_change"):
                s_cont_parts.append("[Same Scene Angle]")
            elif s.get("nutze_vorherige_szene") or s.get("anschluss_an_vorherige_szene") or s.get("continuity_environment") or s.get("continuity"):
                s_cont_parts.append("[Environment Ref]")
                
            s_seq = s.get("sequenz") or s.get("sequence") or s.get("ort") or s.get("location")
            if s_seq:
                s_cont_parts.append(f"[{s_seq}]")
            s_cont = (" " + " ".join(s_cont_parts)) if s_cont_parts else ""
            
            raw_p = (s.get("idee") or s.get("idea") or s.get("prompt") or "").strip()
            # If the prompt is the multi-line Minimax prompt, extract its summary if available
            if "summary:" in raw_p.lower():
                m_sum = re.search(r'summary:\s*([^\n]+(?:\n[^\n]+)?)', raw_p, re.IGNORECASE)
                if m_sum:
                    raw_p = m_sum.group(1).strip()
            
            active_vars = s.get("variables") or root_vars
            p_text = interpolate_variables(raw_p, active_vars)
            
            civitai_summary.append(f"- Scene {s_id_str} ({s_dur}s){s_cont}: {p_text}")
            if s.get("variables"):
                var_str = ", ".join([f"{k}='{v}'" for k, v in s["variables"].items()])
                civitai_summary.append(f"  State: {var_str}")
            if s.get("loras"):
                s_loras_list = s["loras"] if isinstance(s["loras"], list) else [s["loras"]]
                sl_display = []
                for sl in s_loras_list:
                    sl_k = sl.get("key") or sl.get("name") or sl.get("lora") if isinstance(sl, dict) else str(sl)
                    sl_display.append(sl_k)
                    if sl_k in lora_presets_dict:
                        real_f = os.path.basename(lora_presets_dict[sl_k]["lora_name"]).replace(".safetensors", "")
                        tag = f"<lora:{real_f}:1.0>"
                    else:
                        tag = f"<lora:{sl_k}:1.0>"
                    if tag not in lora_tags:
                        lora_tags.append(tag)
                if sl_display:
                    civitai_summary.append(f"  Scene LoRAs: {', '.join(sl_display)}")

    full_description = "\n".join(civitai_summary)

    metadata_json = {
        "generator": "MovieGenerator",
        "title": movie_title,
        "screenplay": screenplay,
        "scenes": prepared_scenes
    }
    metadata_json_str = json.dumps(metadata_json, ensure_ascii=False)

    def escape_ffmetadata(val):
        val = str(val).replace('\\', '\\\\')
        val = val.replace('=', '\\=')
        val = val.replace(';', '\\;')
        val = val.replace('#', '\\#')
        val = val.replace('\n', '\\\n')
        return val

    # Write metadata to a dedicated ffmetadata file to bypass Windows command line length limits (WinError 206)
    ffmeta_path = os.path.join(scenes_dir, "ffmetadata.txt")
    with open(ffmeta_path, "w", encoding="utf-8") as f:
        f.write(";FFMETADATA1\n")
        f.write(f"title={escape_ffmetadata(movie_title)}\n")
        f.write("artist=MovieGenerator AI Studio\n")
        f.write(f"description={escape_ffmetadata(full_description)}\n")
        f.write(f"comment={escape_ffmetadata(metadata_json_str)}\n")

    # Map scenes to transition settings
    scene_lookup = {}
    if prepared_scenes:
        for sc in prepared_scenes:
            sid = sc.get("id")
            if sid is not None:
                scene_lookup[str(sid)] = sc
    elif screenplay:
        s_list = screenplay.get("szenen") or screenplay.get("scenes") or []
        for idx, sc in enumerate(s_list):
            sid = sc.get("id", idx + 1)
            scene_lookup[str(sid)] = sc

    TRANSITION_MAP = {
        "cut": None,
        "hart": None,
        "none": None,
        "fade": "fade",
        "dissolve": "fade",
        "crossfade": "fade",
        "cross_dissolve": "fade",
        "fadeblack": "fadeblack",
        "fade_to_black": "fadeblack",
        "blende_schwarz": "fadeblack",
        "fadewhite": "fadewhite",
        "dip_to_white": "fadewhite",
        "blende_weiss": "fadewhite",
        "wipeleft": "wipeleft",
        "wiperight": "wiperight",
        "smoothleft": "smoothleft",
        "smoothright": "smoothright",
        "circlecrop": "circlecrop",
    }

    transitions_to_apply = []
    has_custom_transition = False
    for i in range(len(scene_files) - 1):
        sfile = scene_files[i]
        m = re.search(r'(\d+)', sfile)
        sid = str(int(m.group(1))) if m else str(i + 1)
        sc_data = scene_lookup.get(sid, {})
        t_raw = str(sc_data.get("transition") or sc_data.get("uebergang") or sc_data.get("blende") or "cut").strip().lower()
        t_type = TRANSITION_MAP.get(t_raw)
        try:
            t_dur = float(sc_data.get("transition_duration") or sc_data.get("uebergang_dauer") or 0.75)
        except (ValueError, TypeError):
            t_dur = 0.75
        transitions_to_apply.append((t_type, t_dur))
        if t_type is not None:
            has_custom_transition = True

    if not has_custom_transition or len(scene_files) <= 1:
        # Fast lossless stream concatenation via ffmpeg_list.txt
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", "ffmpeg_list.txt",
            "-i", "ffmetadata.txt",
            "-map_metadata", "1",
            "-c", "copy",
            final_video_path
        ]
    else:
        # Cinematic transition assembly via FFmpeg xfade + acrossfade filter complex
        print("   🎬 Wende filmische Szenenübergänge (xfade) an...")
        inputs_cmd = []
        filter_steps = []
        durations = []
        has_audios = []

        for i, sfile in enumerate(scene_files):
            spath = os.path.join(scenes_dir, sfile)
            d = get_video_duration(spath) or 5.0
            durations.append(d)
            inputs_cmd.extend(["-i", sfile])
            has_a = has_audio_stream(spath)
            has_audios.append(has_a)

            filter_steps.append(f"[{i}:v]format=yuv420p[v_in_{i}]")
            if has_a:
                filter_steps.append(f"[{i}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a_in_{i}]")
            else:
                filter_steps.append(f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=duration={d:.3f}[a_in_{i}]")

        cur_v = "v_in_0"
        cur_a = "a_in_0"
        running_dur = durations[0]

        for i in range(len(scene_files) - 1):
            next_v = f"v_in_{i+1}"
            next_a = f"a_in_{i+1}"
            dur_next = durations[i+1]
            t_type, req_dur = transitions_to_apply[i]

            t_dur = min(req_dur, running_dur / 2.0, dur_next / 2.0)
            if t_dur < 0.1:
                t_type = None

            out_v = f"v_trans_{i+1}"
            out_a = f"a_trans_{i+1}"

            if t_type is None:
                filter_steps.append(f"[{cur_v}][{next_v}]concat=n=2:v=1:a=0[{out_v}]")
                filter_steps.append(f"[{cur_a}][{next_a}]concat=n=2:v=0:a=1[{out_a}]")
                running_dur = running_dur + dur_next
            else:
                offset = max(0.0, running_dur - t_dur)
                filter_steps.append(f"[{cur_v}][{next_v}]xfade=transition={t_type}:duration={t_dur:.3f}:offset={offset:.3f}[{out_v}]")
                filter_steps.append(f"[{cur_a}][{next_a}]acrossfade=d={t_dur:.3f}[{out_a}]")
                running_dur = offset + dur_next

            cur_v = out_v
            cur_a = out_a

        meta_input_idx = len(scene_files)
        inputs_cmd.extend(["-i", "ffmetadata.txt"])

        cmd = ["ffmpeg", "-y"] + inputs_cmd + [
            "-filter_complex", ";".join(filter_steps),
            "-map", f"[{cur_v}]",
            "-map", f"[{cur_a}]",
            "-map_metadata", str(meta_input_idx),
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            final_video_path
        ]
    
    try:
        res = subprocess.run(cmd, cwd=scenes_dir, check=True, capture_output=True, text=True)
        print(t("cutting_success", path=final_video_path))

        # Check for Music Studio soundtrack scoring
        music_cfg = (screenplay.get("music") if isinstance(screenplay, dict) else None) or SETTINGS.get("music_studio", {})
        if music_cfg and (music_cfg.get("enabled") is True or (isinstance(screenplay, dict) and screenplay.get("music", {}).get("enabled") is True)):
            try:
                print(t("music_starting"))
                wf_music_path = find_file("workflow_music_ace.json", [WORKFLOWS_DIR, BASE_DIR])
                if wf_music_path and os.path.exists(wf_music_path):
                    with open(wf_music_path, "r", encoding="utf-8") as mf:
                        wf_music = json.load(mf)
                    
                    # Determine exact video duration
                    movie_dur = get_video_duration(final_video_path)
                    if not movie_dur and prepared_scenes:
                        movie_dur = sum(float(sc.get("dauer", 5)) for sc in prepared_scenes)
                    if not movie_dur:
                        movie_dur = 30.0

                    # Configurable checkpoint (NOT hardcoded!)
                    chosen_ckpt = (
                        music_cfg.get("checkpoint") or 
                        music_cfg.get("model") or 
                        SETTINGS.get("music_studio", {}).get("checkpoint") or 
                        "Other\\base model\\ace_step_v1_3.5b.safetensors"
                    )
                    prompt_tags = music_cfg.get("prompt") or music_cfg.get("tags")
                    if not prompt_tags:
                        print("   🧠 LM Studio: Erstelle musikalische Tags für den Film-Soundtrack...")
                        p_title = screenplay.get("titel") or screenplay.get("title") or movie_name
                        p_scenes = screenplay.get("scenes") or screenplay.get("szenen") if isinstance(screenplay, dict) else None
                        prompt_tags = ask_lm_studio_music_tags(p_title, p_desc, scenes=p_scenes)
                        music_cfg["prompt"] = prompt_tags
                    
                    music_steps = music_cfg.get("steps") or SETTINGS.get("music_studio", {}).get("steps", 40)
                    music_cfg_scale = music_cfg.get("cfg") or SETTINGS.get("music_studio", {}).get("cfg", 4.0)
                    music_vol = float(music_cfg.get("volume") or SETTINGS.get("music_studio", {}).get("volume", 0.20))
                    use_ducking = bool(music_cfg.get("ducking") if music_cfg.get("ducking") is not None else SETTINGS.get("music_studio", {}).get("ducking", True))

                    print(t("music_generating", duration=movie_dur, model=os.path.basename(chosen_ckpt)))
                    aud_data, aud_fn = generate_movie_soundtrack(
                        wf_music,
                        prompt_tags=prompt_tags,
                        duration_seconds=movie_dur,
                        checkpoint=chosen_ckpt,
                        steps=music_steps,
                        cfg=music_cfg_scale
                    )

                    if aud_data:
                        # Save companion soundtrack file
                        ext = os.path.splitext(aud_fn)[1] if aud_fn else ".flac"
                        soundtrack_file = os.path.abspath(os.path.join(movie_dir, f"{movie_name}_soundtrack{ext}"))
                        with open(soundtrack_file, "wb") as af:
                            af.write(aud_data)
                        print(t("music_generated", path=soundtrack_file))

                        # Mix soundtrack into movie with auto-ducking
                        print(t("music_mixing"))
                        raw_backup_path = os.path.abspath(os.path.join(movie_dir, f"{movie_name}_RAW.mp4"))
                        shutil.copy2(final_video_path, raw_backup_path)

                        scored_temp_path = os.path.abspath(os.path.join(movie_dir, f"{movie_name}_SCORED.mp4"))
                        mix_ok = mix_soundtrack_into_movie(
                            raw_backup_path,
                            soundtrack_file,
                            scored_temp_path,
                            volume=music_vol,
                            ducking=use_ducking
                        )
                        if mix_ok and os.path.exists(scored_temp_path):
                            shutil.move(scored_temp_path, final_video_path)
                            print(t("music_mixed_success", path=final_video_path))
                        else:
                            print("   ⚠️ Audio-Mix fehlgeschlagen, behalte untermalte Rohfassung.")
                else:
                    print("   ⚠️ workflow_music_ace.json nicht gefunden.")
            except Exception as me:
                print(f"   ⚠️ Music Studio Fehler: {me}")
        
        # Optional WebM export with embedded metadata
        if SETTINGS.get("export_webm", True):
            final_webm_path = os.path.abspath(os.path.join(movie_dir, f"{movie_name}_FINAL.webm"))
            print(t("webm_export_start"))
            webm_cmd = [
                "ffmpeg", "-y",
                "-i", final_video_path,
                "-i", "ffmetadata.txt",
                "-map", "0:v", "-map", "0:a?",
                "-map_metadata", "1",
                "-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0",
                "-deadline", "realtime", "-cpu-used", "4",
                "-c:a", "libopus",
                final_webm_path
            ]
            try:
                subprocess.run(webm_cmd, cwd=scenes_dir, check=True, capture_output=True, text=True)
                print(t("webm_export_success", path=final_webm_path))
            except Exception as we:
                print(f"   ⚠️ WebM export warning: {we}")

        # Create Civitai-compatible preview image for the final movie
        final_preview_path = os.path.abspath(os.path.join(movie_dir, f"{movie_name}_FINAL_preview.png"))
        unet_name = wf_i2v.get("620", {}).get("inputs", {}).get("unet_name", "") if wf_i2v else ""
        model_name = os.path.basename(unet_name).replace(".safetensors", "") if unet_name else "minimax_h3"

        # Resolve sampling parameters from workflow (e.g. 8 steps, er_sde, beta, CFG 1.0)
        steps, sampler, scheduler, cfg, seed = get_workflow_sampling_params(wf_i2v)

        # Resolve local .metadata.json files for exact Civitai resource IDs & hashes
        all_lora_files = []
        for lora_tag in lora_tags:
            m_tag = re.search(r'<lora:([^:>]+)', lora_tag)
            if m_tag:
                all_lora_files.append(m_tag.group(1) + ".safetensors")

        # Also scan workflow for embedded LoRAs (e.g. Minimax turbo LoRA in node 674)
        if wf_i2v:
            for nid, node in wf_i2v.items():
                if not isinstance(node, dict):
                    continue
                inputs = node.get("inputs", {})
                for k, v in inputs.items():
                    if isinstance(v, dict) and "lora" in v and v.get("on", True):
                        all_lora_files.append(v["lora"])
                if "lora_name" in inputs:
                    all_lora_files.append(inputs["lora_name"])

        civ_res_info = build_civitai_resource_metadata(model_path=unet_name, loras_list=all_lora_files)
        if civ_res_info["civitai_resources"]:
            print(t("civitai_resources_resolved", count=len(civ_res_info["civitai_resources"])))

        hash_parts = []
        if civ_res_info["model_hash"]:
            hash_parts.append(f"Model hash: {civ_res_info['model_hash']}")
        if civ_res_info["lora_hashes"]:
            hash_parts.append(f"Lora hashes: \"{', '.join(civ_res_info['lora_hashes'])}\"")
        if civ_res_info["civitai_resources"]:
            hash_parts.append(f"Civitai resources: {json.dumps(civ_res_info['civitai_resources'], ensure_ascii=False)}")
        
        extra_meta_str = (", " + ", ".join(hash_parts)) if hash_parts else ""
        
        a1111_movie_params = (
            f"{full_description}\n"
            + (f"LoRAs: {' '.join(lora_tags)}\n" if lora_tags else "")
            + "Negative prompt: worst quality, low quality, blurry, distorted, deformed\n"
            + f"Steps: {steps}, Sampler: {sampler}, Schedule type: {scheduler}, CFG scale: {cfg:.1f}, Seed: {seed}, Size: 1344x768, Model: {model_name}{extra_meta_str}"
        )
        if create_preview_image_with_metadata(final_video_path, final_preview_path, a1111_params_text=a1111_movie_params, prompt_workflow=wf_i2v):
            print(t("preview_image_created", path=final_preview_path))
    except subprocess.CalledProcessError as cpe:
        err_msg = cpe.stderr.strip() if cpe.stderr else str(cpe)
        print(t("cutting_error", error=err_msg))
    except Exception as e:
        print(t("cutting_error", error=e))
        
    if os.path.exists(list_path):
        try:
            os.remove(list_path)
        except Exception:
            pass
    if os.path.exists(ffmeta_path):
        try:
            os.remove(ffmeta_path)
        except Exception:
            pass

def main():
    # 0. Check for CLI maintenance flags
    if len(sys.argv) >= 2 and sys.argv[1].lower() in ["--scan-models", "--scan", "--rebuild-presets", "--update-catalog", "-s"]:
        models_dir = get_comfy_models_dir()
        if not models_dir:
            print(t("catalog_scan_no_models_dir"))
            return
        print(t("catalog_scan_start", dir=models_dir))
        stats = build_or_update_catalog(models_dir)
        print(t("catalog_scan_completed", total_loras=stats["total_loras"], new_loras=stats["new_loras"], total_models=stats["total_presets"]))
        return

    if len(sys.argv) >= 2 and sys.argv[1].lower() in ["--configure-minimax", "-m", "--minimax"]:
        models_dir = get_comfy_models_dir()
        cur_mm = SETTINGS.get("minimax_i2v", {})
        updated_mm = configure_minimax_interactive(models_dir, cur_mm)
        SETTINGS["minimax_i2v"] = updated_mm
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as sf:
                json.dump(SETTINGS, sf, indent=2, ensure_ascii=False)
            print(t("minimax_config_saved"))
        except Exception as e:
            print(f"⚠️ Konnte settings.json nicht speichern: {e}")
        return

    if len(sys.argv) >= 2 and sys.argv[1].lower() in ["--editor", "-e", "--agency", "--script-agency"]:
        from script_agency import run_script_agency
        run_script_agency(blocking=True)
        return

    # 1. Check for targeted scene re-shooting flag (--scene <id> or --only-scene <id>)
    target_scene_id = None
    cli_args = list(sys.argv[1:])
    for flag in ["--scene", "--only-scene"]:
        if flag in cli_args:
            s_idx = cli_args.index(flag)
            if s_idx + 1 < len(cli_args):
                target_scene_id = cli_args[s_idx + 1]
                del cli_args[s_idx:s_idx + 2]
                break

    # Determine screenplay input
    if len(cli_args) >= 1:
        screenplay_input = cli_args[0]
    else:
        # Interactive menu selection or fallback
        print(f"\n🎬 MovieGenerator v{__version__} • Master Regisseur")
        while True:
            available = [f for f in os.listdir(PROJECTS_DIR) if f.endswith(".json")]
            if available:
                print(t("menu_available_screenplays"))
                for idx, f in enumerate(available, 1):
                    print(f"  [{idx}] {f}")
                print(t("menu_scan_models_option"))
                print(t("menu_minimax_option"))
                print(t("menu_editor_option"))
                print(t("menu_instruction"))
                try:
                    choice = input(t("menu_prompt")).strip()
                    if choice.lower() in ["s", "scan"]:
                        models_dir = get_comfy_models_dir()
                        if not models_dir:
                            print(t("catalog_scan_no_models_dir"))
                        else:
                            print(t("catalog_scan_start", dir=models_dir))
                            stats = build_or_update_catalog(models_dir)
                            print(t("catalog_scan_completed", total_loras=stats["total_loras"], new_loras=stats["new_loras"], total_models=stats["total_presets"]))
                        print()
                        continue
                    elif choice.lower() in ["m", "minimax"]:
                        models_dir = get_comfy_models_dir()
                        cur_mm = SETTINGS.get("minimax_i2v", {})
                        updated_mm = configure_minimax_interactive(models_dir, cur_mm)
                        SETTINGS["minimax_i2v"] = updated_mm
                        try:
                            with open(SETTINGS_FILE, "w", encoding="utf-8") as sf:
                                json.dump(SETTINGS, sf, indent=2, ensure_ascii=False)
                            print(t("minimax_config_saved"))
                        except Exception as e:
                            print(f"⚠️ Konnte settings.json nicht speichern: {e}")
                        print()
                        continue
                    elif choice.lower() in ["e", "editor", "agency"]:
                        from script_agency import run_script_agency
                        run_script_agency(blocking=True)
                        print()
                        continue
                    elif choice.isdigit() and 1 <= int(choice) <= len(available):
                        screenplay_input = os.path.join(PROJECTS_DIR, available[int(choice) - 1])
                        break
                    elif choice in available:
                        screenplay_input = os.path.join(PROJECTS_DIR, choice)
                        break
                    else:
                        print(t("menu_invalid_choice"))
                        time.sleep(3)
                        return
                except Exception:
                    return
            else:
                print(t("menu_no_screenplays"))
                print(t("menu_scan_models_option"))
                print(t("menu_minimax_option"))
                print(t("menu_editor_option"))
                try:
                    choice = input(t("menu_prompt")).strip()
                    if choice.lower() in ["s", "scan"]:
                        models_dir = get_comfy_models_dir()
                        if not models_dir:
                            print(t("catalog_scan_no_models_dir"))
                        else:
                            print(t("catalog_scan_start", dir=models_dir))
                            stats = build_or_update_catalog(models_dir)
                            print(t("catalog_scan_completed", total_loras=stats["total_loras"], new_loras=stats["new_loras"], total_models=stats["total_presets"]))
                        print()
                        continue
                    elif choice.lower() in ["m", "minimax"]:
                        models_dir = get_comfy_models_dir()
                        cur_mm = SETTINGS.get("minimax_i2v", {})
                        updated_mm = configure_minimax_interactive(models_dir, cur_mm)
                        SETTINGS["minimax_i2v"] = updated_mm
                        try:
                            with open(SETTINGS_FILE, "w", encoding="utf-8") as sf:
                                json.dump(SETTINGS, sf, indent=2, ensure_ascii=False)
                            print(t("minimax_config_saved"))
                        except Exception as e:
                            print(f"⚠️ Konnte settings.json nicht speichern: {e}")
                        print()
                        continue
                    elif choice.lower() in ["e", "editor", "agency"]:
                        from script_agency import run_script_agency
                        run_script_agency(blocking=True)
                        print()
                        continue
                except Exception:
                    pass
                time.sleep(5)
                return

    # Resolve screenplay path
    if not os.path.exists(screenplay_input):
        cand1 = os.path.join(PROJECTS_DIR, screenplay_input)
        cand2 = os.path.join(PROJECTS_DIR, screenplay_input + ".json")
        if os.path.exists(cand1):
            screenplay_path = cand1
        elif os.path.exists(cand2):
            screenplay_path = cand2
        else:
            screenplay_path = screenplay_input
    else:
        screenplay_path = screenplay_input

    film_name = os.path.splitext(os.path.basename(screenplay_path))[0]

    # Create structured project directories: Projects/<film_name>/{Characters, Scenes, Movie}
    project_dir = os.path.join(PROJECTS_DIR, film_name)
    characters_dir = os.path.join(project_dir, "Characters")
    scenes_dir = os.path.join(project_dir, "Scenes")
    movie_dir = os.path.join(project_dir, "Movie")

    os.makedirs(characters_dir, exist_ok=True)
    os.makedirs(scenes_dir, exist_ok=True)
    os.makedirs(movie_dir, exist_ok=True)

    # Save a copy of the screenplay in the project directory if not already there
    local_screenplay_copy = os.path.join(project_dir, f"{film_name}.json")
    original_screenplay_backup = os.path.join(project_dir, f"{film_name}_original.json")

    # Ensure a pristine copy of the original input screenplay is preserved for diffs/reference
    if not os.path.exists(original_screenplay_backup):
        try:
            shutil.copy2(screenplay_path, original_screenplay_backup)
        except Exception:
            pass

    # Check if an extended screenplay already exists in project_dir with pre-generated prompts
    target_load_path = screenplay_path
    if os.path.exists(local_screenplay_copy) and os.path.abspath(screenplay_path) != os.path.abspath(local_screenplay_copy):
        try:
            with open(local_screenplay_copy, "r", encoding="utf-8") as lf:
                local_data = json.load(lf)
            local_scenes = local_data.get("szenen") or local_data.get("scenes") or []
            if any(s.get("prompt") for s in local_scenes):
                target_load_path = local_screenplay_copy
        except Exception:
            pass
    elif not os.path.exists(local_screenplay_copy) and os.path.abspath(screenplay_path) != os.path.abspath(local_screenplay_copy):
        try:
            shutil.copy2(screenplay_path, local_screenplay_copy)
        except Exception:
            pass

    print(t("loading_screenplay", film_name=film_name))
    print(t("project_dir", path=project_dir))
    print(f"   ├── Characters: {characters_dir}")
    print(f"   ├── Scenes:     {scenes_dir}")
    print(f"   └── Movie:      {movie_dir}")

    with open(target_load_path, "r", encoding="utf-8") as f:
        screenplay = json.load(f)

    # Load workflows and presets
    wf_t2i_path = find_file("workflow_t2i.json", [WORKFLOWS_DIR, BASE_DIR])
    wf_i2v_path = find_file("workflow_i2v_api.json", [WORKFLOWS_DIR, BASE_DIR])
    t2i_presets_path = find_file("t2i_presets.json", [PRESETS_DIR, BASE_DIR])

    with open(wf_t2i_path, "r", encoding="utf-8") as f:
        wf_t2i = json.load(f)
        
    with open(wf_i2v_path, "r", encoding="utf-8") as f:
        wf_i2v = json.load(f)

    # Apply Minimax I2V configuration from settings.json
    mm_cfg = SETTINGS.get("minimax_i2v", {})
    if mm_cfg and wf_i2v:
        configured_unet = mm_cfg.get("unet_name")
        if configured_unet and "620" in wf_i2v and "inputs" in wf_i2v["620"]:
            wf_i2v["620"]["inputs"]["unet_name"] = configured_unet

        configured_turbo = mm_cfg.get("turbo_lora")
        if configured_turbo and "674" in wf_i2v and "inputs" in wf_i2v["674"]:
            if "lora_1" in wf_i2v["674"]["inputs"]:
                wf_i2v["674"]["inputs"]["lora_1"]["lora"] = configured_turbo
                wf_i2v["674"]["inputs"]["lora_1"]["strength"] = float(mm_cfg.get("turbo_strength", 1.0))

        configured_steps = mm_cfg.get("steps")
        if configured_steps is not None and "750" in wf_i2v and "inputs" in wf_i2v["750"]:
            wf_i2v["750"]["inputs"]["value"] = int(configured_steps)

        configured_clip = mm_cfg.get("clip_name")
        if configured_clip and "128" in wf_i2v and "inputs" in wf_i2v["128"]:
            wf_i2v["128"]["inputs"]["clip_name"] = configured_clip

        configured_v_vae = mm_cfg.get("video_vae_name")
        if configured_v_vae and "119" in wf_i2v and "inputs" in wf_i2v["119"]:
            wf_i2v["119"]["inputs"]["vae_name"] = configured_v_vae

        configured_a_vae = mm_cfg.get("audio_vae_name")
        if configured_a_vae and "120" in wf_i2v and "inputs" in wf_i2v["120"]:
            wf_i2v["120"]["inputs"]["vae_name"] = configured_a_vae

        unet_disp = os.path.basename(configured_unet) if configured_unet else "default"
        turbo_disp = os.path.basename(configured_turbo) if configured_turbo else "default"
        steps_disp = configured_steps if configured_steps is not None else wf_i2v.get("750", {}).get("inputs", {}).get("value", "?")
        print(t("minimax_loaded_config", unet=unet_disp, turbo=turbo_disp, steps=steps_disp))


    t2i_presets = {}
    if not os.path.exists(t2i_presets_path):
        models_dir = get_comfy_models_dir()
        if models_dir:
            print(t("presets_not_found_autoscan"))
            build_or_update_catalog(models_dir, presets_path=t2i_presets_path)

    if os.path.exists(t2i_presets_path):
        try:
            with open(t2i_presets_path, "r", encoding="utf-8") as pf:
                t2i_presets = json.load(pf)
        except Exception as pe:
            print(t("presets_load_error", error=pe))

    # =========================================================================
    # PHASE 1: Screenwriting & Character Prompting (LM Studio)
    # =========================================================================
    # Initialize screenplay variables
    active_variables = {}
    root_vars = screenplay.get("variablen") or screenplay.get("variables") or {}
    if isinstance(root_vars, dict):
        active_variables.update(root_vars)

    characters_list = screenplay.get("charaktere") or screenplay.get("characters") or []
    for c in characters_list:
        c_name = c.get("name", "").strip()
        c_outfit = c.get("outfit") or c.get("kleidung") or c.get("status") or c.get("wardrobe")
        if c_outfit and c_name:
            var_key = f"outfit_{re.sub(r'[^a-zA-Z0-9]', '_', c_name.lower())}"
            if var_key not in active_variables:
                active_variables[var_key] = str(c_outfit)

    if active_variables:
        var_summary = ", ".join(f"{k}='{v}'" for k, v in active_variables.items())
        print(t("variables_initialized", count=len(active_variables), vars=var_summary))

    scenes_list = screenplay.get("szenen") or screenplay.get("scenes") or []

    # Check if LM Studio is actually needed for any character or scene
    chars_needing_llm = []
    for i, char in enumerate(characters_list):
        char_name = char.get("name", f"actor_{i+1}").strip()
        safe_name = re.sub(r'[\\/*?:"<>| ]', '_', char_name)
        char_file = os.path.join(characters_dir, f"{safe_name}.png")
        if os.path.exists(char_file):
            continue
        auto_prompt = not (
            char.get("ki_prompt_generieren") is False or 
            char.get("auto_prompt") is False or 
            char.get("generate_prompt") is False
        )
        if auto_prompt and not char.get("prompt"):
            chars_needing_llm.append(char)

    scenes_needing_llm = []
    for idx, scene in enumerate(scenes_list):
        auto_prompt = not (
            scene.get("ki_prompt_generieren") is False or 
            scene.get("auto_prompt") is False or 
            scene.get("generate_prompt") is False
        )
        existing_p = (scene.get("prompt") or scene.get("idea") or scene.get("idee") or "").strip()
        has_minimax_prompt = bool("summary:" in existing_p.lower() or "[shot 1]:" in existing_p.lower())
        if auto_prompt and not has_minimax_prompt:
            scenes_needing_llm.append(scene)

    needs_llm = bool(chars_needing_llm or scenes_needing_llm)
    if needs_llm:
        print(t("phase1_start"))
        lms_load()
    else:
        print(t("phase1_header_skip", file=os.path.basename(target_load_path)))

    prepared_scenes = []
    try:
        # 1. Generate/optimize character prompts via AI (if not already cached)
        if chars_needing_llm:
            print(t("phase1_developing_chars"))
            for i, char in enumerate(characters_list):
                char_name = char.get("name", f"actor_{i+1}").strip()
                safe_name = re.sub(r'[\\/*?:"<>| ]', '_', char_name)
                char_file = os.path.join(characters_dir, f"{safe_name}.png")

                # If character image already exists in folder, skip prompt generation
                if os.path.exists(char_file):
                    print(t("char_already_exists_skip_prompt", name=char_name, file=char_file))
                    continue

                preset_name = char.get("modell") or char.get("preset") or char.get("model") or t2i_presets.get("default", "anima_catpony")
                presets_dict = t2i_presets.get("presets", {})
                preset = presets_dict.get(preset_name, {})

                auto_prompt = not (
                    char.get("ki_prompt_generieren") is False or 
                    char.get("auto_prompt") is False or 
                    char.get("generate_prompt") is False
                )
                if not auto_prompt:
                    print(t("char_keep_manual_prompt", name=char_name))
                    continue
                dummy_defaults = [
                    "a brave protagonist with a determined expression",
                    "ein mutiger protagonist mit entschlossenem blick"
                ]
                existing_p = (char.get("prompt") or "").strip().lower().rstrip(".! ")
                if existing_p and existing_p not in dummy_defaults:
                    continue

                first_scene_id = get_character_first_scene(char, scenes_list)
                char_active_vars = get_variables_for_scene(screenplay, first_scene_id)
                if "first_scene" not in char and "erste_szene" not in char:
                    char["first_scene"] = first_scene_id

                print(t("char_optimizing_prompt", name=char_name, preset=preset_name))
                ki_char_prompt = ask_lm_studio_character(char, screenplay, preset_name, preset, active_variables=char_active_vars)
                char["prompt"] = ki_char_prompt
                print(t("char_new_prompt", name=char_name, prompt=ki_char_prompt[:90]))

        # 2. Generate Minimax scene prompts with sequence grouping & previous shot context
        if scenes_needing_llm:
            print(t("phase1_writing_scenes"))
        previous_shot_info = None
        scenes_list = screenplay.get("szenen") or screenplay.get("scenes") or []
        for idx, scene in enumerate(scenes_list):
            scene_id = scene.get("id", idx + 1)

            # Bilingual sequence / bundle / location grouping
            seq_name = (
                scene.get("sequenz") or 
                scene.get("sequence") or 
                scene.get("scene_group") or 
                scene.get("bundle") or 
                scene.get("group")
            )
            loc_name = (
                scene.get("ort") or 
                scene.get("location") or 
                scene.get("setting")
            )

            # Bilingual continuity flags
            direct_continuation = bool(
                scene.get("direkter_anschluss") or 
                scene.get("direct_continuation") or 
                scene.get("match_cut")
            )
            same_scene = bool(
                scene.get("gleiche_szene") or 
                scene.get("same_scene") or 
                scene.get("angle_change") or 
                scene.get("shot_reverse_shot")
            )
            use_previous_scene = bool(
                scene.get("anschluss_an_vorherige_szene") or 
                scene.get("continuity_environment") or 
                scene.get("environmental_continuity") or 
                scene.get("continuity")
            )

            # Detect if this shot belongs to the same ongoing sequence/scene
            is_same_seq = False
            if previous_shot_info:
                prev_seq = previous_shot_info.get("sequence")
                prev_loc = previous_shot_info.get("location")
                if seq_name and prev_seq and str(seq_name).strip().lower() == str(prev_seq).strip().lower():
                    is_same_seq = True
                elif loc_name and prev_loc and str(loc_name).strip().lower() == str(prev_loc).strip().lower():
                    is_same_seq = True
                elif same_scene or direct_continuation:
                    is_same_seq = True
                elif use_previous_scene and (not seq_name or seq_name == prev_seq):
                    is_same_seq = True

            # If within the same sequence or same scene, automatically maintain environment reference
            if (is_same_seq or same_scene) and not direct_continuation:
                if scene.get("anschluss_an_vorherige_szene") is not False and scene.get("continuity_environment") is not False:
                    use_previous_scene = True

            # Check for scene-level variable updates (bilingual)
            scene_var_updates = (
                scene.get("variablen_update") or 
                scene.get("variables_update") or 
                scene.get("set_variables") or 
                scene.get("variablen") or 
                scene.get("variables") or 
                {}
            )
            if isinstance(scene_var_updates, dict) and scene_var_updates:
                active_variables.update(scene_var_updates)
                update_summary = ", ".join(f"{k}='{v}'" for k, v in scene_var_updates.items())
                print(t("variables_updated", id=scene_id, updates=update_summary))

            # Check for per-scene character status updates (bilingual)
            char_status_updates = (
                scene.get("charakter_status") or 
                scene.get("character_status") or 
                scene.get("character_states") or 
                {}
            )

            # Interpolate variables in scene idea: {variable_name}
            raw_scene_idea = scene.get("idee") or scene.get("idea") or scene.get("prompt") or ""
            scene_idea = interpolate_variables(raw_scene_idea, active_variables)

            # Build context of the previous shot for LM Studio
            prev_shot_ctx = None
            if previous_shot_info:
                prev_shot_ctx = {
                    "id": previous_shot_info["id"],
                    "summary": previous_shot_info["summary"],
                    "same_sequence": is_same_seq,
                    "same_scene": same_scene,
                    "sequence": seq_name or previous_shot_info.get("sequence"),
                    "location": loc_name or previous_shot_info.get("location")
                }

            seq_info = {
                "sequence": seq_name,
                "location": loc_name
            }

            auto_prompt = not (
                scene.get("ki_prompt_generieren") is False or 
                scene.get("auto_prompt") is False or 
                scene.get("generate_prompt") is False
            )

            existing_p = (scene.get("prompt") or scene.get("idea") or scene.get("idee") or "").strip()
            has_minimax_prompt = bool("summary:" in existing_p.lower() or "[shot 1]:" in existing_p.lower())
            
            raw_scene_loras = scene.get("loras") or scene.get("lora") or []
            if isinstance(raw_scene_loras, str):
                existing_scene_loras = [l.strip() for l in raw_scene_loras.split(",") if l.strip()]
            elif isinstance(raw_scene_loras, list):
                existing_scene_loras = list(raw_scene_loras)
            else:
                existing_scene_loras = []

            # Resolve characters active in this specific scene
            scene_chars = resolve_scene_characters(scene, characters_list)

            if not auto_prompt and existing_p:
                if needs_llm:
                    print(t("scene_keep_manual_prompt", id=scene_id))
                minimax_prompt = existing_p
                calculated_duration = (
                    scene.get("dauer_sekunden") or 
                    scene.get("duration_seconds") or 
                    scene.get("duration") or 
                    scene.get("dauer") or 
                    5
                )
                final_scene_loras = existing_scene_loras
            elif has_minimax_prompt:
                if needs_llm:
                    print(t("scene_already_prompted_skip", id=scene_id))
                minimax_prompt = existing_p
                calculated_duration = (
                    scene.get("dauer_sekunden") or 
                    scene.get("duration_seconds") or 
                    scene.get("duration") or 
                    scene.get("dauer") or 
                    5
                )
                final_scene_loras = existing_scene_loras
            else:
                minimax_prompt, calculated_duration, selected_loras = ask_lm_studio(
                    scene_idea,
                    scene_chars,
                    use_previous_scene=use_previous_scene,
                    direct_continuation=direct_continuation,
                    active_variables=active_variables,
                    character_states=char_status_updates,
                    previous_shot_context=prev_shot_ctx,
                    same_scene=same_scene,
                    sequence_info=seq_info,
                    t2i_presets=t2i_presets
                )
                final_scene_loras = existing_scene_loras if existing_scene_loras else selected_loras

            # Extract shot summary for the next shot's continuity context
            cur_summary = scene.get("summary")
            if not cur_summary:
                m_sum = re.search(r'summary:\s*([^\n]+(?:\n[^\n]+)?)', minimax_prompt, re.IGNORECASE)
                cur_summary = m_sum.group(1).strip() if m_sum else scene_idea

            cur_soundscape = scene.get("soundscape") or scene.get("overall_soundscape") or ""

            previous_shot_info = {
                "id": scene_id,
                "summary": cur_summary,
                "sequence": seq_name,
                "location": loc_name
            }

            # Update scene dictionary in screenplay with generated prompt & duration & loras
            scene["prompt"] = minimax_prompt
            scene["dauer_sekunden"] = calculated_duration
            if cur_summary and "summary" not in scene:
                scene["summary"] = cur_summary
            if cur_soundscape and "soundscape" not in scene:
                scene["soundscape"] = cur_soundscape
            if final_scene_loras:
                scene["loras"] = final_scene_loras
            if seq_name and "sequenz" not in scene and "sequence" not in scene:
                scene["sequence"] = seq_name
            if loc_name and "ort" not in scene and "location" not in scene:
                scene["location"] = loc_name

            prepared_scenes.append({
                "id": scene_id,
                "prompt": minimax_prompt,
                "summary": cur_summary,
                "soundscape": cur_soundscape,
                "dauer": calculated_duration,
                "loras": final_scene_loras,
                "characters": scene_chars,
                "nutze_vorherige_szene": use_previous_scene,
                "direkter_anschluss": direct_continuation,
                "gleiche_szene": same_scene,
                "sequenz": seq_name,
                "ort": loc_name,
                "variables": dict(active_variables),
                "idee": scene_idea,
                "turbo": scene.get("turbo"),
                "steps": scene.get("steps") or scene.get("schritte"),
                "megapixels": scene.get("megapixels") or scene.get("resolution") or scene.get("aufloesung"),
                "upscale": scene.get("upscale") or scene.get("hochskalieren")
            })

            continuity_badges = []
            if direct_continuation:
                continuity_badges.append(t("scene_continuity_seamless"))
            elif same_scene:
                continuity_badges.append(t("scene_continuity_same_scene"))
            elif use_previous_scene:
                continuity_badges.append(t("scene_continuity_ref"))
            if seq_name:
                continuity_badges.append(t("scene_sequence_badge", seq=seq_name))

            anschluss_txt = "".join(continuity_badges)
            if needs_llm:
                print(t("scene_written", id=scene_id, dauer=calculated_duration, anschluss=anschluss_txt))
            else:
                print(t("scene_ready", id=scene_id, dauer=calculated_duration, anschluss=anschluss_txt))

        # Save extended screenplay with AI-generated character & scene prompts to the project directory
        if needs_llm:
            try:
                with open(local_screenplay_copy, "w", encoding="utf-8") as sf:
                    json.dump(screenplay, sf, indent=2, ensure_ascii=False)
                print(t("screenplay_extended_saved", path=local_screenplay_copy))
            except Exception as se:
                print(f"⚠️ Could not save extended screenplay: {se}")
    finally:
        # Immediately unload LLM as soon as all screenplay prompts are written!
        if needs_llm:
            lms_unload()

    # =========================================================================
    # PHASE 2: Actor Casting (T2I in ComfyUI)
    # =========================================================================
    print(t("phase2_start"))
    try:
        urllib.request.urlopen(f"http://{SERVER_ADDRESS}/system_stats", timeout=3)
    except Exception:
        print(t("comfyui_unreachable", server=SERVER_ADDRESS))
        time.sleep(5)
        return

    # Build lookup map for resolving reference characters by ID or name
    char_lookup = {}
    for idx_c, c_item in enumerate(characters_list):
        c_id = c_item.get("id", idx_c + 1)
        char_lookup[str(c_id)] = c_item
        if c_item.get("name"):
            char_lookup[c_item.get("name").strip().lower()] = c_item

    for i, char in enumerate(characters_list):
        char_name = char.get("name", f"actor_{i+1}").strip()
        safe_name = re.sub(r'[\\/*?:"<>| ]', '_', char_name)
        char_file = os.path.join(characters_dir, f"{safe_name}.png")

        # Check if character already exists in project folder!
        if os.path.exists(char_file):
            with open(char_file, "rb") as cf:
                char_img_data = cf.read()
            uploaded_name = upload_file(char_img_data, f"{safe_name}.png", "image/png")
            char["echter_dateiname"] = uploaded_name
            print(t("char_already_exists_skip_t2i", name=char_name, file=char_file))
            continue

        # Clean up any leftover I2I nodes from previous characters
        for k in ["950", "951"]:
            if k in wf_t2i:
                del wf_t2i[k]

        # Check for optional character reference link (I2I style transfer / aging)
        ref_char_val = (
            char.get("reference_id") or 
            char.get("referenz_id") or 
            char.get("reference_character") or 
            char.get("referenz_charakter") or
            char.get("parent_character")
        )
        has_ref = False
        ref_char_name = ""
        denoise_val = 1.0

        if ref_char_val is not None:
            ref_key = str(ref_char_val).strip()
            target_ref_char = char_lookup.get(ref_key) or char_lookup.get(ref_key.lower())
            if target_ref_char:
                ref_char_name = target_ref_char.get("name", f"actor_{ref_key}").strip()
                ref_safe = re.sub(r'[\\/*?:"<>| ]', '_', ref_char_name)
                ref_file = os.path.join(characters_dir, f"{ref_safe}.png")
                if os.path.exists(ref_file):
                    try:
                        with open(ref_file, "rb") as rf:
                            ref_img_data = rf.read()
                        uploaded_ref_name = upload_file(ref_img_data, f"ref_{ref_safe}.png", "image/png")
                        
                        raw_denoise = char.get("denoise") or char.get("denoising") or char.get("denoising_strength") or 0.65
                        try:
                            denoise_val = max(0.05, min(1.0, float(raw_denoise)))
                        except (ValueError, TypeError):
                            denoise_val = 0.65

                        # Node 950: Load reference image
                        wf_t2i["950"] = {
                            "inputs": {"image": uploaded_ref_name},
                            "class_type": "LoadImage"
                        }
                        # Node 951: Encode reference into latent space using VAE (Node 15)
                        wf_t2i["951"] = {
                            "inputs": {
                                "pixels": ["950", 0],
                                "vae": ["15", 0]
                            },
                            "class_type": "VAEEncode"
                        }
                        wf_t2i["19"]["inputs"]["latent_image"] = ["951", 0]
                        wf_t2i["19"]["inputs"]["denoise"] = denoise_val
                        has_ref = True
                    except Exception as re_err:
                        print(f"   ⚠️ Could not setup reference image for '{ref_char_name}': {re_err}")
                else:
                    print(t("char_ref_not_found", ref_id=ref_char_val, ref_name=ref_char_name))
            else:
                print(t("char_ref_not_found", ref_id=ref_char_val, ref_name=ref_char_val))

        if not has_ref:
            # Standard Text-to-Image (T2I)
            wf_t2i["19"]["inputs"]["latent_image"] = ["28", 0]
            wf_t2i["19"]["inputs"]["denoise"] = 1.0

        # Character does not exist yet -> generate anew
        preset_name = char.get("modell") or char.get("preset") or char.get("model") or t2i_presets.get("default", "anima_catpony")
        presets_dict = t2i_presets.get("presets", {})
        preset = presets_dict.get(preset_name)

        if not preset and presets_dict:
            default_key = t2i_presets.get("default", list(presets_dict.keys())[0])
            print(t("model_unknown_fallback", model=preset_name, default=default_key))
            preset_name = default_key
            preset = presets_dict.get(default_key, {})

        if preset:
            if "unet_name" in preset and "44" in wf_t2i:
                wf_t2i["44"]["inputs"]["unet_name"] = preset["unet_name"]
            if "clip_name" in preset and "45" in wf_t2i:
                wf_t2i["45"]["inputs"]["clip_name"] = preset["clip_name"]
            if "clip_type" in preset and "45" in wf_t2i:
                wf_t2i["45"]["inputs"]["type"] = preset["clip_type"]
            if "vae_name" in preset and "15" in wf_t2i:
                wf_t2i["15"]["inputs"]["vae_name"] = preset["vae_name"]
            if "steps" in preset and "19" in wf_t2i:
                wf_t2i["19"]["inputs"]["steps"] = preset["steps"]
            if "cfg" in preset and "19" in wf_t2i:
                wf_t2i["19"]["inputs"]["cfg"] = preset["cfg"]
            if "sampler_name" in preset and "19" in wf_t2i:
                wf_t2i["19"]["inputs"]["sampler_name"] = preset["sampler_name"]
            if "scheduler" in preset and "19" in wf_t2i:
                wf_t2i["19"]["inputs"]["scheduler"] = preset["scheduler"]
            if "aspect_ratio" in preset and "54" in wf_t2i:
                wf_t2i["54"]["inputs"]["aspect_ratio"] = preset["aspect_ratio"]
            if "megapixels" in preset and "54" in wf_t2i:
                wf_t2i["54"]["inputs"]["megapixels"] = preset["megapixels"]
            
            neg_prompt = char.get("negative_prompt") or preset.get("negative_prompt")
            if neg_prompt is not None and "12" in wf_t2i:
                wf_t2i["12"]["inputs"]["text"] = neg_prompt

        # Dynamically attach LoRAs for this character
        char_loras = char.get("loras") or char.get("lora") or []
        if isinstance(char_loras, (str, dict)):
            char_loras = [char_loras]

        keys_to_clean = [k for k in list(wf_t2i.keys()) if k.startswith("800")]
        for k in keys_to_clean:
            del wf_t2i[k]

        current_model = ["44", 0]
        current_clip = ["45", 0]
        applied_loras_info = []
        extra_trigger_words = []
        lora_presets_dict = t2i_presets.get("lora_presets", {})

        for l_idx, lora_item in enumerate(char_loras):
            if isinstance(lora_item, str):
                l_name = lora_item
                custom_strength = None
            elif isinstance(lora_item, dict):
                l_name = lora_item.get("name") or lora_item.get("lora")
                custom_strength = lora_item.get("strength")
            else:
                continue

            if not l_name:
                continue

            if l_name in lora_presets_dict:
                l_cfg = lora_presets_dict[l_name]
                real_file = l_cfg["lora_name"]
                s_model = custom_strength if custom_strength is not None else l_cfg.get("strength_model", 1.0)
                s_clip = custom_strength if custom_strength is not None else l_cfg.get("strength_clip", s_model)
                triggers = l_cfg.get("trigger_words", "")

                compatible = l_cfg.get("kompatible_modelle")
                if compatible and preset_name not in compatible:
                    is_fam_compat = any(
                        (c.startswith("anima") and preset_name.startswith("anima")) or
                        (c.startswith("krea") and preset_name.startswith("krea")) or
                        (c.startswith("sdxl") and (preset_name.startswith("anima") or preset_name.startswith("sdxl"))) or
                        (c.startswith("zimage") and preset_name.startswith("zimage"))
                        for c in compatible
                    )
                    if not is_fam_compat:
                        print(t("lora_compat_notice", lora=l_name, models=', '.join(compatible), chosen=preset_name))
            else:
                real_file = l_name
                s_model = custom_strength if custom_strength is not None else 1.0
                s_clip = s_model
                triggers = ""

            if triggers:
                extra_trigger_words.append(triggers)

            node_id = f"800{l_idx}"
            wf_t2i[node_id] = {
                "inputs": {
                    "model": current_model,
                    "clip": current_clip,
                    "lora_name": real_file,
                    "strength_model": s_model,
                    "strength_clip": s_clip
                },
                "class_type": "LoraLoader"
            }
            current_model = [node_id, 0]
            current_clip = [node_id, 1]
            applied_loras_info.append(f"{l_name} ({s_model})")

        wf_t2i["19"]["inputs"]["model"] = current_model
        wf_t2i["11"]["inputs"]["clip"] = current_clip
        wf_t2i["12"]["inputs"]["clip"] = current_clip

        raw_char_prompt = char.get("prompt") or char.get("description") or char.get("beschreibung") or ""
        first_scene_id = get_character_first_scene(char, scenes_list)
        char_active_vars = get_variables_for_scene(screenplay, first_scene_id)
        if "first_scene" not in char and "erste_szene" not in char:
            char["first_scene"] = first_scene_id
        full_prompt = interpolate_variables(raw_char_prompt, char_active_vars)
        print(t("char_casting_variables_used", name=char_name, scene=first_scene_id))
        if extra_trigger_words:
            new_triggers = [tw for tw in extra_trigger_words if tw.lower() not in full_prompt.lower()]
            if new_triggers:
                full_prompt = full_prompt.rstrip(", ") + ", " + ", ".join(new_triggers)

        steps_info = wf_t2i["19"]["inputs"].get("steps", "?")
        cfg_info = wf_t2i["19"]["inputs"].get("cfg", "?")
        lora_status_str = f" | LoRAs: {', '.join(applied_loras_info)}" if applied_loras_info else ""
        if has_ref:
            print(t("char_casting_running_ref", num=i+1, name=char_name, ref_id=ref_char_val, ref_name=ref_char_name, denoise=denoise_val, model=preset_name, loras=lora_status_str, steps=steps_info, cfg=cfg_info))
        else:
            print(t("char_casting_running", num=i+1, name=char_name, model=preset_name, loras=lora_status_str, steps=steps_info, cfg=cfg_info))

        wf_t2i["11"]["inputs"]["text"] = full_prompt
        wf_t2i["19"]["inputs"]["seed"] = random.randint(1, 999999999999999)
        
        res = queue_prompt(wf_t2i)
        prompt_id = res['prompt_id']
        
        char_saved = False
        while True:
            history = get_history(prompt_id)
            if prompt_id in history:
                prompt_info = history[prompt_id]
                status_info = prompt_info.get("status", {})
                if status_info.get("status_str") == "error":
                    err_msg = "Unknown ComfyUI error"
                    for msg in status_info.get("messages", []):
                        if msg[0] == "execution_error":
                            err_msg = msg[1].get("exception_message", str(msg[1]))
                    print(f"   ❌ ComfyUI Error during character casting for '{char_name}': {err_msg.strip()}")
                    break

                outputs = prompt_info.get('outputs', {})
                for node_id in outputs:
                    if 'images' in outputs[node_id]:
                        img_info = outputs[node_id]['images'][0]
                        img_data = get_image(img_info['filename'], img_info['subfolder'], img_info['type'])
                        
                        # Build Civitai / A1111 parameter text for character casting portrait
                        model_name_used = preset.get("unet_name", preset_name) if preset else preset_name
                        civitai_actor_params = (
                            f"{full_prompt}\n"
                            f"Negative prompt: {neg_prompt or ''}\n"
                            f"Steps: {steps_info}, Sampler: {wf_t2i['19']['inputs'].get('sampler_name', 'er_sde')}, "
                            f"CFG scale: {cfg_info}, Seed: {wf_t2i['19']['inputs']['seed']}, "
                            f"Size: {wf_t2i.get('54', {}).get('inputs', {}).get('aspect_ratio', '3:4')}, "
                            f"Model: {model_name_used}"
                        )
                        if applied_loras_info:
                            civitai_actor_params += f", LoRAs: {', '.join(applied_loras_info)}"
                        if has_ref:
                            civitai_actor_params += f", I2I Reference: #{ref_char_val} ({ref_char_name}), Denoise: {denoise_val}"

                        # Save image with embedded Civitai parameters and ComfyUI workflow JSON
                        save_image_with_metadata(img_data, char_file, prompt_workflow=wf_t2i, a1111_params_text=civitai_actor_params)

                        with open(char_file, "rb") as cf:
                            saved_img_bytes = cf.read()

                        uploaded_name = upload_file(saved_img_bytes, f"{safe_name}.png", "image/png")
                        char["echter_dateiname"] = uploaded_name
                        char_saved = True
                        print(t("char_generated_saved", name=char_name, file=char_file))
                        break
                break
            time.sleep(2)

        if not char_saved and not os.path.exists(char_file):
            print(f"⚠️ Character casting for '{char_name}' could not be completed. Stopping generation to prevent downstream errors.")
            return

    # Free T2I casting models (Anima, WanVAE, BiRefNet) from VRAM before starting video generation
    free_comfyui_memory(unload_models=True, free_memory=True)

    # =========================================================================
    # PHASE 3: Video Production (Minimax Studio)
    # =========================================================================
    print(t("phase3_start"))
    last_video_data = None
    last_video_path = None

    for idx, scene_data in enumerate(prepared_scenes):
        szene_id = scene_data["id"]
        target_path = os.path.join(scenes_dir, f"Szene_{szene_id:02d}.mp4")

        # Targeted Scene Re-Shooting Filter (--scene <id>):
        # Skip all non-target scenes while preserving last_video_data for match cuts
        if target_scene_id is not None:
            is_target = False
            try:
                if int(szene_id) == int(target_scene_id):
                    is_target = True
            except (ValueError, TypeError):
                if str(szene_id).lower() == str(target_scene_id).lower():
                    is_target = True

            if not is_target:
                if os.path.exists(target_path):
                    try:
                        with open(target_path, "rb") as vf:
                            last_video_data = vf.read()
                        last_video_path = target_path
                    except Exception:
                        pass
                continue
            else:
                # Force reshoot for target scene by removing previous video
                if os.path.exists(target_path):
                    try:
                        os.remove(target_path)
                        print(f"   🔄 Entferne alte Fassung von Szene {szene_id} für Neuaufnahme...")
                    except Exception as rm_err:
                        print(f"   ⚠️ Konnte alte Szene nicht löschen: {rm_err}")

        # Smart Scene Caching: Skip scene if it is already rendered on disk
        if os.path.exists(target_path):
            print(t("scene_already_exists_skip", id=szene_id, file=target_path))
            try:
                with open(target_path, "rb") as vf:
                    last_video_data = vf.read()
                last_video_path = target_path
            except Exception as read_err:
                print(f"   ⚠️ Could not load existing video data for Scene {szene_id}: {read_err}")
            continue

        print(t("scene_shooting", id=szene_id))
        
        # --- Director's Control: Scene-specific Turbo, Steps, Resolution & Upscaling ---
        scene_turbo_val = scene_data.get("turbo")
        scene_steps_val = scene_data.get("steps")
        scene_mp_val = scene_data.get("megapixels")
        scene_upscale_val = scene_data.get("upscale")

        # 1. Turbo & Steps resolution
        is_turbo_disabled = (scene_turbo_val is False) or (str(scene_turbo_val).strip().lower() in ["off", "false", "no", "0", "disable", "disabled", "hq"])
        turbo_active = False if is_turbo_disabled else (True if configured_turbo else False)

        if "674" in wf_i2v and "inputs" in wf_i2v["674"]:
            if "lora_1" in wf_i2v["674"]["inputs"]:
                wf_i2v["674"]["inputs"]["lora_1"]["on"] = turbo_active

        # Determine steps: scene_steps > configured_steps or defaults (8 for turbo, 20 for non-turbo HQ)
        if scene_steps_val is not None and str(scene_steps_val).strip():
            try:
                active_steps = int(scene_steps_val)
            except (ValueError, TypeError):
                active_steps = 20 if not turbo_active else (int(configured_steps) if configured_steps else 8)
        else:
            if not turbo_active:
                active_steps = 20
            else:
                active_steps = int(configured_steps) if configured_steps is not None else int(wf_i2v.get("750", {}).get("inputs", {}).get("value", 8))

        if "750" in wf_i2v and "inputs" in wf_i2v["750"]:
            wf_i2v["750"]["inputs"]["value"] = active_steps

        # 2. Native Resolution (Megapixels in Node 115)
        # Default: 0.25 (approx. 672x384 in 16:9), Wide/Detail: 0.45 (approx. 896x512), Native HD: 0.75 (approx. 1152x648)
        active_mp = 0.25
        if scene_mp_val is not None and str(scene_mp_val).strip():
            try:
                active_mp = float(scene_mp_val)
            except (ValueError, TypeError):
                s_mp_lower = str(scene_mp_val).strip().lower()
                if s_mp_lower in ["detail", "high", "totale", "wide", "0.45"]:
                    active_mp = 0.45
                elif s_mp_lower in ["native_hd", "hd", "ultra", "0.75"]:
                    active_mp = 0.75
                else:
                    active_mp = 0.25

        if "115" in wf_i2v and "inputs" in wf_i2v["115"]:
            wf_i2v["115"]["inputs"]["megapixels"] = active_mp

        # 3. Upscaling Bypass (Node 702 & 761)
        is_upscale_off = (scene_upscale_val is False) or (str(scene_upscale_val).strip().lower() in ["off", "none", "false", "bypass", "native", "0"])
        if "702" in wf_i2v and "inputs" in wf_i2v["702"]:
            if is_upscale_off:
                # Direct feed from VAEDecode (node 703) -> bypasses RealESRGAN
                wf_i2v["702"]["inputs"]["images"] = ["703", 0]
            else:
                # Standard feed from ImageUpscaleWithModel (node 761)
                wf_i2v["702"]["inputs"]["images"] = ["761", 0]

        turbo_status_str = "AN" if turbo_active else "AUS (HQ)"
        upscale_status_str = "AUS (Nativ)" if is_upscale_off else "2x RealESRGAN"
        print(t("scene_shooting_settings", id=szene_id, turbo=turbo_status_str, steps=active_steps, mp=active_mp, upscale=upscale_status_str))

        # Reset dynamic scene LoRAs from node 674 (keep base lora_1 intact)
        if "674" in wf_i2v and "inputs" in wf_i2v["674"]:
            keys_to_remove_674 = [k for k in wf_i2v["674"]["inputs"].keys() if re.match(r"^lora_[2-9]\d*$", k)]
            for k in keys_to_remove_674:
                del wf_i2v["674"]["inputs"][k]

        scene_loras = scene_data.get("loras") or scene_data.get("lora") or []
        if isinstance(scene_loras, str):
            scene_loras = [l.strip() for l in scene_loras.split(",") if l.strip()]

        applied_scene_loras = []
        extra_scene_triggers = []
        lora_presets_dict = t2i_presets.get("lora_presets", {}) if t2i_presets else {}

        if "674" in wf_i2v and "inputs" in wf_i2v["674"]:
            for sl_idx, sl_item in enumerate(scene_loras):
                if isinstance(sl_item, str):
                    sl_key = sl_item.strip()
                    sl_strength = None
                elif isinstance(sl_item, dict):
                    sl_key = sl_item.get("key") or sl_item.get("name") or sl_item.get("lora")
                    sl_strength = sl_item.get("strength")
                else:
                    continue

                if not sl_key:
                    continue

                if sl_key in lora_presets_dict:
                    l_cfg = lora_presets_dict[sl_key]
                    real_file = l_cfg.get("lora_name", "")
                    s_model = sl_strength if sl_strength is not None else l_cfg.get("strength_model", 1.0)
                    triggers = l_cfg.get("trigger_words", "")
                else:
                    real_file = sl_key
                    s_model = sl_strength if sl_strength is not None else 1.0
                    triggers = ""
                    for pk, pv in lora_presets_dict.items():
                        if pk.lower() == sl_key.lower():
                            l_cfg = pv
                            real_file = l_cfg.get("lora_name", "")
                            s_model = sl_strength if sl_strength is not None else l_cfg.get("strength_model", 1.0)
                            triggers = l_cfg.get("trigger_words", "")
                            sl_key = pk
                            break

                if real_file:
                    next_slot = f"lora_{sl_idx + 2}"
                    wf_i2v["674"]["inputs"][next_slot] = {
                        "on": True,
                        "lora": real_file,
                        "strength": s_model
                    }
                    applied_scene_loras.append(f"{sl_key} ({s_model})")
                    if triggers and triggers.lower() not in scene_data["prompt"].lower():
                        extra_scene_triggers.append(triggers)

        if applied_scene_loras:
            print(t("scene_loras_active", count=len(applied_scene_loras), loras=", ".join(applied_scene_loras)))

        raw_scene_chars = scene_data.get("characters") or resolve_scene_characters(scene_data, characters_list)
        resolved_scene_chars = []
        if raw_scene_chars:
            for sc in raw_scene_chars:
                if isinstance(sc, dict):
                    resolved_scene_chars.append(sc)
                elif isinstance(sc, str):
                    matched = char_lookup.get(sc.strip().lower()) or char_lookup.get(sc.strip())
                    if matched:
                        resolved_scene_chars.append(matched)
                    else:
                        resolved_scene_chars.append({"name": sc.strip()})
                else:
                    resolved_scene_chars.append(sc)

        final_scene_prompt = scene_data["prompt"]
        if extra_scene_triggers:
            final_scene_prompt = f"{final_scene_prompt}\n\n[Scene enhancements: {', '.join(extra_scene_triggers)}]"
        
        # Assemble full Minimax template (subject_definitions, summary, detailed_description, soundscape, non_diegetic_music)
        chars_for_envelope = resolved_scene_chars if resolved_scene_chars else characters_list
        final_scene_prompt = build_minimax_api_prompt(final_scene_prompt, characters=chars_for_envelope, scene_data=scene_data)
        wf_i2v["138"]["inputs"]["value"] = final_scene_prompt
        
        keys_to_remove = [k for k in wf_i2v["136"]["inputs"].keys() if k.startswith("ref_images.ref_image_") or k.startswith("ref_videos.")]
        for k in keys_to_remove:
            del wf_i2v["136"]["inputs"][k]
        for k in ["687", "9100", "9200", "9201", "9202", "9203"]:
            if k in wf_i2v:
                del wf_i2v[k]
        
        current_cond_node = "648"
        wf_i2v["126"]["inputs"]["conditioning"] = ["648", 0]
            
        # Clean up any leftover 900X character image loader nodes
        for k in [k for k in list(wf_i2v.keys()) if re.match(r"^900\d+$", k)]:
            del wf_i2v[k]

        if resolved_scene_chars:
            char_names_log = ", ".join(c.get("name", f"Actor_{c_idx+1}") for c_idx, c in enumerate(resolved_scene_chars) if isinstance(c, dict))
            if char_names_log:
                print(f"   🎭 Scene {szene_id} active cast: {char_names_log}")
            valid_ref_idx = 0
            for i, char in enumerate(resolved_scene_chars):
                fallback_name = (char.get("name") if isinstance(char, dict) else str(char)) or f"actor_{i+1}"
                safe_char_name = re.sub(r'[\\/*?:"<>| ]', '_', fallback_name)
                
                # Retrieve uploaded filename, or upload from disk if exists
                char_file_name = char.get("echter_dateiname") if isinstance(char, dict) else None
                if not char_file_name:
                    local_char_file = os.path.join(characters_dir, f"{safe_char_name}.png")
                    if os.path.exists(local_char_file):
                        try:
                            with open(local_char_file, "rb") as cf:
                                uploaded_name = upload_file(cf.read(), f"{safe_char_name}.png", "image/png")
                            char_file_name = uploaded_name
                            if isinstance(char, dict):
                                char["echter_dateiname"] = uploaded_name
                        except Exception as up_err:
                            print(f"   ⚠️ Could not upload local image for '{fallback_name}': {up_err}")
                
                if not char_file_name:
                    print(f"   ⚠️ Warning: Character portrait '{safe_char_name}.png' not found! Skipping reference.")
                    continue

                node_id = f"900{valid_ref_idx}"
                wf_i2v[node_id] = {
                    "inputs": {"image": char_file_name},
                    "class_type": "LoadImage"
                }
                wf_i2v["136"]["inputs"][f"ref_images.ref_image_{valid_ref_idx}"] = [node_id, 0]
                valid_ref_idx += 1


            
        if scene_data["nutze_vorherige_szene"] and last_video_data is not None:
            uploaded_video = upload_file(last_video_data, "previous_scene.mp4", "video/mp4")
            # Limit reference video to 672x384 and 33 frames (VAE encoding <45s)
            wf_i2v["9100"] = {
                "inputs": {
                    "video": uploaded_video,
                    "force_rate": 0,
                    "custom_width": 672,
                    "custom_height": 384,
                    "frame_load_cap": 33,
                    "skip_first_frames": 0,
                    "select_every_nth": 2
                },
                "class_type": "VHS_LoadVideo"
            }
            wf_i2v["136"]["inputs"]["ref_videos.ref_video_0"] = ["9100", 0]
            print(t("scene_linking_prev"))

        # 1. Forward direct match cut via MiniMaxH3AddGuide (first_frame, frame_idx: 0)
        if scene_data.get("direkter_anschluss") and last_video_path is not None:
            print(t("scene_extracting_last_frame"))
            last_frame_bytes = extract_last_frame(last_video_path)
            if last_frame_bytes:
                uploaded_frame_name = upload_file(last_frame_bytes, f"last_frame_scene_{szene_id}.png", "image/png")
                wf_i2v["9200"] = {
                    "inputs": {"image": uploaded_frame_name},
                    "class_type": "LoadImage"
                }
                wf_i2v["9201"] = {
                    "inputs": {
                        "positive": [current_cond_node, 0],
                        "latent": ["682", 0],
                        "vae": ["119", 0],
                        "image": ["9200", 0],
                        "frame_idx": 0
                    },
                    "class_type": "MiniMaxH3AddGuide"
                }
                current_cond_node = "9201"
                print(t("scene_direct_connection_active", frame=uploaded_frame_name))
            else:
                print(t("scene_extract_last_frame_failed"))

        # 2. Backward direct match cut: If next scene already exists and requested match cut, anchor its start frame as our last frame (frame_idx: -1)
        if idx + 1 < len(prepared_scenes):
            next_scene_data = prepared_scenes[idx + 1]
            next_id = next_scene_data.get("id", idx + 2)
            next_match_cut = bool(
                next_scene_data.get("direkter_anschluss") or 
                next_scene_data.get("direct_continuation") or 
                next_scene_data.get("match_cut")
            )
            next_target_file = os.path.join(scenes_dir, f"Szene_{next_id:02d}.mp4")
            if next_match_cut and os.path.exists(next_target_file):
                print(t("scene_extracting_next_first_frame", next_id=next_id))
                next_first_frame_bytes = extract_video_frame(next_target_file, time_offset="00:00:00.000")
                if next_first_frame_bytes:
                    uploaded_next_frame = upload_file(next_first_frame_bytes, f"first_frame_scene_{next_id}.png", "image/png")
                    wf_i2v["9202"] = {
                        "inputs": {"image": uploaded_next_frame},
                        "class_type": "LoadImage"
                    }
                    wf_i2v["9203"] = {
                        "inputs": {
                            "positive": [current_cond_node, 0],
                            "latent": ["682", 0],
                            "vae": ["119", 0],
                            "image": ["9202", 0],
                            "frame_idx": -1
                        },
                        "class_type": "MiniMaxH3AddGuide"
                    }
                    current_cond_node = "9203"
                    print(t("scene_backward_connection_active", next_id=next_id, frame=uploaded_next_frame))

        wf_i2v["126"]["inputs"]["conditioning"] = [current_cond_node, 0]
        
        wf_i2v["142"]["inputs"]["seed"] = random.randint(1, 999999999999999)
        wf_i2v["132"]["inputs"]["value"] = scene_data["dauer"]

        res = queue_prompt(wf_i2v)
        prompt_id = res['prompt_id']
        print(t("scene_rendering_started"))
        
        while True:
            history = get_history(prompt_id)
            if prompt_id in history:
                prompt_info = history[prompt_id]
                status_info = prompt_info.get("status", {})
                if status_info.get("status_str") == "error":
                    err_msg = "Unknown ComfyUI error"
                    for msg in status_info.get("messages", []):
                        if msg[0] == "execution_error":
                            err_msg = msg[1].get("exception_message", str(msg[1]))
                    print(f"   ❌ ComfyUI Error during rendering of Scene {szene_id}: {err_msg.strip()}")
                    break

                outputs = prompt_info.get('outputs', {})
                for node_id in outputs:
                    for media_key in ['gifs', 'videos', 'images']:
                        if media_key in outputs[node_id]:
                            media_list = outputs[node_id][media_key]
                            if media_list and str(media_list[0]['filename']).endswith('.mp4'):
                                vid_info = media_list[0]
                                vid_data = get_image(vid_info['filename'], vid_info['subfolder'], vid_info['type'])
                                
                                # Save video in Projects/<film_name>/Scenes/
                                target_path = os.path.join(scenes_dir, f"Szene_{szene_id:02d}.mp4")
                                with open(target_path, "wb") as vf:
                                    vf.write(vid_data)
                                last_video_data = vid_data
                                last_video_path = target_path
                                
                                # Inject Civitai-compatible metadata tags into the scene MP4
                                scene_meta_desc = (
                                    f"Prompt: {scene_data['prompt']}\n"
                                    f"Duration: {scene_data['dauer']}s, Seed: {wf_i2v['142']['inputs']['seed']}, Model: minimax_h3"
                                )
                                inject_video_metadata(
                                    target_path,
                                    title=f"{film_name} - Scene {szene_id:02d}",
                                    description=scene_meta_desc,
                                    prompt_workflow_dict=wf_i2v
                                )

                                # Generate companion preview PNG for the scene with embedded Civitai metadata
                                scene_preview_path = os.path.join(scenes_dir, f"Szene_{szene_id:02d}_preview.png")
                                scene_unet = wf_i2v.get("620", {}).get("inputs", {}).get("unet_name", "") if wf_i2v else ""
                                scene_model = os.path.basename(scene_unet).replace(".safetensors", "") if scene_unet else "minimax_h3"
                                
                                # Resolve sampling parameters dynamically from workflow
                                sc_steps, sc_sampler, sc_scheduler, sc_cfg, sc_seed = get_workflow_sampling_params(wf_i2v)
                                if "142" in wf_i2v and "seed" in wf_i2v["142"].get("inputs", {}):
                                    sc_seed = wf_i2v["142"]["inputs"]["seed"]

                                # Collect scene LoRAs from workflow
                                sc_lora_files = []
                                for nid, node in wf_i2v.items():
                                    if not isinstance(node, dict):
                                        continue
                                    inputs = node.get("inputs", {})
                                    for k, v in inputs.items():
                                        if isinstance(v, dict) and "lora" in v and v.get("on", True):
                                            sc_lora_files.append(v["lora"])
                                    if "lora_name" in inputs:
                                        sc_lora_files.append(inputs["lora_name"])

                                sc_meta = build_civitai_resource_metadata(model_path=scene_unet, loras_list=sc_lora_files)
                                sc_parts = []
                                if sc_meta["model_hash"]:
                                    sc_parts.append(f"Model hash: {sc_meta['model_hash']}")
                                if sc_meta["lora_hashes"]:
                                    sc_parts.append(f"Lora hashes: \"{', '.join(sc_meta['lora_hashes'])}\"")
                                if sc_meta["civitai_resources"]:
                                    sc_parts.append(f"Civitai resources: {json.dumps(sc_meta['civitai_resources'], ensure_ascii=False)}")
                                sc_extra = (", " + ", ".join(sc_parts)) if sc_parts else ""

                                scene_a1111_params = (
                                    f"{scene_data['prompt']}\n"
                                    "Negative prompt: worst quality, low quality, blurry, distorted, deformed\n"
                                    f"Steps: {sc_steps}, Sampler: {sc_sampler}, Schedule type: {sc_scheduler}, CFG scale: {sc_cfg:.1f}, Seed: {sc_seed}, Size: 1344x768, Model: {scene_model}{sc_extra}"
                                )
                                create_preview_image_with_metadata(
                                    target_path,
                                    scene_preview_path,
                                    a1111_params_text=scene_a1111_params,
                                    prompt_workflow=wf_i2v,
                                    time_offset="00:00:01.000"
                                )

                                print(t("scene_finished", id=szene_id, path=target_path))
                                
                                last_video_data = vid_data
                                last_video_path = target_path
                                free_comfyui_memory(unload_models=False, free_memory=True)
                                break
                break
            time.sleep(10)

    print(t("all_scenes_finished"))
    assemble_movie(scenes_dir, movie_dir, film_name, screenplay=screenplay, prepared_scenes=prepared_scenes, wf_i2v=wf_i2v, t2i_presets=t2i_presets)

if __name__ == "__main__":
    try:
        main()
    finally:
        lms_unload()