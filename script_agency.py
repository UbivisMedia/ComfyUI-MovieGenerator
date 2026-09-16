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
from http.server import HTTPServer, BaseHTTPRequestHandler

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
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

# Ensure required directories exist
os.makedirs(PROJECTS_DIR, exist_ok=True)
os.makedirs(PRESETS_DIR, exist_ok=True)
os.makedirs(WEB_DIR, exist_ok=True)


def load_settings():
    """Loads settings.json if available."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def get_comfy_models_dir():
    """Finds configured or fallback models_dir."""
    settings = load_settings()
    cfg_dir = settings.get("comfyui", {}).get("models_dir", "").strip()
    if cfg_dir and os.path.exists(cfg_dir):
        return cfg_dir
    search_paths = settings.get("comfyui", {}).get("models_search_paths", [
        "../ComfyUI/models",
        "../ComfyUI_windows_portable/ComfyUI/models"
    ])
    for p in search_paths:
        full_p = os.path.normpath(os.path.join(BASE_DIR, p))
        if os.path.exists(full_p):
            return full_p
    return None


def get_presets_data():
    """Loads t2i_presets.json, with fallback to t2i_presets.example.json."""
    primary = os.path.join(PRESETS_DIR, "t2i_presets.json")
    fallback = os.path.join(PRESETS_DIR, "t2i_presets.example.json")
    target = primary if os.path.exists(primary) else fallback

    if os.path.exists(target):
        try:
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading presets: {e}")

    return {
        "default": "anima_catpony",
        "presets": {},
        "lora_presets": {}
    }


def find_free_port(start_port=7860, max_tries=50):
    """Finds an available TCP port."""
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


# -------------------------------------------------------------
# LM Studio Local AI Integration
# -------------------------------------------------------------

def get_lm_studio_config():
    """Reads LM Studio configuration from settings.json."""
    settings = load_settings()
    lms = settings.get("lm_studio", {})
    url = lms.get("url", "http://127.0.0.1:1234/v1/chat/completions")
    model_name = lms.get("model_name", "")
    try:
        temp = float(lms.get("temperature", 0.7))
    except (TypeError, ValueError):
        temp = 0.7
    return {
        "url": url,
        "model_name": model_name,
        "temperature": temp
    }


def check_lm_studio_status():
    """Checks if LM Studio Local Server is running and lists loaded models."""
    cfg = get_lm_studio_config()
    url = cfg["url"]
    base_url = url.split("/chat/completions")[0] if "/chat/completions" in url else url.rstrip("/")
    models_url = f"{base_url}/models"
    try:
        req = urllib.request.Request(models_url, headers={"User-Agent": "MovieGenerator-ScriptAgency"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models_list = [m.get("id") for m in data.get("data", []) if m.get("id")]
            active_model = cfg["model_name"]
            if not active_model and models_list:
                active_model = models_list[0]
            elif models_list and active_model not in models_list:
                active_model = models_list[0]
            return {
                "online": True,
                "model": active_model or "Local LLM",
                "models": models_list,
                "url": url
            }
    except Exception as e:
        return {
            "online": False,
            "model": cfg.get("model_name") or "Offline",
            "error": str(e),
            "url": url
        }


def call_lm_studio(messages, temperature=0.7, max_tokens=5000):
    """Sends a chat completion request to the LM Studio Local Server."""
    cfg = get_lm_studio_config()

    # Prepend anti-thinking system message if none provided to keep reasoning models fast and direct
    has_system = any(m.get("role") == "system" for m in messages)
    clean_messages = list(messages)
    if not has_system:
        clean_messages.insert(0, {
            "role": "system",
            "content": "You are a direct, concise movie screenwriter assistant. Never output your internal thinking, reasoning process, or preamble. Start directly with the final response."
        })

    payload = {
        "model": cfg["model_name"] or "default",
        "messages": clean_messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    req = urllib.request.Request(
        cfg["url"],
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        msg = res["choices"][0]["message"]
        content = (msg.get("content") or "").strip()
        reasoning = (msg.get("reasoning_content") or "").strip()
        if not content and reasoning:
            # If the model put the final output or summary inside reasoning:
            if "summary:" in reasoning:
                content = "summary:" + reasoning.split("summary:", 1)[1]
            elif "Summary:" in reasoning:
                content = "summary:" + reasoning.split("Summary:", 1)[1]
            else:
                content = reasoning
        return content


def clean_elaborated_prompt(text, fallback_idea, characters=None):
    """Hardened sanitizer that guarantees NO thinking process or preamble leaks into the prompt."""
    if not text:
        text = ""
    
    # 1. If summary: or Summary: is present, discard EVERYTHING before it
    for marker in ["summary:", "Summary:", "**summary:**", "**Summary:**"]:
        if marker in text:
            text = text[text.index(marker):]
            text = "summary:" + text[len(marker):]
            break
            
    # 2. If summary: is STILL missing (e.g. model output only thinking or cut off):
    if "summary:" not in text.lower():
        extracted_shot = ""
        # Try to find [Shot 1] or Action/Framing in the thinking draft:
        shot_match = re.search(r'\[Shot 1\]:?\s*([^\n]+(?:\n(?![0-9]+\.|\*)[^\n]+)*)', text, re.IGNORECASE)
        if shot_match:
            extracted_shot = shot_match.group(1).strip()
        else:
            action_match = re.search(r'(?:Action/Framing|Action):\*?\s*([^\n]+(?:\n(?![0-9]+\.|\*)[^\n]+)*)', text, re.IGNORECASE)
            if action_match:
                extracted_shot = action_match.group(1).strip()
                
        if not extracted_shot or any(tr in extracted_shot.lower() for tr in ["analyze the request", "thinking process"]):
            extracted_shot = fallback_idea
            
        extracted_shot = re.sub(r'^\*+\s*', '', extracted_shot).strip()
        
        summary_sentence = fallback_idea.split('.')[0].strip() if fallback_idea else "A cinematic sequence."
        text = f"""summary: {summary_sentence}.
