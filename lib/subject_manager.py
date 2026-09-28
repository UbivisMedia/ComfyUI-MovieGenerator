"""
lib/subject_manager.py - Centralized Subject & Cast Management for MovieGenerator

Provides unified, robust logic for resolving scene cast members, capping active
reference images to MiniMax H3's hardware limit (max 9), and dynamically re-mapping
global character IDs (<Subject X>) to local 1-based scene slots (<Subject 1> .. <Subject N>).

Shared across both master_regisseur.py (full movie generation & targeted reshoots)
and script_agency.py (single-scene ideation, screenplay harmonization, and web APIs).
"""

import os
import re
import json

MAX_MINIMAX_SUBJECTS = 9


def build_character_lookup(characters_list):
    """
    Builds a comprehensive lookup map from various keys (id, name, clean name, short name)
    to character dictionaries.
    """
    char_map = {}
    if not characters_list:
        return char_map

    for idx, c in enumerate(characters_list):
        if not isinstance(c, dict):
            c = {"name": str(c), "id": idx + 1}
        c_id = str(c.get("id") or (idx + 1)).strip()
        char_map[c_id] = c
        c_name = str(c.get("name") or "").strip()
        if c_name:
            char_map[c_name.lower()] = c
            # Map without spaces/punctuation
            c_clean = re.sub(r'[^a-zA-Z0-9]', '', c_name.lower())
            if c_clean:
                char_map[c_clean] = c
            # Map suffix if prefixed (e.g. Team_2_Laura -> laura)
            parts = re.split(r'[_ -]+', c_name)
            if len(parts) > 1:
                short = parts[-1].strip().lower()
                if short and short not in char_map:
                    char_map[short] = c

    return char_map


def resolve_scene_characters(scene, characters_list=None, max_subjects=MAX_MINIMAX_SUBJECTS):
    """
    Resolves the list of character objects active in a specific scene.
    Preserves the exact order of appearance in the scene definition.
    Supports:
      - dict objects
      - character names ('Team_2_Laura')
      - tags like '<Subject 7> (Laura)' or '<Subject 7>'
    Falls back to idea/prompt text inspection or first cast members.
    Hard-caps at max_subjects (default 9) to prevent ComfyUI MiniMaxH3 node crashes.
    """
    if not characters_list:
        characters_list = []

    char_map = build_character_lookup(characters_list)

    raw_chars = (
        scene.get("charaktere") or 
        scene.get("characters") or 
        scene.get("cast") or 
        scene.get("actors")
    )

    resolved = []
    if raw_chars:
        if isinstance(raw_chars, str):
            raw_list = [x.strip() for x in raw_chars.split(",") if x.strip()]
        elif isinstance(raw_chars, list):
            raw_list = raw_chars
        else:
            raw_list = [raw_chars]

        for item in raw_list:
            if not item:
                continue
            if isinstance(item, dict):
                k_id = str(item.get("id") or "").strip()
                k_name = str(item.get("name") or "").strip().lower()
                found = char_map.get(k_id) or char_map.get(k_name) or item
                if found not in resolved:
                    resolved.append(found)
            else:
                s_item = str(item).strip()
                found = None

                # 1. Check for <Subject X> tag inside item string
                m_sub = re.search(r'<Subject\s+(\d+)>', s_item, re.IGNORECASE)
                if m_sub and m_sub.group(1) in char_map:
                    found = char_map[m_sub.group(1)]

                # 2. Check exact string or clean string
                if not found:
                    found = char_map.get(s_item.lower())
                if not found:
                    s_clean = re.sub(r'[^a-zA-Z0-9]', '', s_item.lower())
                    found = char_map.get(s_clean)

                # 3. Check if any known character name is in s_item
                if not found:
                    for name_key, c_obj in char_map.items():
                        if len(name_key) >= 3 and name_key in s_item.lower():
                            found = c_obj
                            break

                # 4. Fallback: create minimal dict if unknown
                if not found:
                    found = {"name": s_item, "id": len(resolved) + 1}

                if found not in resolved:
                    resolved.append(found)

    # Fallback: check mentions in idea / prompt / summary
    if not resolved and characters_list:
        text_corpus = (
            str(scene.get("idee") or "") + " " + 
            str(scene.get("idea") or "") + " " + 
            str(scene.get("prompt") or "") + " " +
            str(scene.get("summary") or "")
        ).lower()

        for idx, c in enumerate(characters_list):
            c_name = str(c.get("name", "")).strip().lower()
            c_id = str(c.get("id", idx + 1))
            parts = re.split(r'[_ -]+', c_name)
            short_name = parts[-1].strip().lower() if len(parts) > 1 else ""

            matched = False
            if c_name and c_name in text_corpus:
                matched = True
            elif short_name and len(short_name) >= 3 and re.search(rf'\b{re.escape(short_name)}\b', text_corpus):
                matched = True
            elif f"<subject {c_id}>" in text_corpus or f"<picture {c_id}>" in text_corpus:
                matched = True

            if matched and c not in resolved:
                resolved.append(c)

    # Absolute fallback if still empty: first character of project cast
    if not resolved and characters_list:
        resolved = [characters_list[0]]

    # Hard cap at max_subjects
    if len(resolved) > max_subjects:
        print(f"   ⚠️ Warning: Scene active cast exceeds MiniMax limit ({len(resolved)} > {max_subjects}). Capping to first {max_subjects}.")
        resolved = resolved[:max_subjects]

    return resolved


