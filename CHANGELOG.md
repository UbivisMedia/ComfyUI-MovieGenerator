# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
