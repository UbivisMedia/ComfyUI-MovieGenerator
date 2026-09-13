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
        "comfyui": {
            "server_address": "127.0.0.1:8188"
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
                    # ComfyUI configuration
                    if "comfyui" in cfg and isinstance(cfg["comfyui"], dict):
                        defaults["comfyui"]["server_address"] = cfg["comfyui"].get("server_address", defaults["comfyui"]["server_address"])
                    elif "server_address" in cfg:
                        defaults["comfyui"]["server_address"] = cfg["server_address"]

                    # LM Studio configuration
                    if "lm_studio" in cfg and isinstance(cfg["lm_studio"], dict):
                        defaults["lm_studio"]["url"] = cfg["lm_studio"].get("url", defaults["lm_studio"]["url"])
                        defaults["lm_studio"]["model_name"] = cfg["lm_studio"].get("model_name", defaults["lm_studio"]["model_name"])
                        defaults["lm_studio"]["temperature"] = cfg["lm_studio"].get("temperature", defaults["lm_studio"]["temperature"])
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

def ask_lm_studio_character(char, screenplay, preset_name, preset):
    """Invokes LM Studio to generate the optimal T2I character casting prompt."""
    char_name = char.get("name", "Character")
    existing_prompt = char.get("prompt") or char.get("beschreibung") or char.get("rolle") or char.get("idee") or char.get("description") or ""
    
    # Short scenes overview for narrative context
    scenes_overview = "\n".join([f"- Szene {s.get('id', idx+1)}: {s.get('idee', '')}" for idx, s in enumerate(screenplay.get("szenen", []))])
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

def ask_lm_studio(idea, characters, use_previous_scene=False, direct_continuation=False):
    print(t("scene_elaborating", idea=idea))
    
    char_definitions = ""
    for i, char in enumerate(characters):
        char_definitions += f"<Subject {i+1}> is the character in <Picture {i+1}> ({char['name']}).\n"

    video_instructions = []
    if use_previous_scene:
        env_snippet = load_prompt_template(
            "continuity_environment.txt",
            "The user wants to keep the continuity from the previous scene. You MUST include '<Video 1> establishes the environment' in your detailed description so the model knows to use the previous video as a reference for the location/setting."
        )
        video_instructions.append(env_snippet.strip())
    if direct_continuation:
        matchcut_snippet = load_prompt_template(
            "continuity_matchcut.txt",
            "CRITICAL CONTINUITY: This scene is a DIRECT SEAMLESS CONTINUATION (match cut) starting from the exact final frame of the previous scene. The action and character motion must immediately pick up where the previous scene ended without resetting posture or changing camera angle abruptly."
        )
        video_instructions.append(matchcut_snippet.strip())

    video_instruction = ("\nIMPORTANT CONTINUITY INSTRUCTIONS:\n" + "\n".join(video_instructions)) if video_instructions else ""

    default_minimax_instruction = """You are an expert prompt engineer for the Minimax video generation model.
You will receive a short scene idea in German. Translate it to English and expand it into this EXACT format.
Also, estimate how many seconds this shot should take based on the action (between 3 and 15) and write it at the very end as DURATION: X.

CRITICAL AUDIO REQUIREMENT:
- Absolutely NO non-diegetic background music, soundtrack, or score! The individual scenes will be spliced together, so inconsistent music ruins the final movie.
- Under 'overall_soundscape:', describe ONLY realistic diegetic ambient sounds, natural environment foley (footsteps, breathing, cloth rustle, room acoustics), and character speech/dialogue if any.
- Under 'non_diegetic_music:', ALWAYS write: None

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
        video_instruction=video_instruction,
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
        return (
            f"subject_definitions:\n{char_definitions.strip()}\n\n"
            f"summary:\n[reference generation] {idea}\n\n"
            f"detailed_description:\n[Shot 1]: {idea}\n\n"
            f"overall_soundscape:\nNatural ambient room sounds, diegetic foley effects, and speech. Strictly no background music.\n\n"
            f"non_diegetic_music:\nNone",
            5
        )

def assemble_movie(scenes_dir, movie_dir, movie_name, screenplay=None, prepared_scenes=None):
    """Concatenates all generated scene clips into the final movie using FFmpeg with embedded Civitai metadata."""
    print(t("cutting_start"))
    
    scene_files = sorted([f for f in os.listdir(scenes_dir) if f.startswith("Szene_") and f.endswith(".mp4")])
    
    if not scene_files:
        print(t("cutting_no_scenes"))
        return
        
    list_path = os.path.join(scenes_dir, "ffmpeg_list.txt")
    with open(list_path, "w", encoding="utf-8") as lf:
        for scene in scene_files:
            lf.write(f"file '{scene}'\n")
            
    final_video_path = os.path.join(movie_dir, f"{movie_name}_FINAL.mp4")

    # Build Civitai-compatible metadata summary
    movie_title = (screenplay.get("titel") or screenplay.get("title") or movie_name) if screenplay else movie_name
    movie_desc = (screenplay.get("beschreibung") or screenplay.get("description") or "") if screenplay else ""

    civitai_summary = [f"Title: {movie_title}"]
    if movie_desc:
        civitai_summary.append(f"Description: {movie_desc}")
    civitai_summary.append("Generator: MovieGenerator AI Studio (ComfyUI Minimax I2V + T2I Casting)")

    if screenplay and (screenplay.get("charaktere") or screenplay.get("characters")):
        chars_list = screenplay.get("charaktere") or screenplay.get("characters")
        civitai_summary.append("\nCast & Models:")
        for c in chars_list:
            c_name = c.get("name", "Unknown")
            c_model = c.get("modell") or c.get("preset") or c.get("model") or "default"
            c_loras = c.get("loras") or c.get("lora") or []
            if isinstance(c_loras, list):
                lora_str = ", ".join([str(x.get("name") if isinstance(x, dict) else x) for x in c_loras])
            else:
                lora_str = str(c_loras)
            civitai_summary.append(f"- {c_name} (Model: {c_model}" + (f", LoRAs: {lora_str}" if lora_str else "") + ")")

    if prepared_scenes:
        civitai_summary.append("\nScenes & Prompts:")
        for s in prepared_scenes:
            s_id = s.get("id", "?")
            s_dur = s.get("dauer", "?")
            s_cont = " [Match Cut]" if s.get("direkter_anschluss") else (" [Environment Ref]" if s.get("nutze_vorherige_szene") else "")
            civitai_summary.append(f"- Scene {s_id} ({s_dur}s){s_cont}:")
            p_text = s.get("prompt", "").strip()
            if p_text:
                civitai_summary.append(f"  Prompt: {p_text}")

    full_description = "\n".join(civitai_summary)

    metadata_json = {
        "generator": "MovieGenerator",
        "title": movie_title,
        "screenplay": screenplay,
        "scenes": prepared_scenes
    }
    metadata_json_str = json.dumps(metadata_json, ensure_ascii=False)

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "ffmpeg_list.txt",
        "-c", "copy",
        "-metadata", f"title={movie_title}",
        "-metadata", "artist=MovieGenerator AI Studio",
        "-metadata", f"description={full_description}",
        "-metadata", f"comment={metadata_json_str}",
        final_video_path
    ]
    
    try:
        subprocess.run(cmd, cwd=scenes_dir, check=True, capture_output=True)
        print(t("cutting_success", path=final_video_path))
    except Exception as e:
        print(t("cutting_error", error=e))
        
    if os.path.exists(list_path):
        os.remove(list_path)

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
    if os.path.abspath(screenplay_path) != os.path.abspath(local_screenplay_copy):
        try:
            shutil.copy2(screenplay_path, local_screenplay_copy)
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
    
    prepared_scenes = []
    try:
        # 1. Generate/optimize character prompts via AI (if not already cached)
        print(t("phase1_developing_chars"))
        characters_list = screenplay.get("charaktere") or screenplay.get("characters") or []
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

            if char.get("ki_prompt_generieren") is False or char.get("auto_prompt") is False:
                print(t("char_keep_manual_prompt", name=char_name))
                continue

            print(t("char_optimizing_prompt", name=char_name, preset=preset_name))
            ki_char_prompt = ask_lm_studio_character(char, screenplay, preset_name, preset)
            char["prompt"] = ki_char_prompt
            print(t("char_new_prompt", name=char_name, prompt=ki_char_prompt[:90]))

        # 2. Generate Minimax scene prompts
        print(t("phase1_writing_scenes"))
        scenes_list = screenplay.get("szenen") or screenplay.get("scenes") or []
        for scene in scenes_list:
            use_previous_scene = scene.get("anschluss_an_vorherige_szene", False) or scene.get("continuity_environment", False)
            direct_continuation = scene.get("direkter_anschluss", False) or scene.get("direct_continuation", False)
            scene_idea = scene.get("idee") or scene.get("idea", "")
            minimax_prompt, calculated_duration = ask_lm_studio(scene_idea, characters_list, use_previous_scene, direct_continuation)
            
            prepared_scenes.append({
                "id": scene["id"],
                "prompt": minimax_prompt,
                "dauer": calculated_duration,
                "nutze_vorherige_szene": use_previous_scene,
                "direkter_anschluss": direct_continuation
            })
            continuity_txt = t("scene_continuity_seamless") if direct_continuation else (t("scene_continuity_ref") if use_previous_scene else "")
            print(t("scene_written", id=scene['id'], dauer=calculated_duration, anschluss=continuity_txt))
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

                                print(t("scene_finished", id=szene_id, path=target_path))
                                
                                last_video_data = vid_data
                                last_video_path = target_path
                                free_comfyui_memory(unload_models=False, free_memory=True)
                                break
                break
            time.sleep(10)

    print(t("all_scenes_finished"))
    assemble_movie(scenes_dir, movie_dir, film_name, screenplay=screenplay, prepared_scenes=prepared_scenes)

if __name__ == "__main__":
    try:
        main()
    finally:
        lms_unload()