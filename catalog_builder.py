"""
Catalog Builder for MovieGenerator
Scans local ComfyUI models directory (loras, diffusion_models, checkpoints)
and automatically builds or updates Presets/t2i_presets.json.
Enriches entries with metadata from companion files (.metadata.json, .civitai.info)
and safetensors header metadata (__metadata__).
"""

import os
import re
import json
import struct
import html


def read_safetensors_header(filepath):
    """
    Reads the JSON header from a .safetensors file without loading tensor weights.
    Returns the '__metadata__' dict if present, else empty dict.
    """
    try:
        with open(filepath, "rb") as f:
            header_len_bytes = f.read(8)
            if len(header_len_bytes) != 8:
                return {}
            header_len = struct.unpack("<Q", header_len_bytes)[0]
            if header_len <= 0 or header_len > 100_000_000:
                return {}
            header_bytes = f.read(header_len)
            header_json = json.loads(header_bytes.decode("utf-8", errors="ignore"))
            return header_json.get("__metadata__", {})
    except Exception:
        return {}


def find_companion_metadata(filepath):
    """
    Finds and parses companion metadata files (.metadata.json, .civitai.info, or .json)
    matching the given model file.
    """
    base, _ = os.path.splitext(filepath)
    candidates = [
        f"{base}.metadata.json",
        f"{base}.civitai.info",
        f"{base}.json",
    ]
    for cand in candidates:
        if os.path.exists(cand):
            try:
                with open(cand, "r", encoding="utf-8", errors="ignore") as f:
                    return json.load(f)
            except Exception:
                continue
    return None


def clean_description(raw_text, max_len=140):
    """Cleans HTML tags and excessive whitespace from model descriptions."""
    if not raw_text:
        return ""
    text = html.unescape(str(raw_text))
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse multiple whitespace
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "..."
    return text


def extract_trigger_words(companion_meta, header_meta):
    """Extracts trigger words from companion civitai metadata or safetensors header."""
    triggers = []

    # 1. Companion Civitai metadata: trainedWords list
    if companion_meta:
        tw = companion_meta.get("trainedWords") or companion_meta.get("trained_words")
        if isinstance(tw, list):
            for w in tw:
                if isinstance(w, str) and w.strip():
                    triggers.extend([x.strip() for x in w.split(",") if x.strip()])
        elif isinstance(tw, str) and tw.strip():
            triggers.extend([x.strip() for x in tw.split(",") if x.strip()])

    # 2. Header metadata: modelspec.trigger_phrase
    if not triggers and header_meta:
        tp = header_meta.get("modelspec.trigger_phrase")
        if tp and isinstance(tp, str):
            triggers.extend([x.strip() for x in tp.split(",") if x.strip()])

    # 3. Header metadata: ss_tag_frequency top tags
    if not triggers and header_meta:
        tag_freq_str = header_meta.get("ss_tag_frequency")
        if tag_freq_str:
            try:
                tag_dict = json.loads(tag_freq_str) if isinstance(tag_freq_str, str) else tag_freq_str
                all_tags = {}
                for subset in tag_dict.values():
                    if isinstance(subset, dict):
                        for t, cnt in subset.items():
                            all_tags[t] = all_tags.get(t, 0) + cnt
                # Sort tags by frequency and pick top 4 meaningful tags
                sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
                for t, _ in sorted_tags[:4]:
                    clean_t = str(t).strip()
                    if clean_t and clean_t not in ["1girl", "1boy", "solo"]:
                        triggers.append(clean_t)
            except Exception:
                pass

    # Deduplicate while preserving order
    seen = set()
    result = []
    for t in triggers:
        low = t.lower()
        if low not in seen:
            seen.add(low)
            result.append(t)

    return ", ".join(result[:8])


