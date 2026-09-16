# 🎬 Script Agency — Visual Screenplay Studio & AI Screenwriter

**Script Agency** is MovieGenerator's interactive, browser-based screenplay studio. It pairs a visual, multi-scene storyboarding environment with an intelligent **AI Screenwriter Co-Director** powered by your local LM Studio models.

It allows you to cast actors with tailored LoRAs, structure multi-shot sequences, control camera angle cuts and match cuts, manage persistent wardrobe variables, and collaborate with a local LLM to translate rough ideas into cinematic, production-ready Minimax prompts.

---

## 🚀 Quick Launch

You can launch the Script Agency in three ways:

1. **One-Click Windows Launcher**:
   Double-click `start_script_agency.bat`.
2. **Interactive Main Menu**:
   Double-click `create_movie.bat` and press `[E]` to open the Screenplay Editor. When you close the editor, the menu automatically refreshes.
3. **Command Line (Terminal / PowerShell)**:
   ```bash
   python script_agency.py
   ```

By default, the server runs locally on **`http://127.0.0.1:7860/`** (or increments to `7861`, `7862`, etc. if port 7860 is occupied). It uses standard Python libraries only with zero external pip dependencies.

---

## 🌟 Key Features

### 1. Visual Multi-Scene Storyboard
- **Sequence & Location Bundling**: Group consecutive shots taking place in the same dramatic beat using `sequence` and `location`. This guarantees continuity across cuts.
- **Shot Continuity Badges**:
  - **Match-Cut (`match_cut`)**: Zero-jump-cut physical continuation anchored to the final frame of the previous scene.
  - **Same Scene (`same_scene`)**: Camera perspective switch (over-the-shoulder, reverse-shot, close-up) where characters remain in their established physical postures.
  - **Environmental Continuity (`use_previous_scene`)**: Uses the previous shot video as an environmental lighting and architecture guide.
- **Scene LoRA Picker**: Assign scene-specific Minimax H3 LoRAs (camera motion, martial arts, intimate scenes, film styles) with single-click modal dialogs.
- **Direct Reordering & Duplication**: Move shots up or down, duplicate complex setups, or delete shots.

### 2. Actor Casting & Model Catalog Explorer
- **Preset-Aware LoRA Stacking**: Select any diffusion model (e.g. `anima_cyberrealistic`, `krea2_turbo_int8`, `anima_catpony`). The studio automatically filters and presents only compatible LoRAs from your local ComfyUI model folder.
- **LoRA Trigger Phrases & Strength**: Inspect LoRA descriptions, trigger words, and tweak strength values per actor.
- **Instant Model Re-scan**: Click `🔄 Katalog-Scan` anytime to scan newly downloaded models and LoRAs directly from ComfyUI without restarting.

### 3. Persistent Variables & Wardrobe State Machine
- **Global Variables**: Define initial character wardrobe states or environmental attributes (`{outfit_maya}`, `{weather}`, `{scanner}`).
- **Interactive Insertion Chips**: Insert `{variable_name}` placeholders directly into scene ideas with a single click.
- **Scene-Specific Overrides (`variables_update`)**: Update a character's wardrobe or props in any shot (e.g. `{"outfit_maya": "tactical jacket removed, wearing black tank top"}`). Subsequent shots inherit this state automatically!

---

## 🤖 AI Screenwriter & Co-Director (LM Studio Integration)

The studio connects directly to your local **LM Studio** server (`http://127.0.0.1:1234/v1/chat/completions`) to act as your autonomous screenwriting assistant.

### 🪄 1. Elaborate Scene Idea (`btn-ai-elaborate-scene`)
Turns a short idea or director note (in German or English) into an official, multi-part Minimax prompt block:

- **`summary:`**: Concise one-sentence action summary in English.
- **`detailed_description:`**: Cinematic medium/close-up shot description with 35mm film aesthetics, lighting, and camera movement.
- **`overall_soundscape:`**: High-fidelity diegetic ambient acoustics, foley, breathing, and dialogue.
- **`non_diegetic_music: None`**: Strictly excludes background music so audio can be spliced losslessly during post-production.
- **`DURATION: X`**: Dynamically estimated duration between 3 and 15 seconds.
- **`LORAS:`**: Auto-selected matching Minimax LoRAs from your local catalog.