def resolve_scene_location(scene, locations_list=None):
    """
    Resolves the location object or dict for a given scene.
    Supports:
      - Explicit location dict or ID
      - String name matching a location in locations_list
      - String fallback
    """
    if not scene:
        return None

    raw_loc = scene.get("location") or scene.get("drehort") or scene.get("ort") or scene.get("set")
    loc_id = scene.get("location_id")

    if not locations_list:
        locations_list = []

    loc_map = {}
    for idx, loc in enumerate(locations_list):
        if not isinstance(loc, dict):
            loc = {"name": str(loc), "id": idx + 1}
        lid = str(loc.get("id") or (idx + 1)).strip()
        loc_map[lid] = loc
        lname = str(loc.get("name") or "").strip().lower()
        if lname:
            loc_map[lname] = loc
            clean = re.sub(r'[^a-zA-Z0-9]', '', lname)
            if clean:
                loc_map[clean] = loc

    if loc_id and str(loc_id).strip() in loc_map:
        return loc_map[str(loc_id).strip()]

    if raw_loc:
        if isinstance(raw_loc, dict):
            return raw_loc
        s_loc = str(raw_loc).strip()
        if s_loc.lower() in loc_map:
            return loc_map[s_loc.lower()]
        s_clean = re.sub(r'[^a-zA-Z0-9]', '', s_loc.lower())
        if s_clean and s_clean in loc_map:
            return loc_map[s_clean]
        return {"name": s_loc}

    return None


def build_subject_definitions(scene_characters, location=None, max_subjects=MAX_MINIMAX_SUBJECTS):
    """
    Generates the standard Minimax subject definitions header:
    <Subject 1> is the character in <Picture 1> (Name1).
    <Subject 2> is the character in <Picture 2> (Name2).
    Optional location environment plate:
    <Subject 3> is the location in <Picture 3> (LocationName).
    """
    lines = []
    chars_to_use = scene_characters[:max_subjects] if scene_characters else []
    for i, char in enumerate(chars_to_use):
        c_name = char.get("name") if isinstance(char, dict) else str(char)
        lines.append(f"<Subject {i+1}> is the character in <Picture {i+1}> ({c_name}).")

    if location and len(chars_to_use) < max_subjects:
        loc_idx = len(chars_to_use) + 1
        loc_name = location.get("name") if isinstance(location, dict) else str(location)
        if loc_name and loc_name.strip():
            lines.append(f"<Subject {loc_idx}> is the location in <Picture {loc_idx}> ({loc_name.strip()}).")

    return "\n".join(lines)


