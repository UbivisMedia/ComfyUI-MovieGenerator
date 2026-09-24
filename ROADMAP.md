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

## 🎨 Phase 2: Visual Aesthetics & Character Continuity (v1.3.0)
*Focus: Peak visual fidelity, persistent character identity, and color harmony.*

### 1. Character Continuity 2.0 (IP-Adapter / FaceID)
* **Challenge:** Rapid camera movements or novel angles can introduce subtle facial drift away from the master portrait.
* **Solution:**
  * Optional **IP-Adapter FaceID / PuLID** pass inside the ComfyUI pipeline prior to I2V generation.
  * Extracts biometric and structural facial landmarks from `Characters/<Name>.png` to enforce strict identity consistency across all angles.
  * **Multi-Angle Portrait Studio:** Pre-render frontal, 3/4-view, and profile portraits per character to automatically inject the best starting perspective.

### 2. Cinematic Color Grading & 3D LUTs
* **Challenge:** Different diffusion seeds can produce inconsistent color temperatures (e.g., warm daytime in shot 1, cool tint in shot 2).
* **Solution:**
  * Post-processing 3D LUT (Cube LUT) pipeline via FFmpeg:
    * *Teal & Orange* (Modern blockbuster aesthetic)
    * *Bleach Bypass* (High contrast, gritty dramatic look)
    * *Golden Hour / Warm Sunset* (Romantic & coastal warmth)
    * *Noir / Monochrome*
  * Subtle organic 35mm film grain overlay to blend diffusion artifacts and eliminate AI smoothness.

### 3. Frame Interpolation & Slow Motion (RIFE / FILM)
* **Challenge:** Minimax generates at 16 fps or 24 fps. Action beats and emotional pauses benefit from higher frame rates or deliberate slow motion.
* **Solution:**
  * Per-scene toggle: `Slow Motion (50% Speed)` using AI frame interpolation (RIFE / FILM).
  * Smooth 60 fps export option for sweeping panoramic camera motions.

---

## 🎙️ Phase 3: Sound Design & Dedicated Narration (v1.4.0)
*Focus: Multi-track stems, professional voiceover, and layered acoustic depth.*

### 1. Dedicated Voiceover & Narration Engine
* **Challenge:** Minimax generates in-scene dialogue with `<d>...</d>`, but voiceover narration, internal monologue, or documentary-style voice requires precise timestamp synchronization.
* **Solution:**
  * Integration with local high-quality TTS engines (**F5-TTS**, **ChatterBox**, or **Coqui TTS**).
  * Dedicated `voiceover` field per scene: Generates isolated audio stems perfectly mapped to the scene window.

### 2. Multi-Track Audio Mixer in Web Editor
* **Challenge:** Sound effects, dialogue, and music are combined directly into a single master mix.
* **Solution:**
  * Interactive 3-channel mixer in the Script Agency web UI:
    1. **Channel 1: Production Audio** (Minimax dialogue & environmental foley)
    2. **Channel 2: Voiceover / Narration**
    3. **Channel 3: Score / BGM** (with configurable auto-ducking sensitivity)
  * Visual waveform preview with real-time compression ducking curves.

---

## ⚡ Phase 4: Studio Performance & Real-Time Monitoring (v2.0.0)
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
    * **21:9** Cinemascope with anamorphic letterboxing.

### 3. Dynamic VRAM & Resource Management
* **Solution:**
  * Automatic checkpoint unload (e.g., Minimax UNet) upon video generation completion to reclaim VRAM for ACE Music generation.
  * Dual-GPU balancing (e.g., GPU 0 dedicated to video diffusion, GPU 1 dedicated to audio & LLM inference).

---

## 📋 Prioritization Matrix

| Feature | Impact & Value | Complexity | Recommended Order |
| :--- | :--- | :--- | :--- |
| **Incremental Scene Re-Rendering** | 🔴 Critical (Massive time saver) | 🟡 Medium | **#1 (v1.2)** |
| **Scene Transitions (`xfade` Dissolve/Fade)** | 🔴 High (Polished cinematic flow) | 🟢 Low | **#2 (v1.2)** |
| **In-Browser Video Player & Filmstrip Timeline** | 🟡 High (Ergonomics) | 🟡 Medium | **#3 (v1.2)** |
| **Cinematic Color Grading & LUTs** | 🟡 High (Visual coherence) | 🟢 Low | **#4 (v1.3)** |
| **Dedicated Voiceover / Narration Engine** | 🟡 High (New narrative formats) | 🟡 Medium | **#5 (v1.3)** |
| **Character Continuity 2.0 (IP-Adapter)** | 🔴 Critical (Facial fidelity) | 🔴 Complex | **#6 (v2.0)** |
| **Live ComfyUI Queue & Latents in Browser** | 🟡 High (Studio UX Polish) | 🟡 Medium | **#7 (v2.0)** |

---
*Roadmap created September 19, 2026 for MovieGenerator Studio.*