detailed_description:
[Shot 1]: {extracted_shot}
overall_soundscape:
Realistic ambient environment sounds, foley, and natural breathing. Strictly no music.
non_diegetic_music:
None
DURATION: 6
LORAS: None"""

    # 3. Clean any leftover markdown headers/thinking remnants
    lines = text.splitlines()
    clean_lines = []
    for line in lines:
        l_strip = line.strip().lower()
        if any(tr in l_strip for tr in ["here's a thinking", "here is a thinking", "here's a plan", "thinking process"]):
            continue
        clean_lines.append(line)
        
    cleaned = "\n".join(clean_lines).strip()
    return cleaned


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
    """Translates and expands a scene idea into a cinematic Minimax video prompt with continuity."""
    scene_obj = payload.get("scene") if isinstance(payload.get("scene"), dict) else {}
    idea = payload.get("idea") or scene_obj.get("idea") or scene_obj.get("idee") or scene_obj.get("prompt") or ""
    idea = idea.strip()
    if not idea:
        return {"success": False, "error": "Keine Szenenidee angegeben. Bitte gib zuerst eine Idee oder Handlung für die Szene ein."}

    characters = payload.get("characters") or scene_obj.get("characters") or []
    continuity = payload.get("continuity") or scene_obj
    variables = payload.get("variables") or {}
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

    preceding_blocks = []
    # Focus especially on scenes with the same sequence or location, or immediately preceding
    for ps in preceding_scenes[-4:]:
        ps_id = ps.get("id", "?")
        ps_seq = ps.get("sequence", "")
        ps_loc = ps.get("location", "")
        ps_idea = (ps.get("idea", "") or "").strip()
        if ps_idea:
            # Check if same sequence / scene group
            is_same_group = (sequence and ps_seq and sequence.lower() == ps_seq.lower()) or \
                            (location and ps_loc and location.lower() == ps_loc.lower())
            tag = " [SAME SCENE/SEQUENCE]" if is_same_group else ""
            preceding_blocks.append(f"- Shot #{ps_id}{tag} (Sequence: '{ps_seq}', Location: '{ps_loc}'):\n  {ps_idea}")

    preceding_text = "\n".join(preceding_blocks) if preceding_blocks else "None (this is the first shot)."

    char_defs = []
    char_names_lower = []
    for i, c in enumerate(characters):
        c_name = c if isinstance(c, str) else c.get("name", f"Character_{i+1}")
        char_defs.append(f"<Subject {i+1}> is the character in <Picture {i+1}> ({c_name}).")
        char_names_lower.append(c_name.lower())
    char_definitions = "\n".join(char_defs)

    # Filter variables: ONLY include variables that are directly in the idea or belong to the active characters!
    var_lines = []
    for k, v in variables.items():
        k_lower = k.lower()
        if f"{{{k}}}" in idea or f"{{{k_lower}}}" in idea.lower():
            var_lines.append(f"- {{{k}}} = '{v}'")
        elif any(cn in k_lower for cn in char_names_lower):
            var_lines.append(f"- {{{k}}} = '{v}'")
    var_text = "\n".join(var_lines) if var_lines else "None."

    presets = get_presets_data()
    lora_presets = presets.get("lora_presets", {})
    avail_loras = []
    for k, v in lora_presets.items():
        comp = v.get("kompatible_modelle", [])
        lname = v.get("lora_name", "").lower()
        if any(m in comp for m in ["minimax_h3", "minimax_h3_video"]) or "minimax" in lname or "mmh3" in k:
            if "turbo" not in k.lower():
                desc = v.get("beschreibung", "")
                avail_loras.append(f"- {k}: {desc}")
    avail_loras_text = "\n".join(avail_loras[:15]) if avail_loras else "None."

    # Documentation knowledge base loaded from docs/
    docs_knowledge = load_screenplay_docs_knowledge()

    messages = [
        {
            "role": "system",
            "content": f"""You are an expert cinematic prompt engineer for MovieGenerator.
