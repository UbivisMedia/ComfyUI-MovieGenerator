# Presets & LoRA Catalog Reference

MovieGenerator includes a centralized catalog in [Presets/t2i_presets.json](file:///e:/MovieGenerator/Presets/t2i_presets.json) configuring base diffusion models (presets) and 104+ curated LoRA weights.

---

## 1. Base Model Presets (`presets`)

Specify the model in character definitions using `"modell": "<preset_name>"` (or `"preset": "<preset_name>"`).

| Preset Key | Architecture | Recommended Use Case | Default Steps | CFG | Default Sampler & Scheduler |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `anima_cyberrealistic` | SDXL / Anima | Detailed, photorealistic humans, faces, realistic skin, cinematic lighting. | 28 | 3.5 | `er_sde` / `beta57` |
| `krea2_turbo_int8` | Krea 2 Turbo (INT8) | Extremely fast modern photorealism. Optimized for photographic portraits. | 8 | 1.0 | `euler` / `simple` |
| `anima_catpony` *(Default)* | SDXL / Anima Pony | Expressive stylized, aesthetic anime, and semi-realistic characters. | 30 | 4.0 | `er_sde` / `beta57` |
| `anima_turbo` | SDXL / Anima Turbo | High-speed casting with fast turnaround (8 steps). | 8 | 1.8 | `er_sde` / `beta57` |
| `anima_finalcut_int8` | SDXL / Anima INT8 | VRAM-friendly INT8 model for low-CFG setups (12 steps). | 12 | 2.0 | `er_sde` / `beta57` |

---

## 2. Using LoRAs in Character Definitions

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
  {"name": "krea_cinematic", "strength": 0.6}
]
```

When a LoRA is applied:
1. `master_regisseur.py` chains a dedicated `LoraLoader` node into the ComfyUI workflow.
2. If the LoRA defines `trigger_words`, the script automatically appends them to the character's prompt unless they are already present.
3. If the model preset is incompatible with the chosen LoRA, a gentle warning is printed to the console while execution safely proceeds.

---

## 3. LoRA Catalog by Family

### A. Anima Models (CyberRealistic, CatPony, Turbo, FinalCut)

| Key | Description | Trigger Words | Default Strength |
| :--- | :--- | :--- | :--- |
| `realskin` | Realskin v2 — Photorealistic skin pores, texture, and natural sharpness | `realskin style, realistic skin texture, highly detailed skin` | 0.8 |
| `anima_detailer` | Detailer by Volnovik — Increases micro-details in hair, eyes, and clothes | `detailed masterpiece, intricate details` | 0.7 |
| `portrait_myth` | Myth Portrait Style — Artistic, aesthetic portrait look | `myth portrait style` | 0.85 |
| `dark_lines` | Dark Lines — Bold contours and dramatic anime line art | `dark lines style, bold outlines` | 0.8 |
| `anima_smooth_lines` | Smooth Lines — Soft outlines and fluid illustration style | `smooth lines style, clean lineart` | 0.8 |
| `anima_background_art` | Background Art Style — Painterly anime backgrounds and scenery | `anime background art style, scenery, outdoors, sky` | 0.8 |
| `anima_magic` | Magic Effects v2 — Glowing particles, magic aura, luminous spells | `hkmagic, magic glow, glowing particles` | 0.8 |
| `anima_boss_battle` | Boss Battle v1 — Dramatic action poses and epic encounter lighting | `bosstyle, epic battle, dynamic pose` | 0.8 |
| `anima_masterpiece` | Masterpiece v5.1 — Global aesthetic booster | `masterpiece, best quality, ultra detailed` | 0.7 |
| `anima_semi_realistic` | Semi-Realistic Anima — Blends anime forms with photorealistic shading | `semi-realistic, realistic lighting` | 0.8 |
| `anima_eop_realism` | EOP Realism — Enhanced depth and physical presence | `photorealistic shading, depth` | 0.8 |
| `anima_sky_light_v4` | Sky02 Light v4 — Ethereal soft lighting and anime glow | `sky02 style, soft lighting` | 0.8 |
| `anima_sky_v5` | Sky02 v5 — High contrast, vivid character composition | `sky02v5, vibrant colors` | 0.8 |
| `anima_girl_underwear` | Underwear & Lingerie detailer | `jyojishitagi, 1girl, underwear, panties` | 0.8 |
| `anima_volleyball_uniform` | Sportswear & athletic jersey style | `volleyball uniform, shorts, shirt, athletic` | 0.8 |
| `anima_turbo_lora` | Turbo step reducer | — | 1.0 |

### B. Krea 2 Turbo Models (`krea2_turbo_int8`)

#### Dedicated Character Faces & Actors
*Note: Characters can be called either with the `krea_` prefix or directly by their name (e.g. `"krea_amanda"` or `"amanda"`).*

| Key / Alias | Gender / Ethnicity | Trigger Words |
| :--- | :--- | :--- |
| `krea_amanda` / `amanda` | Female, Caucasian | `amanda, woman` |
| `krea_amelie` / `amelie` | Female, European | `amelie, woman` |
| `krea_anika` / `anika` | Female, South Asian | `anika, woman` |
| `krea_ashley` / `ashley` | Female, Western | `ashley, woman` |
| `krea_brynn` / `brynn` | Female, Western | `brynn, woman` |
| `krea_chinese` / `chinese` | Female, Chinese Face | `chinese woman, realistic chinese face` |
| `krea_elara` / `elara` | Female, Mediterranean | `elara, woman` |
| `krea_elena` / `elena` | Female, Eastern European | `elena, woman` |
| `krea_japanese` / `japanese` | Female, Japanese Face | `japanese woman, realistic japanese face` |
| `krea_keiran` / `keiran` | Male Actor, Handsome Caucasian | `keiran, man, handsome man` |
| `krea_korean` / `korean` | Female, Korean Face | `korean woman, realistic korean face` |
| `krea_lily` / `lily` | Female, Youthful Western | `lily, woman` |
| `krea_nieve` / `nieve` | Female, Fair/Porcelain | `nieve, woman` |
| `krea_noa` / `noa` | Female, Modern | `noa, woman` |
| `krea_sienna` / `sienna` | Female, Warm tones | `sienna, woman` |
| `krea_stella` / `stella` | Female, Glamour | `stella, woman` |
| `krea_tessa` / `tessa` | Female, Western | `tessa, woman` |
| `krea_thai` / `thai` | Female, Thai Face | `thai woman, realistic thai face` |
| `krea_wren` / `wren` | Female, Natural | `wren, woman` |
| `krea_zariah` / `zariah` | Female, Afro-diaspora/Latina | `zariah, woman` |

#### Krea 2 Styles & Tools
| Key | Description | Trigger Words |
| :--- | :--- | :--- |
| `krea_cinematic` | Cinematic Shot — Anamorphic cinema lighting, depth of field | `cinematic shot, anamorphic, dramatic lighting` |
| `krea_darkbrush` | Darkbrush — Moody painterly brushstroke aesthetic | `darkbrush style` |
| `krea_vintage` | Vintage Film — Retro film grain, analog color grade | `vintage style, analog film grain, retro` |
| `krea_amateur` | Amateur Photo — Candid, unedited snapshot authenticity | `amateur photo, candid shot` |

### C. Illustrious / Anime / NoobAI
- `il_anime_screencap`: TV anime screenshot & retro coloring (`anime screencap, anime coloring, 2d, anime style`)
- `il_detailer`: Precision edge enhancement (`jeddtl02, high detail, ultra detailed, sharp focus`)
- `il_smooth_booster`: Gradient smoothing & cleanup
- `il_hong_ying`: Character LoRA (`hongyingwailxl, animal ears`)
- `il_neisill`: Manga style (`neiill`)
- `il_isometric_fantasy`: Isometric cartoon environment (`cartoon isometric fantasy`)

### D. SDXL 1.0 & SD 1.5
- `sdxl_amateur_photo`: Authentic smartphone mirror selfies (`amateur photo, mirror selfie`)
- `sdxl_black_and_white`: Charcoal & pencil sketches (`Black and white art, charcoal drawing, pencil drawing`)
- `sdxl_dmd2_4step`: 4-step turbo inference acceleration
- `sdxl_gremlins`: Gremlin/Gizmo character LoRA (`xgremlinx, xgizmox`)
- `sd15_cinematic`: Cinematic style lighting
- `sd15_trainstation`: Visual novel train station background asset
