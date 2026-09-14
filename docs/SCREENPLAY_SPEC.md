# Screenplay JSON Specification (Drehbuch-Format)

This document provides the definitive specification for MovieGenerator screenplay files (`Projects/<film_name>.json`). Large Language Models (LLMs) and automated agents must adhere to this schema when creating new movie scripts.

---

## Root Schema Overview

A valid screenplay JSON consists of a single root object with two primary arrays:

```json
{
  "titel": "Movie Title",
  "variablen": {
    "outfit_elara": "white silk slip dress",
    "lighting": "warm sunset"
  },
  "charaktere": [ ... ],
  "szenen": [ ... ]
}
```

| Key | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `titel` / `title` | `String` | No | Display title for the movie project and Civitai metadata tags. |
| `variablen` / `variables` | `Object` | No | Key-value dictionary of initial story state (e.g. character wardrobe, weather, lighting). |
| `charaktere` | `Array<CharacterObject>` | Yes | Defines the cast of actors/subjects to be cast and visually referenced across scenes. |
| `szenen` | `Array<SceneObject>` | Yes | Defines the sequence of shots/scenes to be generated, directed, and spliced together. |

---

## 1. Character Specification (`charaktere`)

Each item in `charaktere` defines an actor reference image that will be rendered during Phase 2 (Casting) and injected as visual context (`ref_images`) during Phase 3 (Video Generation).

```json
{
  "id": 1,
  "name": "Elara",
  "modell": "anima_cyberrealistic",
  "loras": [
    "realskin",
    {"name": "anima_detailer", "strength": 0.8}
  ],
  "prompt": "masterpiece, best quality, 1girl, 20 years old, chestnut brown hair, hazel eyes, delicate facial features, wearing a white silk dress, full body shot, simple background, soft lighting",
  "negative_prompt": "worst quality, low quality, blurry, deformed limbs",
  "ki_prompt_generieren": true
}
```

### Field Details

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `Integer` | Recommended | `1, 2, ...` | Unique numerical identifier for the character. |
| `name` | `String` | **Yes** | `"actor_1"` | Character name. Used as filename for the reference portrait (`Projects/<film>/Characters/<name>.png`). |
| `modell` / `preset` / `model` | `String` | No | `"anima_catpony"` | Key of the T2I preset defined in `Presets/t2i_presets.json`. Examples: `anima_cyberrealistic`, `krea2_turbo_int8`, `anima_catpony`, `anima_turbo`, `anima_finalcut_int8`. |
| `loras` / `lora` | `Array<String \| Object>` | No | `[]` | List of LoRAs to apply during casting. Can be a string key (e.g. `"realskin"`) or an object with custom strength: `{"name": "realskin", "strength": 0.8}`. |
| `prompt` | `String` | Recommended | `""` | Visual description of the character. If `ki_prompt_generieren` is enabled, LM Studio uses this as a starting point to engineer an optimal English prompt. |
| `negative_prompt` | `String` | No | Preset default | Custom negative prompt overriding the model preset negative prompt. |
| `reference_id` / `referenz_id` / `reference_character` | `Integer \| String` | No | `null` | **Character Reference Link (I2I Continuity)**. Links this character to a previously cast character by ID (e.g. `1`) or name (e.g. `"Leo_Real_Boy"`). Instead of generating from scratch, ComfyUI uses the reference image as an Image-to-Image latent base, preserving facial structure, posture, and clothing across different styles (e.g. photorealistic $\rightarrow$ anime) or age progressions. |
| `denoise` | `Float` | No | `0.65` (when referenced), `1.0` (standard T2I) | **Denoising Strength for Reference Casting** (`0.05` to `1.0`). Lower values retain more of the original reference image; higher values grant the new model and prompt more stylistic freedom. |
| `ki_prompt_generieren` / `auto_prompt` | `Boolean` | No | `true` | When `true`, Phase 1 prompts LM Studio to refine the character prompt. If set to `false`, the exact text in `prompt` is used verbatim. |

### Casting Rules & Character Continuity
1. **Reference Framing**: Characters should always be prompted in a **neutral standing pose** (`full body shot` or `medium shot`, `standing`, `looking at viewer`, `simple background`, `soft studio lighting`). Never put complex background clutter into character casting prompts, as Minimax will mistakenly interpret background clutter as part of the actor's identity!
2. **Stylistic Transformation & Aging (`reference_id`)**: When a story calls for the same character across different art styles (e.g. photorealistic boy $\rightarrow$ anime boy) or across age milestones (8-year-old child $\rightarrow$ 90-year-old elder), set `"reference_id": <id>` on the secondary character. ComfyUI will run Image-to-Image over the primary character's portrait, keeping facial proportions and bone structure intact while transforming texture and style.
3. **Actor Persistence**: If `<name>.png` already exists in `Projects/<film_name>/Characters/`, the pipeline will automatically reuse it. If you want to force re-casting, change the `name` or delete the existing PNG.