def remap_scene_subjects(text, scene_characters, all_characters=None, max_subjects=MAX_MINIMAX_SUBJECTS):
    """
    Dynamically maps character references in text (idea, prompt, detailed_description)
    to the 1-based local scene slot (1..max_subjects).
    
    If the text contains '<Subject 7> (Laura)' and Laura is the 1st character in scene_characters,
    this translates '<Subject 7>' -> '<Subject 1>'.
    
    Uses a safe two-pass replacement to avoid cross-over collisions.
    """
    if not text or not scene_characters:
        return text

    chars_to_use = scene_characters[:max_subjects]

    # Map each scene character to local index (1..N)
    char_to_local_idx = {}
    for local_idx, c in enumerate(chars_to_use):
        target_idx = local_idx + 1
        c_name = (c.get("name") if isinstance(c, dict) else str(c)).strip()
        c_id = str(c.get("id", "")) if isinstance(c, dict) else ""
        if c_name:
            char_to_local_idx[c_name.lower()] = target_idx
            parts = re.split(r'[_ -]+', c_name)
            if len(parts) > 1:
                short = parts[-1].strip().lower()
                char_to_local_idx[short] = target_idx
        if c_id:
            char_to_local_idx[c_id] = target_idx

    # Map global IDs from all_characters to local indices
    global_id_to_local = {}
    char_list = []
    if isinstance(all_characters, dict):
        char_list = all_characters.get("characters", [])
    elif isinstance(all_characters, list):
        char_list = all_characters

    for c in char_list:
        if isinstance(c, dict):
            gid = str(c.get("id", ""))
            gname = str(c.get("name", "")).strip().lower()
        else:
            gid = ""
            gname = str(c).strip().lower()

        parts = re.split(r'[_ -]+', gname)
        short = parts[-1].strip().lower() if len(parts) > 1 else ""

        if gname in char_to_local_idx:
            if gid:
                global_id_to_local[gid] = char_to_local_idx[gname]
        elif short and short in char_to_local_idx:
            if gid:
                global_id_to_local[gid] = char_to_local_idx[short]
        elif gid and gid in char_to_local_idx:
            global_id_to_local[gid] = char_to_local_idx[gid]

    # Also map any character directly if c_id was in char_to_local_idx
    for k, v in char_to_local_idx.items():
        if k.isdigit() and k not in global_id_to_local:
            global_id_to_local[k] = v

    # Pass 1: Replace <Subject X> with unique placeholders
    def replace_subj_placeholder(m):
        old_id = m.group(1)
        if old_id in global_id_to_local:
            return f"__SUBJ_REMAP_{global_id_to_local[old_id]}__"
        return m.group(0)

    # Pass 1 for <Picture X> as well
    def replace_pic_placeholder(m):
        old_id = m.group(1)
        if old_id in global_id_to_local:
            return f"__PIC_REMAP_{global_id_to_local[old_id]}__"
        return m.group(0)

    result = re.sub(r'<Subject\s+(\d+)>', replace_subj_placeholder, text, flags=re.IGNORECASE)
    result = re.sub(r'<Picture\s+(\d+)>', replace_pic_placeholder, result, flags=re.IGNORECASE)

    # Pass 2: Replace placeholders with final clean tags
    result = re.sub(r'__SUBJ_REMAP_(\d+)__', r'<Subject \1>', result)
    result = re.sub(r'__PIC_REMAP_(\d+)__', r'<Picture \1>', result)

    return result


