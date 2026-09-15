# Presets & LoRA Catalog Reference

MovieGenerator uses a modular, machine-independent preset and LoRA architecture. Base diffusion models and compatible LoRA weights are defined in `Presets/t2i_presets.json`.

> [!NOTE]
> **Privacy & Local Setup**: `Presets/t2i_presets.json` is strictly machine-local and ignored by Git. A clean starter template is provided in [`Presets/t2i_presets.example.json`](file:///e:/MovieGenerator/Presets/t2i_presets.example.json). Your personal local models and LoRAs are automatically cataloged during the initial setup wizard or via the catalog scanner.

---

## 1. Automatic Model & LoRA Catalog Builder

MovieGenerator automatically scans your local ComfyUI environment and indexes all available diffusion models and LoRAs:

### How the Catalog is Built:
1. **Interactive First-Run Wizard**: During the initial setup (`master_regisseur.py` on first start), the wizard detects your ComfyUI `models/` directory and prompts you to build your local catalog, with an optional toggle to filter out NSFW/adult content.
2. **Interactive Screenplay Menu**: Select option `[S]` at any time to re-scan models:
   ```text
   [S] ComfyUI-Modelle & LoRAs scannen / Presets aktualisieren
   ```
3. **Command Line Flag**:
   ```bash
   python master_regisseur.py --scan-models
   ```
4. **Automatic Startup Fallback**: If `Presets/t2i_presets.json` does not exist, MovieGenerator automatically initializes from `t2i_presets.example.json` and scans your local models.

### What the Scanner Does:
* **Deep Directory Scan**: Recursively searches `models/loras/`, `models/diffusion_models/`, and `models/checkpoints/` for `.safetensors` and `.gguf` files.
* **Metadata Extraction**:
  * **Companion Files**: Reads `.metadata.json`, `.civitai.info`, and `.json` downloaded by Civitai Helper / Civitai Manager for titles, descriptions, base models, and trained trigger words.
  * **Safetensors Headers**: Reads header metadata (`__metadata__`) without loading tensor weights to extract trigger phrases and architecture details.
* **NSFW Filter Option**: When enabled, filters out adult content based on Civitai metadata (`nsfw: true`, `nsfwLevel > 1`) and explicit keyword tags.
* **Smart Merge**: Existing manual tweaks, custom strengths (`strength_model`), and descriptions are **strictly preserved**, while newly downloaded LoRAs are seamlessly added.

---

## 2. Base Model Presets (`presets`)

Specify the model preset in character definitions using `"modell": "<preset_name>"` (or `"preset": "<preset_name>"`).

| Preset Key | Architecture | Recommended Use Case | Default Steps | CFG | Default Sampler & Scheduler |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `anima_cyberrealistic` | SDXL / Anima | Detailed, photorealistic humans, realistic skin, cinematic lighting. | 28 | 3.5 | `er_sde` / `beta57` |
| `krea2_turbo_int8` | Krea 2 Turbo (INT8) | Ultra-fast modern photorealism. Optimized for photographic casting. | 8 | 1.0 | `euler` / `simple` |
| `anima_catpony` *(Default)* | SDXL / Anima Pony | Expressive stylized, aesthetic anime, and semi-realistic characters. | 30 | 4.0 | `er_sde` / `beta57` |
| `anima_turbo` | SDXL / Anima Turbo | High-speed casting with fast turnaround (8 steps). | 8 | 1.8 | `er_sde` / `beta57` |
| `anima_finalcut_int8` | SDXL / Anima INT8 | VRAM-friendly INT8 model for low-CFG setups (12 steps). | 12 | 2.0 | `er_sde` / `beta57` |

---

## 3. Using LoRAs in Character Definitions

LoRAs can be attached to characters in the screenplay JSON in two ways:

### A. Simple Key (Uses Preset Default Strength)
```json
"loras": [
  "realskin",
  "anima_detailer"
]
```

### B. Object with Custom Strength Override
```json
"loras": [
  {"name": "realskin", "strength": 0.85},
  {"name": "anima_detailer", "strength": 0.6}
]
```

### How MovieGenerator Handles LoRAs:
1. `master_regisseur.py` dynamically chains `LoraLoader` nodes into the ComfyUI workflow.
2. If the LoRA defines `trigger_words`, the script automatically appends them to the character's prompt unless already present.
3. If the model preset is incompatible with the chosen LoRA, a warning is logged to the console while generation proceeds safely.

---

## 4. Common LoRA Categories & Examples

The scanner automatically categorizes your local LoRAs into compatible models:

### A. Photorealism & Detail Boosters
* `realskin`: Photorealistic skin pores, subtle texture, and natural sharpness. Trigger words: `realskin style, realistic skin texture, highly detailed skin`.
* `anima_detailer`: Precision micro-details in hair, eyes, and clothing. Trigger words: `detailed masterpiece, intricate details`.
* `il_detailer`: Sharp focus and crisp edge enhancement. Trigger words: `jeddtl02, high detail, sharp focus`.

### B. Artistic & Cinematic Styles
* `krea_cinematic`: Anamorphic cinema lighting, shallow depth of field. Trigger words: `cinematic shot, anamorphic, dramatic lighting`.
* `krea_vintage`: Retro film grain, analog warmth. Trigger words: `vintage style, analog film grain, retro`.
* `dark_lines`: Emphasized anime outlines and graphic novel shading. Trigger words: `dark lines style, bold outlines`.
* `anima_background_art`: Painterly scenic backgrounds, skies, and nature. Trigger words: `anime background art style, scenery, outdoors, sky`.

---

## 5. MiniMax H3 Video LoRAs (Scene-Level)

MiniMax H3 video diffusion models support scene-specific motion, combat, camera dynamics, and visual aesthetics via ComfyUI node `674` (`Power Lora Loader (rgthree)`).

### How Scene LoRAs Work:
1. **Automatic LLM Selection (LM Studio)**: During Phase 1 prompt generation, the complete catalog of compatible scene LoRAs is provided to LM Studio. The model analyzes the shot action and tags up to 2 relevant LoRAs (e.g. `LORAS: mmh3_combat_v2`).
2. **Manual Director Override**: You can also specify LoRAs directly in any scene within your screenplay JSON:
   ```json
   {
     "id": 3,
     "idee": "Maya delivers a spinning martial arts kick to disarm the enemy.",
     "loras": ["mmh3_combat_v2", "mmh3_poly_perfect"]
   }
   ```
3. **Dynamic Stacking & Isolation**: Node `674` preserves the base turbo acceleration LoRA (`lora_1`) and dynamically stacks scene LoRAs (`lora_2`, `lora_3`, etc.) with their respective weights and trigger words, automatically resetting after each scene.
4. **Metadata Preservation**: Active scene LoRAs are embedded into the MP4 video headers, preview PNGs, and assembled final film metadata.

### Representative MiniMax H3 Motion & Style LoRAs:

| Key | Description | Trigger Words |
| :--- | :--- | :--- |
| `mmh3_combat_v2` | Dynamic combat impact, martial arts strikes, action choreography | `prfight2, prfin1, martial arts fighting, dynamic combat impact` |
| `mmh3_poly_perfect` | Polyhedron video enhancer: clean eyes, skin details, hands | `perfe8ct, perfect eyes, perfect skin, perfect hands` |
| `mmh3_nafasp_natural` | Natural facial expressions, dialogue delivery, mouth movements | `nafasp, natural facial expressions, lifelike speech movement` |
| `mmh3_cinematic_movie` | 35mm film grain, cinematic depth and movie texture | `cinematic texture, film grain` |
| `mmh3_digicam_realism` | Y2K camcorder aesthetic, flash lighting, handheld texture | `d1g1cam, digicam style, raw camcorder footage` |
| `mmh3_digital_art` | Vibrant digital concept art painting aesthetic | `digital art style, cinematic concept art, vibrant painted aesthetic` |
| `mmh3_flatanime` | 2D flat anime illustration video aesthetic | `flat anime style` |
| `mmh3_bounce` | Dynamic physics and motion momentum | `bounce motion` |
| `mmh3_fl2v_lightx2v_turbo` | Internal 8-step turbo acceleration base LoRA | — |