---

## 2. Scene Specification (`szenen`)

Each item in `szenen` represents an individual camera shot rendered by Minimax.

```json
{
  "id": 1,
  "sequence": "dining_table",
  "location": "Modern Kitchen Dining Table",
  "dauer_sekunden": 5,
  "idee": "Elara stands on the balcony in the evening light. A gentle wind blows through her hair as she looks out over the city.",
  "anschluss_an_vorherige_szene": false,
  "direkter_anschluss": false,
  "same_scene": false
}
```

### Field Details

| Field (DE / EN) | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `Integer` | **Yes** | — | Numerical sequence identifier for the shot/scene (`1, 2, 3...`). Ordered strictly by ID. |
| `idee` / `idea` / `prompt` | `String` | **Yes** | — | Shot narrative idea or director instruction. Supports `{variable_name}` substitution. |
| `dauer_sekunden` / `duration` / `duration_seconds` | `Integer` | No | Estimated by LLM (3–10) | Target video length in seconds. |
| `sequence` / `sequenz` / `scene_group` / `bundle` | `String` | No | `null` | **Scene Grouping / Sequence ID**. Consecutive shots sharing the same sequence automatically share environment and physical proximity context. |
| `location` / `ort` / `setting` | `String` | No | `null` | **Location Tag** (e.g. `"Balcony"`, `"Kitchen Dining Table"`). Informs the LLM of the continuous physical environment. |
| `same_scene` / `gleiche_szene` / `angle_change` | `Boolean` | No | `false` | **Same Scene / Camera Angle Change**. Informs LM Studio that the shot is an angle cut (e.g. close-up, over-the-shoulder) within the same scene. Automatically enforces that characters start **ALREADY** in their established positions without resetting postures or re-approaching. |
| `anschluss_an_vorherige_szene` / `continuity_environment` / `continuity` | `Boolean` | No | `false` (or auto if in same sequence) | **Environmental Continuity**. Passes the previous rendered scene video into Minimax as `ref_videos.ref_video_0` to preserve room lighting, background, and atmosphere. |
| `direkter_anschluss` / `direct_continuation` / `match_cut` | `Boolean` | No | `false` | **Match Cut (Zero Jump Cut)**. Extracts the exact final frame of the previous scene and uses it as the initial frame (`MiniMaxH3AddGuide`). Motion continues seamlessly. |
| `variablen_update` / `variables_update` / `set_variables` | `Object` | No | `{}` | Key-value updates to story/wardrobe variables (e.g. `{"outfit_chloe": "wearing only pink top, apron removed"}`). Persists for all subsequent shots until changed again. |
| `charakter_status` / `character_status` | `Object` | No | `{}` | Per-scene character temporary state annotations (e.g. `{"Chloe": "sitting close to Liam, leaning forward"}`). |
| `ki_prompt_generieren` / `auto_prompt` / `generate_prompt` | `Boolean` | No | `true` | When `false`, uses the exact text in `idee`/`prompt` verbatim without LM Studio expansion. |

---

## 3. Dynamic Variables & Wardrobe Continuity

In multi-scene AI movies, characters frequently change clothes, undress, get wet, or undergo visual changes. By default, Minimax references the static casting image (`<Picture X>`) for facial identity, which means Minimax will attempt to redraw the original clothing unless explicitly told otherwise.

The **Variable System** solves this by maintaining a persistent state machine across scenes:

### How it works:
1. **Define Baseline Outfits** in the root `"variablen"` dictionary (or per character in `"charaktere"`):
   ```json
   "variablen": {
     "outfit_chloe": "white chef apron over light pink top",
     "outfit_liam": "simple grey t-shirt"
   }
   ```
2. **Update Variables on Specific Scenes** via `"variablen_update"`:
   ```json
   {
     "id": 5,
     "idee": "Chloe stirs the eggs, then slowly unties her apron and sets it on the counter.",
     "variablen_update": {
       "outfit_chloe": "wearing only light pink top, chef apron untied and removed"
     }
   }
   ```
3. **Template Interpolation in Ideas**: You can use `{variable_name}` directly inside `idee`:
   ```json
   "idee": "Medium Shot: Chloe ({outfit_chloe}) and Liam ({outfit_liam}) work side-by-side."
   ```
