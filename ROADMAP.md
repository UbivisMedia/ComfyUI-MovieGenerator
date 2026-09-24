# 🗺️ MovieGenerator & Script Agency — Development Roadmap

This roadmap outlines the strategic development path for **MovieGenerator** and **Script Agency**. It organizes meaningful improvements, quality enhancements, and new feature sets across logical release phases and domain areas.

---

## 🎯 Milestone Overview

```mermaid
timeline
    title MovieGenerator Evolution
    section v1.1 (Released)
        Director's Control : Per-Scene Turbo, Steps, Resolution, Upscale
        Music Studio : Time-synchronized scoring with Auto-Ducking
    section v1.2 (Released)
        Visual Timeline & Video Preview : Interactive filmstrip & in-browser video playback
        Scene Transitions : Dissolves, crossfades, fade-to-black via FFmpeg xfade
        Incremental Re-Rendering : Re-render individual scenes on demand
    section v1.3 (Current Focus)
        TTS & Voiceover Engine : Dedicated narration track (F5-TTS, ChatterBox, Coqui)
        Color Grading & Film LUTs : Unified cinematic looks & 35mm grain across all scenes
        Multi-Track Audio Mixer : Graphical waveform, dialogue, ambience & BGM levels
    section v2.0 (Next-Gen Studio)
        Character Consistency 2.0 : IP-Adapter / FaceID / PuLID integration
        Live ComfyUI Queue in Web : Realtime step progress, latent preview & ETA in browser
        Social Cuts & Aspect Ratios : 9:16 Vertical Smart-Crop & 21:9 Cinemascope
```

---

## 🚀 Phase 1: Workflow & Editing Comfort (v1.2.0) ✅ [Completed]

*Focus: User ergonomics, rapid iteration loops, and cinematic pacing.*

### 1. Incremental Re-Rendering & Smart Cache ✅

* **Challenge:** Modifying a single shot in Scene 4 previously required re-rendering the entire project or manually manipulating disk files.
* **Solution Implemented:**
  * Added `--scene <id>` and `--only-scene <id>` selective generation in `master_regisseur.py`.
  * **`🔄 Szene neu drehen / Reshoot Scene`** button directly integrated into each scene card and timeline cell.
  * Fast re-stitching of the master film within seconds after any individual scene finishes, preserving existing match-cut anchor frames.

### 2. Visual Storyboard Timeline & In-Browser Video Preview ✅

* **Challenge:** Directors had to review the final cut in an external media player rather than inspecting shots directly within Script Agency.
* **Solution Implemented:**
  * **Interactive Filmstrip Timeline:** Horizontal scrubber bar displaying shot thumbnails, cumulative duration, and scene status badges.
  * **In-Browser Video Playback:** HTML5 video player modal with HTTP 206 partial content streaming for both scene clips and full movie assembly.
  * **Instant Scene Card Navigation:** Clicking any filmstrip thumbnail auto-scrolls to and highlights the target scene card.

### 3. Cinematic Scene Transitions ✅

* **Challenge:** All shots were previously joined via hard cuts or direct match-cuts.
* **Solution Implemented:**
  * Transition selector per scene:
    * `Hard Cut` (Default — uses ultra-fast lossless `-c copy` stream concatenation)
    * `Cross-Dissolve` (`dissolve`, smooth overlapping blend)
    * `Fade to Black` (`fadeblack`, act transitions, passage of time)
    * `Dip to White` (`fadewhite`, flashbacks, dream sequences, lightning)
    * `Wipe Left / Wipe Right` (`wipeleft`, `wiperight`, dynamic action cuts)
  * Assembled seamlessly via FFmpeg `xfade` (video) and `acrossfade` (audio) chained filtergraphs with automatic duration offsets.
  * Interactive transition chips directly in the filmstrip timeline to cycle transition types with one click.

---

## 🎨 Phase 2: Visual Aesthetics & Dedicated Narration (v1.3.0) ✅

*Focus: Non-diegetic narration, multi-stem audio mixing, cinematic color grading, and analog film grain.*

### 1. Dedicated Voiceover & Narration Engine ✅

* **Challenge:** Minimax generates diegetic in-scene dialogue via `<d>...</d>` with automatic lip-sync, but non-diegetic voiceover narration, documentary voice, or internal monologue requires precise synchronization, stem isolation, and dedicated narrator timbres.
* **Solution Implemented:**
  * Dedicated `voiceover` / `narration` field and `voiceover_voice` selector per scene card in Movie Studio.
  * Multi-engine TTS architecture (`lib/tts_manager.py`) supporting:
    * **Edge-TTS:** 14 high-fidelity neural voices (German: Conrad, Katja, Killian, Amala; English: Christopher, Jenny, Guy, Aria, Sonia, Ryan) with instant in-browser audio preview (`GET /api/voiceover/preview`).
    * **Kokoro ONNX:** Local zero-VRAM neural speech synthesis in ComfyUI (`workflow_tts_kokoro.json`).
  * Automated stem mixing (`mix_voiceover_into_scene_clip`): Blends voiceover with original scene audio/foley using configurable volume and background attenuation (`sidechain` balance), which then feeds seamlessly into the master soundtrack auto-ducking pipeline.
  * Studio Settings pane for default narrator voice, global volume, and scene audio attenuation.
  * Visual `🎙️` badges in the Storyboard Filmstrip timeline for instant scene narration overview.