def build_minimax_api_prompt(prompt_text, characters=None, scene_data=None, all_characters=None, location=None, max_subjects=MAX_MINIMAX_SUBJECTS):
    """
    Ensures the final prompt submitted to ComfyUI node 138 has the full Minimax template envelope:
    subject_definitions, summary, detailed_description, overall_soundscape, and non_diegetic_music: None.
    
    Dynamically maps all subjects in detailed_description to 1..N matching the exact order
    of the scene's character portraits and optional filming location plate.
    """
    if not prompt_text:
        return ""

    chars_to_use = (characters or (scene_data.get("characters") if scene_data else None) or [])[:max_subjects]
    loc_to_use = location or (scene_data.get("location") if scene_data else None)

    # Clean existing envelope structures if present
    clean_text = prompt_text.strip()
    
    # Extract / strip existing subject_definitions
    clean_text = re.sub(r'(?i)subject_definitions:\s*[\s\S]*?(?=(?:summary:|detailed_description:|\[shot|\Z))', '', clean_text).strip()

    # Extract summary if present, else fallback
    summary = ""
    sum_match = re.search(r'(?i)summary:\s*([^\n]+(?:\n[^\n]+)?)', clean_text)
    if sum_match:
        summary = sum_match.group(1).strip()
        clean_text = clean_text[:sum_match.start()] + clean_text[sum_match.end():]
    elif scene_data and scene_data.get("summary"):
        summary = str(scene_data["summary"]).strip()
    if not summary:
        clean_first = re.sub(r'^\[Shot \d+\]:?\s*', '', clean_text.strip())
        sentences = [s.strip() for s in re.split(r'[.!?\n]', clean_first) if s.strip()]
        summary = sentences[0] if sentences else clean_first[:100]

    # Extract soundscape if present, else fallback
    soundscape = ""
    snd_match = re.search(r'(?i)overall_soundscape:\s*([\s\S]*?)(?=(?:non_diegetic_music:|\Z))', clean_text)
    if snd_match:
        soundscape = snd_match.group(1).strip()
        clean_text = clean_text[:snd_match.start()] + clean_text[snd_match.end():]
    elif scene_data and (scene_data.get("soundscape") or scene_data.get("overall_soundscape")):
        soundscape = str(scene_data.get("soundscape") or scene_data.get("overall_soundscape")).strip()
    if not soundscape:
        soundscape = "Realistic ambient environment sounds, foley, and natural breathing. Strictly no music."

    # Strip non_diegetic_music if present in raw text
    clean_text = re.sub(r'(?i)non_diegetic_music:\s*[^\n]*', '', clean_text).strip()

    # Strip detailed_description: tag prefix
    clean_text = re.sub(r'(?i)^detailed_description:\s*', '', clean_text).strip()

    # What remains is the actual shot description
    detailed = clean_text.strip()
    if not detailed.lower().startswith("[shot"):
        detailed = f"[Shot 1]: {detailed}"

    # Remap subjects in detailed description and summary to dynamic local indices
    if chars_to_use:
        detailed = remap_scene_subjects(detailed, chars_to_use, all_characters=all_characters, max_subjects=max_subjects)
        summary = remap_scene_subjects(summary, chars_to_use, all_characters=all_characters, max_subjects=max_subjects)

    # Build fresh, perfectly aligned subject definitions (including location if present)
    subj_defs = build_subject_definitions(chars_to_use, location=loc_to_use, max_subjects=max_subjects)

    parts = []
    if subj_defs.strip():
        parts.append(f"subject_definitions:\n{subj_defs.strip()}")
    parts.append(f"summary:\n{summary}")
    parts.append(f"detailed_description:\n{detailed}")
    parts.append(f"overall_soundscape:\n{soundscape}")
    parts.append("non_diegetic_music:\nNone")

    return "\n\n".join(parts)


def detect_scene_character_angle(scene_text, char_name=None):
    """
    Analyzes scene prompt, idea, or directorial camera notes to determine the optimal
    character perspective angle ('profile', 'three_quarter', or 'frontal').
    """
    if not scene_text or not isinstance(scene_text, str):
        return "frontal"

    text = scene_text.lower()
    
    # Check if specific character context exists (e.g. "profile of Elena" or "Elena turned sideways")
    if char_name:
        c_clean = char_name.lower().strip()
        c_idx = text.find(c_clean)
        if c_idx != -1:
            snippet = text[max(0, c_idx - 60):min(len(text), c_idx + len(c_clean) + 60)]
            if any(k in snippet for k in ["profile", "side view", "seitenprofil", "seitenansicht", "90 degree", "90°", "looking sideways", "turned 90", "looking left", "looking right", "from the side"]):
                return "profile"
            if any(k in snippet for k in ["three-quarter", "three quarter", "3/4", "45 degree", "45°", "schräg", "halbprofil", "over the shoulder", "over-the-shoulder", "turned slightly", "looking away", "glances away", "walking towards", "diagonal", "angled"]):
                return "three_quarter"
            if any(k in snippet for k in ["frontal", "front view", "face to face", "facing camera", "head-on", "straight-on", "close-up", "nahaufnahme"]):
                return "frontal"

    # Global scene prompt check
    if any(k in text for k in ["profile", "side view", "seitenprofil", "seitenansicht", "from the side", "90 degree", "90°", "looking left", "looking right", "turned sideways", "turned 90", "side-on"]):
        return "profile"
    if any(k in text for k in ["three-quarter", "three quarter", "3/4", "45 degree", "45°", "schräg", "halbprofil", "over the shoulder", "over-the-shoulder", "turned slightly", "looking away", "glances away", "walking towards", "diagonal", "angled"]):
        return "three_quarter"
    
    return "frontal"


