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

from localization import t

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRESETS_DIR = os.path.join(BASE_DIR, "Presets")
WORKFLOWS_DIR = os.path.join(BASE_DIR, "Workflows")
PROJECTS_DIR = os.path.join(BASE_DIR, "Projects")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

def load_settings():
    """Loads configuration from settings.json with safe fallback default values."""
    defaults = {
        "language": "auto",
        "export_webm": False,
        "comfyui": {
            "server_address": "127.0.0.1:8188",
            "models_dir": "",
            "models_search_paths": [
                "../ComfyUI/models",
                "../ComfyUI_windows_portable/ComfyUI/models"
            ]
        },
        "lm_studio": {
            "url": "http://127.0.0.1:1234/v1/chat/completions",
            "model_name": "gemma-4-e4b-uncensored-hauhaucs-aggressive",
            "temperature": 0.7
        }
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as sf:
                cfg = json.load(sf)
                if isinstance(cfg, dict):
                    if "language" in cfg:
                        defaults["language"] = cfg["language"]
                    if "export_webm" in cfg:
                        defaults["export_webm"] = bool(cfg["export_webm"])

                    # ComfyUI configuration
                    if "comfyui" in cfg and isinstance(cfg["comfyui"], dict):
                        defaults["comfyui"].update(cfg["comfyui"])
                    elif "server_address" in cfg:
                        defaults["comfyui"]["server_address"] = cfg["server_address"]

                    # LM Studio configuration
                    if "lm_studio" in cfg and isinstance(cfg["lm_studio"], dict):
                        defaults["lm_studio"].update(cfg["lm_studio"])
                    else:
                        if "lm_studio_url" in cfg:
                            defaults["lm_studio"]["url"] = cfg["lm_studio_url"]
                        if "llm_model_name" in cfg:
                            defaults["lm_studio"]["model_name"] = cfg["llm_model_name"]
                        if "temperature" in cfg:
                            defaults["lm_studio"]["temperature"] = cfg["temperature"]
        except Exception:
            pass
    return defaults

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
    return json.loads(urllib.request.urlopen(req).read())

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

def ask_lm_studio_character(char, screenplay, preset_name, preset):
    """Invokes LM Studio to generate the optimal T2I character casting prompt."""
    char_name = char.get("name", "Character")
    existing_prompt = char.get("prompt") or char.get("beschreibung") or char.get("rolle") or char.get("idee") or char.get("description") or ""
    
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

def interpolate_variables(text, variables):
    """Replaces {variable_name} in text with its current value from variables dictionary."""
    if not text or not variables:
        return text
    result = text
    for key, val in variables.items():
        result = result.replace(f"{{{key}}}", str(val))
    return result

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

def ask_lm_studio(
    idea,
    characters,
    use_previous_scene=False,
    direct_continuation=False,
    active_variables=None,
    character_states=None,
    previous_shot_context=None,
    same_scene=False,
    sequence_info=None
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

CRITICAL SCENE & SHOT CONTINUITY:
{continuity_instruction}

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

Here is the scene idea:
{idee}"""

    minimax_template = load_prompt_template("minimax_scene.txt", default_minimax_instruction)
    instruction = format_prompt_template(
        minimax_template,
        char_definitions=char_definitions.strip(),
        continuity_instruction=continuity_instruction,
        video_instruction=video_instruction,
        state_instruction=state_instruction,
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

        # Strictly ensure non_diegetic_music is set to None and no background music is generated
        if "non_diegetic_music:" in content.lower():
            content = re.sub(r'non_diegetic_music:\s*.*', 'non_diegetic_music:\nNone', content, flags=re.IGNORECASE)
        else:
            content += "\n\nnon_diegetic_music:\nNone"

        if "overall_soundscape:" not in content.lower():
            content += "\n\noverall_soundscape:\nRealistic ambient environment sounds, subtle foley, and natural breathing. Strictly no music."
            
        return content, duration
    except Exception as e:
        print(t("lms_scene_error", error=e))
        state_fallback = f"\n[Active Wardrobe & State: {state_instruction}]" if active_variables or character_states else ""
        return (
            f"subject_definitions:\n{char_definitions.strip()}\n\n"
            f"summary:\n[reference generation] {idea}\n\n"
            f"detailed_description:\n[Shot 1]: {idea}{state_fallback}\n\n"
            f"overall_soundscape:\nNatural ambient room sounds, diegetic foley effects, and speech. Strictly no background music.\n\n"
            f"non_diegetic_music:\nNone",
            5
        )

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

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", "ffmpeg_list.txt",
        "-i", "ffmetadata.txt",
        "-map_metadata", "1",
        "-c", "copy",
        final_video_path
    ]
    
    try:
        res = subprocess.run(cmd, cwd=scenes_dir, check=True, capture_output=True, text=True)
        print(t("cutting_success", path=final_video_path))
        
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
    # 1. Determine screenplay input
    if len(sys.argv) >= 2:
        screenplay_input = sys.argv[1]
    else:
        # Interactive menu selection or fallback
        available = [f for f in os.listdir(PROJECTS_DIR) if f.endswith(".json")]
        if available:
            print(t("menu_available_screenplays"))
            for idx, f in enumerate(available, 1):
                print(f"  [{idx}] {f}")
            print(t("menu_instruction"))
            try:
                choice = input(t("menu_prompt")).strip()
                if choice.isdigit() and 1 <= int(choice) <= len(available):
                    screenplay_input = os.path.join(PROJECTS_DIR, available[int(choice) - 1])
                elif choice in available:
                    screenplay_input = os.path.join(PROJECTS_DIR, choice)
                else:
                    print(t("menu_invalid_choice"))
                    time.sleep(3)
                    return
            except Exception:
                return
        else:
            print(t("menu_no_screenplays"))
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
    if os.path.abspath(screenplay_path) != os.path.abspath(local_screenplay_copy):
        try:
            shutil.copy2(screenplay_path, local_screenplay_copy)
        except Exception:
            pass

    # Ensure a pristine copy of the original input screenplay is preserved for diffs/reference
    if not os.path.exists(original_screenplay_backup):
        try:
            shutil.copy2(screenplay_path, original_screenplay_backup)
        except Exception:
            pass

    print(t("loading_screenplay", film_name=film_name))
    print(t("project_dir", path=project_dir))
    print(f"   ├── Characters: {characters_dir}")
    print(f"   ├── Scenes:     {scenes_dir}")
    print(f"   └── Movie:      {movie_dir}")

    with open(screenplay_path, "r", encoding="utf-8") as f:
        screenplay = json.load(f)

    # Load workflows and presets
    wf_t2i_path = find_file("workflow_t2i.json", [WORKFLOWS_DIR, BASE_DIR])
    wf_i2v_path = find_file("workflow_i2v_api.json", [WORKFLOWS_DIR, BASE_DIR])
    t2i_presets_path = find_file("t2i_presets.json", [PRESETS_DIR, BASE_DIR])

    with open(wf_t2i_path, "r", encoding="utf-8") as f:
        wf_t2i = json.load(f)
        
    with open(wf_i2v_path, "r", encoding="utf-8") as f:
        wf_i2v = json.load(f)

    t2i_presets = {}
    if os.path.exists(t2i_presets_path):
        try:
            with open(t2i_presets_path, "r", encoding="utf-8") as pf:
                t2i_presets = json.load(pf)
        except Exception as pe:
            print(t("presets_load_error", error=pe))

    # =========================================================================
    # PHASE 1: Screenwriting & Character Prompting (LM Studio)
    # =========================================================================
    print(t("phase1_start"))
    lms_load()
    
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

    prepared_scenes = []
    try:
        # 1. Generate/optimize character prompts via AI (if not already cached)
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

            print(t("char_optimizing_prompt", name=char_name, preset=preset_name))
            ki_char_prompt = ask_lm_studio_character(char, screenplay, preset_name, preset)
            char["prompt"] = ki_char_prompt
            print(t("char_new_prompt", name=char_name, prompt=ki_char_prompt[:90]))

        # 2. Generate Minimax scene prompts with sequence grouping & previous shot context
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

            if not auto_prompt and scene.get("prompt"):
                print(t("scene_keep_manual_prompt", id=scene_id))
                minimax_prompt = scene["prompt"]
                calculated_duration = (
                    scene.get("dauer_sekunden") or 
                    scene.get("duration_seconds") or 
                    scene.get("duration") or 
                    scene.get("dauer") or 
                    5
                )
            else:
                minimax_prompt, calculated_duration = ask_lm_studio(
                    scene_idea,
                    characters_list,
                    use_previous_scene=use_previous_scene,
                    direct_continuation=direct_continuation,
                    active_variables=active_variables,
                    character_states=char_status_updates,
                    previous_shot_context=prev_shot_ctx,
                    same_scene=same_scene,
                    sequence_info=seq_info
                )

            # Extract shot summary for the next shot's continuity context
            m_sum = re.search(r'summary:\s*([^\n]+(?:\n[^\n]+)?)', minimax_prompt, re.IGNORECASE)
            cur_summary = m_sum.group(1).strip() if m_sum else scene_idea

            previous_shot_info = {
                "id": scene_id,
                "summary": cur_summary,
                "sequence": seq_name,
                "location": loc_name
            }

            # Update scene dictionary in screenplay with generated prompt & duration
            scene["prompt"] = minimax_prompt
            scene["dauer_sekunden"] = calculated_duration
            if seq_name and "sequenz" not in scene and "sequence" not in scene:
                scene["sequence"] = seq_name
            if loc_name and "ort" not in scene and "location" not in scene:
                scene["location"] = loc_name

            prepared_scenes.append({
                "id": scene_id,
                "prompt": minimax_prompt,
                "dauer": calculated_duration,
                "nutze_vorherige_szene": use_previous_scene,
                "direkter_anschluss": direct_continuation,
                "gleiche_szene": same_scene,
                "sequenz": seq_name,
                "ort": loc_name,
                "variables": dict(active_variables),
                "idee": scene_idea
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
            print(t("scene_written", id=scene_id, dauer=calculated_duration, anschluss=anschluss_txt))

        # Save extended screenplay with AI-generated character & scene prompts to the project directory
        try:
            with open(local_screenplay_copy, "w", encoding="utf-8") as sf:
                json.dump(screenplay, sf, indent=2, ensure_ascii=False)
            print(t("screenplay_extended_saved", path=local_screenplay_copy))
        except Exception as se:
            print(f"⚠️ Could not save extended screenplay: {se}")
    finally:
        # Immediately unload LLM as soon as all screenplay prompts are written!
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

        full_prompt = char["prompt"]
        if extra_trigger_words:
            new_triggers = [tw for tw in extra_trigger_words if tw.lower() not in full_prompt.lower()]
            if new_triggers:
                full_prompt = full_prompt.rstrip(", ") + ", " + ", ".join(new_triggers)

        steps_info = wf_t2i["19"]["inputs"].get("steps", "?")
        cfg_info = wf_t2i["19"]["inputs"].get("cfg", "?")
        lora_status_str = f" | LoRAs: {', '.join(applied_loras_info)}" if applied_loras_info else ""
        print(t("char_casting_running", num=i+1, name=char_name, model=preset_name, loras=lora_status_str, steps=steps_info, cfg=cfg_info))

        wf_t2i["11"]["inputs"]["text"] = full_prompt
        wf_t2i["19"]["inputs"]["seed"] = random.randint(1, 999999999999999)
        
        res = queue_prompt(wf_t2i)
        prompt_id = res['prompt_id']
        
        while True:
            history = get_history(prompt_id)
            if prompt_id in history:
                outputs = history[prompt_id]['outputs']
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

                        # Save image with embedded Civitai parameters and ComfyUI workflow JSON
                        save_image_with_metadata(img_data, char_file, prompt_workflow=wf_t2i, a1111_params_text=civitai_actor_params)

                        with open(char_file, "rb") as cf:
                            saved_img_bytes = cf.read()

                        uploaded_name = upload_file(saved_img_bytes, f"{safe_name}.png", "image/png")
                        char["echter_dateiname"] = uploaded_name
                        print(t("char_generated_saved", name=char_name, file=char_file))
                        break
                break
            time.sleep(2)

    # Free T2I casting models (Anima, WanVAE, BiRefNet) from VRAM before starting video generation
    free_comfyui_memory(unload_models=True, free_memory=True)

    # =========================================================================
    # PHASE 3: Video Production (Minimax Studio)
    # =========================================================================
    print(t("phase3_start"))
    last_video_data = None
    last_video_path = None

    for scene_data in prepared_scenes:
        szene_id = scene_data["id"]
        print(t("scene_shooting", id=szene_id))
        
        wf_i2v["138"]["inputs"]["value"] = scene_data["prompt"]
        
        keys_to_remove = [k for k in wf_i2v["136"]["inputs"].keys() if k.startswith("ref_images.ref_image_") or k.startswith("ref_videos.")]
        for k in keys_to_remove:
            del wf_i2v["136"]["inputs"][k]
        if "9100" in wf_i2v:
            del wf_i2v["9100"]
        if "9200" in wf_i2v:
            del wf_i2v["9200"]
        if "9201" in wf_i2v:
            del wf_i2v["9201"]
        wf_i2v["126"]["inputs"]["conditioning"] = ["648", 0]
            
        for i, char in enumerate(characters_list):
            node_id = f"900{i}" 
            wf_i2v[node_id] = {
                "inputs": {"image": char["echter_dateiname"]},
                "class_type": "LoadImage"
            }
            wf_i2v["136"]["inputs"][f"ref_images.ref_image_{i}"] = [node_id, 0]
            
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

        # Direct seamless match cut via MiniMaxH3AddGuide (first_frame)
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
                        "positive": ["648", 0],
                        "latent": ["682", 0],
                        "vae": ["119", 0],
                        "image": ["9200", 0],
                        "frame_idx": 0
                    },
                    "class_type": "MiniMaxH3AddGuide"
                }
                wf_i2v["126"]["inputs"]["conditioning"] = ["9201", 0]
                print(t("scene_direct_connection_active", frame=uploaded_frame_name))
            else:
                print(t("scene_extract_last_frame_failed"))
        
        wf_i2v["142"]["inputs"]["seed"] = random.randint(1, 999999999999999)
        wf_i2v["132"]["inputs"]["value"] = scene_data["dauer"]

        res = queue_prompt(wf_i2v)
        prompt_id = res['prompt_id']
        print(t("scene_rendering_started"))
        
        while True:
            history = get_history(prompt_id)
            if prompt_id in history:
                outputs = history[prompt_id]['outputs']
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