#!/usr/bin/env python3
"""
Script Agency • MovieGenerator Visual Screenplay Studio
Local Web Server & REST API for interactive screenplay editing.
"""

import os
import sys
import json
import socket
import urllib.parse
import urllib.request
import webbrowser
import threading
import re
import base64
import time
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from version import __version__
from lib.subject_manager import (
    resolve_scene_characters,
    build_subject_definitions,
    remap_scene_subjects,
    build_minimax_api_prompt,
    MAX_MINIMAX_SUBJECTS
)
from lib.settings_manager import (
    SETTINGS_FILE,
    load_settings,
    save_settings,
    DEFAULT_SETTINGS,
    deep_merge_settings
)
from lib.comfy_manager import (
    get_comfy_models_dir,
    find_minimax_unets,
    find_minimax_turbo_loras,
    detect_steps_from_lora_name,
    find_music_checkpoints,
    get_audio_model_profile
)
from lib.llm_manager import (
    get_lm_studio_config,
    check_lm_studio_status,
    call_lm_studio,
    fetch_lm_studio_models
)
from lib.color_manager import (
    get_color_catalog,
    COLOR_LOOKS,
    GRAIN_PRESETS,
    LETTERBOX_PRESETS
)
from lib.tts_manager import (
    get_available_voices,
    generate_voiceover_stem
)

# Set terminal UTF-8 encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.join(BASE_DIR, "Projects")
PRESETS_DIR = os.path.join(BASE_DIR, "Presets")
WEB_DIR = os.path.join(BASE_DIR, "web")

# Ensure required directories exist
os.makedirs(PROJECTS_DIR, exist_ok=True)
os.makedirs(PRESETS_DIR, exist_ok=True)
os.makedirs(WEB_DIR, exist_ok=True)



_LORA_COMPANION_CACHE = {}
_ACTIVE_RESHOOTS = {}  # key: f"{project}_{scene_id}" -> dict
_ACTIVE_PRODUCTIONS = {}  # key: safe_project -> dict
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
VIDEO_EXTS = (".mp4", ".webm")


def _extract_published_date(meta_dict):
    """Extracts YYYY-MM-DD from publishedAt or createdAt metadata."""
    if not isinstance(meta_dict, dict):
        return None
    val = (
        meta_dict.get("publishedAt") or
        (meta_dict.get("civitai") or {}).get("publishedAt") or
        (meta_dict.get("model") or {}).get("publishedAt") or
        meta_dict.get("createdAt") or
        (meta_dict.get("civitai") or {}).get("createdAt")
    )
    if isinstance(val, str):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", val)
        if m:
            return m.group(1)
    return None