When elaborating a single scene, output ONLY the final structured video prompt in English.
Do NOT output JSON. Absolutely NO reasoning, planning, or commentary.
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
- Environmental Reference: {continuity.get('use_previous_scene', False)}

Preceding Shots in the Screenplay (Maintain seamless posture and action continuity from these previous shots):
{preceding_text}

Character Bindings:
{char_definitions if char_definitions else "<Subject 1> is the character in <Picture 1>."}
Active Variables: {var_text}
Available Video LoRAs: {avail_loras_text}

Task:
Generate ONLY the cinematic Minimax prompt for this shot. If this is in the same scene/sequence as preceding shots, ensure characters maintain their established posture and positions!
Output format MUST be exactly:
summary: [one concise sentence describing the continuous scene action]
detailed_description:
[Shot 1]: [cinematic medium shot framing the action in 2-3 concise sentences using <Subject X> tags alongside character names]
overall_soundscape: [realistic ambient sound, foley, and spoken dialogue. Strictly NO music.]
non_diegetic_music: None
DURATION: 6
LORAS: None"""
        }
    ]

    try:
        raw_out = call_lm_studio(messages, temperature=0.3, max_tokens=4000)
        
        # Run hardened cleaner to guarantee no thinking process or preamble leaks into prompt:
        raw_out = clean_elaborated_prompt(raw_out, fallback_idea=idea, characters=characters)

        duration = 6
        dur_match = re.search(r'DURATION:\s*(\d+)', raw_out, re.IGNORECASE)
        if dur_match:
            try:
                duration = max(3, min(15, int(dur_match.group(1))))
            except ValueError:
                pass
            raw_out = re.sub(r'DURATION:\s*\d+', '', raw_out, flags=re.IGNORECASE).strip()

        selected_loras = []
        lora_match = re.search(r'LORAS:\s*([^\n]+)', raw_out, re.IGNORECASE)
        if lora_match:
            cand_str = lora_match.group(1).strip()
            raw_out = re.sub(r'LORAS:\s*[^\n]+', '', raw_out, flags=re.IGNORECASE).strip()
            if cand_str.lower() not in ["none", "n/a", "no", ""]:
                for item in re.split(r'[,;\s]+', cand_str):
                    clean_item = item.strip().strip("'\"`")
                    if clean_item in lora_presets and clean_item not in selected_loras:
                        selected_loras.append(clean_item)

        return {
            "success": True,
            "scene": {
                "idea": raw_out.strip(),
                "duration": duration,
                "loras": selected_loras
            },
            "elaborated_idea": raw_out.strip(),
            "duration": duration,
            "loras": selected_loras
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def ai_suggest_next_scene(payload):
    """Brainstorms and suggests the next logical scene for the screenplay."""
    sp = payload.get("screenplay") or payload
    title = sp.get("title") or payload.get("title") or "Film"
    description = sp.get("description") or payload.get("description") or ""
    characters = sp.get("characters") or payload.get("characters") or []
    scenes = sp.get("scenes") or payload.get("scenes") or []
    variables = sp.get("variables") or payload.get("variables") or {}

    char_names = [c.get("name") if isinstance(c, dict) else str(c) for c in characters]
    char_list_str = ", ".join(char_names) if char_names else "Hero, Antagonist"

    preceding = []
    for idx, s in enumerate(scenes[-4:]):
        s_id = s.get("id", idx + 1)
        s_seq = s.get("sequence", "")
        s_loc = s.get("location", "")
        s_idea = (s.get("idea", "") or "")[:120]
        preceding.append(f"Scene #{s_id} [{s_seq} - {s_loc}]: {s_idea}")
    preceding_str = "\n".join(preceding) if preceding else "No preceding scenes yet (opening scene)."

    var_str = ", ".join([f"{k}='{v}'" for k, v in variables.items()]) if variables else "None"

    prompt = f"""Movie Title: {title}