def determine_lora_compat(rel_path, filename, companion_meta, header_meta):
    """
    Determines compatible base models and default strength for a LoRA.
    Returns (kompatible_modelle_list, default_strength_model, default_strength_clip).
    """
    rel_low = rel_path.lower()
    fn_low = filename.lower()
    
    base_model = ""
    if companion_meta:
        base_model = str(companion_meta.get("baseModel") or companion_meta.get("base_model") or "").lower()
    if not base_model and header_meta:
        base_model = str(header_meta.get("ss_base_model_version") or header_meta.get("modelspec.architecture") or "").lower()

    # MiniMax H3 Video
    if "minimax" in rel_low or "minimax" in base_model or "mmh3" in fn_low or "h3" in rel_low:
        return ["minimax_h3", "minimax_h3_video"], 1.0, 1.0

    # Anima / Anime Pony / CyberRealistic
    if "anima" in rel_low or "anima" in base_model:
        return ["anima_cyberrealistic", "anima_catpony", "anima_turbo", "anima_finalcut_int8"], 0.8, 0.8

    # Krea 2 Turbo
    if "krea" in rel_low or "krea" in base_model:
        return ["krea2_turbo_int8"], 0.8, 0.8

    # Illustrious / NoobAI
    if "illustrious" in rel_low or "illustrious" in base_model or "noobai" in base_model:
        return ["illustrious"], 0.8, 0.8

    # Pony Diffusion / SDXL
    if "pony" in rel_low or "pony" in base_model:
        return ["anima_catpony", "pony"], 0.8, 0.8

    # Wan Video 2.1 / 2.2
    if "wan" in rel_low or "wan" in base_model:
        return ["wan2.1", "wan2.2"], 1.0, 1.0

    # Flux
    if "flux" in rel_low or "flux" in base_model:
        return ["flux"], 0.8, 0.8

    # General SDXL default
    if "sdxl" in rel_low or "sdxl" in base_model:
        return ["anima_cyberrealistic", "sdxl"], 0.8, 0.8

    # Default fallback
    return ["anima_catpony", "anima_cyberrealistic"], 0.8, 0.8


def generate_clean_key(filename, rel_path):
    """Derives a clean snake_case dictionary key from a file path."""
    clean = os.path.splitext(filename)[0]
    # Remove common technical tags
    clean = re.sub(r"[-_](?:v\d+(?:\.\d+)*|epoch\d+|step\d+|bf16|fp16|fp8|int8|convrot|resized_avg_rank_\d+)", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"[^a-zA-Z0-9_]+", "_", clean)
    clean = re.sub(r"_+", "_", clean).strip("_").lower()

    # Prefix hint based on directory structure
    rel_parts = [p.lower() for p in os.path.split(rel_path)[0].split(os.sep) if p]
    if any("minimax" in p for p in rel_parts) and not clean.startswith("mmh3"):
        clean = f"mmh3_{clean}"
    elif any("krea" in p for p in rel_parts) and not clean.startswith("krea"):
        clean = f"krea_{clean}"
    elif any("illustrious" in p for p in rel_parts) and not clean.startswith("il_"):
        clean = f"il_{clean}"

    return clean or "lora_custom"


def is_nsfw_lora(rel_path, filename, companion_meta, header_meta):
    """
    Detects if a LoRA contains adult/NSFW content based on file paths, civitai metadata, and trigger words.
    """
    combined_text = f"{rel_path} {filename}".lower()
    
    # 1. Companion civitai metadata checks
    if companion_meta:
        if companion_meta.get("nsfw") is True:
            return True
        nsfw_level = companion_meta.get("nsfwLevel")
        if isinstance(nsfw_level, (int, float)) and nsfw_level > 1:
            return True
        model_meta = companion_meta.get("model", {})
        if isinstance(model_meta, dict) and model_meta.get("nsfw") is True:
            return True
        tags = companion_meta.get("tags") or []
        for t in tags:
            tag_name = (t if isinstance(t, str) else t.get("name", "")).lower()
            if any(w in tag_name for w in ["nsfw", "nude", "nudity", "erotic", "hentai", "sex", "porn", "xxx"]):
                return True

    # 2. Common explicit keywords in relative path or filename
    explicit_keywords = [
        "nsfw", "xxx", "nude", "naked", "erotic", "hentai", "futa",
        "blowjob", "cumshot", "deepthroat", "fingering", "titjob", "penis",
        "vagina", "nipple_play", "cowgirl_position", "anal", "masturbat",
        "sensual_fingering", "malesuck", "worship_touch", "underwear"
    ]
    for kw in explicit_keywords:
        if kw in combined_text:
            return True

    return False


