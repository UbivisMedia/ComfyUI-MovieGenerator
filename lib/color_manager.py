"""
lib/color_manager.py - Cinematic Color Grading, 3D LUTs & Film Grain Engine for MovieGenerator

Provides curated cinematic color looks (Teal & Orange, Bleach Bypass, Golden Hour, Noir, etc.),
organic 35mm film grain simulation, anamorphic letterboxing (21:9 Cinemascope),
and 3D Cube LUT integration via FFmpeg filtergraphs.
"""

import os
import re

# Curated cinematic looks via optimized FFmpeg curves and color adjustments
COLOR_LOOKS = {
    "none": {
        "id": "none",
        "name_de": "Natürlich (Original)",
        "name_en": "Natural (Original)",
        "desc_de": "Unberührtes Diffusionsergebnis ohne Nachbearbeitung.",
        "desc_en": "Untouched diffusion output without color grading.",
        "filter": ""
    },
    "teal_orange": {
        "id": "teal_orange",
        "name_de": "Teal & Orange (Blockbuster)",
        "name_en": "Teal & Orange (Blockbuster)",
        "desc_de": "Warme Hauttöne und kühle Türkis-Schatten – der klassische Kino-Look.",
        "desc_en": "Warm skin tones with deep teal/cyan shadows – modern blockbuster palette.",
        "filter": "curves=m='0/0 0.5/0.48 1/1':r='0/0 0.25/0.22 0.75/0.82 1/1':g='0/0 0.5/0.48 1/1':b='0/0 0.25/0.32 0.75/0.68 1/0.92',eq=contrast=1.12:saturation=1.15"
    },
    "warm_golden": {
        "id": "warm_golden",
        "name_de": "Goldene Stunde (Warm Sunset)",
        "name_en": "Golden Hour (Warm Sunset)",
        "desc_de": "Warme Sonnenuntergangstöne, goldene Highlights und weiche Kontraste.",
        "desc_en": "Warm sunset glow, golden highlights and romantic warmth.",
        "filter": "curves=r='0/0 0.5/0.56 1/1':b='0/0 0.5/0.42 1/0.88',eq=contrast=1.06:saturation=1.14"
    },
    "bleach_bypass": {
        "id": "bleach_bypass",
        "name_de": "Bleach Bypass (Gritty Drama)",
        "name_en": "Bleach Bypass (Gritty Drama)",
        "desc_de": "Entsättigt, harter Kontrast und raue Silberhalogenid-Ästhetik.",
        "desc_en": "High contrast, desaturated silver halide dramatic look.",
        "filter": "eq=contrast=1.32:saturation=0.52:brightness=-0.02"
    },
    "film_noir": {
        "id": "film_noir",
        "name_de": "Film Noir (Monochrom)",
        "name_en": "Film Noir (Monochrome)",
        "desc_de": "Tiefes Schwarz-Weiß mit seidigen Mitteltönen und dramatischen Schatten.",
        "desc_en": "High-contrast monochrome with deep velvety shadows and rich highlights.",
        "filter": "hue=s=0,curves=all='0/0 0.2/0.14 0.6/0.65 1/1',eq=contrast=1.25"
    },
    "matrix_cyber": {
        "id": "matrix_cyber",
        "name_de": "Matrix / Cyber Green",
        "name_en": "Matrix / Cyber Green",
        "desc_de": "Kühler Sci-Fi-Grün/Cyan-Ton mit tiefem Kontrast für Thriller.",
        "desc_en": "Cold green/cyan tint with crushed blacks for sci-fi and tech thrillers.",
        "filter": "curves=r='0/0 0.5/0.42 1/0.9':g='0/0 0.5/0.55 1/1':b='0/0 0.5/0.48 1/0.95',eq=contrast=1.15:saturation=0.92"
    },
    "vintage_film": {
        "id": "vintage_film",
        "name_de": "Vintage 1970s (Warmes Zelluloid)",
        "name_en": "Vintage 1970s (Retro Film)",
        "desc_de": "Nostalgischer 70er-Look mit angehobenen Schatten und verblasstem Glanz.",
        "desc_en": "Nostalgic 1970s warmth with lifted faded shadows and organic patina.",
        "filter": "curves=m='0/0.05 0.5/0.5 1/0.96':r='0/0.04 0.5/0.53 1/1':b='0/0.08 0.5/0.46 1/0.9',eq=contrast=1.05:saturation=0.9"
    }
}

# Organic 35mm grain simulations (FFmpeg temporal noise)
GRAIN_PRESETS = {
    "none": {
        "id": "none",
        "name_de": "Keine Körnung (Glatt)",
        "name_en": "No Grain (Clean)",
        "filter": ""
    },
    "subtle": {
        "id": "subtle",
        "name_de": "Dezent (35mm Feinkorn)",
        "name_en": "Subtle (35mm Fine Grain)",
        "filter": "noise=alls=7:allf=t"
    },
    "medium": {
        "id": "medium",
        "name_de": "Mittel (35mm Standard)",
        "name_en": "Medium (35mm Standard)",
        "filter": "noise=alls=12:allf=t+u"
    },
    "heavy": {
        "id": "heavy",
        "name_de": "Stark (16mm Vintage / Gritty)",
        "name_en": "Heavy (16mm Vintage / Gritty)",
        "filter": "noise=alls=20:allf=t+u"
    }
}

# Framing & Letterboxing
LETTERBOX_PRESETS = {
    "none": {
        "id": "none",
        "name_de": "Standard 16:9 Vollbild",
        "name_en": "Standard 16:9 Full",
        "filter": ""
    },
    "cinemascope": {
        "id": "cinemascope",
        "name_de": "Cinemascope 21:9 (2.39:1 Kinobalken)",
        "name_en": "Cinemascope 21:9 (2.39:1 Letterbox)",
        "filter": "drawbox=y=0:h=ih*0.125:c=black:t=fill,drawbox=y=ih-ih*0.125:h=ih*0.125:c=black:t=fill"
    }
}


def build_color_filter(look="none", grain="none", letterbox="none", custom_lut_path=None):
    """
    Compiles an FFmpeg video filter substring combining color look,
    grain simulation, and letterbox bars.
    Returns empty string if all are 'none'.
    """
    filters = []

    # 1. Custom 3D LUT or preset color look
    if custom_lut_path and os.path.exists(custom_lut_path):
        escaped_lut = custom_lut_path.replace("\\", "/").replace(":", "\\:")
        filters.append(f"lut3d=file='{escaped_lut}'")
    else:
        look_data = COLOR_LOOKS.get(look)
        if look_data and look_data.get("filter"):
            filters.append(look_data["filter"])

    # 2. Organic film grain
    grain_data = GRAIN_PRESETS.get(grain)
    if grain_data and grain_data.get("filter"):
        filters.append(grain_data["filter"])

    # 3. Framing / Letterboxing
    lb_data = LETTERBOX_PRESETS.get(letterbox)
    if lb_data and lb_data.get("filter"):
        filters.append(lb_data["filter"])

    return ",".join(filters)


def get_color_catalog():
    """Returns color grading options for UI consumption."""
    return {
        "looks": list(COLOR_LOOKS.values()),
        "grains": list(GRAIN_PRESETS.values()),
        "framing": list(LETTERBOX_PRESETS.values())
    }