Storyline & Logline: {description}
Cast: {char_list_str}
Story Props/Variables: {var_str}

Preceding Scenes:
{preceding_str}

Task:
Create the next logical, engaging scene in this film in 2 to 3 concise sentences.
Return ONLY a single valid JSON object without markdown wrapping or preamble, in exactly this JSON structure:
{{
  "sequence": "Sequence or Beat title (e.g. Confrontation in Alley)",
  "location": "Location setting (e.g. Neon-lit back alley)",
  "duration": 6,
  "characters": ["{char_names[0] if char_names else 'Hero'}"],
  "idea": "Vivid concise cinematic description of what happens in this scene...",
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
Extract up to 3 truly essential recurring props, iconic character outfits, or primary locations repeatedly mentioned in the story above.
STRICT RULES:
1. ONLY extract items EXPLICITLY mentioned in the scenes or storyline above.
2. Do NOT invent hypothetical items, sci-fi gadgets, or accessories not found in the text.
3. If no recurring props or outfits exist, return an empty JSON object: {{}}
4. Return ONLY valid JSON mapping variable_name to description, e.g.:
{{
  "outfit_hero": "worn dark leather jacket"
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


def ai_optimize_character_prompt(payload):
    """Optimizes a character description into model-tailored ComfyUI tags."""
    char = payload.get("character", {})
    preset_name = payload.get("preset", "anima_catpony")
    title = payload.get("title", "")
    story_desc = payload.get("description", "")

    char_name = char.get("name", "Character")
    char_desc = char.get("description", "")

    presets = get_presets_data()
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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # -------------------------------------------------------------
        # REST API Routes
        # -------------------------------------------------------------
        if path == "/api/localization":
            from localization import get_current_language, get_all_editor_translations
            self.send_json({
                "active_lang": get_current_language(),
                "translations": get_all_editor_translations()
            })
            return

        if path == "/api/presets":
            presets = get_presets_data()
            self.send_json(presets)
            return

        if path == "/api/llm/status":
            self.send_json(check_lm_studio_status())
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
                self.send_json({
                    "file": safe_name,
                    "data": content
                })
            except Exception as e:
                self.send_error_json(f"Fehler beim Lesen der Datei: {e}", status=500)
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
            else:
                self.send_error_json(f"Unbekannte KI-Aufgabe '{task}'")
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
                self.send_json({
                    "success": True,
                    "stats": stats,
                    "message": f"Katalog aktualisiert: {stats['total_loras']} LoRAs ({stats['new_loras']} neu) und {stats['total_presets']} Modell-Presets."
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
    print("🎬 SCRIPT AGENCY • MovieGenerator Visual Screenplay Studio")
    print(f"👉 Web-Editor läuft unter: {url}")
    print("   [Tipp] Drücke Strg+C im Terminal oder klicke '✕' im Web, um zu beenden.")
    print("=" * 60 + "\n")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    if blocking:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Script Agency beendet.")
        finally:
            httpd.server_close()
    else:
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        return httpd


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Script Agency - Visual Screenplay Editor")
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