#### 🧠 Grounded in Project Documentation (`docs/`)
The AI Screenwriter dynamically loads and references:
- **`docs/LLM_SYSTEM_PROMPT.md`**: Technical constraints, dynamic variables, and continuity rules.
- **`prompts/minimax_scene.txt`**: Audio, subject tagging, and camera instructions.

#### 🎞️ Context-Aware Shot Continuity
When elaborating a shot, the AI Screenwriter ingests the **preceding shots in the screenplay**—especially shots sharing the same `sequence` or `location`. If a previous shot established that characters were standing near a bed, the new shot naturally continues from that exact physical posture without having them walk into the room again or re-initiate already completed actions!

#### 🏷️ Mandatory Subject Tagging (`<Subject X>`)
The engine maps character names to `<Subject X>` tags bound to casting portraits (`<Picture X>`), ensuring Minimax preserves facial identity and visual consistency across cuts.

---

### 💡 2. Suggest Next Scene (`btn-ai-suggest-scene`)
Brainstorms the next dramatic beat in the screenplay. It analyzes:
- The overall movie title and logline description.
- Active cast members.
- Global variables and props.
- The preceding 4 shots in the film.
- Produces a logical next scene object complete with sequence title, location, estimated duration, participating actors, and narrative idea.

---

### 🪄 3. Suggest Scene Variables (`btn-ai-suggest-scene-vars`)
Analyzes the scene's action to detect whether any character changed clothes, removed an item, or altered appearance, and suggests clean `variables_update` dictionary keys without hallucinating unrelated props.

---

## 🛡️ Reasoning Model Support & Hardened Sanitization

Modern local LLMs (e.g. `gemma-4-e4b-uncensored`, `DeepSeek-R1`, `Qwen-QwQ`) produce extensive internal reasoning / Chain-of-Thought (*"Here's a thinking process to construct the prompt: 1. Analyze the request..."*).

Script Agency incorporates specialized safeguards for reasoning models:
1. **Generous Token Budgets (4000+ Tokens)**:
   Reasoning models share token limits between internal thinking and final output. Script Agency provides 4000+ tokens to ensure the model finishes thinking and completes the prompt.
2. **Hardened Post-Processing (`clean_elaborated_prompt`)**:
   - Strips all internal thinking traces, preambles, and conversational intros before `summary:`.
   - If a model's generation is truncated or halts inside reasoning, the engine extracts the drafted camera action and synthesizes a valid, clean Minimax prompt block.
   - **Zero reasoning leaks into your screenplay!**

---

## 🔌 REST API Endpoints

The `script_agency.py` server exposes lightweight JSON endpoints:

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/api/projects` | `GET` | Lists all screenplay projects in `Projects/`. |
| `/api/project/load?name=<file>` | `GET` | Loads screenplay JSON with automatic backup creation. |
| `/api/project/save` | `POST` | Saves screenplay JSON with atomic write and `.bak` safety backup. |
| `/api/presets` | `GET` | Returns diffusion presets, models, and compatible LoRA catalog. |
| `/api/catalog/rescan` | `POST` | Triggers background model/LoRA scan via `catalog_builder.py`. |
| `/api/llm/status` | `GET` | Checks if LM Studio is online and reports the active model. |
| `/api/llm/generate` | `POST` | Handles AI generation tasks (`elaborate_scene`, `suggest_scene`, `suggest_variables`). |
| `/api/shutdown` | `POST` | Gracefully shuts down the web server and releases port. |

---

## 💡 Best Practices

1. **Bundle Scenes by Sequence**:
   Give consecutive shots the same `sequence` name (e.g. `Bedroom Talk`, `Car Chase`). The AI Screenwriter and Minimax will both maintain tight environmental and posture continuity.
2. **Use Variables for Wardrobe Changes**:
   Whenever a character changes clothes, use the **`variables_update`** field on that scene. Minimax will override the casting portrait's original outfit and lock the new clothing in place.
3. **Review Continuity Toggles**:
   - Use **Same Scene** when changing camera angles within the same room.
   - Use **Match-Cut** when continuing an uninterrupted physical motion (e.g. reaching for an object, throwing a punch).
4. **Export & Render**:
   Once your screenplay is ready in the Script Agency, simply click save, close the editor, and run `create_movie.bat` to launch full autonomous rendering!