def resolve_character_reference_image(char, scene=None, characters_dir=None):
    """
    Resolves the exact file path and angle to use as reference image for a character in a scene.
    Supports:
      1. Turnaround Sheet (if use_turnaround_sheet is true or scene requests turnaround)
      2. Scene-specific explicit angle ('frontal', 'three_quarter', 'profile', 'turnaround')
      3. Auto-detected angle based on scene prompt / camera perspective
      4. Graceful fallback to master portrait (<safe_name>.png) if specific angle file does not exist.
    """
    if not isinstance(char, dict):
        char = {"name": str(char)}

    char_name = char.get("name") or "character"
    safe_char_name = re.sub(r'[\\/*?:"<>| ]', '_', char_name)

    if not characters_dir:
        characters_dir = ""

    # Check for turnaround sheet preference
    use_turnaround = bool(char.get("use_turnaround_sheet") or char.get("turnaround_sheet_active"))
    
    # Check scene overrides
    scene_angles = {}
    if scene and isinstance(scene, dict):
        scene_angles = scene.get("character_angles") or scene.get("char_angles") or {}
    
    char_id_str = str(char.get("id") or "")
    explicit_angle = scene_angles.get(char_name) or scene_angles.get(char_name.lower()) or scene_angles.get(char_id_str)
    
    if explicit_angle == "turnaround" or (explicit_angle in (None, "", "auto") and use_turnaround):
        turnaround_file = os.path.join(characters_dir, f"{safe_char_name}_turnaround.png")
        if os.path.exists(turnaround_file):
            return {
                "file_path": turnaround_file,
                "angle": "turnaround",
                "is_turnaround": True,
                "safe_name": safe_char_name,
                "filename": f"{safe_char_name}_turnaround.png"
            }

    # Determine desired angle
    desired_angle = explicit_angle if (explicit_angle and explicit_angle != "auto") else None
    if not desired_angle and scene:
        scene_prompt = scene.get("prompt") or scene.get("idea") or ""
        desired_angle = detect_scene_character_angle(scene_prompt, char_name)
    if not desired_angle:
        desired_angle = "frontal"

    # Check candidate angle files
    angle_candidates = []
    if desired_angle == "profile":
        angle_candidates = [
            f"{safe_char_name}_profile.png",
            f"{safe_char_name}_side.png"
        ]
    elif desired_angle == "three_quarter":
        angle_candidates = [
            f"{safe_char_name}_three_quarter.png",
            f"{safe_char_name}_3_4.png",
            f"{safe_char_name}_angled.png"
        ]
    elif desired_angle == "frontal":
        angle_candidates = [
            f"{safe_char_name}_frontal.png",
            f"{safe_char_name}.png"
        ]

    for cand in angle_candidates:
        cand_path = os.path.join(characters_dir, cand)
        if os.path.exists(cand_path):
            return {
                "file_path": cand_path,
                "angle": desired_angle,
                "is_turnaround": False,
                "safe_name": safe_char_name,
                "filename": cand
            }

    # Default fallback to master portrait
    master_file = os.path.join(characters_dir, f"{safe_char_name}.png")
    return {
        "file_path": master_file,
        "angle": "frontal",
        "is_turnaround": False,
        "safe_name": safe_char_name,
        "filename": f"{safe_char_name}.png"
    }