def scan_loras_directory(loras_dir, filter_nsfw=False):
    """
    Recursively scans loras_dir for .safetensors and .gguf files.
    Returns a dict mapping candidate_key -> lora_config.
    """
    results = {}
    if not loras_dir or not os.path.exists(loras_dir):
        return results

    for root, _, files in os.walk(loras_dir):
        for f in files:
            if not f.endswith((".safetensors", ".gguf")):
                continue

            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, loras_dir)
            
            # Extract metadata
            companion_meta = find_companion_metadata(full_path)
            header_meta = read_safetensors_header(full_path) if f.endswith(".safetensors") else {}
            
            if filter_nsfw and is_nsfw_lora(rel_path, f, companion_meta, header_meta):
                continue
            
            # Determine human-readable title / description
            title = ""
            if companion_meta:
                title = companion_meta.get("name") or companion_meta.get("model", {}).get("name") or ""
            if not title and header_meta:
                title = header_meta.get("modelspec.title") or header_meta.get("title") or ""
            if not title:
                title = os.path.splitext(f)[0].replace("_", " ").title()

            raw_desc = ""
            if companion_meta:
                raw_desc = companion_meta.get("description") or ""
            if not raw_desc and header_meta:
                raw_desc = header_meta.get("modelspec.description") or ""
            
            desc = clean_description(raw_desc, max_len=140) if raw_desc else f"{title} LoRA"
            triggers = extract_trigger_words(companion_meta, header_meta)
            compat, s_model, s_clip = determine_lora_compat(rel_path, f, companion_meta, header_meta)

            key = generate_clean_key(f, rel_path)

            results[rel_path] = {
                "suggested_key": key,
                "beschreibung": desc,
                "lora_name": rel_path,
                "kompatible_modelle": compat,
                "strength_model": s_model,
                "strength_clip": s_clip,
                "trigger_words": triggers,
            }

    return results


# Standard fallback profiles for recognized base model architectures
# Used when companion metadata does not specify custom sampling parameters.
BASE_MODEL_PROFILES = {
    "anima": {
        "clip_name": "qwen_3_06b_base.safetensors",
        "clip_type": "stable_diffusion",
        "vae_name": "qwen_image_vae.safetensors",
        "sampler_name": "er_sde",
        "scheduler": "beta57",
        "steps": 30,
        "cfg": 3.5,
        "aspect_ratio": "3:4 (Portrait Standard)",
        "megapixels": 1.2,
        "negative_prompt": "score_4, score_5, score_6, worst quality, low quality, blurry, deformed, bad anatomy",
    },
    "krea2": {
        "clip_name": "qwen3VL_4b.safetensors",
        "clip_type": "krea2",
        "vae_name": "qwen_image_vae.safetensors",
        "sampler_name": "euler",
        "scheduler": "simple",
        "steps": 8,
        "cfg": 1.0,
        "aspect_ratio": "3:4 (Portrait Standard)",
        "megapixels": 1.0,
        "negative_prompt": "worst quality, low quality, blurry, distorted, unnatural anatomy",
    },
    "zimage": {
        "clip_name": "qwen_3_06b_base.safetensors",
        "clip_type": "stable_diffusion",
        "vae_name": "qwen_image_vae.safetensors",
        "sampler_name": "euler",
        "scheduler": "simple",
        "steps": 8,
        "cfg": 1.5,
        "aspect_ratio": "3:4 (Portrait Standard)",
        "megapixels": 1.0,
        "negative_prompt": "worst quality, low quality, blurry",
    },
    "sdxl": {
        "clip_name": "clip_l.safetensors",
        "clip_type": "sdxl",
        "vae_name": "sdxl_vae.safetensors",
        "sampler_name": "dpmpp_2m",
        "scheduler": "karras",
        "steps": 28,
        "cfg": 4.5,
        "aspect_ratio": "3:4 (Portrait Standard)",
        "megapixels": 1.0,
        "negative_prompt": "worst quality, low quality, blurry, bad anatomy",
    },
    "default": {
        "clip_name": "clip_l.safetensors",
        "clip_type": "sdxl",
        "vae_name": "sdxl_vae.safetensors",
        "sampler_name": "euler",
        "scheduler": "normal",
        "steps": 25,
        "cfg": 4.0,
        "aspect_ratio": "3:4 (Portrait Standard)",
        "megapixels": 1.0,
        "negative_prompt": "worst quality, low quality, blurry",
    },
}