4. **Automatic Minimax Prompt Injection**: The engine automatically compiles the current active states into a `CRITICAL CHARACTER WARDROBE & STATE CONTINUITY` block for LM Studio. This instructs Minimax to use `<Picture X>` solely for the actor's facial likeness while forcefully rendering their current scene clothing.

---

## 4. Continuity Modes & Scene Bundling

The pipeline provides four distinct levels of continuity between scenes:

### Mode A: Independent Cut (`anschluss_an_vorherige_szene: false`, `direkter_anschluss: false`)
- **Use case**: New location, significant time skip, or complete change of scenery.
- **Behavior**: Minimax generates the scene purely from the text prompt and the character face references (`ref_images`). Characters may begin in standard postures.

### Mode B: Environmental Continuity (`anschluss_an_vorherige_szene: true`, `direkter_anschluss: false`)
- **Use case**: New angle or subsequent beat in the same setting.
- **Behavior**: The previous video is fed into Minimax as a visual style and environmental guide (`ref_videos`), ensuring colors, furniture, and lighting match.

### Mode C: Direct Seamless Continuation / Match Cut (`direkter_anschluss: true` / `direct_continuation: true`)
- **Use case**: Continuous real-time action split across multiple render batches (e.g. uninterrupted motion, continuous dialog delivery).
- **Behavior**: Extracts the last frame of the previous clip via FFmpeg and anchors it as `first_frame` (frame 0) of the new clip (`MiniMaxH3AddGuide`). Eliminates pose snapping and visual jumps entirely.

### Mode D: Same Scene Angle Cut (`same_scene: true` / `gleiche_szene: true`)
- **Use case**: Changing camera perspectives (e.g. wide shot to close-up, over-the-shoulder, reaction shot) while characters remain in the same physical position.
- **Behavior**: Does not force a static initial frame (allowing full freedom of camera choreography), but strictly instructs LM Studio that characters are **ALREADY** in their established physical posture. Prevents redundant actions like characters repeatedly walking in, sitting down again, or re-initiating hugs across cuts.

### 5. Sequence Bundles (`sequence` / `sequenz`)
When multiple consecutive shots belong to the same dramatic scene (e.g. shots 14 to 25 at a breakfast table), group them using `"sequence"`:
```json
{
  "id": 14,
  "sequence": "breakfast_table",
  "location": "Kitchen Dining Table",
  "idee": "Chloe and Liam sit down facing each other."
},
{
  "id": 15,
  "sequence": "breakfast_table",
  "same_scene": true,
  "idee": "Close-up on their hands touching over the plate."
}
```
All shots sharing the same `"sequence"` tag automatically inherit environmental continuity and physical posture tracking.

---

## 6. Complete Valid Screenplay Example

```json
{
  "charaktere": [
    {
      "id": 1,
      "name": "Detective_Cole",
      "modell": "krea2_turbo_int8",
      "loras": [
        "krea_keiran",
        "krea_cinematic"
      ],
      "prompt": "masterpiece, 1man, 35 years old, sharp jawline, short dark hair, wearing a wet trench coat, weary expression, full body shot, simple background, dramatic noir lighting",
      "ki_prompt_generieren": false
    },
    {
      "id": 2,
      "name": "Sarah",
      "modell": "krea2_turbo_int8",
      "loras": [
        "krea_elena",
        "krea_vintage"
      ],
      "prompt": "masterpiece, 1girl, 28 years old, blonde bob haircut, emerald eyes, vintage green jacket, confident expression, full body shot, simple background, soft cinematic lighting",
      "ki_prompt_generieren": false
    }
  ],
  "szenen": [
    {
      "id": 1,
      "dauer_sekunden": 5,
      "idee": "Establishing shot: Detective Cole stands under a flickering neon light on a rainy street corner, checking his wristwatch.",
      "anschluss_an_vorherige_szene": false,
      "direkter_anschluss": false
    },
    {
      "id": 2,
      "dauer_sekunden": 5,
      "idee": "Close-up: Sarah steps out of the shadow of the doorway into the soft neon rain light and looks directly at Cole.",
      "anschluss_an_vorherige_szene": true,
      "direkter_anschluss": false
    },
    {
      "id": 3,
      "dauer_sekunden": 6,
      "idee": "Medium two-shot: Cole turns his head towards Sarah. She walks toward him and speaks quietly while rain drips from his coat.",
      "anschluss_an_vorherige_szene": true,
      "direkter_anschluss": true
    }
  ]
}
```
