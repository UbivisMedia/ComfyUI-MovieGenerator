"""
lib/comfy_manager.py - Centralized ComfyUI API Client & Model Discovery for MovieGenerator

Provides unified HTTP communication with ComfyUI (queue prompt, history, view, upload, VRAM cleanup)
and intelligent model discovery (Minimax UNETs, Turbo LoRAs, Audio checkpoints, dynamic portable paths).
"""

import os
import re
import json
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# ComfyUI Model Discovery
# ---------------------------------------------------------------------------

def get_comfy_models_dir(configured_dir=None, search_paths=None, base_dir=None):
    """
    Resolves the ComfyUI models directory without hardcoded drive paths.
    Checks:
    1. 'models_dir' configured in settings.json (absolute or relative)
    2. 'models_search_paths' list configured in settings.json
    3. Dynamic portable candidates relative to MovieGenerator (sibling ComfyUI folders)
    """
    root = base_dir or BASE_DIR
    settings_file = os.path.join(root, "settings.json")
    if not configured_dir and os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as sf:
                s_data = json.load(sf)
            configured_dir = s_data.get("comfyui", {}).get("models_dir")
            if not search_paths:
                search_paths = s_data.get("comfyui", {}).get("models_search_paths")
        except Exception:
            pass

    # 1. Configured direct models_dir
    if configured_dir and isinstance(configured_dir, str) and configured_dir.strip():
        m_path = configured_dir.strip()
        resolved = m_path if os.path.isabs(m_path) else os.path.abspath(os.path.join(root, m_path))
        if os.path.exists(resolved) and os.path.isdir(resolved):
            return resolved

    # 2. Configured search paths list
    candidates = []
    if search_paths:
        if isinstance(search_paths, str):
            candidates.append(search_paths)
        elif isinstance(search_paths, list):
            candidates.extend(search_paths)

    # 3. Dynamic portable candidates relative to MovieGenerator
    portable_fallbacks = [
        os.path.join(root, "..", "ComfyUI", "models"),
        os.path.join(root, "..", "ComfyUI_windows_portable", "ComfyUI", "models"),
        os.path.join(root, "models"),
    ]
    candidates.extend(portable_fallbacks)

    for c in candidates:
        if not isinstance(c, str) or not c.strip():
            continue
        c_clean = c.strip()
        resolved = c_clean if os.path.isabs(c_clean) else os.path.abspath(os.path.join(root, c_clean))
        if os.path.exists(resolved) and os.path.isdir(resolved):
            return resolved

    return None


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


# ---------------------------------------------------------------------------
# ComfyUI API Execution
# ---------------------------------------------------------------------------

def queue_prompt(prompt_workflow, server_address="127.0.0.1:8188", client_id="master_regisseur"):
    """Submits a graph workflow to ComfyUI's /prompt queue endpoint."""
    payload = {"prompt": prompt_workflow, "client_id": client_id}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(f"http://{server_address}/prompt", data=data)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        print(f"   ❌ HTTPError from ComfyUI ({e.code}): {err_body}")
        raise


def get_history(prompt_id, server_address="127.0.0.1:8188"):
    """Fetches execution outputs from ComfyUI's /history endpoint."""
    try:
        req = urllib.request.Request(f"http://{server_address}/history/{prompt_id}")
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception:
        return {}


def get_image(filename, subfolder, folder_type, server_address="127.0.0.1:8188"):
    """Downloads an output image/video artifact from ComfyUI's /view endpoint."""
    url = f"http://{server_address}/view?filename={filename}&subfolder={subfolder}&type={folder_type}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def upload_file(file_data, filename, content_type="image/png", server_address="127.0.0.1:8188"):
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

    req = urllib.request.Request(f"http://{server_address}/upload/image", data=body)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        return res["name"]


def free_comfyui_memory(server_address="127.0.0.1:8188", unload_models=False, free_memory=True):
    """Frees ComfyUI memory/VRAM cache via its /free endpoint."""
    try:
        data = json.dumps({"unload_models": unload_models, "free_memory": free_memory}).encode("utf-8")
        req = urllib.request.Request(
            f"http://{server_address}/free",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Audio Model Profiles & Dynamic Configuration
# ---------------------------------------------------------------------------

AUDIO_MODEL_PROFILES = {
    "ace_step_1_5": {
        "family": "ACE-Step 1.5",
        "description": "ACE-Step 1.5 (SFT / AIO)",
        "default_steps": 40,
        "min_steps": 20,
        "max_steps": 100,
        "default_cfg": 2.0,
        "min_cfg": 1.0,
        "max_cfg": 3.0,
        "recommended_cfg_hint": "1.0 – 2.0 (über 2.0 kann zu Übersteuerungen führen)",
        "recommended_steps_hint": "30 – 50 Steps",
        "lyrics_tag": "[instrumental]"
    },
    "ace_step_v1": {
        "family": "ACE-Step v1",
        "description": "ACE-Step v1 (Base / FP8)",
        "default_steps": 40,
        "min_steps": 20,
        "max_steps": 80,
        "default_cfg": 4.0,
        "min_cfg": 1.0,
        "max_cfg": 7.0,
        "recommended_cfg_hint": "3.5 – 4.5",
        "recommended_steps_hint": "35 – 45 Steps",
        "lyrics_tag": "[instrumental]"
    },
    "stable_audio": {
        "family": "Stable Audio",
        "description": "Stable Audio Medium / Base",
        "default_steps": 35,
        "min_steps": 20,
        "max_steps": 80,
        "default_cfg": 5.0,
        "min_cfg": 1.0,
        "max_cfg": 8.0,
        "recommended_cfg_hint": "4.0 – 6.0",
        "recommended_steps_hint": "30 – 50 Steps",
        "lyrics_tag": "[instrumental]"
    },
    "generic": {
        "family": "Generic Audio",
        "description": "Standard Audio Checkpoint",
        "default_steps": 40,
        "min_steps": 10,
        "max_steps": 100,
        "default_cfg": 2.5,
        "min_cfg": 1.0,
        "max_cfg": 10.0,
        "recommended_cfg_hint": "1.5 – 4.0",
        "recommended_steps_hint": "30 – 50 Steps",
        "lyrics_tag": "[instrumental]"
    }
}


def get_audio_model_profile(filename_or_path, custom_profiles=None):
    """
    Dynamically resolves recommended steps, CFG scale and hints for a given audio checkpoint.
    Allows user-defined overrides via custom_profiles dictionary.
    """
    if not filename_or_path:
        return dict(AUDIO_MODEL_PROFILES["generic"])

    fn_lower = os.path.basename(str(filename_or_path)).lower()

    # Check custom user profiles first if provided
    if custom_profiles and isinstance(custom_profiles, dict):
        for pattern, prof in custom_profiles.items():
            if pattern.lower() in fn_lower:
                base = dict(AUDIO_MODEL_PROFILES["generic"])
                base.update(prof)
                return base

    # ACE-Step 1.5 (SFT / AIO or 1.5 in name)
    if "1.5" in fn_lower or "15" in fn_lower or "aio" in fn_lower or "acestep_v1.5" in fn_lower:
        return dict(AUDIO_MODEL_PROFILES["ace_step_1_5"])

    # ACE-Step v1 / older ACE models
    if "ace" in fn_lower:
        return dict(AUDIO_MODEL_PROFILES["ace_step_v1"])

    # Stable Audio
    if "stable_audio" in fn_lower or "stableaudio" in fn_lower or "sa_" in fn_lower:
        return dict(AUDIO_MODEL_PROFILES["stable_audio"])

    return dict(AUDIO_MODEL_PROFILES["generic"])
