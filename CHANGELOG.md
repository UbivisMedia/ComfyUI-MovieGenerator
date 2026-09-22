# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.3] - 2026-09-22

### ✨ Added
- **Studio Settings GUI (`settings.json` Editor)**: Added a comprehensive, comfortable visual settings editor accessible via the top navigation bar (`⚙️ Einstellungen` / `⚙️ Settings`).
  - **Minimax I2V & Turbo**: Select detected Minimax diffusion UNET models from ComfyUI, configure Turbo LoRAs, steps, strength slider with live value indicator, and VAE/CLIP models.
  - **Visual LoRA Picker for Turbo**: Integrated the rich visual LoRA picker modal (`⚡ LoRA-Picker`) directly into the settings editor, allowing users to browse cover thumbnails, descriptions, and trigger words to pick their preferred Turbo LoRA with automated step detection (3, 4, 8 steps).
  - **Music Studio Settings**: Configure default soundtrack generation, select ACE-Step / audio checkpoints, set default steps, CFG scale, volume slider with live percentage badge, and smart auto-ducking.
  - **LM Studio & System**: Configure LM Studio API endpoint, dynamically fetch and pick available language models via `Abrufen` / `Fetch`, set temperature/creativity slider, configure ComfyUI server address, models directory, and WebM export.
- **Settings Backend API (`script_agency.py`)**:
  - `GET /api/settings`: Returns merged settings with `DEFAULT_SETTINGS`.
  - `POST /api/settings`: Saves new configuration to `settings.json` with automated `.bak` backup and live in-memory synchronization.
  - `GET /api/settings/models`: Scans and enumerates local Minimax UNET models, Turbo LoRAs with auto-detected step recommendations, audio checkpoints, and queries LM Studio models via HTTP.
- **Bilingual Studio Settings Localization**: Comprehensive German and English translation keys added to `localization/de.json` and `localization/en.json`.

---

## [1.2.2] - 2026-09-22

### 🐛 Fixed
- **Director's Control Settings in Single-Scene Re-Shoot (HQ / Steps)**: Fixed an issue where re-rendering a scene (e.g. via the single-scene reshoot button) fell back to the default 8-step Turbo mode despite the scene being configured for "HQ / Kein Turbo (20 Steps)". When `master_regisseur.py` loaded the project, it previously prioritized an existing subfolder copy (`Projects/<film>/<film>.json`) which contained stale default parameters from an earlier run, ignoring the master screenplay (`Projects/<film>.json`) saved by Script Agency.
- **Master Screenplay Priority & Continuity**: `master_regisseur.py` now treats the specified screenplay path as the authoritative source of truth for all scene settings (`turbo`, `steps`, `megapixels`, `upscale`), borrows AI prompts from the project copy only when the master file lacks them, and keeps the project directory copy synchronized.
- **Dual-Path Project Saving**: `POST /api/project` in `script_agency.py` now writes to both the root project file (`Projects/<name>.json`) and the project subfolder (`Projects/<name>/<name>.json`) if the directory exists, preventing stale state drift.
- **Auto-Save Before Scene Re-Shoot**: Added automatic pre-flight screenplay saving in `web/app.js` prior to triggering `/api/scene/rerender` whenever changes are unsaved (`state.isDirty`).
- **Missing Localization Key**: Added `scene_shooting_settings` to `localization/de.json` and `localization/en.json` to correctly log director render parameters in the console during Phase 3.

### ✨ Added
- **Dynamic GUI Versioning**: Removed hardcoded version numbers from the web interface. The version is now read dynamically from `version.py` (`__version__`), exposed via `/api/version` and `/api/localization`, and automatically injected into `.version-tag` elements both during static HTML delivery and upon client-side application initialization.
- **Movie Studio Branding & Architecture**: Rebranded the web interface from "Script Agency" to **Movie Studio** (`MovieGenerator Visual Production Studio`) to reflect its evolution into a complete suite (scriptwriting, casting, directing, scoring, timeline, video player, and re-rendering).
- **Dedicated `movie_studio.py` & `start_movie_studio.bat` Launchers**: Added `movie_studio.py` and `start_movie_studio.bat` as explicit GUI entry points, clarifying the clean separation between CLI/Worker (`master_regisseur.py` / `create_movie.bat`) and Web GUI (`movie_studio.py` / `start_movie_studio.bat`). Backward-compatibility aliases for `script_agency.py` remain fully intact.

---

## [1.2.1] - 2026-09-22