def detect_base_family(rel_path, meta=None, header_meta=None):
    """
    Detects the base model family (anima, krea2, zimage, sdxl, default)
    from metadata tags, baseModel string, or directory path.
    """
    rel_low = rel_path.lower()
    base_model = ""
    tags_str = ""
    if meta and isinstance(meta, dict):
        base_model = str(meta.get("baseModel") or meta.get("base_model") or "").lower()
        tags_str = " ".join(str(t).lower() for t in meta.get("tags", []))
    if not base_model and header_meta and isinstance(header_meta, dict):
        base_model = str(header_meta.get("ss_base_model_version") or header_meta.get("modelspec.architecture") or "").lower()

    haystack = f"{rel_low} {base_model} {tags_str}"
    if "anima" in haystack or "illustrious" in haystack or "pony" in haystack:
        return "anima"
    if "krea" in haystack:
        return "krea2"
    if "zimage" in haystack or "z-image" in haystack or "moody" in haystack:
        return "zimage"
    if "sdxl" in haystack:
        return "sdxl"
    return "default"


def scan_diffusion_models(models_dir):
    """
    Dynamically scans diffusion_models directory for available base models / UNets.
    Extracts recommended settings from companion metadata (.metadata.json, .civitai.info)
    or falls back to architectural standard profiles (BASE_MODEL_PROFILES).
    Contains ZERO hardcoded model lists.
    """
    discovered_presets = {}
    if not models_dir or not os.path.exists(models_dir):
        return discovered_presets

    VIDEO_AUDIO_KEYWORDS = [
        "minimax", "wan", "cogvideo", "i2v", "t2v", "music", "infinitetalk",
        "qwen34bllm", "qwen3_4_b", "part", "tmp"
    ]

    diff_dir = os.path.join(models_dir, "diffusion_models")
    if not os.path.exists(diff_dir):
        return discovered_presets

    for root, _, files in os.walk(diff_dir):
        for f in sorted(files):
            if not f.endswith((".safetensors", ".gguf")):
                continue
            if f.endswith(".part") or f.endswith(".tmp"):
                continue

            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, diff_dir)
            rel_low = rel_path.lower()
            fn_low = f.lower()

            if any(k in rel_low for k in VIDEO_AUDIO_KEYWORDS):
                continue

            # Parse companion metadata (Civitai metadata etc.)
            meta = find_companion_metadata(full_path) or {}
            civitai_data = meta.get("civitai", {}) if isinstance(meta, dict) else {}

            sample_meta = {}
            img_list = civitai_data.get("images", []) or (meta.get("images", []) if isinstance(meta, dict) else [])
            if isinstance(img_list, list):
                for im in img_list:
                    if isinstance(im, dict) and im.get("meta"):
                        sample_meta = im["meta"]
                        break

            # Detect Base Model Architecture Family & apply standard baseline profile
            family = detect_base_family(rel_path, meta=meta)
            profile = dict(BASE_MODEL_PROFILES.get(family, BASE_MODEL_PROFILES["default"]))

            # Model title & description from metadata
            raw_title = meta.get("model_name") or meta.get("name") or os.path.splitext(f)[0]
            raw_desc = meta.get("modelDescription") or meta.get("description") or ""
            clean_desc_text = clean_description(raw_desc, 120)
            if clean_desc_text:
                desc = f"{raw_title} - {clean_desc_text}"
            else:
                desc = f"{raw_title} - T2I Diffusion Model"

            # Sampler & Scheduler (override profile with metadata if available)
            sampler_name = profile["sampler_name"]
            scheduler = profile["scheduler"]
            sampler_str = str(sample_meta.get("sampler") or "").lower()
            if "dpm" in sampler_str:
                sampler_name = "dpmpp_2m"
            elif "euler" in sampler_str:
                sampler_name = "euler"
            elif "er_sde" in sampler_str:
                sampler_name = "er_sde"

            sched_str = str(sample_meta.get("Schedule type") or sample_meta.get("scheduler") or "").lower()
            if "karras" in sched_str or "karras" in sampler_str:
                scheduler = "karras"
            elif "simple" in sched_str:
                scheduler = "simple"
            elif "beta" in sched_str:
                scheduler = "beta57"
            elif "normal" in sched_str:
                scheduler = "normal"

            # Steps & CFG (override profile with metadata if available)
            steps = profile["steps"]
            cfg = profile["cfg"]
            if sample_meta.get("steps"):
                try:
                    steps = max(6, min(50, int(sample_meta["steps"])))
                except Exception:
                    pass
            elif "turbo" in fn_low or "int8" in fn_low:
                steps = min(steps, 10)
                cfg = min(cfg, 2.0)

            if sample_meta.get("cfgScale"):
                try:
                    cfg = max(1.0, min(15.0, float(sample_meta["cfgScale"])))
                except Exception:
                    pass

            neg_prompt = sample_meta.get("negativePrompt") or profile["negative_prompt"]

            # Derive clean preset key
            prefix = family if family != "default" else "model"
            clean_fn = re.sub(r"[-_](?:v\d+(?:\.\d+)*|epoch\d+|step\d+|bf16|fp16|fp8|int8|convrot|pruned)", "", os.path.splitext(f)[0], flags=re.IGNORECASE)
            clean_fn = re.sub(r"[^a-zA-Z0-9_]+", "_", clean_fn).strip("_").lower()
            if prefix and not clean_fn.startswith(prefix):
                p_key = f"{prefix}_{clean_fn}"
            else:
                p_key = clean_fn

            # Ensure unique key
            orig_p_key = p_key
            counter = 2
            while p_key in discovered_presets and discovered_presets[p_key].get("unet_name") != rel_path:
                p_key = f"{orig_p_key}_{counter}"
                counter += 1

            discovered_presets[p_key] = {
                "beschreibung": desc,
                "unet_name": rel_path,
                "clip_name": profile["clip_name"],
                "clip_type": profile["clip_type"],
                "vae_name": profile["vae_name"],
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "aspect_ratio": profile["aspect_ratio"],
                "megapixels": profile["megapixels"],
                "negative_prompt": neg_prompt,
            }

    return discovered_presets