def resolve_lora_path(lora_name):
    """Resolves absolute path of a LoRA file inside models directory."""
    models_dir = get_comfy_models_dir()
    if not models_dir or not lora_name:
        return None
    norm_name = os.path.normpath(lora_name)
    candidates = [
        os.path.join(models_dir, "loras", norm_name),
        os.path.join(models_dir, norm_name),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return cand
    return None


def find_companion_media_and_meta(lora_file):
    """Finds preview media and metadata for a given LoRA safetensors file."""
    if not lora_file or not os.path.exists(lora_file):
        return None, None, None
    folder = os.path.dirname(lora_file)
    base = os.path.splitext(os.path.basename(lora_file))[0]

    try:
        files = os.listdir(folder)
    except Exception:
        return None, None, None

    img_cands = []
    vid_cands = []
    meta_cands = []

    for f in files:
        f_low = f.lower()
        if f.startswith(base):
            if f_low.endswith(IMAGE_EXTS):
                img_cands.append(f)
            elif f_low.endswith(VIDEO_EXTS):
                vid_cands.append(f)
            elif f_low.endswith((".metadata.json", ".civitai.info", ".json")):
                meta_cands.append(f)

    def score_name(fname):
        name_no_ext = os.path.splitext(fname)[0]
        if name_no_ext == base:
            return 0
        if name_no_ext == f"{base}.preview":
            return 1
        return 2

    chosen_media = None
    media_type = None
    if img_cands:
        img_cands.sort(key=score_name)
        chosen_media = os.path.join(folder, img_cands[0])
        media_type = "image"
    elif vid_cands:
        vid_cands.sort(key=score_name)
        chosen_media = os.path.join(folder, vid_cands[0])
        media_type = "video"

    pub_date = None
    if meta_cands:
        meta_cands.sort(key=score_name)
        for mf in meta_cands:
            meta_path = os.path.join(folder, mf)
            try:
                with open(meta_path, "r", encoding="utf-8", errors="ignore") as jf:
                    data = json.load(jf)
                    d = _extract_published_date(data)
                    if d:
                        pub_date = d
                        break
            except Exception:
                pass

    return chosen_media, media_type, pub_date


def get_lora_companion_info(lora_key, lora_name):
    """Returns companion info (media path, preview URL, media type, published date) with caching."""
    cache_key = f"{lora_key}:{lora_name}"
    if cache_key in _LORA_COMPANION_CACHE:
        return _LORA_COMPANION_CACHE[cache_key]

    lora_path = resolve_lora_path(lora_name)
    media_f, m_type, p_date = find_companion_media_and_meta(lora_path)

    preview_url = None
    if media_f and m_type:
        preview_url = f"/api/loras/media?name={urllib.parse.quote(lora_key)}"

    info = {
        "media_file": media_f,
        "media_type": m_type,
        "preview_url": preview_url,
        "published_at": p_date,
        "has_preview": bool(preview_url)
    }
    _LORA_COMPANION_CACHE[cache_key] = info
    return info


_MODEL_COMPANION_CACHE = {}


def resolve_model_path(unet_or_ckpt):
    """Resolves absolute path of a base/diffusion model inside models directory."""
    models_dir = get_comfy_models_dir()
    if not models_dir or not unet_or_ckpt:
        return None
    norm_name = os.path.normpath(unet_or_ckpt)
    candidates = [
        os.path.join(models_dir, "diffusion_models", norm_name),
        os.path.join(models_dir, "checkpoints", norm_name),
        os.path.join(models_dir, "unet", norm_name),
        os.path.join(models_dir, norm_name),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return cand
    # Fallback search inside subdirectories
    for subdir in ["diffusion_models", "checkpoints", "unet"]:
        target_dir = os.path.join(models_dir, subdir)
        if os.path.exists(target_dir):
            base_fname = os.path.basename(norm_name)
            for root, _, files in os.walk(target_dir):
                if base_fname in files:
                    return os.path.join(root, base_fname)
    return None


def get_model_companion_info(model_key, unet_name):
    """Returns companion info (media path, preview URL, media type, published date) for a model."""
    cache_key = f"{model_key}:{unet_name}"
    if cache_key in _MODEL_COMPANION_CACHE:
        return _MODEL_COMPANION_CACHE[cache_key]

    m_path = resolve_model_path(unet_name)
    media_f, m_type, p_date = find_companion_media_and_meta(m_path)

    preview_url = None
    if media_f and m_type:
        preview_url = f"/api/models/media?name={urllib.parse.quote(model_key)}"

    info = {
        "media_file": media_f,
        "media_type": m_type,
        "preview_url": preview_url,
        "published_at": p_date,
        "has_preview": bool(preview_url)
    }
    _MODEL_COMPANION_CACHE[cache_key] = info
    return info


def serve_media_file(handler, file_path, content_type):
    """Serves media file with byte-range and caching support."""
    try:
        file_size = os.path.getsize(file_path)
        range_header = handler.headers.get("Range")

        if range_header and range_header.startswith("bytes="):
            range_val = range_header[6:].strip()
            parts = range_val.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
            if start >= file_size:
                handler.send_error(416, "Requested Range Not Satisfiable")
                return
            end = min(end, file_size - 1)
            length = end - start + 1

            handler.send_response(206)
            handler.send_header("Content-Type", content_type)
            handler.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            handler.send_header("Content-Length", str(length))
            handler.send_header("Accept-Ranges", "bytes")
            handler.send_header("Cache-Control", "public, max-age=86400")
            handler.end_headers()

            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = length
                buf_size = 64 * 1024
                while remaining > 0:
                    chunk = f.read(min(remaining, buf_size))
                    if not chunk:
                        break
                    handler.wfile.write(chunk)
                    remaining -= len(chunk)
        else:
            handler.send_response(200)
            handler.send_header("Content-Type", content_type)
            handler.send_header("Content-Length", str(file_size))
            handler.send_header("Accept-Ranges", "bytes")
            handler.send_header("Cache-Control", "public, max-age=86400")
            handler.end_headers()

            with open(file_path, "rb") as f:
                buf_size = 64 * 1024
                while True:
                    chunk = f.read(buf_size)
                    if not chunk:
                        break
                    handler.wfile.write(chunk)
    except (ConnectionResetError, BrokenPipeError):
        pass
    except Exception as e:
        try:
            handler.send_error(500, f"Fehler beim Übertragen der Datei: {e}")
        except Exception:
            pass


def get_presets_data(enrich=True):
    """Loads t2i_presets.json, with fallback to t2i_presets.example.json.
    Optionally enriches lora_presets with preview media and publishedAt metadata.
    """
    primary = os.path.join(PRESETS_DIR, "t2i_presets.json")
    fallback = os.path.join(PRESETS_DIR, "t2i_presets.example.json")
    target = primary if os.path.exists(primary) else fallback

    data = {
        "default": "anima_catpony",
        "presets": {},
        "lora_presets": {}
    }

    if os.path.exists(target):
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading presets: {e}")

    if enrich and "presets" in data and isinstance(data["presets"], dict):
        for mkey, mval in data["presets"].items():
            if isinstance(mval, dict):
                munet = mval.get("unet_name") or mval.get("checkpoint") or ""
                cinfo = get_model_companion_info(mkey, munet)
                mval["preview_url"] = cinfo.get("preview_url")
                mval["media_type"] = cinfo.get("media_type")
                mval["published_at"] = cinfo.get("published_at")
                mval["has_preview"] = cinfo.get("has_preview", False)

    if enrich and "lora_presets" in data and isinstance(data["lora_presets"], dict):
        for lkey, lval in data["lora_presets"].items():
            if isinstance(lval, dict):
                lname = lval.get("lora_name", "")
                cinfo = get_lora_companion_info(lkey, lname)
                lval["preview_url"] = cinfo.get("preview_url")
                lval["media_type"] = cinfo.get("media_type")
                lval["published_at"] = cinfo.get("published_at")
                lval["has_preview"] = cinfo.get("has_preview", False)

    return data


def find_free_port(start_port=7860, max_tries=50):
    """Finds an available TCP port."""
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


# -------------------------------------------------------------
# Modular Prompt Extraction
# -------------------------------------------------------------

def extract_elaborated_components(text, fallback_idea=""):
    """Extracts clean modular components from an elaborated prompt or raw LLM output:
    - detailed_description: Pure cinematic shot instructions starting with [Shot 1]: ...
    - summary: 1-sentence action summary
    - soundscape: Ambient environmental soundscape (excluding non_diegetic_music)
    """
    if not text:
        text = ""

    # 1. Strip reasoning blocks like <think>...</think>
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)

    # 2. Strip outer markdown fences: ```markdown ... ```
    text = re.sub(r'^```[a-zA-Z]*\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())

    # 3. Strip metadata tags
    text = re.sub(r'(?:VARIABLES_UPDATE|VARIABLE_UPDATES|SCENE_VARIABLES):\s*(\{[\s\S]*?\}|[^\n]+)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'DURATION:\s*[^\n]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'LORAS:\s*[^\n]*', '', text, flags=re.IGNORECASE)

    # 4. Normalize section headers (strip markdown asterisks/bolding)
    text = re.sub(r'(?i)\*\*(summary:?)\*\*', r'\1', text)
    text = re.sub(r'(?i)\*\*(detailed_description:?)\*\*', r'\1', text)
    text = re.sub(r'(?i)\*\*(overall_soundscape:?)\*\*', r'\1', text)
    text = re.sub(r'(?i)\*\*(non_diegetic_music:?)\*\*', r'\1', text)
    text = re.sub(r'(?i)\*\*(subject_definitions:?)\*\*', r'\1', text)

    summary = ""
    detailed = ""
    soundscape = ""

    # Extract summary
    sum_match = re.search(r'\bsummary:\s*([^\n]+(?:\n(?!(?:detailed_description:|overall_soundscape:|non_diegetic_music:|\[Shot|\*\*))[^\n]+)*)', text, re.IGNORECASE)
    if sum_match:
        summary = sum_match.group(1).strip()
        summary = re.sub(r'^\[reference generation\]\s*', '', summary, flags=re.IGNORECASE).strip()

    # Extract soundscape
    sound_match = re.search(r'\boverall_soundscape:\s*([^\n]+(?:\n(?!(?:non_diegetic_music:|\*\*))[^\n]+)*)', text, re.IGNORECASE)
    if sound_match:
        soundscape = sound_match.group(1).strip()
        soundscape = re.sub(r'(?i)non_diegetic_music:.*', '', soundscape).strip()

    # Extract detailed_description
    det_match = re.search(r'\bdetailed_description:\s*([\s\S]*?)(?=\n\s*(?:overall_soundscape:|non_diegetic_music:|$))', text, re.IGNORECASE)
    if det_match:
        detailed = det_match.group(1).strip()
    else:
        # Check if [Shot 1]: exists directly
        shot_match = re.search(r'(\[Shot 1\]:?[\s\S]*?)(?=\n\s*(?:overall_soundscape:|non_diegetic_music:|$))', text, re.IGNORECASE)
        if shot_match:
            detailed = shot_match.group(1).strip()
        elif "summary:" in text.lower() and sum_match:
            after_sum = text[sum_match.end():]
            after_sum = re.sub(r'(?i)(?:overall_soundscape:|non_diegetic_music:)[\s\S]*', '', after_sum).strip()
            if after_sum:
                detailed = after_sum
        else:
            action_match = re.search(r'(?:Action/Framing|Action):\*?\s*([^\n]+(?:\n(?![0-9]+\.|\*)[^\n]+)*)', text, re.IGNORECASE)
            if action_match:
                detailed = action_match.group(1).strip()
            else:
                detailed = text.strip()

    # Clean detailed description: remove detailed_description header, markdown bullets, and [Shot 1]: tags
    if detailed:
        detailed = re.sub(r'(?i)^detailed_description:\s*', '', detailed).strip()
        detailed = re.sub(r'^[\*\-\>\s]+', '', detailed).strip()
        detailed = re.sub(r'(?i)^\[Shot \d+\]:?\s*', '', detailed).strip()
    else:
        fallback = fallback_idea or "A cinematic shot framing the scene."
        detailed = re.sub(r'(?i)^\[Shot \d+\]:?\s*', '', fallback).strip()

    # Strip any reasoning or prompt meta phrases from detailed
    lines = detailed.splitlines()
    clean_lines = []
    for line in lines:
        l_strip = line.strip().lower()
        if any(tr in l_strip for tr in ["here's a thinking", "here is a thinking", "here's a plan", "thinking process"]):
            continue
        if line.strip().startswith('```'):
            continue
        clean_lines.append(line)
    detailed = "\n".join(clean_lines).strip()
    detailed = re.sub(r'(?i)^\[Shot \d+\]:?\s*', '', detailed).strip()

    # If summary is still empty, derive from detailed or fallback
    if not summary:
        clean_d = re.sub(r'^\[Shot \d+\]:?\s*', '', detailed).strip()
        sentences = [s.strip() for s in re.split(r'[.!?\n]', clean_d) if s.strip()]
        summary = sentences[0] if sentences else (fallback_idea or clean_d[:100])

    if not soundscape:
        soundscape = "Realistic ambient environment sounds, foley, and natural breathing. Strictly no music."

    return {
        "detailed_description": detailed,
        "summary": summary,
        "soundscape": soundscape
    }


def clean_elaborated_prompt(text, fallback_idea, characters=None):
    """Hardened sanitizer that guarantees ONLY the pure detailed shot description ([Shot 1]: ...)
    remains for the prompt input field, with zero reasoning, no boilerplate headers (summary/soundscape),
    and no non_diegetic_music clutter."""
    comps = extract_elaborated_components(text, fallback_idea=fallback_idea)
    return comps["detailed_description"]


def get_llm_wisdom():
    """Loads the consolidated, token-optimized LLM wisdom and screenwriting rules from prompts/llm_wisdom.md."""
    wisdom_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "llm_wisdom.md")
    if os.path.exists(wisdom_path):
        try:
            with open(wisdom_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            print(f"[MovieStudio] Warning: Failed to read prompts/llm_wisdom.md: {e}")
    return """# MOVIEGENERATOR RULES:
1. VARIABLES: Root 'variables' are permanent and persistent. On scenes, 'variables_update' is strictly a DELTA (changes only). If no change occurs, 'variables_update': {} must be EMPTY!
2. GRANULAR WARDROBE: Use <char>_top, <char>_bottom, <char>_shoes, <char>_accessory.
3. MINIMAX TAGGING: Always use '<Subject X> (Name)' in 'idea'.
4. WHITELIST: Use only installed models and LoRAs."""


def load_screenplay_docs_knowledge():
    """Loads knowledge rules and continuity directives from docs/ directory."""
    docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    sections = []
    
    # 1. docs/LLM_SYSTEM_PROMPT.md
    llm_doc = os.path.join(docs_dir, "LLM_SYSTEM_PROMPT.md")
    if os.path.exists(llm_doc):
        try:
            with open(llm_doc, "r", encoding="utf-8") as f:
                txt = f.read()
                # Extract sections 3 & 4 (Dynamic Variables and Scene Directing & Continuity)
                if "3. DYNAMIC VARIABLES" in txt:
                    part = txt[txt.index("3. DYNAMIC VARIABLES"):]
                    if "```\n\n---" in part:
                        part = part[:part.index("```\n\n---")]
                    elif "```" in part:
                        part = part[:part.index("```")]
                    sections.append(part.strip())
        except Exception:
            pass

    # 2. prompts/minimax_scene.txt
    prompt_doc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "minimax_scene.txt")
    if os.path.exists(prompt_doc):
        try:
            with open(prompt_doc, "r", encoding="utf-8") as f:
                p_txt = f.read()
                if "CRITICAL AUDIO REQUIREMENT:" in p_txt and "FORMAT TO FOLLOW STRICTLY:" in p_txt:
                    p_part = p_txt[p_txt.index("CRITICAL AUDIO REQUIREMENT:"):p_txt.index("FORMAT TO FOLLOW STRICTLY:")]
                    sections.append(p_part.strip())
        except Exception:
            pass

    return "\n\n".join(sections)


def ai_elaborate_scene(payload):
    """Translates and expands a scene idea into a cinematic Minimax video prompt with continuity,
    incorporating active cumulative variables and elaborating scene-specific wardrobe/prop updates."""
    scene_obj = payload.get("scene") if isinstance(payload.get("scene"), dict) else {}
    idea = payload.get("idea") or scene_obj.get("idea") or scene_obj.get("idee") or scene_obj.get("prompt") or ""
    idea = idea.strip()
    if not idea:
        return {"success": False, "error": "Keine Szenenidee angegeben. Bitte gib zuerst eine Idee oder Handlung für die Szene ein."}

    characters = payload.get("characters") or scene_obj.get("characters") or []
    continuity = payload.get("continuity") or scene_obj
    sequence = payload.get("sequence") or scene_obj.get("sequence") or scene_obj.get("sequenz") or ""
    location = payload.get("location") or scene_obj.get("location") or scene_obj.get("ort") or ""

    # Preceding scenes context for seamless continuity
    preceding_scenes = payload.get("preceding_scenes") or []
    if not preceding_scenes and payload.get("scenes"):
        all_s = payload.get("scenes") or []
        curr_id = scene_obj.get("id")
        for s in all_s:
            if curr_id and s.get("id") == curr_id:
                break
            preceding_scenes.append(s)

    # 1. Resolve cumulative active variables entering this scene
    active_vars = payload.get("active_variables")
    if not isinstance(active_vars, dict) or not active_vars:
        base_vars = payload.get("global_variables") or payload.get("variables") or {}
        active_vars = dict(base_vars)
        for ps in preceding_scenes:
            ps_upd = (
                ps.get("variables_update") or 
                ps.get("variablen_update") or 
                ps.get("set_variables") or 
                {}
            )
            if isinstance(ps_upd, str) and ps_upd.strip():
                try:
                    ps_upd = json.loads(ps_upd)
                except Exception:
                    parts = ps_upd.split(":", 1)
                    if len(parts) == 2:
                        ps_upd = {parts[0].strip(): parts[1].strip()}
                    else:
                        ps_upd = {}
            if isinstance(ps_upd, dict):
                active_vars.update(ps_upd)

    preceding_blocks = []
    # Focus especially on scenes with the same sequence or location, or immediately preceding
    for ps in preceding_scenes[-4:]:
        ps_id = ps.get("id", "?")
        ps_seq = ps.get("sequence", "")
        ps_loc = ps.get("location", "")
        ps_idea = (ps.get("idea", "") or "").strip()
        ps_vars = ps.get("variables_update") or ps.get("variablen_update") or {}
        var_note = ""
        if isinstance(ps_vars, dict) and ps_vars:
            var_note = f"\n  Variable updates in Shot #{ps_id}: {json.dumps(ps_vars)}"
        elif isinstance(ps_vars, str) and ps_vars.strip():
            var_note = f"\n  Variable updates in Shot #{ps_id}: {ps_vars.strip()}"
        if ps_idea:
            is_same_group = (sequence and ps_seq and sequence.lower() == ps_seq.lower()) or \
                            (location and ps_loc and location.lower() == ps_loc.lower())
            tag = " [SAME SCENE/SEQUENCE]" if is_same_group else ""
            preceding_blocks.append(f"- Shot #{ps_id}{tag} (Sequence: '{ps_seq}', Location: '{ps_loc}'):\n  {ps_idea}{var_note}")

    preceding_text = "\n".join(preceding_blocks) if preceding_blocks else "None (this is the first shot)."

    # 2. Resolve active characters in scene and format dynamic bindings (<Subject 1> .. <Subject N>)
    all_screenplay_chars = payload.get("all_characters") or []
    if not all_screenplay_chars and payload.get("screenplay"):
        all_screenplay_chars = payload.get("screenplay", {}).get("characters") or []

    scene_chars = resolve_scene_characters(scene_obj if scene_obj else {"characters": characters}, all_screenplay_chars)
    char_definitions = build_subject_definitions(scene_chars)

    char_names_clean = []
    char_display_names = []
    for c in scene_chars:
        c_name = c.get("name") if isinstance(c, dict) else str(c)
        char_display_names.append(c_name)
        char_names_clean.append(re.sub(r'[^a-zA-Z0-9]', '', c_name.lower()))

    # Remap incoming idea if it contains global <Subject X> tags
    if all_screenplay_chars and scene_chars:
        idea = remap_scene_subjects(idea, scene_chars, all_screenplay_chars)

    # Format all active variables at the start of this scene (character wardrobes & active story props)
    char_var_lines = []
    prop_var_lines = []
    for k, v in active_vars.items():
        k_clean = re.sub(r'[^a-zA-Z0-9]', '', k.lower())
        matched_char = None
        for i, c_clean in enumerate(char_names_clean):
            if c_clean and c_clean in k_clean:
                matched_char = char_display_names[i]
                break
        if matched_char:
            char_var_lines.append(f"- {matched_char} ({k}): '{v}'")
        else:
            prop_var_lines.append(f"- {k}: '{v}'")

    all_var_lines = char_var_lines + prop_var_lines
    var_text = "\n".join(all_var_lines) if all_var_lines else "None (standard reference appearance, no active props modified)."

    presets = get_presets_data()
    lora_presets = presets.get("lora_presets", {})
    avail_loras = []
    for k, v in lora_presets.items():
        if v.get("available") is False:
            continue
        comp = v.get("kompatible_modelle", [])
        lname = v.get("lora_name", "").lower()
        if any(m in comp for m in ["minimax_h3", "minimax_h3_video"]) or "minimax" in lname or "mmh3" in k:
            if "turbo" not in k.lower():
                desc = v.get("beschreibung", "")
                avail_loras.append(f"- {k}: {desc}")
    avail_loras_text = "\n".join(avail_loras[:15]) if avail_loras else "None."

    connect_to_scene_id = (
        payload.get("connect_to_scene") or 
        scene_obj.get("connect_to_scene") or 
        (continuity.get("connect_to_scene") if isinstance(continuity, dict) else None)
    )
    anchor_note = ""
    if connect_to_scene_id:
        anchor_s = None
        for ps in preceding_scenes:
            if str(ps.get("id")) == str(connect_to_scene_id):
                anchor_s = ps
                break
        if anchor_s:
            a_idea = (anchor_s.get("idea", "") or "").strip()
            anchor_note = f"\n- CRITICAL STORYLINE CONTINUATION: This shot connects directly to Shot #{connect_to_scene_id} ({anchor_s.get('sequence', '')} - {anchor_s.get('location', '')}). Action, posture, and match-cut motion resume directly from Shot #{connect_to_scene_id}: \"{a_idea}\" (cross-cutting / parallel storyline continuity)."

    docs_knowledge = load_screenplay_docs_knowledge()

    messages = [
        {
            "role": "system",
            "content": f"""You are an expert cinematic prompt engineer for MovieGenerator.
When elaborating a single scene, output ONLY the final structured video prompt in English followed by metadata fields.
Do NOT output any conversational text, thinking logs, or commentary.
Your response MUST begin immediately with the word 'summary:'.

Knowledge & Continuity Specifications (from docs/):
{docs_knowledge}"""
        },
        {
            "role": "user",
            "content": f"""Current Scene Idea to Elaborate:
"{idea}"

Screenplay Context & Continuity:
- Location: {location or 'Not specified'}
- Sequence / Scene Group: {sequence or 'Not specified'}
- Same Scene Camera Angle Cut: {continuity.get('same_scene', False)}
- Direct Motion Match-Cut: {continuity.get('match_cut', False)}
- Environmental Reference: {continuity.get('use_previous_scene', False)}{anchor_note}

Preceding Shots in the Screenplay (Maintain seamless posture and action continuity from these previous shots):
{preceding_text}

Character Bindings:
{char_definitions if char_definitions else "<Subject 1> is the character in <Picture 1>."}

Current Active Story & Wardrobe Variables (Entering this Scene):
{var_text}
Characters and items ALREADY possess these exact states at the start of this shot. Reflect these states in the action and framing.

Available Video LoRAs: {avail_loras_text}

Task:
1. Generate the cinematic Minimax prompt for this shot in English. If this is in the same scene/sequence as preceding shots, ensure characters maintain their established posture and physical proximity without re-initiating finished movements.
2. Detect if the action in THIS SPECIFIC SCENE explicitly causes a character to change wardrobe, put on or remove gear (e.g. goggles pulled on / over eyes, jacket removed, dress torn, gloves put on), or alter the state of an active prop (e.g. scanner activated, weapon drawn).
   - If wardrobe/props change in this shot, output the new state as a JSON dictionary under 'VARIABLES_UPDATE:', e.g.
     VARIABLES_UPDATE: {{"goggles": "pulled up over eyes, glowing cyan readouts"}}
   - If NO wardrobe or prop changes occur in this shot, write:
     VARIABLES_UPDATE: {{}}
   - STRICT: ONLY record changes that are EXPLICITLY happening in this shot. Do NOT invent props or clothing not mentioned in the text!

Output format MUST be strictly structured as follows:
summary: [one concise sentence describing the continuous scene action in English]
detailed_description:
[Shot 1]: [Comprehensive, multi-sentence (4-6 sentences) immersive cinematic description in English establishing camera framing, lighting atmosphere, tactile environmental interaction, subject tension, anatomy, micro-movements, and textures using <Subject X> tags alongside character names. If live-action, specify photorealistic 35mm cinematic film footage, real life camera shot, hyperrealistic textures.]

Cinematic details: [Shallow depth of field (DOF), rim lighting, volumetric light rays, shutter effect, bokeh background blur]

[Camera Movement Suggestion]: [Precise camera movement direction, e.g. slow steady tracking shot, gentle dolly zoom / push-in, smooth orbit, or dynamic pan/tilt]

overall_soundscape: [realistic diegetic ambient environment sounds, foley, and spoken dialogue. Strictly NO background music, soundtrack, or score.]
non_diegetic_music: None
DURATION: 6
LORAS: None
VARIABLES_UPDATE: {{}}"""
        }
    ]

    try:
        raw_out = call_lm_studio(messages, temperature=0.3, max_tokens=4000)

        # 1. Parse VARIABLES_UPDATE
        var_updates = {}
        var_match = re.search(r'(?:VARIABLES_UPDATE|VARIABLE_UPDATES|SCENE_VARIABLES):\s*(\{[\s\S]*?\}|[^\n]+)', raw_out, re.IGNORECASE)
        if var_match:
            raw_var_str = var_match.group(1).strip()
            raw_out = raw_out[:var_match.start()] + raw_out[var_match.end():]
            json_sub = re.search(r'\{[\s\S]*?\}', raw_var_str)
            if json_sub:
                try:
                    parsed_vars = json.loads(json_sub.group(0))
                    if isinstance(parsed_vars, dict):
                        var_updates = {str(k).strip(): str(v).strip() for k, v in parsed_vars.items() if v}
                except Exception:
                    pass
            elif ":" in raw_var_str and not any(raw_var_str.lower().startswith(x) for x in ["none", "n/a", "no", "{}"]):
                parts = raw_var_str.split(":", 1)
                k = parts[0].strip().strip("'\"`")
                v = parts[1].strip().strip("'\"`")
                if k and v:
                    var_updates[k] = v

        # 2. Parse DURATION
        duration = 6
        dur_match = re.search(r'DURATION:\s*(\d+)', raw_out, re.IGNORECASE)
        if dur_match:
            try:
                duration = max(3, min(15, int(dur_match.group(1))))
            except ValueError:
                pass
        raw_out = re.sub(r'DURATION:\s*[^\n]*', '', raw_out, flags=re.IGNORECASE)

        # 3. Parse LORAS
        selected_loras = []
        lora_match = re.search(r'LORAS:\s*([^\n]+)', raw_out, re.IGNORECASE)
        if lora_match:
            cand_str = lora_match.group(1).strip()
            raw_out = re.sub(r'LORAS:\s*[^\n]*', '', raw_out, flags=re.IGNORECASE)
            if cand_str.lower() not in ["none", "n/a", "no", ""]:
                for item in re.split(r'[,;\s]+', cand_str):
                    clean_item = item.strip().strip("'\"`")
                    if clean_item in lora_presets and clean_item not in selected_loras:
                        selected_loras.append(clean_item)

        # 4. Extract modular components: Prompt field gets ONLY the detailed_description ([Shot 1]: ...)
        comps = extract_elaborated_components(raw_out, fallback_idea=idea)
        clean_prompt = comps["detailed_description"]
        summary_text = comps["summary"]
        soundscape_text = comps["soundscape"]

        if all_screenplay_chars and scene_chars:
            clean_prompt = remap_scene_subjects(clean_prompt, scene_chars, all_screenplay_chars)
            summary_text = remap_scene_subjects(summary_text, scene_chars, all_screenplay_chars)

        return {
            "success": True,
            "scene": {
                "idea": clean_prompt,
                "prompt": clean_prompt,
                "summary": summary_text,
                "soundscape": soundscape_text,
                "duration": duration,
                "loras": selected_loras,
                "variables_update": var_updates
            },
            "elaborated_idea": clean_prompt,
            "summary": summary_text,
            "soundscape": soundscape_text,
            "duration": duration,
            "loras": selected_loras,
            "variables_update": var_updates
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def ai_suggest_next_scene(payload):
    """Brainstorms and suggests the next logical scene for the screenplay with comprehensive cinematic depth."""
    sp = payload.get("screenplay") or payload
    title = sp.get("title") or payload.get("title") or "Film"
    description = sp.get("description") or payload.get("description") or ""
    characters = sp.get("characters") or payload.get("characters") or []
    scenes = sp.get("scenes") or payload.get("scenes") or []
    variables = sp.get("variables") or payload.get("variables") or {}
    producer_instructions = (sp.get("producer_instructions") or payload.get("producer_instructions") or "").strip()

    # Format character bindings (<Subject X>)
    chars_text, char_names, char_id_map, dominant_model = format_character_bindings(characters)
    char_list_str = ", ".join(char_names) if char_names else "Hero, Antagonist"

    # Compute running cumulative variables up to this next scene
    active_vars = dict(variables)
    for ps in scenes:
        ps_upd = ps.get("variables_update") or ps.get("variablen_update") or {}
        if isinstance(ps_upd, str) and ps_upd.strip():
            try:
                ps_upd = json.loads(ps_upd)
            except Exception:
                pass
        if isinstance(ps_upd, dict):
            active_vars.update(ps_upd)

    preceding = []
    for idx, s in enumerate(scenes[-5:]):
        s_id = s.get("id", idx + 1)
        s_seq = s.get("sequence", "")
        s_loc = s.get("location", "")
        s_idea = (s.get("idea", "") or "").strip()
        s_upd = s.get("variables_update") or s.get("variablen_update") or {}
        upd_str = f" [State: {json.dumps(s_upd)}]" if (isinstance(s_upd, dict) and s_upd) else ""
        preceding.append(f"Shot #{s_id} [{s_seq} - {s_loc}]:\n  {s_idea}{upd_str}")
    preceding_str = "\n".join(preceding) if preceding else "No preceding scenes yet (opening shot of the film)."

    wisdom_rules = get_llm_wisdom()
    producer_block = f"\nProducer Directing / Visual Style Notes:\n\"{producer_instructions}\"\n" if producer_instructions else ""

    prompt = f"""You are an expert cinematic director and prompt engineer for MovieGenerator (Minimax Video).
Task: Propose the next logical, visually stunning cinematic scene for this film.

{wisdom_rules}

Movie Title: {title}
Storyline & Logline: {description}{producer_block}

Cast & Minimax Character Bindings:
{chars_text}

Active Cumulative Story & Wardrobe Variables entering this scene:
{json.dumps(active_vars, indent=2, ensure_ascii=False) if active_vars else "None"}

Preceding Scenes (Story context & continuous action):
{preceding_str}

CRITICAL SCENE PROMPT QUALITY & DEPTH REQUIREMENTS:
The 'idea' field MUST be comprehensive and immersive (resembling a professional National Geographic or cinematic film director's shot description):
1. Opening sentence defines camera shot scale, angle, and perspective (e.g. 'A wide, low-angle shot of...', 'An extreme close-up shot focusing on...', 'A dynamic mid-shot capturing...').
2. Multi-sentence description of the physical action, anatomical tension, gaze, micro-expressions, and tactile interaction with the environment (ground kick-up, dust clouds, rain, volumetric lighting, deep shadows, rim lighting).
3. In 'idea', refer to characters using their '<Subject X> (Name)' tags matching the cast bindings above!
4. Append a dedicated 'Cinematic details:' line (specifying shallow depth of field, rim lighting, volumetric light rays, shutter effect, bokeh background blur).
5. Append a dedicated '[Camera Movement Suggestion]:' line (specifying precise camera trajectory: slow tracking shot, gentle dolly zoom / push-in, subtle 360-degree orbit, dynamic whip pan or tilt).
6. STRICT AUDIO RULE: Absolutely NO background music, soundtrack, score, or instrument names! (Music is handled by a separate audio system; putting music in video prompts ruins the video).
7. If the scene explicitly alters character clothing or gear state, record it in 'variables_update'. Otherwise, use {{}}.

Return ONLY a single valid JSON object without markdown wrapping or preamble, in exactly this JSON structure:
{{
  "sequence": "Sequence or Beat title (e.g. The Hunt & Confrontation)",
  "location": "Vivid location setting (e.g. Vast African Savanna during Golden Hour)",
  "duration": 6,
  "characters": ["{char_names[0] if char_names else 'Hero'}"],
  "idea": "A wide, low-angle shot of... Detailed multi-sentence description with <Subject X> tags, tactile environment, and lighting.\\n\\nCinematic details: Shallow depth of field (DOF), golden hour glow, volumetric rays, rim lighting.\\n\\n[Camera Movement Suggestion]: Slow, steady tracking shot following <Subject 1> from behind as distance closes.",
  "same_scene": false,
  "variables_update": {{}}
}}"""

    try:
        raw_out = call_lm_studio([{"role": "user", "content": prompt}], temperature=0.7, max_tokens=5000)
        json_match = re.search(r'(\{[\s\S]*\})', raw_out)
        if json_match:
            parsed = json.loads(json_match.group(1))
        else:
            raw_clean = re.sub(r'^```[a-zA-Z]*\n?', '', raw_out.strip())
            raw_clean = re.sub(r'\n?```$', '', raw_clean.strip())
            parsed = json.loads(raw_clean)

        # Ensure idea and prompt are populated with the rich cinematic description
        raw_idea = str(parsed.get("idea") or parsed.get("idee") or parsed.get("prompt") or "").strip()
        parsed["idea"] = raw_idea
        parsed["prompt"] = raw_idea

        # Ensure <Subject X> tags are present in idea for referenced characters if missing
        scene_chars_list = parsed.get("characters") or []
        if isinstance(scene_chars_list, str):
            scene_chars_list = [scene_chars_list] if scene_chars_list.strip() else []
        for c_name_raw in scene_chars_list:
            c_key = c_name_raw.strip().lower()
            if c_key in char_id_map:
                cid = char_id_map[c_key]
                subj_tag = f"<Subject {cid}>"
                if subj_tag not in raw_idea:
                    raw_idea = re.sub(rf'\b{re.escape(c_name_raw)}\b', f"{subj_tag} ({c_name_raw})", raw_idea, count=1, flags=re.IGNORECASE)
                    parsed["idea"] = raw_idea
                    parsed["prompt"] = raw_idea

        return {
            "success": True,
            "scene": parsed,
            "suggested_scene": parsed
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"KI-Antwort konnte nicht als JSON verarbeitet werden: {e}",
            "raw": raw_out if 'raw_out' in locals() else ""
        }


def ai_suggest_variables(payload):
    """Suggests recurring props, outfits, or locations from the storyline, or scene-level updates."""
    sp = payload.get("screenplay") or payload
    title = sp.get("title") or payload.get("title", "")
    description = sp.get("description") or payload.get("description", "")
    scenes = sp.get("scenes") or payload.get("scenes", [])
    existing_vars = payload.get("variables") or payload.get("global_variables") or sp.get("variables", {})
    specific_scene = payload.get("scene")

    if specific_scene:
        idea = specific_scene.get("idea", "")
        prompt = f"""Movie: {title}
Scene Idea:
"{idea}"
Currently active variables: {json.dumps(existing_vars)}

Task:
Does this specific scene explicitly describe a character changing clothes, putting on gear, or altering a held prop?
STRICT RULES:
1. Extract ONLY clothing, gear, or prop changes that are EXPLICITLY written in the scene text above.
2. NEVER invent props, goggles, weapons, or items not mentioned in the text.
3. If the scene does not describe any specific wardrobe change or prop state change, return an empty JSON object: {{}}
4. Return ONLY valid JSON mapping variable name to description, e.g. {{"item_name": "new state"}} or {{}}."""
    else:
        scenes_text = "\n".join([f"- Scene #{s.get('id', i+1)}: {(s.get('idea', '') or '')[:140]}" for i, s in enumerate(scenes[:12])])
        prompt = f"""Movie Title: {title}
Storyline: {description}
Key Scenes:
{scenes_text}
Existing Variables: {json.dumps(existing_vars)}

Task:
Extract up to 3 truly essential recurring props or granular character wardrobe variables (<char>_top, <char>_bottom, <char>_shoes) mentioned in the story above.
STRICT RULES:
1. ONLY extract items EXPLICITLY mentioned in the scenes or storyline above.
2. For character clothing, use granular body parts: '<name>_top', '<name>_bottom', '<name>_shoes'.
3. Do NOT invent hypothetical items, sci-fi gadgets, or accessories not found in the text.
4. If no recurring props or outfits exist, return an empty JSON object: {{}}
5. Return ONLY valid JSON mapping variable_name to description, e.g.:
{{
  "hero_top": "worn dark leather jacket",
  "hero_bottom": "rugged blue denim jeans",
  "hero_shoes": "black combat boots"
}}"""

    try:
        raw_out = call_lm_studio([{"role": "user", "content": prompt}], temperature=0.6, max_tokens=5000)
        json_match = re.search(r'(\{[\s\S]*\})', raw_out)
        if json_match:
            parsed = json.loads(json_match.group(1))
        else:
            raw_clean = re.sub(r'^```[a-zA-Z]*\n?', '', raw_out.strip())
            raw_clean = re.sub(r'\n?```$', '', raw_clean.strip())
            parsed = json.loads(raw_clean)
        return {
            "success": True,
            "variables": parsed,
            "scene_variables_update": parsed if specific_scene else {}
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


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


def ai_optimize_character_prompt(payload):
    """Optimizes a character description into model-tailored ComfyUI tags."""
    char = payload.get("character", {})
    variables = payload.get("variables") or {}
    preset_name = payload.get("preset", "anima_catpony")
    title = payload.get("title", "")
    story_desc = payload.get("description", "")

    char_name = char.get("name", "Character")
    raw_desc = char.get("description") or char.get("beschreibung") or char.get("prompt") or ""
    char_desc = interpolate_variables(raw_desc, variables)

    presets = get_presets_data(enrich=False)
    preset_info = presets.get("presets", {}).get(preset_name, {})
    model_desc = preset_info.get("beschreibung", preset_name)

    prompt = f"""You are an expert AI prompt engineer for image generation models (Stable Diffusion / SDXL / Pony / Anima / CyberRealistic).
Create a single, highly detailed, visually compelling English prompt for the character casting sheet of '{char_name}'.

MOVIE ATMOSPHERE:
Title: {title}
Storyline: {story_desc}

TARGET IMAGE MODEL:
'{preset_name}' ({model_desc})

CHARACTER INFORMATION:
Name: {char_name}
Original description/notes: {char_desc}

GUIDELINES:
1. Write the prompt entirely in English as a comma-separated list of descriptive visual tags and phrases.
2. Adapt style to target model:
   - If realistic (e.g. cyberrealistic, krea): photographic terms, skin texture, natural lighting, realistic clothing.
   - If anime (e.g. catpony, turbo): clean anime aesthetics, expressive eyes, hair details, stylized outfit.
3. Frame as a clean solo character casting shot: full body shot or medium shot, simple background, soft studio lighting.
4. Return ONLY the final prompt text without markdown, quotes, or explanations."""

    try:
        raw_out = call_lm_studio([{"role": "user", "content": prompt}], temperature=0.7)
        clean_prompt = raw_out.strip().strip('"\'`')
        clean_prompt = re.sub(r'^```[a-zA-Z]*\n?', '', clean_prompt)
        clean_prompt = re.sub(r'\n?```$', '', clean_prompt).strip()
        return {"success": True, "prompt": clean_prompt}
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_character_portrait_comfy(project_name, char, variables=None, remove_bg=True):
    """Generates a character casting image using ComfyUI and active model/LoRA presets.
    Interpolates variables ({celina_top}, etc.) into the character prompt based on the character's first scene appearance.
    """
    # If variables were not provided or only root variables, calculate variables up to character's first_scene
    if not variables:
        try:
            from master_regisseur import get_character_first_scene, get_variables_for_scene
            safe_proj = os.path.splitext(os.path.basename(project_name))[0]
            proj_json = os.path.join(PROJECTS_DIR, f"{safe_proj}.json")
            if not os.path.exists(proj_json):
                proj_json = os.path.join(PROJECTS_DIR, safe_proj, f"{safe_proj}.json")
            if os.path.exists(proj_json):
                with open(proj_json, "r", encoding="utf-8") as pf:
                    proj_data = json.load(pf)
                scenes = proj_data.get("scenes") or proj_data.get("szenen") or []
                first_scene_id = get_character_first_scene(char, scenes)
                variables = get_variables_for_scene(proj_data, first_scene_id)
        except Exception:
            pass

    settings = load_settings()
    server_address = settings.get("comfyui", {}).get("server_address", "127.0.0.1:8188")

    # Check ComfyUI server status
    try:
        urllib.request.urlopen(f"http://{server_address}/system_stats", timeout=3)
    except Exception as e:
        return {
            "success": False,
            "error": f"ComfyUI ist nicht erreichbar ({server_address}). Bitte stelle sicher, dass ComfyUI gestartet ist."
        }

    # Load workflow_t2i.json
    wf_path = os.path.join(BASE_DIR, "Workflows", "workflow_t2i.json")
    if not os.path.exists(wf_path):
        return {"success": False, "error": "Workflow-Datei 'workflow_t2i.json' nicht gefunden."}

    try:
        with open(wf_path, "r", encoding="utf-8") as f:
            wf_t2i = json.load(f)
    except Exception as e:
        return {"success": False, "error": f"Fehler beim Laden von workflow_t2i.json: {e}"}

    # Load presets
    t2i_presets = get_presets_data(enrich=False)
    preset_name = char.get("model") or char.get("modell") or char.get("preset") or t2i_presets.get("default", "anima_catpony")
    presets_dict = t2i_presets.get("presets", {})
    preset = presets_dict.get(preset_name, {})

    if not preset and presets_dict:
        default_key = t2i_presets.get("default", list(presets_dict.keys())[0])
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

    # LoRAs
    char_loras = char.get("loras") or char.get("lora") or []
    if isinstance(char_loras, (str, dict)):
        char_loras = [char_loras]

    keys_to_clean = [k for k in list(wf_t2i.keys()) if k.startswith("800")]
    for k in keys_to_clean:
        del wf_t2i[k]

    current_model = ["44", 0]
    current_clip = ["45", 0]
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
            real_file = l_cfg.get("lora_name", l_name)
            s_model = custom_strength if custom_strength is not None else l_cfg.get("strength_model", 1.0)
            s_clip = custom_strength if custom_strength is not None else l_cfg.get("strength_clip", s_model)
            triggers = l_cfg.get("trigger_words", "")
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

    wf_t2i["19"]["inputs"]["model"] = current_model
    wf_t2i["11"]["inputs"]["clip"] = current_clip
    wf_t2i["12"]["inputs"]["clip"] = current_clip

    # Determine prompt to use:
    # If auto_prompt is enabled, use LM Studio to optimize description, or fallback to description.
    # Never let default placeholder prompts ("A brave protagonist...") override the user's description.
    is_auto_prompt = char.get("auto_prompt") is not False and char.get("ki_prompt_generieren") is not False
    desc_text = (char.get("description") or char.get("beschreibung") or "").strip()
    fixed_prompt = (char.get("prompt") or "").strip()
    dummy_defaults = [
        "a brave protagonist with a determined expression",
        "ein mutiger protagonist mit entschlossenem blick"
    ]
    is_dummy_prompt = any(fixed_prompt.lower().rstrip(".! ") == d for d in dummy_defaults)

    final_raw_prompt = ""
    if is_auto_prompt and desc_text:
        try:
            opt_res = ai_optimize_character_prompt({
                "character": char,
                "preset": preset_name,
                "variables": variables or {}
            })
            if opt_res and opt_res.get("success") and opt_res.get("prompt"):
                final_raw_prompt = opt_res["prompt"]
                char["prompt"] = final_raw_prompt
        except Exception:
            pass
        if not final_raw_prompt:
            final_raw_prompt = desc_text
    elif fixed_prompt and not is_dummy_prompt:
        final_raw_prompt = fixed_prompt
    elif desc_text:
        final_raw_prompt = desc_text
    else:
        final_raw_prompt = fixed_prompt or "high quality portrait of a character"

    full_prompt = interpolate_variables(final_raw_prompt, variables or {})
    if extra_trigger_words:
        new_triggers = [tw for tw in extra_trigger_words if tw.lower() not in full_prompt.lower()]
        if new_triggers:
            full_prompt = full_prompt.rstrip(", ") + ", " + ", ".join(new_triggers)

    wf_t2i["11"]["inputs"]["text"] = full_prompt
    import random
    wf_t2i["19"]["inputs"]["seed"] = random.randint(1, 999999999999999)

    # Queue to ComfyUI
    p_data = json.dumps({"prompt": wf_t2i, "client_id": "script_agency"}).encode("utf-8")
    req = urllib.request.Request(f"http://{server_address}/prompt", data=p_data)
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        prompt_id = resp["prompt_id"]
    except Exception as e:
        return {"success": False, "error": f"Fehler beim Übermitteln an ComfyUI: {e}"}

    # Poll history until finished
    start_time = time.time()
    img_data = None
    while time.time() - start_time < 180:
        time.sleep(1.0)
        try:
            h_req = urllib.request.Request(f"http://{server_address}/history/{prompt_id}")
            h_data = json.loads(urllib.request.urlopen(h_req, timeout=5).read())
            if prompt_id in h_data:
                p_info = h_data[prompt_id]
                status_info = p_info.get("status", {})
                if status_info.get("status_str") == "error":
                    err_msg = "ComfyUI Ausführungsfehler"
                    for msg in status_info.get("messages", []):
                        if msg[0] == "execution_error":
                            err_msg = msg[1].get("exception_message", str(msg[1]))
                    return {"success": False, "error": err_msg}

                outputs = p_info.get("outputs", {})
                for nid in outputs:
                    if "images" in outputs[nid] and outputs[nid]["images"]:
                        img_info = outputs[nid]["images"][0]
                        v_url = f"http://{server_address}/view?filename={urllib.parse.quote(img_info['filename'])}&subfolder={urllib.parse.quote(img_info.get('subfolder', ''))}&type={urllib.parse.quote(img_info.get('type', 'output'))}"
                        img_data = urllib.request.urlopen(urllib.request.Request(v_url), timeout=15).read()
                        break
                if img_data:
                    break
        except Exception:
            pass

    if not img_data:
        return {"success": False, "error": "Zeitüberschreitung beim Warten auf die Bildgenerierung in ComfyUI."}

    # Optional background removal via rembg
    final_img_bytes = img_data
    if remove_bg:
        try:
            import importlib
            rembg_mod = importlib.import_module("rembg")
            rembg_remove = getattr(rembg_mod, "remove")
            from PIL import Image
            import io
            pil_img = Image.open(io.BytesIO(img_data)).convert("RGBA")
            bg_removed = rembg_remove(pil_img)
            out_buf = io.BytesIO()
            bg_removed.save(out_buf, format="PNG")
            final_img_bytes = out_buf.getvalue()
        except Exception as bg_err:
            print(f"⚠️ Hintergrund konnte nicht entfernt werden: {bg_err}")

    # Save to project characters dir
    safe_project = os.path.splitext(os.path.basename(project_name))[0]
    char_name = char.get("name", "character").strip() or "character"
    safe_char = re.sub(r'[\\/*?:"<>| ]', '_', char_name)

    proj_chars_dir = os.path.join(PROJECTS_DIR, safe_project, "Characters")
    os.makedirs(proj_chars_dir, exist_ok=True)
    target_png = os.path.join(proj_chars_dir, f"{safe_char}.png")

    with open(target_png, "wb") as f:
        f.write(final_img_bytes)

    timestamp = int(time.time())
    img_url = f"/api/characters/image?project={urllib.parse.quote(safe_project)}&name={urllib.parse.quote(safe_char)}&t={timestamp}"

    return {
        "success": True,
        "image": f"Characters/{safe_char}.png",
        "image_url": img_url,
        "prompt_used": full_prompt,
        "generated_prompt": char.get("prompt") or full_prompt
    }


def get_t2i_catalog_summary():
    """Returns available image models and top LoRA presets for LLM prompt context."""
    presets_data = get_presets_data()
    presets_dict = presets_data.get("presets", {})
    loras_dict = presets_data.get("lora_presets", {})

    models = []
    valid_model_keys = []
    for k, v in presets_dict.items():
        if v.get("available") is False:
            continue
        valid_model_keys.append(k)
        desc = v.get("beschreibung", "") or k
        models.append(f"- '{k}': {desc}")

    valid_lora_keys = [k for k, v in loras_dict.items() if v.get("available") is not False]

    # Categorize top LoRAs for clarity
    detail_loras = ["realskin", "anima_detailer", "il_detailer", "anima_masterpiece", "anima_eop_realism", "anima_semi_realistic"]
    style_loras = ["portrait_myth", "dark_lines", "anima_smooth_lines", "anima_background_art", "krea_cinematic", "krea_vintage"]
    motion_loras = ["mmh3_combat_v2", "mmh3_poly_perfect", "mmh3_nafasp_natural", "mmh3_cinematic_movie", "mmh3_digicam_realism"]

    curated_keys = []
    for group in [detail_loras, style_loras, motion_loras]:
        for k in group:
            if k in loras_dict and loras_dict[k].get("available") is not False and k not in curated_keys:
                curated_keys.append(k)

    # Add other top LoRAs up to 28
    for k in valid_lora_keys:
        if k not in curated_keys and len(curated_keys) < 28:
            curated_keys.append(k)

    loras = []
    for k in curated_keys:
        desc = loras_dict.get(k, {}).get("beschreibung", "") or k
        loras.append(f"- '{k}': {desc}")

    default_model = presets_data.get("default", "anima_cyberrealistic")
    if (default_model not in valid_model_keys or presets_dict.get(default_model, {}).get("available") is False) and valid_model_keys:
        default_model = valid_model_keys[0]

    return "\n".join(models), valid_model_keys, "\n".join(loras), valid_lora_keys, default_model


def format_character_bindings(characters):
    """Formats character list with exact <Subject X> IDs according to SCREENPLAY_SPEC.md.
    Returns char_bindings_text, char_names, id_map, dominant_model."""
    lines = []
    names = []
    id_map = {}
    dominant_model = None

    for idx, c in enumerate(characters):
        if not isinstance(c, dict):
            c = {"name": str(c), "id": idx + 1}
        c_id = c.get("id") or (idx + 1)
        c_name = c.get("name") or f"Character_{c_id}"
        c_desc = c.get("description") or c.get("beschreibung") or ""
        c_model = c.get("model") or c.get("modell") or ""
        c_loras = c.get("loras") or []
        if c_model and not dominant_model:
            dominant_model = c_model

        lora_str = f", LoRAs: {c_loras}" if c_loras else ""
        lines.append(f"- <Subject {c_id}> ({c_name}): ID {c_id}, Model: '{c_model or 'default'}'{lora_str}. Notes: {c_desc}")
        names.append(c_name)
        id_map[c_name.lower()] = c_id

    char_text = "\n".join(lines) if lines else "None (cast is currently empty)."
    return char_text, names, id_map, dominant_model


def sanitize_character_definition(c, valid_model_keys, valid_lora_keys, fallback_model):
    """Strictly validates and sanitizes a newly generated character against local presets."""
    name = str(c.get("name") or "").strip()
    desc = str(c.get("description") or "").strip()

    # Model: Strictly enforce valid model key
    raw_model = str(c.get("model") or "").strip().lower()
    chosen_model = fallback_model
    for vm in valid_model_keys:
        if raw_model == vm.lower() or vm.lower() in raw_model:
            chosen_model = vm
            break

    # LoRAs: Strictly filter out any non-existent LoRA
    raw_loras = c.get("loras") if isinstance(c.get("loras"), list) else []
    cleaned_loras = []
    for l in raw_loras:
        l_str = str(l if isinstance(l, str) else l.get("name", "")).strip()
        for vl in valid_lora_keys:
            if l_str.lower() == vl.lower():
                if vl not in cleaned_loras:
                    cleaned_loras.append(vl)
                break

    # Prompt: Ensure clean neutral portrait prompt
    prompt = str(c.get("charakter_prompt") or c.get("prompt") or "").strip()
    if not prompt:
        prompt = f"masterpiece, best quality, photographic portrait of {name}, solo, full body shot, looking at viewer, simple background, soft studio lighting"

    return {
        "name": name,
        "description": desc,
        "model": chosen_model,
        "loras": cleaned_loras,
        "charakter_prompt": prompt
    }


def extract_json_object(raw_text):
    """Helper to cleanly extract a JSON dict or array from LLM responses even with markdown noise."""
    if not raw_text:
        return None
    raw_clean = re.sub(r'^```[a-zA-Z]*\n?', '', raw_text.strip())
    raw_clean = re.sub(r'\n?```$', '', raw_clean.strip())
    try:
        parsed = json.loads(raw_clean)
        if isinstance(parsed, list):
            return {"scenes": parsed}
        return parsed
    except Exception:
        pass

    json_match = re.search(r'(\{[\s\S]*\})', raw_clean)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except Exception:
            pass

    array_match = re.search(r'(\[[\s\S]*\])', raw_clean)
    if array_match:
        try:
            arr = json.loads(array_match.group(1))
            return {"scenes": arr}
        except Exception:
            pass
    return None


def ai_generate_story_scenes(payload):
    """Decomposes a detailed storyline into a sequence of cinematic shots respecting max_shot_duration.
    Enforces Minimax <Subject X> tags, auto-casts new characters using ONLY installed presets,
    and initializes/interpolates variables and variables_update."""
    storyline = (payload.get("storyline") or payload.get("description") or "").strip()
    if not storyline:
        return {"success": False, "error": "Keine Storyline angegeben. Bitte gib eine Handlung ein."}

    sp = payload.get("screenplay") or {}
    title = sp.get("title") or payload.get("title") or "Film"
    try:
        max_shot_duration = int(payload.get("max_shot_duration") or 6)
    except (ValueError, TypeError):
        max_shot_duration = 6
    max_shot_duration = max(3, min(20, max_shot_duration))

    try:
        max_tokens = int(payload.get("max_tokens") or 6000)
    except (ValueError, TypeError):
        max_tokens = 6000
    max_tokens = max(1000, min(32000, max_tokens))

    try:
        temperature = float(payload.get("temperature") or 0.7)
    except (ValueError, TypeError):
        temperature = 0.7

    mode = payload.get("mode") or "append"

    existing_chars = sp.get("characters") or payload.get("characters") or []
    existing_scenes = sp.get("scenes") or payload.get("scenes") or []
    existing_vars = sp.get("variables") or payload.get("variables") or {}

    # Format character bindings (<Subject X>)
    chars_text, char_names, char_id_map, dominant_model = format_character_bindings(existing_chars)

    preceding_lines = []
    if mode == "append":
        for idx, s in enumerate(existing_scenes[-6:]):
            s_id = s.get("id", idx + 1)
            s_seq = s.get("sequence", "")
            s_loc = s.get("location", "")
            s_idea = (s.get("idea", "") or "")[:120]
            preceding_lines.append(f"Shot #{s_id} [{s_seq} - {s_loc}]: {s_idea}")
    preceding_text = "\n".join(preceding_lines) if preceding_lines else "None (starting fresh)."

    models_summary, valid_models, loras_summary, valid_loras, default_model = get_t2i_catalog_summary()
    preferred_model = dominant_model or default_model
    wisdom_rules = get_llm_wisdom()

    prompt = f"""You are an expert movie director and prompt engineer for AI film generation (Minimax / ComfyUI).
Convert the provided storyline into a continuous sequence of cinematic shots following MovieGenerator rules.

{wisdom_rules}

AVAILABLE T2I MODELS (USE ONLY THESE):
{models_summary}

AVAILABLE TOP LORAS (USE ONLY THESE):
{loras_summary}

Movie Title: {title}
Storyline:
\"\"\"{storyline}\"\"\"

Existing Cast (<Subject X> Bindings):
{chars_text}

Preceding Shots:
{preceding_text}

Existing Variables:
{json.dumps(existing_vars)}

REQUIRED JSON STRUCTURE:
{{
  "initial_variables": {{
    "hero_top": "worn dark leather jacket over grey shirt",
    "hero_bottom": "rugged blue denim jeans",
    "hero_shoes": "black combat boots"
  }},
  "new_characters": [
    {{
      "name": "Character Name",
      "description": "Visual details and role",
      "model": "{preferred_model}",
      "loras": ["realskin"],
      "charakter_prompt": "masterpiece, best quality, 1man/1girl, age, solo, simple background..."
    }}
  ],
  "scenes": [
    {{
      "sequence": "Sequence Name",
      "location": "Location setting",
      "duration": {min(6, max_shot_duration)},
      "characters": ["Name of character in shot"],
      "idea": "<Subject 1> (CharacterName) in {{hero_top}} and {{hero_bottom}}... Multi-sentence cinematic description with camera framing, environment, physical dynamics, followed by 'Cinematic details: ...' and '[Camera Movement Suggestion]: ...' (Strictly NO background music descriptions)",
      "same_scene": false,
      "variables_update": {{}}
    }}
  ]
}}"""

    try:
        raw_out = call_lm_studio([{"role": "user", "content": prompt}], temperature=temperature, max_tokens=max_tokens)
        parsed = extract_json_object(raw_out)
        if not parsed or not isinstance(parsed, dict):
            return {"success": False, "error": "Story-Generator konnte kein gültiges JSON erzeugen.", "raw": raw_out[:1000]}

        new_vars = parsed.get("initial_variables") or {}
        cleaned_chars = []
        for c in parsed.get("new_characters", []):
            if not isinstance(c, dict) or not c.get("name"):
                continue
            cleaned_chars.append(sanitize_character_definition(c, valid_models, valid_loras, preferred_model))

        # Build full character ID map (existing + new)
        full_id_map = dict(char_id_map)
        start_char_id = len(existing_chars) + 1
        for idx, nc in enumerate(cleaned_chars):
            full_id_map[nc["name"].lower()] = start_char_id + idx

        # Cumulative running variables for delta tracking
        running_vars = dict(new_vars) if isinstance(new_vars, dict) else {}
        for k, v in existing_vars.items():
            if k not in running_vars:
                running_vars[k] = v

        raw_scenes = parsed.get("scenes", [])
        # Normalize and validate scenes, enforcing <Subject X> tags
        cleaned_scenes = []
        for s in raw_scenes:
            if not isinstance(s, dict):
                continue
            dur = s.get("duration") or s.get("dauer") or 6
            try:
                dur_int = int(dur)
            except Exception:
                dur_int = 6
            dur_int = max(3, min(max_shot_duration, dur_int))

            chars = s.get("characters") or []
            if isinstance(chars, str):
                chars = [chars] if chars.strip() else []

            raw_idea = str(s.get("idea") or s.get("idee") or s.get("prompt") or "").strip()

            # Ensure <Subject X> tags are present in idea for referenced characters
            for c_name_raw in chars:
                c_key = c_name_raw.strip().lower()
                if c_key in full_id_map:
                    cid = full_id_map[c_key]
                    subj_tag = f"<Subject {cid}>"
                    # If subject tag not in idea, replace character name with '<Subject X> (Name)'
                    if subj_tag not in raw_idea:
                        raw_idea = re.sub(rf'\b{re.escape(c_name_raw)}\b', f"{subj_tag} ({c_name_raw})", raw_idea, count=1, flags=re.IGNORECASE)

            # Delta-only variables_update: remove any keys that merely repeat existing running values
            raw_upd = s.get("variables_update") if isinstance(s.get("variables_update"), dict) else {}
            clean_upd = {}
            for uk, uv in raw_upd.items():
                if str(running_vars.get(uk, "")).strip() != str(uv).strip():
                    clean_upd[uk] = uv
                    running_vars[uk] = uv

            cleaned_scenes.append({
                "sequence": str(s.get("sequence") or s.get("sequenz") or "Sequenz").strip(),
                "location": str(s.get("location") or s.get("ort") or "Set").strip(),
                "duration": dur_int,
                "characters": chars,
                "idea": raw_idea,
                "same_scene": bool(s.get("same_scene")),
                "match_cut": bool(s.get("match_cut")),
                "variables_update": clean_upd
            })

        return {
            "success": True,
            "scenes": cleaned_scenes,
            "new_characters": cleaned_chars,
            "new_variables": new_vars if isinstance(new_vars, dict) else {},
            "count": len(cleaned_scenes)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def ai_wizard_step_scene(payload):
    """Proposes the next logical scene in an interactive wizard session, or recreates an existing
    intermediate scene with full bi-directional continuity (bridging preceding and following shots).
    Enforces Minimax <Subject X> tags, producer instructions/style, and strict local model/LoRA presets."""
    premise = (payload.get("premise") or payload.get("storyline") or payload.get("description") or "").strip()
    if not premise:
        return {"success": False, "error": "Keine Grundidee / Prämisse angegeben."}

    sp = payload.get("screenplay") or {}
    title = sp.get("title") or payload.get("title") or "Film"
    producer_instructions = (payload.get("producer_instructions") or sp.get("producer_instructions") or "").strip()

    try:
        max_shot_duration = int(payload.get("max_shot_duration") or 6)
    except (ValueError, TypeError):
        max_shot_duration = 6
    max_shot_duration = max(3, min(20, max_shot_duration))

    try:
        max_tokens = int(payload.get("max_tokens") or 4000)
    except (ValueError, TypeError):
        max_tokens = 4000

    user_instruction = (payload.get("user_instruction") or "").strip()

    existing_chars = sp.get("characters") or payload.get("characters") or []
    existing_scenes = sp.get("scenes") or payload.get("scenes") or []
    existing_vars = sp.get("variables") or payload.get("variables") or {}

    # Check if we are recreating a specific existing scene or appending a new one
    target_scene_id = payload.get("target_scene_id")
    target_idx = None
    if target_scene_id is not None:
        try:
            t_id_int = int(target_scene_id)
            for idx, s in enumerate(existing_scenes):
                if int(s.get("id", idx + 1)) == t_id_int:
                    target_idx = idx
                    break
        except (ValueError, TypeError):
            pass

    is_rewriting = (target_idx is not None)
    target_shot_number = int(existing_scenes[target_idx].get("id", target_idx + 1)) if is_rewriting else (len(existing_scenes) + 1)

    # Format character bindings (<Subject X>)
    chars_text, char_names, char_id_map, dominant_model = format_character_bindings(existing_chars)

    # 1. Resolve cumulative active variables entering this shot
    active_vars = dict(existing_vars)
    prior_scenes = existing_scenes[:target_idx] if is_rewriting else existing_scenes
    for ps in prior_scenes:
        ps_upd = ps.get("variables_update") or ps.get("variablen_update") or {}
        if isinstance(ps_upd, str) and ps_upd.strip():
            try:
                ps_upd = json.loads(ps_upd)
            except Exception:
                pass
        if isinstance(ps_upd, dict):
            active_vars.update(ps_upd)

    # Build Preceding and Following Scene Context with state change history
    if is_rewriting:
        preceding = []
        for s in existing_scenes[max(0, target_idx - 5):target_idx]:
            s_id = s.get("id", "")
            s_seq = s.get("sequence", "")
            s_loc = s.get("location", "")
            s_idea = (s.get("idea", "") or "").strip()
            s_upd = s.get("variables_update") or s.get("variablen_update") or {}
            upd_note = f" [State Changes: {json.dumps(s_upd)}]" if (isinstance(s_upd, dict) and s_upd) else ""
            preceding.append(f"Shot #{s_id} [{s_seq} - {s_loc}]: {s_idea}{upd_note}")
        preceding_str = "\n".join(preceding) if preceding else "None (this is the first shot of the film)."

        following = []
        for s in existing_scenes[target_idx + 1:target_idx + 6]:
            s_id = s.get("id", "")
            s_seq = s.get("sequence", "")
            s_loc = s.get("location", "")
            s_idea = (s.get("idea", "") or "").strip()
            s_upd = s.get("variables_update") or s.get("variablen_update") or {}
            upd_note = f" [State Changes: {json.dumps(s_upd)}]" if (isinstance(s_upd, dict) and s_upd) else ""
            following.append(f"Shot #{s_id} [{s_seq} - {s_loc}]: {s_idea}{upd_note}")
        following_str = "\n".join(following) if following else "None (this was the last shot in the current screenplay)."

        task_title = f"REWRITE / RECREATE SHOT #{target_shot_number}"
        continuity_section = f"""CRITICAL BI-DIRECTIONAL CONTINUITY RULES:
You are REWRITING Shot #{target_shot_number}.
This shot MUST logically and stylistically connect the preceding shots to the already existing following shots!
Do NOT break continuity with what happens afterwards in the following shots.

Preceding Shots (Leading up to this shot):
{preceding_str}

Following Shots (What happens AFTER this shot in the film):
{following_str}"""
    else:
        preceding = []
        for idx, s in enumerate(existing_scenes[-6:]):
            s_id = s.get("id", idx + 1)
            s_seq = s.get("sequence", "")
            s_loc = s.get("location", "")
            s_idea = (s.get("idea", "") or "").strip()
            s_upd = s.get("variables_update") or s.get("variablen_update") or {}
            upd_note = f" [State Changes: {json.dumps(s_upd)}]" if (isinstance(s_upd, dict) and s_upd) else ""
            preceding.append(f"Shot #{s_id} [{s_seq} - {s_loc}]: {s_idea}{upd_note}")
        preceding_str = "\n".join(preceding) if preceding else "Opening shot of the film."

        task_title = f"PROPOSE NEXT SHOT (SHOT #{target_shot_number})"
        continuity_section = f"""Story So Far (Preceding Shots):
{preceding_str}"""

    models_summary, valid_models, loras_summary, valid_loras, default_model = get_t2i_catalog_summary()
    preferred_model = dominant_model or default_model
    wisdom_rules = get_llm_wisdom()

    producer_block = f"""\nPRODUCER INSTRUCTIONS & FILM STYLE (GENRE, LOOK, TONE, PACING):
\"{producer_instructions}\"
You MUST strictly follow these producer instructions regarding genre, visual aesthetic, atmosphere, lighting, camera framing, and pace!\n""" if producer_instructions else ""

    user_note = f"\nUser's Specific Direction / Note for this Step:\n\"{user_instruction}\"" if user_instruction else ""

    prompt = f"""You are an interactive AI movie director and screenwriter for MovieGenerator (Minimax / ComfyUI).
Task: {task_title} in this interactive Story Wizard.

{wisdom_rules}

AVAILABLE T2I MODELS (USE ONLY THESE):
{models_summary}

AVAILABLE TOP LORAS (USE ONLY THESE):
{loras_summary}

Movie Title: {title}
Core Premise: \"{premise}\"{producer_block}

Existing Cast (<Subject X> Bindings):
{chars_text}

Current Active State of Characters & Props entering this Shot (Cumulative):
{json.dumps(active_vars, indent=2, ensure_ascii=False)}
(CRITICAL: If an outfit item was removed/undressed in prior shots, respect the active state above! NEVER describe characters wearing clothes they already took off!)

{continuity_section}
{user_note}

REQUIRED JSON STRUCTURE:
{{
  "scene": {{
    "sequence": "Sequence Title",
    "location": "Location Setting",
    "duration": {min(6, max_shot_duration)},
    "characters": ["{char_names[0] if char_names else 'Hero'}"],
    "idea": "Comprehensive, highly detailed cinematic shot description (camera framing, environment, physical dynamics, micro-details/tension, followed by 'Cinematic details: ...' and '[Camera Movement Suggestion]: ...'). Strictly NO background music descriptions!",
    "same_scene": false,
    "variables_update": {{}}
  }},
  "new_characters": [],
  "next_hooks": [
    "Option 1 for next step",
    "Option 2 for next step"
  ]
}}"""

    try:
        raw_out = call_lm_studio([{"role": "user", "content": prompt}], temperature=0.7, max_tokens=max_tokens)
        parsed = extract_json_object(raw_out)
        if not parsed or not isinstance(parsed, dict):
            return {
                "success": False,
                "error": "Wizard-Antwort konnte nicht als gültiges JSON verarbeitet werden.",
                "raw": raw_out[:1000]
            }

        sc = parsed.get("scene") or parsed
        dur = sc.get("duration") or sc.get("dauer") or 6
        try:
            dur_int = int(dur)
        except Exception:
            dur_int = 6
        dur_int = max(3, min(max_shot_duration, dur_int))

        chars = sc.get("characters") or []
        if isinstance(chars, str):
            chars = [chars] if chars.strip() else []

        # Sanitize new characters against strict whitelist
        cleaned_chars = []
        for c in parsed.get("new_characters", []):
            if not isinstance(c, dict) or not c.get("name"):
                continue
            cleaned_chars.append(sanitize_character_definition(c, valid_models, valid_loras, preferred_model))

        # Build full character ID map
        full_id_map = dict(char_id_map)
        start_char_id = len(existing_chars) + 1
        for idx, nc in enumerate(cleaned_chars):
            full_id_map[nc["name"].lower()] = start_char_id + idx

        raw_idea = str(sc.get("idea") or sc.get("idee") or sc.get("prompt") or "").strip()

        # Enforce <Subject X> tags in idea
        for c_name_raw in chars:
            c_key = c_name_raw.strip().lower()
            if c_key in full_id_map:
                cid = full_id_map[c_key]
                subj_tag = f"<Subject {cid}>"
                if subj_tag not in raw_idea:
                    raw_idea = re.sub(rf'\b{re.escape(c_name_raw)}\b', f"{subj_tag} ({c_name_raw})", raw_idea, count=1, flags=re.IGNORECASE)

        default_seq = existing_scenes[target_idx].get("sequence") if is_rewriting else f"Sequenz #{target_shot_number}"
        default_loc = existing_scenes[target_idx].get("location") if is_rewriting else "Set"

        # Delta-only variables_update: eliminate any repeated unchanged variables against cumulative active_vars
        raw_var_upd = sc.get("variables_update") if isinstance(sc.get("variables_update"), dict) else {}
        clean_var_upd = {}
        for vk, vv in raw_var_upd.items():
            if str(active_vars.get(vk, "")).strip() != str(vv).strip():
                clean_var_upd[vk] = vv

        cleaned_scene = {
            "id": target_shot_number,
            "sequence": str(sc.get("sequence") or sc.get("sequenz") or default_seq).strip(),
            "location": str(sc.get("location") or sc.get("ort") or default_loc).strip(),
            "duration": dur_int,
            "characters": chars,
            "idea": raw_idea,
            "same_scene": bool(sc.get("same_scene")),
            "match_cut": bool(sc.get("match_cut")),
            "variables_update": clean_var_upd
        }

        hooks = parsed.get("next_hooks", [])
        if not isinstance(hooks, list):
            hooks = []

        return {
            "success": True,
            "scene": cleaned_scene,
            "new_characters": cleaned_chars,
            "next_hooks": [str(h) for h in hooks if h],
            "step_index": target_shot_number,
            "is_recreated": is_rewriting
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def ai_harmonize_screenplay(payload):
    """Holistic screenplay harmonizer:
    1. Ensures baseline variables exist for each character's outfit ('outfit_<name>') and central story props.
    2. Enforces <Subject X> (CharacterName) tags across all scenes.
    3. Replaces static wardrobe descriptions with {outfit_<name>} placeholders.
    4. Analyzes scenes where outfits or items change state and inserts correct 'variables_update' entries."""
    sp = payload.get("screenplay") or payload
    title = sp.get("title") or payload.get("title") or "Film"
    description = sp.get("description") or payload.get("description") or ""
    characters = sp.get("characters") or []
    scenes = sp.get("scenes") or []
    existing_vars = sp.get("variables") or {}

    if not scenes and not characters:
        return {"success": False, "error": "Keine Szenen oder Charaktere zum Harmonisieren vorhanden."}

    chars_text, char_names, char_id_map, _ = format_character_bindings(characters)

    scenes_dump = []
    for s in scenes:
        scenes_dump.append({
            "id": s.get("id"),
            "sequence": s.get("sequence", ""),
            "location": s.get("location", ""),
            "duration": s.get("duration", 6),
            "characters": s.get("characters", []),
            "idea": s.get("idea", ""),
            "variables_update": s.get("variables_update", {})
        })

    wisdom_rules = get_llm_wisdom()

    prompt = f"""You are a master screenplay continuity editor and technical supervisor for MovieGenerator (Minimax / ComfyUI).
Your task is to harmonize and polish this complete screenplay to achieve 100% compliance with MovieGenerator guidelines.

{wisdom_rules}

TASKS:
1. GRANULAR CHARACTER WARDROBE BASELINES (Root 'variables'):
   For EVERY character in the cast, decompose their wardrobe into granular body-part variables:
   - '<char>_top': Upper body (jacket, shirt, coat, armor)
   - '<char>_bottom': Lower body (pants, cargo trousers, jeans, skirt)
   - '<char>_shoes': Footwear (combat boots, sneakers, shoes)
   - Optional '<char>_accessory': Notable distinct accessories (sunglasses, hat, gloves, holster)
   If legacy 'outfit_<char>' exists, decompose it into these clean body-region variables!
   Preserve essential story props (e.g. 'briefcase_status', 'data_chip').
   DO NOT create variables for general scenery, weather, or generic room lighting!
2. MINIMAX SUBJECT TAGGING:
   In EVERY scene 'idea', ensure characters are referred to using '<Subject X> (CharacterName)' based on their character ID!
   Example: '<Subject 1> (Maya) enters the corridor in her {{maya_top}} and {{maya_bottom}}...'
3. DYNAMIC VARIABLE PLACEHOLDERS:
   Use '{{variable_name}}' (e.g. '{{maya_top}}', '{{maya_bottom}}', '{{scanner}}') in the scene descriptions instead of hardcoding static clothing.
4. STRICT DELTA TRACKING (VARIABLES_UPDATE):
   - Whenever a character explicitly changes a specific piece of clothing, undresses, gets injured, or an item changes state:
     Output ONLY the modified variable in 'variables_update' on THAT specific scene!
     Example: If Maya takes off her jacket in Scene 3, output: "variables_update": {{"maya_top": "dark grey shirt (jacket removed)"}}.
     Do NOT re-list her unchanged pants or boots!
   - If NO clothing or item change occurs in a scene: "variables_update": {{}} MUST be an EMPTY object!
   - NEVER repeat unchanged variables across scenes!

Existing Cast (<Subject X> IDs):
{chars_text}

Current Variables:
{json.dumps(existing_vars)}

Current Scenes:
{json.dumps(scenes_dump, indent=2, ensure_ascii=False)}

Return ONLY a single valid JSON object in this exact format:
{{
  "variables": {{
    "maya_top": "dark tactical vest over black combat shirt",
    "maya_bottom": "black cargo utility pants",
    "maya_shoes": "heavy combat boots",
    "goggles": "resting around neck"
  }},
  "scenes": [
    {{
      "id": 1,
      "sequence": "Sequence Name",
      "location": "Location",
      "duration": 6,
      "characters": ["Maya"],
      "idea": "<Subject 1> (Maya) steps through the door in her {{maya_top}} and {{maya_bottom}}...",
      "same_scene": false,
      "variables_update": {{}}
    }}
  ]
}}"""

    try:
        raw_out = call_lm_studio([{"role": "user", "content": prompt}], temperature=0.4, max_tokens=8000)
        parsed = extract_json_object(raw_out)
        if not parsed or not isinstance(parsed, dict):
            return {"success": False, "error": "Harmonisierung fehlgeschlagen: Kein gültiges JSON erhalten."}

        res_vars = parsed.get("variables")
        if not isinstance(res_vars, dict):
            res_vars = dict(existing_vars)

        res_scenes = parsed.get("scenes")
        if not isinstance(res_scenes, list) or len(res_scenes) == 0:
            res_scenes = scenes

        # Re-merge with original scene metadata & clean redundant variables_update
        running_vars = dict(res_vars)
        updated_scenes = []
        for idx, orig in enumerate(scenes):
            upd = res_scenes[idx] if idx < len(res_scenes) and isinstance(res_scenes[idx], dict) else orig
            merged = dict(orig)
            merged["idea"] = upd.get("idea") or orig.get("idea", "")
            if "sequence" in upd and upd["sequence"]:
                merged["sequence"] = upd["sequence"]
            if "location" in upd and upd["location"]:
                merged["location"] = upd["location"]

            raw_upd = upd.get("variables_update") if isinstance(upd.get("variables_update"), dict) else {}
            clean_upd = {}
            for k, v in raw_upd.items():
                if str(running_vars.get(k, "")).strip() != str(v).strip():
                    clean_upd[k] = v
                    running_vars[k] = v
            merged["variables_update"] = clean_upd
            updated_scenes.append(merged)

        return {
            "success": True,
            "variables": res_vars,
            "scenes": updated_scenes,
            "message": "Drehbuch erfolgreich mit Variablen und Minimax-Tags harmonisiert."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def normalize_screenplay_data(data, filename=""):
    """Normalizes legacy screenplay JSON schemas (e.g. German keys 'charaktere', 'szenen',
    'dauer_sekunden', 'idee', 'anschluss_an_vorherige_szene') into the current standard format."""
    if not isinstance(data, dict):
        data = {}

    converted = False
    if any(k in data for k in ["charaktere", "szenen", "titel", "beschreibung", "variablen", "charakter_prompt"]):
        converted = True

    norm = {}
    default_title = os.path.splitext(os.path.basename(filename))[0].replace("_", " ").title() if filename else "Untitled Film"
    norm["title"] = data.get("title") or data.get("titel") or default_title
    norm["description"] = data.get("description") or data.get("beschreibung") or ""
    norm["producer_instructions"] = data.get("producer_instructions") or data.get("produzenten_anweisung") or data.get("film_style") or ""

    # Variables
    norm["variables"] = data.get("variables") or data.get("variablen") or {}
    if not isinstance(norm["variables"], dict):
        norm["variables"] = {}

    # Characters
    raw_chars = data.get("characters") or data.get("charaktere")
    if not raw_chars and data.get("charakter_prompt"):
        raw_chars = [{"id": 1, "name": "Hero", "prompt": data.get("charakter_prompt")}]
        converted = True
    elif not isinstance(raw_chars, list):
        raw_chars = []

    default_model = "anima_catpony"
    try:
        presets = get_presets_data()
        default_model = presets.get("default", "anima_catpony")
    except Exception:
        pass

    norm_chars = []
    for idx, c in enumerate(raw_chars):
        if not isinstance(c, dict):
            c = {"name": str(c)}
        c_id = c.get("id", idx + 1)
        c_name = c.get("name") or c.get("charakter") or f"Actor_{idx+1}"
        c_model = c.get("model") or c.get("modell") or c.get("preset") or default_model
        raw_loras = c.get("loras") or c.get("lora") or []
        if isinstance(raw_loras, str):
            c_loras = [l.strip() for l in raw_loras.split(",") if l.strip()]
        elif isinstance(raw_loras, list):
            c_loras = list(raw_loras)
        else:
            c_loras = []

        c_desc = c.get("description") or c.get("beschreibung") or c.get("prompt") or ""
        c_prompt = c.get("prompt") or c.get("description") or ""

        auto_prompt = c.get("auto_prompt")
        if auto_prompt is None:
            auto_prompt = c.get("ki_prompt_generieren")
        if auto_prompt is None:
            auto_prompt = not bool(c.get("prompt"))

        char_entry = {
            "id": c_id,
            "name": c_name,
            "model": c_model,
            "loras": c_loras,
            "description": c_desc,
            "prompt": c_prompt,
            "auto_prompt": bool(auto_prompt)
        }
        if "reference_id" in c:
            char_entry["reference_id"] = c["reference_id"]
        if "reference_character" in c:
            char_entry["reference_character"] = c["reference_character"]
        if "denoise" in c:
            char_entry["denoise"] = c["denoise"]
        if "image" in c:
            char_entry["image"] = c["image"]
        elif "bild" in c:
            char_entry["image"] = c["bild"]
        elif "reference_image" in c:
            char_entry["image"] = c["reference_image"]
        if "image_url" in c:
            char_entry["image_url"] = c["image_url"]

        norm_chars.append(char_entry)
    norm["characters"] = norm_chars

    # Scenes
    raw_scenes = data.get("scenes") or data.get("szenen") or []
    if not isinstance(raw_scenes, list):
        raw_scenes = []

    norm_scenes = []
    for idx, s in enumerate(raw_scenes):
        if not isinstance(s, dict):
            s = {"idea": str(s)}
        s_id = s.get("id", idx + 1)
        s_seq = s.get("sequence") or s.get("sequenz") or s.get("scene_group") or s.get("group") or ""
        s_loc = s.get("location") or s.get("ort") or s.get("setting") or ""
        try:
            s_dur = int(s.get("duration") or s.get("dauer_sekunden") or s.get("duration_seconds") or s.get("dauer") or 6)
        except (ValueError, TypeError):
            s_dur = 6
        s_idea = s.get("idea") or s.get("idee") or s.get("prompt") or ""
        s_prompt = s.get("prompt") or s_idea
        s_summary = s.get("summary") or ""
        s_soundscape = s.get("soundscape") or s.get("overall_soundscape") or ""

        # If idea or prompt contains legacy multi-section Minimax boilerplate, clean it!
        cand_text = s_prompt if ("detailed_description:" in s_prompt.lower() or "summary:" in s_prompt.lower()) else s_idea
        if "detailed_description:" in cand_text.lower() or "summary:" in cand_text.lower():
            comps = extract_elaborated_components(cand_text, fallback_idea=s_idea)
            s_idea = comps["detailed_description"]
            s_prompt = comps["detailed_description"]
            if not s_summary:
                s_summary = comps["summary"]
            if not s_soundscape:
                s_soundscape = comps["soundscape"]

        s_idea = re.sub(r'(?i)^\[Shot \d+\]:?\s*', '', s_idea).strip()
        s_prompt = re.sub(r'(?i)^\[Shot \d+\]:?\s*', '', s_prompt).strip()

        s_match_cut = bool(s.get("match_cut") or s.get("direkter_anschluss") or s.get("direct_continuation"))
        s_same_scene = bool(s.get("same_scene") or s.get("gleiche_szene") or s.get("angle_change"))
        s_ref_prev = bool(
            s.get("use_previous_scene") or 
            s.get("nutze_vorherige_szene") or 
            s.get("anschluss_an_vorherige_szene") or 
            s.get("continuity_environment")
        )

        s_chars = s.get("characters") or s.get("charaktere")
        if not s_chars and s.get("character"):
            s_chars = [s.get("character")]
        elif not s_chars and s.get("charakter"):
            s_chars = [s.get("charakter")]
        if not isinstance(s_chars, list):
            s_chars = []

        s_var_upd = (
            s.get("variables_update") or 
            s.get("variablen_update") or 
            s.get("set_variables") or 
            {}
        )
        if isinstance(s_var_upd, str) and s_var_upd.strip():
            try:
                s_var_upd = json.loads(s_var_upd)
            except Exception:
                parts = s_var_upd.split(":", 1)
                if len(parts) == 2:
                    s_var_upd = {parts[0].strip(): parts[1].strip()}
                else:
                    s_var_upd = {}
        if not isinstance(s_var_upd, dict):
            s_var_upd = {}

        raw_s_loras = s.get("loras") or s.get("lora") or []
        if isinstance(raw_s_loras, str):
            s_loras = [l.strip() for l in raw_s_loras.split(",") if l.strip()]
        elif isinstance(raw_s_loras, list):
            s_loras = list(raw_s_loras)
        else:
            s_loras = []

        scene_dict = {
            "id": s_id,
            "sequence": s_seq,
            "location": s_loc,
            "duration": s_dur,
            "idea": s_idea,
            "prompt": s_prompt
        }
        if s_chars:
            scene_dict["characters"] = s_chars
        if s_match_cut:
            scene_dict["match_cut"] = True
        if s_same_scene:
            scene_dict["same_scene"] = True
        if s_ref_prev:
            scene_dict["use_previous_scene"] = True
        s_connect_to = s.get("connect_to_scene") or s.get("connect_to") or s.get("anschluss_an_szene") or s.get("match_cut_scene") or s.get("continuation_scene")
        if s_connect_to is not None and str(s_connect_to).strip():
            try:
                scene_dict["connect_to_scene"] = int(s_connect_to)
            except (ValueError, TypeError):
                scene_dict["connect_to_scene"] = str(s_connect_to).strip()
        if s_var_upd:
            scene_dict["variables_update"] = s_var_upd
        if s_loras:
            scene_dict["loras"] = s_loras
        if s_summary:
            scene_dict["summary"] = s_summary
        if s_soundscape:
            scene_dict["soundscape"] = s_soundscape

        norm_scenes.append(scene_dict)

    norm["scenes"] = norm_scenes
    return norm, converted


class ScriptAgencyHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for Script Agency static assets and REST API."""

    def log_message(self, format, *args):
        # Silence routine static asset logs for cleaner console output
        if self.path.startswith("/api/"):
            sys.stdout.write(f"[API] {args[0]} - {args[1]}\n")
            sys.stdout.flush()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message, status=400):
        self.send_json({"success": False, "error": str(message)}, status=status)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_HEAD(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/music/soundtrack":
            query = urllib.parse.parse_qs(parsed.query)
            proj = query.get("project", [""])[0]
            if not proj:
                self.send_error(404)
                return
            safe_proj = re.sub(r'[\\/*?:"<>| ]', '_', proj)
            proj_dir = os.path.join(PROJECTS_DIR, safe_proj)
            movie_dir = os.path.join(proj_dir, "Movie")
            soundtrack_path = None
            if os.path.exists(movie_dir):
                for f in os.listdir(movie_dir):
                    if "soundtrack" in f.lower() and f.endswith((".flac", ".mp3", ".wav", ".ogg")):
                        soundtrack_path = os.path.join(movie_dir, f)
                        break
            if soundtrack_path and os.path.exists(soundtrack_path):
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(os.path.getsize(soundtrack_path)))
                self.end_headers()
            else:
                self.send_error(404, "Soundtrack not found")
            return
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # -------------------------------------------------------------
        # REST API Routes
        # -------------------------------------------------------------
        if path == "/api/version":
            from version import __version__, __title__
            self.send_json({
                "version": __version__,
                "title": __title__
            })
            return

        if path == "/api/localization":
            from version import __version__, __title__
            from localization import get_current_language, get_all_editor_translations
            self.send_json({
                "version": __version__,
                "title": __title__,
                "active_lang": get_current_language(),
                "translations": get_all_editor_translations()
            })
            return

        # -------------------------------------------------------------
        # GET /api/voices (List available TTS voices)
        # -------------------------------------------------------------
        if path == "/api/voices":
            voices = get_available_voices()
            self.send_json({
                "success": True,
                "voices": voices
            })
            return

        # -------------------------------------------------------------
        # GET /api/color/catalog (List color grading looks and film grain presets)
        # -------------------------------------------------------------
        if path == "/api/color/catalog":
            catalog = get_color_catalog()
            self.send_json({
                "success": True,
                "catalog": catalog
            })
            return

        # -------------------------------------------------------------
        # GET /api/voiceover/audio (Serve temporary preview voiceover audio)
        # -------------------------------------------------------------
        if path == "/api/voiceover/audio":
            fname = query.get("file", [""])[0].strip()
            if not fname or not re.match(r'^vo_preview_[a-zA-Z0-9_\-]+\.wav$', fname):
                self.send_error(400, "Ungültiger Dateiname")
                return
            tpath = os.path.join(BASE_DIR, "Projects", ".preview_audio", fname)
            if not os.path.exists(tpath):
                self.send_error(404, "Audio nicht gefunden")
                return
            try:
                with open(tpath, "rb") as af:
                    adata = af.read()
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(adata)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(adata)
            except Exception as e:
                self.send_error(500, str(e))
            return

        # -------------------------------------------------------------
        # GET /api/settings (Retrieve merged settings.json)
        # -------------------------------------------------------------
        if path == "/api/settings":
            current_cfg = load_settings()
            merged_cfg, _ = deep_merge_settings(current_cfg, DEFAULT_SETTINGS)
            self.send_json({
                "success": True,
                "settings": merged_cfg
            })
            return

        # -------------------------------------------------------------
        # GET /api/settings/models (Scan available models for settings UI)
        # -------------------------------------------------------------
        if path == "/api/settings/models":
            models_dir = get_comfy_models_dir()
            settings = load_settings()
            lm_url = query.get("lm_studio_url", query.get("lm_url", [settings.get("lm_studio", {}).get("url", "http://127.0.0.1:1234/v1/chat/completions")]))[0]

            unets = find_minimax_unets(models_dir) if models_dir else []
            turbo_loras = find_minimax_turbo_loras(models_dir) if models_dir else []

            formatted_unets = []
            for u in unets:
                m_path = resolve_model_path(u)
                media_f, m_type, p_date = find_companion_media_and_meta(m_path)
                preview_url = f"/api/models/media?name={urllib.parse.quote(u)}" if (media_f and m_type) else None
                title = os.path.splitext(os.path.basename(u))[0]
                desc = ""
                if m_path:
                    meta_path = os.path.splitext(m_path)[0] + ".metadata.json"
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path, "r", encoding="utf-8", errors="ignore") as mf:
                                mdata = json.load(mf)
                                if mdata.get("model_name"):
                                    title = mdata.get("model_name")
                                raw_desc = mdata.get("modelDescription") or mdata.get("description") or ""
                                desc = re.sub(r'<[^>]+>', ' ', raw_desc).strip()
                        except Exception:
                            pass
                formatted_unets.append({
                    "filename": u,
                    "title": title,
                    "description": desc,
                    "media_type": m_type,
                    "preview_url": preview_url,
                    "published_at": p_date,
                    "has_preview": bool(preview_url)
                })

            formatted_turbo = []
            for tl in turbo_loras:
                l_path = resolve_lora_path(tl)
                media_f, m_type, p_date = find_companion_media_and_meta(l_path)
                preview_url = f"/api/loras/media?name={urllib.parse.quote(tl)}" if (media_f and m_type) else None
                title = os.path.splitext(os.path.basename(tl))[0]
                desc = ""
                if l_path:
                    meta_path = os.path.splitext(l_path)[0] + ".metadata.json"
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path, "r", encoding="utf-8", errors="ignore") as mf:
                                mdata = json.load(mf)
                                if mdata.get("model_name"):
                                    title = mdata.get("model_name")
                                raw_desc = mdata.get("modelDescription") or mdata.get("description") or ""
                                desc = re.sub(r'<[^>]+>', ' ', raw_desc).strip()
                        except Exception:
                            pass
                formatted_turbo.append({
                    "filename": tl,
                    "title": title,
                    "description": desc,
                    "steps": detect_steps_from_lora_name(tl),
                    "media_type": m_type,
                    "preview_url": preview_url,
                    "published_at": p_date,
                    "has_preview": bool(preview_url)
                })

            music_ckpts = find_music_checkpoints(models_dir) if models_dir else []
            formatted_music = []
            for mc in music_ckpts:
                m_path = resolve_model_path(mc)
                media_f, m_type, p_date = find_companion_media_and_meta(m_path)
                preview_url = f"/api/models/media?name={urllib.parse.quote(mc)}" if (media_f and m_type) else None
                title = os.path.splitext(os.path.basename(mc))[0]
                desc = ""
                if m_path:
                    meta_path = os.path.splitext(m_path)[0] + ".metadata.json"
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path, "r", encoding="utf-8", errors="ignore") as mf:
                                mdata = json.load(mf)
                                if mdata.get("model_name"):
                                    title = mdata.get("model_name")
                                raw_desc = mdata.get("modelDescription") or mdata.get("description") or ""
                                desc = re.sub(r'<[^>]+>', ' ', raw_desc).strip()
                        except Exception:
                            pass
                m_prof = get_audio_model_profile(mc, settings.get("music_studio", {}).get("model_profiles"))
                formatted_music.append({
                    "filename": mc,
                    "title": title,
                    "description": desc,
                    "media_type": m_type,
                    "preview_url": preview_url,
                    "published_at": p_date,
                    "has_preview": bool(preview_url),
                    "profile": m_prof
                })

            lm_models = fetch_lm_studio_models(lm_url) if lm_url else []

            self.send_json({
                "success": True,
                "models_dir": models_dir,
                "minimax_unets": formatted_unets,
                "minimax_turbo_loras": formatted_turbo,
                "music_checkpoints": formatted_music,
                "lm_studio_models": lm_models
            })
            return

        if path == "/api/presets":
            presets = get_presets_data()
            self.send_json(presets)
            return

        if path == "/api/llm/status":
            self.send_json(check_lm_studio_status())
            return

        if path == "/api/music/models":
            models_dir = get_comfy_models_dir()
            found = find_music_checkpoints(models_dir) if models_dir else []
            settings = load_settings()
            cfg_ckpt = settings.get("music_studio", {}).get("checkpoint", "Other\\base model\\ace_step_v1_3.5b.safetensors")
            if cfg_ckpt and cfg_ckpt not in found:
                found.insert(0, cfg_ckpt)

            formatted = []
            custom_profs = settings.get("music_studio", {}).get("model_profiles")
            for f in found:
                title = os.path.splitext(os.path.basename(f))[0]
                m_type = "ACE-Step" if "ace" in f.lower() else ("Music" if "music" in f.lower() else "Audio")
                m_prof = get_audio_model_profile(f, custom_profs)
                formatted.append({
                    "filename": f,
                    "title": title,
                    "type": m_type,
                    "profile": m_prof
                })

            self.send_json({
                "models": formatted,
                "default": cfg_ckpt
            })
            return

        if path == "/api/music/soundtrack":
            proj = query.get("project", [""])[0]
            if not proj:
                self.send_error(400, "Missing project param")
                return
            safe_proj = re.sub(r'[\\/*?:"<>| ]', '_', proj)
            proj_dir = os.path.join(PROJECTS_DIR, safe_proj)
            movie_dir = os.path.join(proj_dir, "Movie")
            soundtrack_path = None
            if os.path.exists(movie_dir):
                for f in os.listdir(movie_dir):
                    if "soundtrack" in f.lower() and f.endswith((".flac", ".mp3", ".wav", ".ogg")):
                        soundtrack_path = os.path.join(movie_dir, f)
                        break
            if soundtrack_path and os.path.exists(soundtrack_path):
                ext = os.path.splitext(soundtrack_path)[1].lower()
                mime = "audio/flac" if ext == ".flac" else ("audio/mpeg" if ext == ".mp3" else "audio/wav")
                with open(soundtrack_path, "rb") as af:
                    content = af.read()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            self.send_error(404, "Soundtrack not found")
            return

        if path == "/api/projects":
            projects = []
            if os.path.exists(PROJECTS_DIR):
                for f in sorted(os.listdir(PROJECTS_DIR)):
                    if f.endswith(".json"):
                        f_path = os.path.join(PROJECTS_DIR, f)
                        title = ""
                        desc = ""
                        chars_count = 0
                        scenes_count = 0
                        try:
                            with open(f_path, "r", encoding="utf-8") as jf:
                                data = json.load(jf)
                                title = data.get("title") or data.get("titel") or ""
                                desc = data.get("description") or data.get("beschreibung") or ""
                                chars = data.get("characters") or data.get("charaktere") or []
                                scenes = data.get("scenes") or data.get("szenen") or []
                                chars_count = len(chars)
                                scenes_count = len(scenes)
                        except Exception:
                            pass
                        projects.append({
                            "file": f,
                            "title": title,
                            "description": desc,
                            "characters_count": chars_count,
                            "scenes_count": scenes_count,
                            "mtime": os.path.getmtime(f_path)
                        })
            self.send_json(projects)
            return

        if path == "/api/project":
            file_param = query.get("file", [""])[0].strip()
            if not file_param:
                self.send_error_json("Parameter 'file' fehlt")
                return

            # Sanitize filename against path traversal
            safe_name = os.path.basename(file_param)
            target_path = os.path.join(PROJECTS_DIR, safe_name)

            if not os.path.exists(target_path):
                self.send_error_json(f"Drehbuch '{safe_name}' nicht gefunden", status=404)
                return

            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                normalized, converted = normalize_screenplay_data(content, filename=safe_name)

                # Check if character images exist on disk in Projects/<safe_project>/Characters/<char_safe>.png
                proj_base = os.path.splitext(safe_name)[0]
                chars_dir = os.path.join(PROJECTS_DIR, proj_base, "Characters")
                for c in normalized.get("characters", []):
                    c_name = c.get("name", "")
                    if c_name:
                        c_safe = re.sub(r'[\\/*?:"<>| ]', '_', c_name)
                        c_png = os.path.join(chars_dir, f"{c_safe}.png")
                        if os.path.exists(c_png):
                            c["image"] = f"Characters/{c_safe}.png"
                            c["image_url"] = f"/api/characters/image?project={urllib.parse.quote(proj_base)}&name={urllib.parse.quote(c_safe)}&t={int(os.path.getmtime(c_png))}"

                self.send_json({
                    "file": safe_name,
                    "data": normalized,
                    "converted_legacy": converted
                })
            except Exception as e:
                self.send_error_json(f"Fehler beim Lesen der Datei: {e}", status=500)
            return

        # -------------------------------------------------------------
        # GET /api/characters/image (Serve character reference portrait)
        # -------------------------------------------------------------
        if path == "/api/characters/image":
            project_param = query.get("project", [""])[0].strip()
            name_param = query.get("name", [""])[0].strip()
            if not project_param or not name_param:
                self.send_error(400, "Parameter 'project' und 'name' erforderlich")
                return

            safe_project = os.path.splitext(os.path.basename(project_param))[0]
            safe_name = re.sub(r'[\\/*?:"<>| ]', '_', os.path.basename(name_param))
            if not safe_name.lower().endswith(".png"):
                safe_name += ".png"

            img_path = os.path.join(PROJECTS_DIR, safe_project, "Characters", safe_name)
            if not os.path.exists(img_path):
                img_path = os.path.join(PROJECTS_DIR, "Characters", safe_name)

            if not os.path.exists(img_path):
                self.send_error(404, "Charakterbild nicht gefunden")
                return

            try:
                with open(img_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Fehler beim Laden des Bildes: {e}")
            return

        # -------------------------------------------------------------
        # GET /api/loras/media (Serve LoRA preview image/video)
        # -------------------------------------------------------------
        if path == "/api/loras/media":
            name_param = query.get("name", [""])[0].strip() or query.get("key", [""])[0].strip()
            if not name_param:
                self.send_error(400, "Parameter 'name' erforderlich")
                return

            presets = get_presets_data(enrich=False)
            lora_presets = presets.get("lora_presets", {})
            lval = lora_presets.get(name_param)
            media_file = None
            if lval:
                cinfo = get_lora_companion_info(name_param, lval.get("lora_name", ""))
                media_file = cinfo.get("media_file")
            else:
                l_path = resolve_lora_path(name_param)
                if l_path:
                    media_file, _, _ = find_companion_media_and_meta(l_path)

            if not media_file or not os.path.exists(media_file):
                self.send_error(404, "Vorschaumedium nicht gefunden")
                return

            ext = os.path.splitext(media_file)[1].lower()
            mime_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".mp4": "video/mp4",
                ".webm": "video/webm"
            }
            content_type = mime_map.get(ext, "application/octet-stream")
            serve_media_file(self, media_file, content_type)
            return

        # -------------------------------------------------------------
        # GET /api/models/media (Serve Base Model preview image/video)
        # -------------------------------------------------------------
        if path == "/api/models/media":
            name_param = query.get("name", [""])[0].strip() or query.get("key", [""])[0].strip()
            if not name_param:
                self.send_error(400, "Parameter 'name' erforderlich")
                return

            presets = get_presets_data(enrich=False)
            model_presets = presets.get("presets", {})
            mval = model_presets.get(name_param)
            media_file = None
            if mval:
                munet = mval.get("unet_name") or mval.get("checkpoint") or ""
                cinfo = get_model_companion_info(name_param, munet)
                media_file = cinfo.get("media_file")
            else:
                m_path = resolve_model_path(name_param)
                if m_path:
                    media_file, _, _ = find_companion_media_and_meta(m_path)

            if not media_file or not os.path.exists(media_file):
                self.send_error(404, "Vorschaumedium nicht gefunden")
                return

            ext = os.path.splitext(media_file)[1].lower()
            mime_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".mp4": "video/mp4",
                ".webm": "video/webm"
            }
            content_type = mime_map.get(ext, "application/octet-stream")
            serve_media_file(self, media_file, content_type)
            return

        # -------------------------------------------------------------
        # -------------------------------------------------------------
        # GET /api/scene/video (Stream rendered scene clip with HTTP 206)
        # -------------------------------------------------------------
        if path == "/api/scene/video":
            project_param = query.get("project", [""])[0].strip()
            scene_param = query.get("scene", [""])[0].strip() or query.get("id", [""])[0].strip()
            if not project_param or not scene_param:
                self.send_error(400, "Parameter 'project' und 'scene' erforderlich")
                return

            safe_project = os.path.splitext(os.path.basename(project_param))[0]
            cand_scenes_dirs = [
                os.path.join(PROJECTS_DIR, safe_project, "Scenes"),
                os.path.join(PROJECTS_DIR, "Scenes")
            ]

            target_file = None
            for sdir in cand_scenes_dirs:
                if not os.path.exists(sdir):
                    continue
                if scene_param.endswith(".mp4"):
                    cand = os.path.join(sdir, os.path.basename(scene_param))
                    if os.path.exists(cand):
                        target_file = cand
                        break
                else:
                    try:
                        s_id = int(re.search(r'\d+', scene_param).group(0))
                        for cand_name in [
                            f"Szene_{s_id:02d}.mp4", f"Szene_{s_id}.mp4",
                            f"szene_{s_id:02d}.mp4", f"szene_{s_id}.mp4",
                            f"Szene_{s_id:02d}.webm", f"Szene_{s_id}.webm"
                        ]:
                            cand_path = os.path.join(sdir, cand_name)
                            if os.path.exists(cand_path):
                                target_file = cand_path
                                break
                    except Exception:
                        pass
                if target_file:
                    break

            if not target_file or not os.path.exists(target_file):
                self.send_error(404, "Szenen-Video nicht gefunden")
                return

            serve_media_file(self, target_file, "video/mp4")
            return

        # -------------------------------------------------------------
        # GET /api/scene/preview (Serve scene companion thumbnail)
        # -------------------------------------------------------------
        if path == "/api/scene/preview":
            project_param = query.get("project", [""])[0].strip()
            scene_param = query.get("scene", [""])[0].strip() or query.get("id", [""])[0].strip()
            if not project_param or not scene_param:
                self.send_error(400, "Parameter 'project' und 'scene' erforderlich")
                return

            safe_project = os.path.splitext(os.path.basename(project_param))[0]
            cand_scenes_dirs = [
                os.path.join(PROJECTS_DIR, safe_project, "Scenes"),
                os.path.join(PROJECTS_DIR, "Scenes")
            ]

            target_file = None
            for sdir in cand_scenes_dirs:
                if not os.path.exists(sdir):
                    continue
                try:
                    s_id = int(re.search(r'\d+', scene_param).group(0))
                    for cand_name in [
                        f"Szene_{s_id:02d}_preview.png", f"Szene_{s_id}_preview.png",
                        f"Szene_{s_id:02d}.png", f"Szene_{s_id}.png",
                        f"Szene_{s_id:02d}_preview.jpg", f"Szene_{s_id}_preview.jpg",
                        f"Szene_{s_id:02d}.jpg", f"Szene_{s_id}.jpg",
                        f"Szene_{s_id:02d}_preview.webp", f"Szene_{s_id}_preview.webp",
                        f"szene_{s_id:02d}_preview.png", f"szene_{s_id}_preview.png",
                        f"szene_{s_id:02d}.png", f"szene_{s_id}.png"
                    ]:
                        cand_path = os.path.join(sdir, cand_name)
                        if os.path.exists(cand_path):
                            target_file = cand_path
                            break
                except Exception:
                    pass
                if target_file:
                    break

            if not target_file or not os.path.exists(target_file):
                self.send_error(404, "Szenen-Vorschaubild nicht gefunden")
                return

            ext = os.path.splitext(target_file)[1].lower()
            mime = "image/png"
            if ext in [".jpg", ".jpeg"]:
                mime = "image/jpeg"
            elif ext == ".webp":
                mime = "image/webp"

            serve_media_file(self, target_file, mime)
            return

        # -------------------------------------------------------------
        # GET /api/movie/video (Stream final assembled movie with HTTP 206)
        # -------------------------------------------------------------
        if path == "/api/movie/video":
            project_param = query.get("project", [""])[0].strip()
            if not project_param:
                self.send_error(400, "Parameter 'project' erforderlich")
                return

            safe_project = os.path.splitext(os.path.basename(project_param))[0]
            cand_movie_dirs = [
                os.path.join(PROJECTS_DIR, safe_project, "Movie"),
                os.path.join(PROJECTS_DIR, "Movie")
            ]

            target_file = None
            for mdir in cand_movie_dirs:
                if not os.path.exists(mdir):
                    continue
                tf = os.path.join(mdir, f"{safe_project}_FINAL.mp4")
                if os.path.exists(tf):
                    target_file = tf
                    break
                for f in os.listdir(mdir):
                    if f.endswith(".mp4") and not f.endswith("_RAW.mp4"):
                        target_file = os.path.join(mdir, f)
                        break
                if target_file:
                    break

            if not target_file or not os.path.exists(target_file):
                self.send_error(404, "Finales Video nicht gefunden")
                return

            serve_media_file(self, target_file, "video/mp4")
            return

        # -------------------------------------------------------------
        # GET /api/movie/render/status (Return status and logs of full movie production)
        # -------------------------------------------------------------
        if path == "/api/movie/render/status":
            project_param = query.get("project", [""])[0].strip()
            if not project_param:
                self.send_error_json("Parameter 'project' erforderlich")
                return

            safe_project = os.path.splitext(os.path.basename(project_param))[0]
            prod_entry = _ACTIVE_PRODUCTIONS.get(safe_project)

            cand_movie_dirs = [
                os.path.join(PROJECTS_DIR, safe_project, "Movie"),
                os.path.join(PROJECTS_DIR, "Movie")
            ]
            final_movie_path = None
            for mdir in cand_movie_dirs:
                if not os.path.exists(mdir):
                    continue
                tf = os.path.join(mdir, f"{safe_project}_FINAL.mp4")
                if os.path.exists(tf):
                    final_movie_path = tf
                    break
                for f in os.listdir(mdir):
                    if f.endswith(".mp4") and not f.endswith("_RAW.mp4"):
                        final_movie_path = os.path.join(mdir, f)
                        break
                if final_movie_path:
                    break

            has_final_movie = final_movie_path is not None and os.path.exists(final_movie_path)
            movie_mtime = int(os.path.getmtime(final_movie_path)) if has_final_movie else 0

            status = prod_entry.get("status", "idle") if prod_entry else "idle"
            start_time = prod_entry.get("start_time") if prod_entry else None
            finished_at = prod_entry.get("finished_at") if prod_entry else None
            elapsed = 0.0
            if start_time:
                end_t = finished_at if finished_at else time.time()
                elapsed = max(0.0, end_t - start_time)

            logs = prod_entry.get("logs", []) if prod_entry else []
            last_log = prod_entry.get("last_log") if prod_entry else None
            error = prod_entry.get("error") if prod_entry else None

            self.send_json({
                "success": True,
                "project": safe_project,
                "status": status,
                "start_time": start_time,
                "finished_at": finished_at,
                "elapsed": round(elapsed, 1),
                "error": error,
                "last_log": last_log,
                "logs": logs[-100:],
                "movie_ready": has_final_movie,
                "movie_url": f"/api/movie/video?project={urllib.parse.quote(safe_project)}&t={movie_mtime}" if has_final_movie else None,
                "movie_file": os.path.basename(final_movie_path) if has_final_movie else None
            })
            return

        # -------------------------------------------------------------
        # GET /api/scenes/status (Return render state & media URLs for storyboard timeline)
        # -------------------------------------------------------------
        if path == "/api/scenes/status":
            project_param = query.get("project", [""])[0].strip()
            if not project_param:
                self.send_error_json("Parameter 'project' erforderlich")
                return

            safe_project = os.path.splitext(os.path.basename(project_param))[0]
            proj_dir = os.path.join(PROJECTS_DIR, safe_project)
            cand_scenes_dirs = [
                os.path.join(proj_dir, "Scenes"),
                os.path.join(PROJECTS_DIR, "Scenes")
            ]
            cand_movie_dirs = [
                os.path.join(proj_dir, "Movie"),
                os.path.join(PROJECTS_DIR, "Movie")
            ]

            proj_json = os.path.join(PROJECTS_DIR, f"{safe_project}.json")
            if not os.path.exists(proj_json):
                proj_json = os.path.join(proj_dir, f"{safe_project}.json")

            screenplay_scenes = []
            if os.path.exists(proj_json):
                try:
                    with open(proj_json, "r", encoding="utf-8") as f:
                        sp_data = json.load(f)
                    screenplay_scenes = sp_data.get("scenes") or sp_data.get("szenen") or []
                except Exception:
                    pass

            scene_results = []
            for idx, sc in enumerate(screenplay_scenes):
                sid = sc.get("id", idx + 1)
                try:
                    s_num = int(sid)
                except Exception:
                    s_num = idx + 1

                target_v = None
                target_p = None

                for sdir in cand_scenes_dirs:
                    if not os.path.exists(sdir):
                        continue
                    if not target_v:
                        for cand_name in [
                            f"Szene_{s_num:02d}.mp4", f"Szene_{s_num}.mp4",
                            f"szene_{s_num:02d}.mp4", f"szene_{s_num}.mp4",
                            f"Szene_{s_num:02d}.webm", f"Szene_{s_num}.webm"
                        ]:
                            cand_path = os.path.join(sdir, cand_name)
                            if os.path.exists(cand_path):
                                target_v = cand_path
                                break
                    if not target_p:
                        for cand_name in [
                            f"Szene_{s_num:02d}_preview.png", f"Szene_{s_num}_preview.png",
                            f"Szene_{s_num:02d}.png", f"Szene_{s_num}.png",
                            f"Szene_{s_num:02d}_preview.jpg", f"Szene_{s_num}_preview.jpg",
                            f"Szene_{s_num:02d}.jpg", f"Szene_{s_num}.jpg",
                            f"Szene_{s_num:02d}_preview.webp", f"Szene_{s_num}_preview.webp",
                            f"szene_{s_num:02d}_preview.png", f"szene_{s_num}_preview.png",
                            f"szene_{s_num:02d}.png", f"szene_{s_num}.png"
                        ]:
                            cand_path = os.path.join(sdir, cand_name)
                            if os.path.exists(cand_path):
                                target_p = cand_path
                                break

                has_video = target_v is not None
                has_preview = target_p is not None

                v_mtime = int(os.path.getmtime(target_v)) if has_video else 0
                p_mtime = int(os.path.getmtime(target_p)) if has_preview else 0

                v_url = f"/api/scene/video?project={urllib.parse.quote(safe_project)}&scene={s_num}&t={v_mtime}" if has_video else None
                p_url = f"/api/scene/preview?project={urllib.parse.quote(safe_project)}&scene={s_num}&t={p_mtime}" if has_preview else None

                reshoot_key = f"{safe_project}_{s_num}"
                reshoot_job = _ACTIVE_RESHOOTS.get(reshoot_key)
                is_rendering = bool(reshoot_job and reshoot_job.get("status") == "rendering")

                sc_dur = float(sc.get("duration") or sc.get("dauer_sekunden") or sc.get("dauer") or 6.0)
                sc_trans = str(sc.get("transition") or sc.get("uebergang") or sc.get("blende") or "cut")
                sc_trans_dur = float(sc.get("transition_duration") or sc.get("uebergang_dauer") or 0.75)

                scene_results.append({
                    "id": s_num,
                    "sequence": sc.get("sequence") or sc.get("sequenz") or "",
                    "location": sc.get("location") or sc.get("ort") or "",
                    "has_video": has_video,
                    "video_url": v_url,
                    "video_mtime": v_mtime,
                    "has_preview": has_preview,
                    "preview_url": p_url,
                    "preview_mtime": p_mtime,
                    "is_rendering": is_rendering,
                    "duration": sc_dur,
                    "transition": sc_trans,
                    "transition_duration": sc_trans_dur
                })

            final_movie_path = None
            for mdir in cand_movie_dirs:
                if not os.path.exists(mdir):
                    continue
                tf = os.path.join(mdir, f"{safe_project}_FINAL.mp4")
                if os.path.exists(tf):
                    final_movie_path = tf
                    break
                for f in os.listdir(mdir):
                    if f.endswith(".mp4") and not f.endswith("_RAW.mp4"):
                        final_movie_path = os.path.join(mdir, f)
                        break
                if final_movie_path:
                    break

            has_final_movie = final_movie_path is not None and os.path.exists(final_movie_path)
            movie_mtime = int(os.path.getmtime(final_movie_path)) if has_final_movie else 0
            active_rendering = [s["id"] for s in scene_results if s["is_rendering"]]

            prod_job = _ACTIVE_PRODUCTIONS.get(safe_project)
            is_movie_rendering = bool(prod_job and prod_job.get("status") == "running")

            self.send_json({
                "success": True,
                "project": safe_project,
                "scenes": scene_results,
                "any_rendering": len(active_rendering) > 0 or is_movie_rendering,
                "active_rendering_scenes": active_rendering,
                "movie_rendering": is_movie_rendering,
                "movie_ready": has_final_movie,
                "movie_url": f"/api/movie/video?project={urllib.parse.quote(safe_project)}&t={movie_mtime}" if has_final_movie else None,
                "movie_file": os.path.basename(final_movie_path) if has_final_movie else None
            })
            return

        # -------------------------------------------------------------
        # Static Asset Serving (HTML, CSS, JS)
        # -------------------------------------------------------------
        rel_path = path.lstrip("/")
        if not rel_path or rel_path == "":
            rel_path = "index.html"

        safe_rel = os.path.normpath(rel_path)
        if safe_rel.startswith("..") or os.path.isabs(safe_rel):
            self.send_error(403, "Forbidden")
            return

        local_file = os.path.join(WEB_DIR, safe_rel)

        if not os.path.exists(local_file) or os.path.isdir(local_file):
            self.send_error(404, "File Not Found")
            return

        # Determine MIME Type
        mime = "text/plain; charset=utf-8"
        if local_file.endswith(".html"):
            mime = "text/html; charset=utf-8"
        elif local_file.endswith(".css"):
            mime = "text/css; charset=utf-8"
        elif local_file.endswith(".js"):
            mime = "application/javascript; charset=utf-8"
        elif local_file.endswith(".json"):
            mime = "application/json; charset=utf-8"
        elif local_file.endswith(".png"):
            mime = "image/png"
        elif local_file.endswith(".svg"):
            mime = "image/svg+xml"

        try:
            with open(local_file, "rb") as f:
                content = f.read()

            if local_file.endswith(".html"):
                from version import __version__
                content_str = content.decode("utf-8", errors="replace")
                content_str = re.sub(r'class="version-tag">[^<]*<', f'class="version-tag">v{__version__}<', content_str)
                content_str = content_str.replace("{{VERSION}}", __version__)
                content = content_str.encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Read JSON body
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = b""
        if content_length > 0:
            post_data = self.rfile.read(content_length)

        payload = {}
        if post_data:
            try:
                payload = json.loads(post_data.decode("utf-8"))
            except Exception as e:
                self.send_error_json(f"Ungültiges JSON im Request Body: {e}")
                return

        # -------------------------------------------------------------
        # POST /api/settings (Save configuration to settings.json)
        # -------------------------------------------------------------
        if path == "/api/settings":
            new_settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload
            if not isinstance(new_settings, dict):
                self.send_error_json("Feld 'settings' als Objekt erforderlich")
                return

            ok, err = save_settings(new_settings)
            if not ok:
                self.send_error_json(f"Fehler beim Speichern der Einstellungen: {err}", status=500)
                return

            try:
                import master_regisseur
                master_regisseur.SETTINGS = new_settings
            except Exception:
                pass

            self.send_json({
                "success": True,
                "message": "Einstellungen erfolgreich in settings.json gespeichert.",
                "settings": new_settings
            })
            return

        # -------------------------------------------------------------
        # POST /api/voiceover/preview (Generate and stream a voiceover preview audio)
        # -------------------------------------------------------------
        if path == "/api/voiceover/preview":
            text = payload.get("text", "").strip()
            voice = payload.get("voice", "de-DE-ConradNeural").strip()
            if not text:
                self.send_error_json("Feld 'text' erforderlich")
                return

            tmp_dir = os.path.join(BASE_DIR, "Projects", ".preview_audio")
            os.makedirs(tmp_dir, exist_ok=True)
            safe_hash = abs(hash(text + voice)) % 100000000
            out_file = os.path.join(tmp_dir, f"vo_preview_{safe_hash}.wav")

            ok, out_path, dur, err = generate_voiceover_stem(text, voice=voice, output_wav_path=out_file)
            if not ok or not os.path.exists(out_path):
                self.send_error_json(f"Fehler bei Voiceover-Vorschau: {err}", status=500)
                return

            self.send_json({
                "success": True,
                "audio_url": f"/api/voiceover/audio?file={os.path.basename(out_path)}",
                "duration": round(dur, 2),
                "voice": voice
            })
            return

        # -------------------------------------------------------------
        # POST /api/music/suggest-tags
        # -------------------------------------------------------------
        if path == "/api/music/suggest-tags":
            title = payload.get("title", "")
            description = payload.get("description", "")
            scenes = payload.get("scenes")
            if not scenes and payload.get("project"):
                safe_proj = re.sub(r'[\\/*?:"<>| ]', '_', payload.get("project", "").strip())
                proj_json = os.path.join(PROJECTS_DIR, f"{safe_proj}.json")
                if os.path.exists(proj_json):
                    try:
                        with open(proj_json, "r", encoding="utf-8") as pf:
                            p_data = json.load(pf)
                            scenes = p_data.get("scenes") or p_data.get("szenen")
                    except Exception:
                        pass
            from master_regisseur import ask_lm_studio_music_tags
            tags = ask_lm_studio_music_tags(title, description, scenes=scenes)
            self.send_json({
                "success": True,
                "prompt_tags": tags,
                "tags": tags
            })
            return

        # -------------------------------------------------------------
        # POST /api/music/score-movie
        # -------------------------------------------------------------
        if path == "/api/music/score-movie":
            project = payload.get("project", "").strip()
            if not project:
                self.send_error_json("Feld 'project' erforderlich")
                return
            safe_proj = re.sub(r'[\\/*?:"<>| ]', '_', project)
            proj_dir = os.path.join(PROJECTS_DIR, safe_proj)
            movie_dir = os.path.join(proj_dir, "Movie")
            final_video = os.path.join(movie_dir, f"{safe_proj}_FINAL.mp4")
            if not os.path.exists(final_video):
                found_v = None
                if os.path.exists(movie_dir):
                    for f in os.listdir(movie_dir):
                        if f.endswith(".mp4") and "soundtrack" not in f.lower() and not f.endswith("_RAW.mp4"):
                            found_v = os.path.join(movie_dir, f)
                            break
                final_video = found_v

            if not final_video or not os.path.exists(final_video):
                self.send_error_json(f"Finales Video für '{project}' nicht gefunden in {movie_dir}. Bitte zuerst die Szenen fertigstellen!")
                return

            from master_regisseur import (
                find_file, WORKFLOWS_DIR, get_video_duration,
                generate_movie_soundtrack, mix_soundtrack_into_movie
            )
            settings = load_settings()
            wf_music_path = find_file("workflow_music_ace.json", [WORKFLOWS_DIR, BASE_DIR])
            if not wf_music_path or not os.path.exists(wf_music_path):
                self.send_error_json("Workflow 'workflow_music_ace.json' nicht gefunden.")
                return

            with open(wf_music_path, "r", encoding="utf-8") as mf:
                wf_music = json.load(mf)

            movie_dur = get_video_duration(final_video) or 30.0
            chosen_ckpt = payload.get("checkpoint") or settings.get("music_studio", {}).get("checkpoint") or "Other\\base model\\ace_step_v1_3.5b.safetensors"
            audio_prof = get_audio_model_profile(chosen_ckpt, settings.get("music_studio", {}).get("model_profiles"))
            prompt_tags = payload.get("prompt") or payload.get("tags") or "cinematic ambient soundtrack, acoustic guitar, warm pads, gentle tempo, instrumental"
            steps = int(payload.get("steps") or settings.get("music_studio", {}).get("steps") or audio_prof.get("default_steps", 40))
            cfg = float(payload.get("cfg") or settings.get("music_studio", {}).get("cfg") or audio_prof.get("default_cfg", 2.0))
            vol = float(payload.get("volume") or 0.20)
            ducking = bool(payload.get("ducking") if payload.get("ducking") is not None else True)

            try:
                aud_data, aud_fn = generate_movie_soundtrack(
                    wf_music,
                    prompt_tags=prompt_tags,
                    duration_seconds=movie_dur,
                    checkpoint=chosen_ckpt,
                    steps=steps,
                    cfg=cfg
                )
                if not aud_data:
                    self.send_error_json("ComfyUI konnte keine Audiodaten erzeugen.")
                    return

                ext = os.path.splitext(aud_fn)[1] if aud_fn else ".flac"
                soundtrack_file = os.path.abspath(os.path.join(movie_dir, f"{safe_proj}_soundtrack{ext}"))
                with open(soundtrack_file, "wb") as af:
                    af.write(aud_data)

                raw_backup = os.path.abspath(os.path.join(movie_dir, f"{safe_proj}_RAW.mp4"))
                if not os.path.exists(raw_backup):
                    shutil.copy2(final_video, raw_backup)

                scored_temp = os.path.abspath(os.path.join(movie_dir, f"{safe_proj}_SCORED.mp4"))
                mix_ok = mix_soundtrack_into_movie(raw_backup, soundtrack_file, scored_temp, volume=vol, ducking=ducking)
                if mix_ok and os.path.exists(scored_temp):
                    shutil.move(scored_temp, final_video)
                    self.send_json({
                        "success": True,
                        "soundtrack_url": f"/api/music/soundtrack?project={safe_proj}&t={int(time.time())}",
                        "video_url": f"/api/projects/video?name={safe_proj}&t={int(time.time())}",
                        "message": "Soundtrack erfolgreich generiert und eingemischt!"
                    })
                else:
                    self.send_error_json("FFmpeg Audio-Mix fehlgeschlagen.")
            except Exception as e:
                self.send_error_json(f"Fehler beim Nachvertonen: {e}")
            return

        # -------------------------------------------------------------
        # POST /api/project (Save Screenplay)
        # -------------------------------------------------------------
        if path == "/api/project":
            raw_filename = payload.get("filename", "").strip()
            data = payload.get("data")

            if not raw_filename or not data:
                self.send_error_json("Felder 'filename' und 'data' erforderlich")
                return

            safe_name = os.path.basename(raw_filename)
            if not safe_name.endswith(".json"):
                safe_name += ".json"

            target_path = os.path.join(PROJECTS_DIR, safe_name)

            # Safeguard: Create .bak file if file already exists
            if os.path.exists(target_path):
                bak_path = f"{target_path}.bak"
                try:
                    with open(target_path, "r", encoding="utf-8") as orig:
                        bak_content = orig.read()
                    with open(bak_path, "w", encoding="utf-8") as bak:
                        bak.write(bak_content)
                except Exception as be:
                    print(f"⚠️ Backup konnte nicht erstellt werden: {be}")

            try:
                with open(target_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                # Synchronize with project subfolder copy if directory exists (Projects/<film_name>/<film_name>.json)
                proj_base = os.path.splitext(safe_name)[0]
                sub_proj_dir = os.path.join(PROJECTS_DIR, proj_base)
                if os.path.isdir(sub_proj_dir):
                    sub_target_path = os.path.join(sub_proj_dir, safe_name)
                    try:
                        with open(sub_target_path, "w", encoding="utf-8") as sf:
                            json.dump(data, sf, indent=2, ensure_ascii=False)
                    except Exception as sbe:
                        print(f"⚠️ Subprojekt-Synchronisation fehlgeschlagen: {sbe}")

                self.send_json({
                    "success": True,
                    "filename": safe_name,
                    "message": f"Drehbuch '{safe_name}' erfolgreich gespeichert."
                })
            except Exception as e:
                self.send_error_json(f"Fehler beim Speichern: {e}", status=500)
            return

        # -------------------------------------------------------------
        # POST /api/llm/generate (Dispatched AI Tasks)
        # -------------------------------------------------------------
        if path == "/api/llm/generate":
            task = payload.get("task", "")
            if task == "elaborate_scene":
                res = ai_elaborate_scene(payload)
                self.send_json(res, status=200)
                return
            elif task == "suggest_next_scene":
                res = ai_suggest_next_scene(payload)
                self.send_json(res, status=200)
                return
            elif task == "suggest_variables":
                res = ai_suggest_variables(payload)
                self.send_json(res, status=200)
                return
            elif task == "optimize_character_prompt":
                res = ai_optimize_character_prompt(payload)
                self.send_json(res, status=200)
                return
            elif task == "generate_story_scenes":
                res = ai_generate_story_scenes(payload)
                self.send_json(res, status=200)
                return
            elif task == "wizard_step_scene":
                res = ai_wizard_step_scene(payload)
                self.send_json(res, status=200)
                return
            elif task == "harmonize_screenplay":
                res = ai_harmonize_screenplay(payload)
                self.send_json(res, status=200)
                return
            else:
                self.send_error_json(f"Unbekannte KI-Aufgabe '{task}'")
                return

        # -------------------------------------------------------------
        # POST /api/characters/upload_image (Upload & Remove BG)
        # -------------------------------------------------------------
        if path == "/api/characters/upload_image":
            project_param = payload.get("project", "").strip()
            char_name = payload.get("name", "").strip()
            image_b64 = payload.get("image_base64", "").strip()
            remove_bg = bool(payload.get("remove_background", True))

            if not project_param or not char_name or not image_b64:
                self.send_error_json("Parameter 'project', 'name' und 'image_base64' erforderlich", status=400)
                return

            safe_project = os.path.splitext(os.path.basename(project_param))[0]
            safe_char = re.sub(r'[\\/*?:"<>| ]', '_', char_name)

            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]

            try:
                img_bytes = base64.b64decode(image_b64)
            except Exception as e:
                self.send_error_json(f"Ungültige Base64-Bilddaten: {e}", status=400)
                return

            # Perform background removal if requested
            if remove_bg:
                try:
                    import importlib
                    rembg_mod = importlib.import_module("rembg")
                    remove_fn = getattr(rembg_mod, "remove")
                    print(f"✂️ [RemBG] Entferne Hintergrund für Charakter '{char_name}'...")
                    img_bytes = remove_fn(img_bytes)
                    print("✅ [RemBG] Hintergrund erfolgreich entfernt!")
                except Exception as re_err:
                    print(f"⚠️ [RemBG] Warnung: Hintergrundentfernung fehlgeschlagen ({re_err}), verwende Originalbild.")

            target_dir = os.path.join(PROJECTS_DIR, safe_project, "Characters")
            os.makedirs(target_dir, exist_ok=True)

            target_filename = f"{safe_char}.png"
            target_file = os.path.join(target_dir, target_filename)

            try:
                with open(target_file, "wb") as f:
                    f.write(img_bytes)

                timestamp = int(time.time())
                image_url = f"/api/characters/image?project={urllib.parse.quote(safe_project)}&name={urllib.parse.quote(safe_char)}&t={timestamp}"
                rel_path = f"Characters/{target_filename}"

                self.send_json({
                    "success": True,
                    "filename": target_filename,
                    "relative_path": rel_path,
                    "image_url": image_url,
                    "message": f"Referenzbild für '{char_name}' erfolgreich gespeichert."
                })
            except Exception as e:
                self.send_error_json(f"Fehler beim Speichern des Bildes: {e}", status=500)
            return

        # -------------------------------------------------------------
        # POST /api/characters/delete_image
        # -------------------------------------------------------------
        if path == "/api/characters/delete_image":
            project_param = payload.get("project", "").strip()
            char_name = payload.get("name", "").strip()
            if not project_param or not char_name:
                self.send_error_json("Parameter 'project' und 'name' erforderlich", status=400)
                return

            safe_project = os.path.splitext(os.path.basename(project_param))[0]
            safe_char = re.sub(r'[\\/*?:"<>| ]', '_', char_name)
            target_file = os.path.join(PROJECTS_DIR, safe_project, "Characters", f"{safe_char}.png")

            if os.path.exists(target_file):
                try:
                    os.remove(target_file)
                except Exception as e:
                    self.send_error_json(f"Fehler beim Löschen des Bildes: {e}", status=500)
                    return

            self.send_json({
                "success": True,
                "message": f"Referenzbild für '{char_name}' gelöscht."
            })
            return

        # -------------------------------------------------------------
        # POST /api/characters/generate_image (Generate portrait in ComfyUI)
        # -------------------------------------------------------------
        if path == "/api/characters/generate_image":
            project_param = payload.get("project", "").strip()
            char_data = payload.get("character", {})
            variables = payload.get("variables", {})
            remove_bg = bool(payload.get("remove_background", True))

            if not project_param or not char_data:
                self.send_error_json("Parameter 'project' und 'character' erforderlich", status=400)
                return

            res = generate_character_portrait_comfy(project_param, char_data, variables=variables, remove_bg=remove_bg)
            if res.get("success"):
                self.send_json(res, status=200)
            else:
                self.send_error_json(res.get("error", "Fehler bei der Bildgenerierung"), status=500)
            return

        # -------------------------------------------------------------
        # POST /api/rescan_catalog (Re-scan models & LoRAs)
        # -------------------------------------------------------------
        if path == "/api/rescan_catalog":
            models_dir = get_comfy_models_dir()
            if not models_dir or not os.path.exists(models_dir):
                self.send_error_json("ComfyUI-Modelle-Ordner nicht gefunden. Bitte in settings.json prüfen.")
                return

            try:
                from catalog_builder import build_or_update_catalog
                target_presets = os.path.join(PRESETS_DIR, "t2i_presets.json")
                stats = build_or_update_catalog(models_dir, presets_path=target_presets)
                _LORA_COMPANION_CACHE.clear()
                _MODEL_COMPANION_CACHE.clear()
                unavail_info = []
                if stats.get('unavailable_loras', 0) > 0:
                    unavail_info.append(f"{stats['unavailable_loras']} LoRAs nicht verfügbar")
                if stats.get('unavailable_presets', 0) > 0:
                    unavail_info.append(f"{stats['unavailable_presets']} Modelle nicht verfügbar")
                unavail_text = f" ({', '.join(unavail_info)})" if unavail_info else ""
                self.send_json({
                    "success": True,
                    "stats": stats,
                    "message": f"Katalog aktualisiert: {stats['total_loras']} LoRAs ({stats['new_loras']} neu) und {stats['total_presets']} Modell-Presets.{unavail_text}"
                })
            except Exception as e:
                self.send_error_json(f"Fehler beim Katalog-Scan: {e}", status=500)
            return

        # -------------------------------------------------------------
        # POST /api/shutdown (Clean server exit)
        # -------------------------------------------------------------
        if path == "/api/shutdown":
            self.send_json({"success": True, "message": "Server wird heruntergefahren."})

            def stop_server():
                import time
                time.sleep(0.5)
                if hasattr(self.server, 'shutdown'):
                    self.server.shutdown()

            threading.Thread(target=stop_server, daemon=True).start()
            return

        # -------------------------------------------------------------
        # POST /api/scene/rerender (Incrementally re-shoot single scene)
        # -------------------------------------------------------------
        if path == "/api/scene/rerender":
            project_param = payload.get("project", "").strip()
            scene_id = payload.get("scene_id")
            if not project_param or scene_id is None:
                self.send_error_json("Parameter 'project' und 'scene_id' erforderlich")
                return

            safe_project = os.path.splitext(os.path.basename(project_param))[0]
            proj_json = os.path.join(PROJECTS_DIR, f"{safe_project}.json")
            if not os.path.exists(proj_json):
                proj_json = os.path.join(PROJECTS_DIR, safe_project, f"{safe_project}.json")

            if not os.path.exists(proj_json):
                self.send_error_json(f"Projekt-Drehbuch '{safe_project}' nicht gefunden")
                return

            reshoot_key = f"{safe_project}_{scene_id}"
            _ACTIVE_RESHOOTS[reshoot_key] = {
                "project": safe_project,
                "scene_id": scene_id,
                "status": "rendering",
                "start_time": time.time(),
                "finished_at": None,
                "error": None
            }

            # Launch master_regisseur.py in background thread with --scene <id>
            def run_targeted_reshoot():
                import subprocess
                cmd = [
                    sys.executable,
                    "-u",
                    os.path.join(BASE_DIR, "master_regisseur.py"),
                    proj_json,
                    "--scene", str(scene_id)
                ]
                print(f"🎬 [Re-Render] Starte gezielten Dreh von Szene {scene_id} für '{safe_project}'...")
                try:
                    subprocess.run(cmd, cwd=BASE_DIR, check=True)
                    print(f"✅ [Re-Render] Szene {scene_id} erfolgreich neu gedreht!")
                    if reshoot_key in _ACTIVE_RESHOOTS:
                        _ACTIVE_RESHOOTS[reshoot_key]["status"] = "completed"
                        _ACTIVE_RESHOOTS[reshoot_key]["finished_at"] = time.time()
                except Exception as ex:
                    print(f"❌ [Re-Render] Fehler beim Drehen von Szene {scene_id}: {ex}")
                    if reshoot_key in _ACTIVE_RESHOOTS:
                        _ACTIVE_RESHOOTS[reshoot_key]["status"] = "error"
                        _ACTIVE_RESHOOTS[reshoot_key]["error"] = str(ex)
                        _ACTIVE_RESHOOTS[reshoot_key]["finished_at"] = time.time()

            t_thread = threading.Thread(target=run_targeted_reshoot, daemon=True)
            t_thread.start()

            self.send_json({
                "success": True,
                "message": f"Dreh für Szene {scene_id} wurde im Hintergrund gestartet.",
                "scene_id": scene_id,
                "project": safe_project
            })
            return

        # -------------------------------------------------------------
        # POST /api/movie/render (Launch full movie production in background)
        # -------------------------------------------------------------
        if path == "/api/movie/render":
            project_param = payload.get("project", "").strip()
            if not project_param:
                self.send_error_json("Parameter 'project' erforderlich")
                return

            safe_project = os.path.splitext(os.path.basename(project_param))[0]
            proj_json = os.path.join(PROJECTS_DIR, f"{safe_project}.json")
            if not os.path.exists(proj_json):
                proj_json = os.path.join(PROJECTS_DIR, safe_project, f"{safe_project}.json")

            if not os.path.exists(proj_json):
                self.send_error_json(f"Projekt-Drehbuch '{safe_project}' nicht gefunden")
                return

            existing_prod = _ACTIVE_PRODUCTIONS.get(safe_project)
            if existing_prod and existing_prod.get("status") == "running":
                self.send_json({
                    "success": False,
                    "error": f"Produktion für '{safe_project}' läuft bereits.",
                    "already_running": True,
                    "project": safe_project
                }, status=409)
                return

            prod_entry = {
                "project": safe_project,
                "status": "running",
                "start_time": time.time(),
                "finished_at": None,
                "error": None,
                "logs": [f"🎬 Starte vollständige Filmproduktion für '{safe_project}'..."],
                "last_log": "Filmproduktion wird initialisiert...",
                "process": None
            }
            _ACTIVE_PRODUCTIONS[safe_project] = prod_entry

            def run_full_production():
                import subprocess
                cmd = [
                    sys.executable,
                    "-u",
                    os.path.join(BASE_DIR, "master_regisseur.py"),
                    proj_json
                ]
                print(f"🎬 [Movie-Produktion] Starte vollständige Filmproduktion für '{safe_project}'...")
                try:
                    proc = subprocess.Popen(
                        cmd,
                        cwd=BASE_DIR,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        encoding="utf-8",
                        errors="replace"
                    )
                    prod_entry["process"] = proc
                    for line in iter(proc.stdout.readline, ''):
                        clean = line.rstrip()
                        if clean:
                            print(f"🎬 [{safe_project}] {clean}")
                            prod_entry["logs"].append(clean)
                            if len(prod_entry["logs"]) > 500:
                                prod_entry["logs"] = prod_entry["logs"][-500:]
                            prod_entry["last_log"] = clean
                    proc.wait()
                    if proc.returncode == 0:
                        print(f"✅ [Movie-Produktion] Produktion für '{safe_project}' erfolgreich abgeschlossen!")
                        prod_entry["status"] = "completed"
                        prod_entry["finished_at"] = time.time()
                        prod_entry["last_log"] = "Filmproduktion erfolgreich abgeschlossen!"
                    else:
                        if prod_entry.get("status") != "cancelled":
                            print(f"❌ [Movie-Produktion] Fehler bei Filmproduktion für '{safe_project}': Exit {proc.returncode}")
                            prod_entry["status"] = "error"
                            prod_entry["error"] = f"Prozess mit Code {proc.returncode} beendet"
                            prod_entry["finished_at"] = time.time()
                            prod_entry["last_log"] = f"Fehler: Beendet mit Code {proc.returncode}"
                except Exception as ex:
                    print(f"❌ [Movie-Produktion] Ausnahme bei Filmproduktion für '{safe_project}': {ex}")
                    if prod_entry.get("status") != "cancelled":
                        prod_entry["status"] = "error"
                        prod_entry["error"] = str(ex)
                        prod_entry["finished_at"] = time.time()
                        prod_entry["last_log"] = f"Fehler: {ex}"

            t_thread = threading.Thread(target=run_full_production, daemon=True)
            t_thread.start()

            self.send_json({
                "success": True,
                "message": f"Vollständige Produktion für '{safe_project}' wurde im Hintergrund gestartet.",
                "project": safe_project
            })
            return

        # -------------------------------------------------------------
        # POST /api/movie/render/cancel (Cancel ongoing full movie production)
        # -------------------------------------------------------------
        if path == "/api/movie/render/cancel":
            project_param = payload.get("project", "").strip()
            if not project_param:
                self.send_error_json("Parameter 'project' erforderlich")
                return

            safe_project = os.path.splitext(os.path.basename(project_param))[0]
            prod_entry = _ACTIVE_PRODUCTIONS.get(safe_project)
            if not prod_entry or prod_entry.get("status") != "running":
                self.send_json({
                    "success": False,
                    "message": "Keine laufende Produktion für dieses Projekt gefunden.",
                    "project": safe_project
                })
                return

            prod_entry["status"] = "cancelled"
            prod_entry["finished_at"] = time.time()
            prod_entry["last_log"] = "Produktion wurde vom Benutzer abgebrochen."
            prod_entry["logs"].append("🛑 Produktion wurde vom Benutzer abgebrochen.")

            proc = prod_entry.get("process")
            if proc:
                try:
                    import subprocess
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                    else:
                        proc.terminate()
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                print(f"🛑 [Movie-Produktion] Produktion für '{safe_project}' wurde abgebrochen.")

            self.send_json({
                "success": True,
                "message": f"Produktion für '{safe_project}' wurde abgebrochen.",
                "project": safe_project
            })
            return

        self.send_error_json(f"Unbekannte POST-Route: {path}", status=404)


def run_script_agency(port=None, host="127.0.0.1", open_browser=True, blocking=True):
    """
    Starts the Script Agency web server.
    Can be called standalone or imported by master_regisseur.py.
    """
    if port is None:
        port = find_free_port(7860)

    server_address = (host, port)
    httpd = HTTPServer(server_address, ScriptAgencyHandler)

    url = f"http://{host}:{port}/"
    print("\n" + "=" * 60)
    print(f"🎬 MOVIE STUDIO v{__version__} • MovieGenerator Visual Production Studio")
    print(f"👉 Web-Editor läuft unter: {url}")
    print("   [Tipp] Drücke Strg+C im Terminal oder klicke '✕' im Web, um zu beenden.")
    print("=" * 60 + "\n")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    if blocking:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Movie Studio beendet.")
        finally:
            httpd.server_close()
    else:
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        return httpd


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Movie Studio - Visual Production Studio")
    parser.add_argument("--port", type=int, default=None, help="Port für den Webserver (Standard: 7860)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host-Adresse (Standard: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Browser nicht automatisch öffnen")
    args = parser.parse_args()

    run_script_agency(
        port=args.port,
        host=args.host,
        open_browser=not args.no_browser,
        blocking=True
    )


if __name__ == "__main__":
    main()
