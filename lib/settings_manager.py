"""
lib/settings_manager.py - Centralized Configuration & Settings Manager for MovieGenerator

Provides unified configuration management, deep merging of user settings with defaults,
automatic schema healing/migrations, and atomic saving with backup generation.
"""

import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


def deep_merge_settings(user_cfg, default_cfg):
    """
    Recursively merges default_cfg into user_cfg for any missing keys.
    Returns (merged_dict, list_of_added_key_paths).
    """
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


def load_settings(settings_file=None, interactive_wizard_callback=None):
    """
    Loads configuration from settings.json with automatic fallback,
    auto-migration / schema healing, and deep-merging of default values.
    """
    file_path = settings_file or SETTINGS_FILE
    defaults = json.loads(json.dumps(DEFAULT_SETTINGS))

    if not os.path.exists(file_path):
        if interactive_wizard_callback and sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
            return interactive_wizard_callback()
        else:
            try:
                with open(file_path, "w", encoding="utf-8") as sf:
                    json.dump(defaults, sf, indent=2, ensure_ascii=False)
            except Exception:
                pass
            return defaults

    try:
        with open(file_path, "r", encoding="utf-8") as sf:
            cfg = json.load(sf)
    except Exception as e:
        print(f"⚠️ Error reading settings from {file_path}: {e}")
        return defaults

    if not isinstance(cfg, dict):
        cfg = {}

    # Auto-heal missing settings
    merged_cfg, added_keys = deep_merge_settings(cfg, defaults)
    if added_keys:
        try:
            with open(file_path, "w", encoding="utf-8") as sf:
                json.dump(merged_cfg, sf, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return merged_cfg


def save_settings(new_settings, settings_file=None, backup=True):
    """
    Saves new configuration dictionary to settings.json with optional .bak backup.
    Returns (True, None) on success or (False, error_message) on failure.
    """
    file_path = settings_file or SETTINGS_FILE
    if not isinstance(new_settings, dict):
        return False, "Settings must be a dictionary object"

    if backup and os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as orig:
                bak_data = orig.read()
            with open(f"{file_path}.bak", "w", encoding="utf-8") as bf:
                bf.write(bak_data)
        except Exception:
            pass

    try:
        with open(file_path, "w", encoding="utf-8") as sf:
            json.dump(new_settings, sf, indent=2, ensure_ascii=False)
        return True, None
    except Exception as e:
        return False, str(e)