### 2. Cinematic Color Grading, 3D LUTs & 35mm Film Grain ✅

* **Challenge:** Independent diffusion seeds across scenes can introduce inconsistent color temperatures and an artificial "AI smooth" plastic finish.
* **Solution Implemented:**
  * Production-grade color management engine (`lib/color_manager.py`) with 7 curated looks:
    * *Teal & Orange* (Modern cinema blockbuster aesthetic)
    * *Bleach Bypass* (High contrast, gritty action & war look)
    * *Warm Golden* (Golden hour, romantic & sunset warmth)
    * *Film Noir* (Monochrome, deep shadows & high contrast)
    * *Matrix Cyber* (High-tech green/cyan dystopia tint)
    * *Vintage 1970s* (Warm nostalgic retro film look)
    * *Custom .cube 3D LUTs* (User-loadable `.cube` LUT files)
  * Analog 35mm Film Grain generator (`none`, `subtle`, `medium`, `heavy`) injecting organic texture to break AI smoothness.
  * Cinemascope 21:9 aspect ratio letterbox filter (anamorphic cinema black bars).
  * Global studio settings and per-scene overrides in the Storyboard with `🎨` visual badges.

---

## ⚡ Phase 3: Character Continuity & Motion Dynamics (v1.4.0)

*Focus: Multi-angle actor reference, advanced identity locking, and AI frame interpolation.*

### 1. Character Continuity 2.0 (IP-Adapter / Multi-Angle Studio)

* **Challenge:** Rapid camera movements or novel angles can introduce subtle facial drift away from the master portrait.
* **Solution:**
  * Optional **IP-Adapter FaceID / PuLID** pass inside the ComfyUI pipeline prior to I2V generation.
  * Extracts biometric and structural facial landmarks from `Characters/<Name>.png` to enforce strict identity consistency across all angles.
  * **Multi-Angle Portrait Studio:** Pre-render frontal, 3/4-view, and profile portraits per character to automatically inject the best starting perspective.

### 2. Frame Interpolation & Slow Motion (RIFE / FILM)

* **Challenge:** Minimax generates at 16 fps or 24 fps. Action beats and emotional pauses benefit from higher frame rates or deliberate slow motion.
* **Solution:**
  * Per-scene toggle: `Slow Motion (50% Speed)` using AI frame interpolation (RIFE / FILM).
  * Smooth 60 fps export option for sweeping panoramic camera motions.

---

## 🚀 Phase 4: Studio Performance & Real-Time Monitoring (v2.0.0)

*Focus: Live feedback loops, multi-format delivery, and resource optimization.*

### 1. Live ComfyUI Render Queue & Latent Preview

* **Challenge:** Progress monitoring currently requires checking terminal logs.
* **Solution:**
  * WebSocket bridge connecting ComfyUI execution events directly to the browser UI:
    * Real-time step counter (e.g., `Step 14 / 20`).
    * Real-time intermediate KSampler latent thumbnail preview.
    * Live ETA countdown and emergency `Cancel Generation` button.

### 2. Multi-Format Social Media Deliverables

* **Solution:**
  * One-click aspect ratio export profiles:
    * **16:9** Widescreen (Cinema & YouTube standard)
    * **9:16** Vertical (TikTok, Instagram Reels, YouTube Shorts) featuring AI smart-crop face tracking to keep actors centered.

### 3. Dynamic VRAM & Resource Management

* **Solution:**
  * Automatic checkpoint unload (e.g., Minimax UNet) upon video generation completion to reclaim VRAM for ACE Music generation.
  * Dual-GPU balancing (e.g., GPU 0 dedicated to video diffusion, GPU 1 dedicated to audio & LLM inference).

---

## 📋 Prioritization Matrix

| Feature | Impact & Value | Complexity | Status |
| :--- | :--- | :--- | :--- |
| **Incremental Scene Re-Rendering** | 🔴 Critical (Massive time saver) | 🟡 Medium | ✅ **Done (v1.2)** |
| **Scene Transitions (`xfade` Dissolve/Fade)** | 🔴 High (Polished cinematic flow) | 🟢 Low | ✅ **Done (v1.2)** |
| **In-Browser Video Player & Filmstrip Timeline** | 🟡 High (Ergonomics) | 🟡 Medium | ✅ **Done (v1.2)** |
| **Dedicated Voiceover & Narration Engine** | 🔴 Critical (Non-diegetic audio) | 🟡 Medium | ✅ **Done (v1.3)** |
| **Cinematic Color Grading & 3D LUTs / Grain** | 🟡 High (Visual coherence) | 🟢 Low | ✅ **Done (v1.3)** |
| **Character Continuity 2.0 (IP-Adapter)** | 🔴 Critical (Facial fidelity) | 🔴 Complex | **Next (v1.4)** |
| **Frame Interpolation & Slow Motion (RIFE)** | 🟡 High (Cinematic motion) | 🟡 Medium | **Next (v1.4)** |
| **Live ComfyUI Queue & Latents in Browser** | 🟡 High (Studio UX Polish) | 🟡 Medium | **Planned (v2.0)** |

---
*Roadmap created September 19, 2026 for MovieGenerator Studio.*
