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
| `ki_prompt_generieren` / `auto_prompt` | `Boolean` | No | `true` | When `true`, Phase 1 prompts LM Studio to refine the character prompt. If set to `false`, the exact text in `prompt` is used verbatim. |

### Casting Rules for LLMs
1. **Reference Framing**: Characters should always be prompted in a **neutral standing pose** (`full body shot` or `medium shot`, `standing`, `looking at viewer`, `simple background`, `soft studio lighting`). Never put complex background clutter into character casting prompts, as Minimax will mistakenly interpret background clutter as part of the actor's identity!
2. **Actor Persistence**: If `<name>.png` already exists in `Projects/<film_name>/Characters/`, the pipeline will automatically reuse it. If you want to force re-casting, change the `name` or delete the existing PNG.

---

## 2. Scene Specification (`szenen`)

Each item in `szenen` represents an individual camera shot rendered by Minimax.

```json
{
  "id": 1,
  "dauer_sekunden": 5,
  "idee": "Elara stands on the balcony in the evening light. A gentle wind blows through her hair as she looks out over the city.",
  "anschluss_an_vorherige_szene": false,
  "direkter_anschluss": false
}
```

### Field Details

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `Integer` | **Yes** | — | Numerical sequence identifier for the scene (`1, 2, 3...`). Scenes are rendered and ordered strictly by ID. |
| `idee` / `prompt` | `String` | **Yes** | — | Scene narrative idea or director instruction. Supports `{variable_name}` placeholder substitution. |
| `dauer_sekunden` | `Integer` | No | Estimated by LLM (3–10) | Target video length in seconds (typically between 4 and 8 seconds). |
| `anschluss_an_vorherige_szene` | `Boolean` | No | `false` | **Environmental Continuity**. When `true`, passes the previous rendered scene video into Minimax as `ref_videos.ref_video_0` to preserve the room, lighting, and atmosphere. |
| `direkter_anschluss` | `Boolean` | No | `false` | **Match Cut (Zero Jump Cut)**. When `true`, automatically extracts the exact last frame of the previous scene and uses it as the initial frame (`MiniMaxH3AddGuide`). The action continues without interruption. |
| `variablen_update` / `set_variables` | `Object` | No | `{}` | Key-value updates to story/wardrobe variables (e.g. `{"outfit_chloe": "wearing only pink top, apron removed"}`). Updated values automatically persist for all subsequent scenes until modified again. |

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

## 4. Continuity Modes Explained

The pipeline provides two distinct levels of continuity between scenes:

### Mode A: Independent Cut (`anschluss_an_vorherige_szene: false`, `direkter_anschluss: false`)
- **Use case**: New location, significant time skip, or complete change of scenery.
- **Behavior**: Minimax generates the scene purely from the text prompt and the character face references (`ref_images`).

### Mode B: Environmental Continuity (`anschluss_an_vorherige_szene: true`, `direkter_anschluss: false`)
- **Use case**: Camera angle change within the same room (e.g. from wide shot to close-up), or next moment in the same setting.
- **Behavior**: The previous video is fed into Minimax as a visual style and environmental guide (`ref_videos`), ensuring colors, furniture, and lighting match.

### Mode C: Direct Seamless Continuation (`anschluss_an_vorherige_szene: true`, `direkter_anschluss: true`)
- **Use case**: Continuous real-time action split across multiple render batches (e.g. dialog exchange, extended motion, continuous physical action).
- **Behavior**: Extracts the last frame of the previous clip via FFmpeg and anchors it as `first_frame` (frame 0) of the new clip. Eliminates pose snapping and visual jumps.

---

## 4. Complete Valid Screenplay Example

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