def build_or_update_catalog(models_dir, presets_path=None, dry_run=False, filter_nsfw=False):
    """
    Scans models_dir and updates or creates presets_path.
    Preserves existing user configurations and custom strength tweaks.
    Returns stats dict.
    """
    if presets_path is None:
        presets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Presets", "t2i_presets.json")

    existing_catalog = {"default": "anima_catpony", "presets": {}, "lora_presets": {}}
    if os.path.exists(presets_path):
        try:
            with open(presets_path, "r", encoding="utf-8") as f:
                existing_catalog = json.load(f)
        except Exception:
            pass
    else:
        # Load clean baseline template if available
        example_path = os.path.join(os.path.dirname(presets_path), "t2i_presets.example.json")
        if os.path.exists(example_path):
            try:
                with open(example_path, "r", encoding="utf-8") as ef:
                    existing_catalog = json.load(ef)
            except Exception:
                pass

    existing_loras = existing_catalog.get("lora_presets", {})
    existing_presets = existing_catalog.get("presets", {})

    # Map existing relative lora file paths -> key to avoid renaming existing keys
    file_to_existing_key = {}
    for k, v in existing_loras.items():
        lname = v.get("lora_name")
        if lname:
            norm = os.path.normpath(lname).lower()
            file_to_existing_key[norm] = k

    # 1. Scan LoRAs
    loras_dir = os.path.join(models_dir, "loras")
    discovered_loras = scan_loras_directory(loras_dir, filter_nsfw=filter_nsfw)

    new_loras_count = 0
    updated_loras_count = 0

    for rel_path, lora_cfg in discovered_loras.items():
        norm_path = os.path.normpath(rel_path).lower()
        if norm_path in file_to_existing_key:
            # Already in catalog: preserve key and custom user tweaks
            matched_key = file_to_existing_key[norm_path]
            existing_entry = existing_loras[matched_key]
            # Backfill missing triggers or description if empty
            changed = False
            if not existing_entry.get("trigger_words") and lora_cfg.get("trigger_words"):
                existing_entry["trigger_words"] = lora_cfg["trigger_words"]
                changed = True
            if not existing_entry.get("beschreibung") and lora_cfg.get("beschreibung"):
                existing_entry["beschreibung"] = lora_cfg["beschreibung"]
                changed = True
            if changed:
                updated_loras_count += 1
        else:
            # Newly discovered LoRA: pick unique key
            cand_key = lora_cfg["suggested_key"]
            final_key = cand_key
            idx = 2
            while final_key in existing_loras:
                final_key = f"{cand_key}_{idx}"
                idx += 1

            existing_loras[final_key] = {
                "beschreibung": lora_cfg["beschreibung"],
                "lora_name": lora_cfg["lora_name"],
                "kompatible_modelle": lora_cfg["kompatible_modelle"],
                "strength_model": lora_cfg["strength_model"],
                "strength_clip": lora_cfg["strength_clip"],
                "trigger_words": lora_cfg["trigger_words"],
            }
            file_to_existing_key[norm_path] = final_key
            new_loras_count += 1

    # 2. Scan Diffusion Models
    discovered_presets = scan_diffusion_models(models_dir)
    new_presets_count = 0
    for p_key, p_cfg in discovered_presets.items():
        if p_key not in existing_presets:
            existing_presets[p_key] = p_cfg
            new_presets_count += 1
        else:
            # Update missing unet_name or checkpoint if local file found
            if not existing_presets[p_key].get("unet_name") and p_cfg.get("unet_name"):
                existing_presets[p_key]["unet_name"] = p_cfg["unet_name"]

    existing_catalog["presets"] = existing_presets
    existing_catalog["lora_presets"] = existing_loras

    if not dry_run:
        os.makedirs(os.path.dirname(presets_path), exist_ok=True)
        with open(presets_path, "w", encoding="utf-8") as f:
            json.dump(existing_catalog, f, indent=2, ensure_ascii=False)

    return {
        "presets_path": presets_path,
        "total_loras": len(existing_loras),
        "new_loras": new_loras_count,
        "updated_loras": updated_loras_count,
        "total_presets": len(existing_presets),
        "new_presets": new_presets_count,
    }


if __name__ == "__main__":
    import sys
    # Test execution
    target_models_dir = r"D:\ComfyUI_windows_portable\ComfyUI\models"
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        target_models_dir = sys.argv[1]

    print(f"Scanning models in: {target_models_dir} ...")
    stats = build_or_update_catalog(target_models_dir)
    print("\nScan completed successfully!")
    print(f"Catalog: {stats['presets_path']}")
    print(f"Total LoRAs in catalog: {stats['total_loras']} (New: {stats['new_loras']}, Updated: {stats['updated_loras']})")
    print(f"Total Base Model Presets: {stats['total_presets']} (New: {stats['new_presets']})")