### 🐛 Fixed
- **Character Casting Continuity & Variable Timeline**: Fixed continuity error where character casting portraits in ComfyUI interpolated `{variables}` (such as wardrobe changes) using values from the very end of the screenplay after LM Studio processed all scenes. Introduced automated detection of each character's first appearance scene (`first_scene`) and scoped variable resolution (`get_variables_for_scene`) so characters are cast in their authentic introductory attire.
- **Video Player Modal Overlay & Layout**: Fixed video player element rendering as a static unhideable box taking up half the viewport height by standardizing its markup on studio-wide `.modal-backdrop` and `.modal-dialog` classes. The player is now properly hidden by default.
- **Scene Re-Rendering Background Thread**: Fixed `NameError: cannot access free variable 'BASE_DIR'` in `script_agency.py` during `POST /api/scene/rerender` by removing redundant local `BASE_DIR` import shadowing in `do_POST()`.

### ✨ Added
- **Dedicated Video Player Header Button**: Added an immediate `🎬 Player` launcher button to the Script Agency top navigation bar to open or close the video player anytime.
- **Enhanced Player Controls**: Added a footer "Schließen" button in the player meta bar in addition to the header close button (✕), backdrop dismissal, and `Escape` key shortcut.
- **Bilingual Localization**: Added UI translations for `btnVideoPlayer`, `btnVideoPlayerTitle`, and `video_no_rendered_found` in `de.json` and `en.json`.

---

## [1.2.0] - 2026-09-20

### 🌟 Highlights
- **Visual Storyboard Filmstrip Timeline (`#storyboardTimelineContainer`)**: An interactive, responsive timeline strip positioned directly above the scene cards. Displays live scene thumbnails, durations, readiness status badges, interactive transition chips, and an immediate full movie playback launcher (`▶️ Gesamten Film abspielen`).
- **In-Browser Video Playback & Streaming**: Integrated HTML5 video player modal (`#videoPlayerModal`) supporting HTTP 206 Partial Content (Range requests) for instant, seekable scrubbing of both individual scene clips and the assembled master movie without leaving Script Agency.
- **Cinematic Scene Transitions**: Added per-scene cinematic transition controls with custom durations (0.5s – 2.0s). Supports **Hard Cut**, **Cross-Dissolve** (`dissolve`), **Fade to Black** (`fadeblack`), **Dip to White** (`fadewhite`), and directional **Wipes** (`wipeleft`, `wiperight`). Transition assembly automatically constructs chained FFmpeg `xfade` (video) and `acrossfade` (audio) complex filtergraphs with sample rate normalization, while seamlessly falling back to ultra-fast lossless stream-copy (`-c copy`) when only hard cuts are used.
- **Incremental Re-Rendering (`--scene <id>`)**: Directors can now re-shoot any single scene directly from its scene card (`🔄 Szene neu drehen` / `Reshoot Scene`) or via CLI flag. Automatically loads existing anchor frames for match-cut continuity, regenerates only the target scene, and immediately reassembles the master movie.

### ✨ Added
- **Storyboard Timeline Track (`web/index.html`, `web/style.css`, `web/app.js`)**:
  - Filmstrip cards displaying thumbnail previews, scene indices, durations, and rendered/pending badges.
  - Interactive transition badges between timeline cards that cycle transitions on click (`CUT` ➔ `DISSOLVE` ➔ `FADE-BLACK` ➔ `FADE-WHITE` ➔ `WIPE-LEFT`) and synchronize instantly with scene card controls.
  - Scene card highlight effect and auto-scroll when clicking timeline thumbnails.
- **In-Browser Video Player Modal (`web/index.html`, `web/style.css`, `web/app.js`)**:
  - Native video controls with keyboard shortcuts (`Escape` to close), duration indicator, and direct file download button.
  - Play buttons integrated into both timeline cards and scene card headers (`▶️`).
- **HTTP 206 Partial Content Media Streaming (`script_agency.py`)**:
  - `GET /api/scene/video?project=...&scene=...`: Stream individual scene clips.
  - `GET /api/scene/preview?project=...&scene=...`: Serve companion preview keyframes.
  - `GET /api/movie/video?project=...`: Stream the assembled full movie.
  - `GET /api/scenes/status?project=...`: Real-time query of all scene statuses, video file sizes, and duration metadata.
  - `POST /api/scene/rerender`: Background execution of selective re-rendering via `master_regisseur.py --scene <id>`.
- **FFmpeg Cinematic Transition Pipeline (`master_regisseur.py`)**:
  - `has_audio_stream(video_path)`: Reliable probe for audio presence across clips.
  - `assemble_movie()`: Dynamically compiles `xfade` and `acrossfade` filter chains with duration offsets.
  - `--scene <id>` and `--only-scene <id>` CLI arguments for targeted scene re-shooting.
