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

    char_defs = []
    char_names_clean = []
    char_display_names = []
    for i, c in enumerate(characters):
        c_name = c if isinstance(c, str) else c.get("name", f"Character_{i+1}")
        char_defs.append(f"<Subject {i+1}> is the character in <Picture {i+1}> ({c_name}).")
        char_display_names.append(c_name)
        char_names_clean.append(re.sub(r'[^a-zA-Z0-9]', '', c_name.lower()))
    char_definitions = "\n".join(char_defs)

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
- Environmental Reference: {continuity.get('use_previous_scene', False)}

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
[Shot 1]: [cinematic medium/close shot framing the action in 2-3 concise sentences using <Subject X> tags alongside character names. If live-action, specify 35mm cinematic film aesthetics.]
overall_soundscape: [realistic ambient environment sounds, foley, and spoken dialogue. Strictly NO music.]
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
                normalized, converted = normalize_screenplay_data(content, filename=safe_name)
                self.send_json({
                    "file": safe_name,
                    "data": normalized,
                    "converted_legacy": converted
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