- **Full Bilingual Localization**:
  - 25+ new translation keys in both `localization/de.json` and `localization/en.json` covering all timeline elements, player modal strings, and transition choices.

---

## [1.1.0] - 2026-09-20

### 🌟 Highlights
- **In-App Directing Guide & Best Practices (`📚 Guide`)**: Comprehensive, interactive studio manual with 6 structured chapters accessible directly from the header navigation. Covers the complete production pipeline, visual continuity rules (Match-Cuts, Last-Frame extraction, camera angles), scene prompting formulas, Director's Control tradeoffs, audio scoring, and a 5-step post-wizard checklist.
- **Script Wizard Co-Director Advisory System**: Prominent advisory callout boxes integrated into both the Wizard setup screen and the step-by-step interactive drafting view. Educates directors that AI scripts serve as a creative rough draft that requires human refinement (camera perspectives, match-cuts, and wardrobe alignment) to avoid disjointed video sequences. Includes direct one-click deep links to the best practices manual.
- **Director's Control (Scene-Specific Render Settings)**: Granular per-scene control over video generation parameters. Choose between fast 8-step Turbo mode or artifact-free 20-step High Quality (HQ) mode for facial stability, select native render resolutions (0.25 MP Standard, 0.45 MP Wide/Detail, 0.75 MP Native HD), and optionally bypass AI upscaling.
- **Music Studio & Time-Synchronized Scoring**: Built-in soundtrack composition using ComfyUI ACE-Step checkpoints matched to the exact film runtime. Generates scene-synchronized progression prompts with timestamps (`[mm:ss - mm:ss]`) that mirror dramatic beats and locations. Features intelligent sidechain auto-ducking via FFmpeg to automatically lower music by 6–8 dB during dialogue and sound effects.
- **Strategic Development Roadmap (`ROADMAP.md`)**: Comprehensive multi-phase evolution plan covering v1.2 (Workflow, Incremental Re-Rendering, Transitions), v1.3 (Continuity & Audio Stems), and v2.0 (Live Queue & Social Cuts).

### ✨ Added
- **In-App Guide Modal (`#guideModal`)**:
  - Split-pane layout with responsive topic navigation and cinema dark aesthetic.
  - 6 chapters with practical comparisons (❌ Vague Prompt vs. ✅ Director's Prompt), technical breakdown charts, and warning callouts.
  - Keyboard shortcut (`Escape`) and backdrop click to close.
- **Script Wizard Advisory Banners**:
  - Full-width amber callout box in initial setup view (`.wizard-director-notice-box`).
  - Compact header hint bar in interactive view (`.wizard-notice-compact`) with instant jump link (`Best Practices ↗`) targeting Chapter 2 (Continuity & Cuts).
- **Time-Synchronized Scene Progression Prompts**:
  - `build_scenes_timeline()` in `master_regisseur.py` calculates cumulative timecodes and extracts scene action, locations, and SFX.
  - LM Studio integration generates timeline-based score progression prompts with timestamps matching actual scene durations.
- **Scene-Level Render Settings (`master_regisseur.py`)**:
  - `turbo`: Toggle Minimax Turbo LoRA on/off (8 steps vs. 20 steps) per scene.
  - `megapixels` / `resolution`: Dynamically set native resolution in ComfyUI node `115` (`ResolutionSelector`).
  - `upscale`: Option to bypass `RealESRGAN_x2` for high native resolutions.
- **Music Studio Pipeline (`master_regisseur.py` & `script_agency.py`)**:
  - ComfyUI music generation workflow (`Workflows/workflow_music_ace.json`).
  - Automated sidechain compression mixing via FFmpeg (`sidechaincompress`).
  - Endpoints: `/api/music/models`, `/api/music/soundtrack`, `/api/music/suggest-tags`, `/api/music/score-movie`.
  - In-browser soundtrack player with download link and volume presets.
- **Full Bilingual Localization**:
  - Over 65 new translation keys in both `localization/de.json` and `localization/en.json` supporting real-time language switching for all new features.

### 🐛 Fixed
- Resolved `NameError: name 'shutil' is not defined` when scoring movies in `script_agency.py`.
- Standardized `/api/music/suggest-tags` response format to prevent toast error notifications on AI tag suggestion.
- Added `do_HEAD` HTTP method handler in `script_agency.py` to prevent 501 Unsupported Method errors when checking soundtrack file existence.

---

## [1.0.0] - 2026-09-18

### 🌟 Highlights
- **Visual Model Picker (SingleChoice)**: Convenient model selection modal dialog with live previews of sample images, animated hover videos, metadata specs, and category filters.
- **Automatic Loading of Existing Character Portraits**: Immediate detection and rendering of on-disk character portraits when opening or switching screenplays.
- **Dynamic Preset Catalog (`catalog_builder.py`)**: Fully automated discovery and configuration of all diffusion models and LoRAs in ComfyUI using generic architecture profiles (`BaseModelProfiles`) — eliminating hardcoded model lists.
- **LoRA Picker Media Enrichment**: Preview sample images, MP4 hover videos, and release dates (`publishedAt`) directly inside the LoRA selection cards.
- **Story Wizard & AI Screenplay Assistant**: Step-by-step scene development with interactive brainstorming, producer instructions, and scene harmonization via local LLMs (LM Studio).
- **Variables & Character Workflow**: Full variable interpolation (`{variables}`) in character prompts and direct character portrait generation in ComfyUI with optional automatic background removal.

---

### ✨ Added
- **Base Model Picker Modal (`#modelModal`)**:
  - Interactive selection window for base and diffusion models.
  - Real-time search across model names, schedulers, samplers, file paths, and descriptions.
  - Quick-filter tabs for model families: *All*, *Anima*, *Krea*, *SDXL*, *Z-Image*, *Other*.
  - Automatic integration of local companion media (`.png`, `.jpeg`, `.webp`, `.mp4`) and publishing dates.
  - SingleChoice selection: Instantly assigns model to character on click and updates the card.
- **Character Card Model Widget**:
  - Compact, clean UI widget displaying thumbnail preview, active model family badge, sampling parameters (Steps, CFG, aspect ratio), and a `🎨 Choose Model` button.
- **Automatic Character Portrait Display**:
  - When loading screenplays, existing portraits in `Projects/<Project>/Characters/<Name>.png` are immediately displayed in the portrait box with an active badge (`✔ Portrait active`).
- **Media Serving API (`GET /api/models/media`)**:
  - Efficient delivery of model preview images and video streams with HTTP byte-range requests and browser caching.
- **Dynamic Diffusion Model Scanning (`catalog_builder.py`)**:
  - Generic `BASE_MODEL_PROFILES` for `anima`, `krea2`, `zimage`, `sdxl`, and `default`.
  - Automatic base family detection and parameter overrides from `.metadata.json`, Civitai exports, or safetensors headers.
- **Enhanced LoRA Picker**:
  - Visual preview of companion images and hover-playable MP4 videos for LoRAs.
  - Date badges displaying `publishedAt` timestamps.
  - Cross-architecture LoRA compatibility checking.
- **Variable Interpolation in Character Prompts**:
  - Full variable replacement (`{celina_top}`, `{celina_bottom}`, etc.) supported in character descriptions and portrait generation prompts.
- **Direct ComfyUI Portrait Generation**:
  - `🎨 Generate Portrait` and `🔄 Regenerate` buttons inside Script Agency to create consistent reference images in ComfyUI.
  - Optional automatic background removal via `rembg`.
- **Story Wizard (`#storyWizardModal`)**:
  - Multi-step screenplay generation wizard with premise setup, maximum target duration, and token limits.
  - Interactive next-scene generation, story hooks, and scene harmonization.
- **Comprehensive Bilingual Localization (DE/EN)**:
  - 100% translated UI for all menus, modals, badges, notifications, and tooltips in `localization/de.json` and `localization/en.json`.

---

### 🔄 Changed
- Replaced the cluttered HTML `<select>` dropdown for model selection with the modern interactive model card widget.
- Refactored `catalog_builder.py` to completely eliminate hardcoded model lists in favor of dynamic profile mapping.
- Improved `master_regisseur.py` prompt optimization to ignore generic dummy placeholders (*"a brave protagonist with a determined expression"*) in favor of the actual character description.

---

### 🐛 Fixed
- **Character Image Loss on Reload**: Fixed `normalizeScreenplay()` in `web/app.js` which previously discarded `c.image` and `c.image_url`.
- **Model Discovery Gaps**: Fixed issue where only a subset of models was returned by scanning all files in `diffusion_models` and `checkpoints`.
- **Windows Terminal Encoding**: Resolved UTF-8 encoding warnings and emoji crashes in Windows terminal environments.

---

## [0.9.0] - Prior Versions
- Core pipeline implementation of `master_regisseur.py` with ComfyUI.
- Initial release of `script_agency.py` web-based screenplay editor.
- Minimax H3 I2V video workflow and Text-to-Image generation support.
