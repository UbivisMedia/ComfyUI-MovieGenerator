"""
lib/turnaround_builder.py - Multi-Angle Turnaround Sheet Composite Builder for MovieGenerator

Combines multiple perspective portrait angles (Frontal, Three-Quarter, Profile)
into a unified multi-view reference turnaround sheet for character continuity
in ComfyUI and MiniMax H3.
"""

import os
from PIL import Image, ImageOps


def build_turnaround_sheet(
    frontal_path=None,
    three_quarter_path=None,
    profile_path=None,
    output_path=None,
    target_height=1024,
    divider_width=4,
    divider_color=(25, 33, 50, 255)
):
    """
    Constructs a composite multi-view turnaround sheet from available perspective images.
    Orders them logically: [Frontal 0°] | [Three-Quarter 45°] | [Profile 90°].
    Normalizes heights, aligns baselines, and adds clean dividers.
    """
    panels = []
    
    # Check and load each perspective
    candidates = [
        ("frontal", frontal_path),
        ("three_quarter", three_quarter_path),
        ("profile", profile_path)
    ]
    
    loaded_imgs = []
    for angle_name, path in candidates:
        if path and os.path.exists(path):
            try:
                img = Image.open(path).convert("RGBA")
                loaded_imgs.append((angle_name, img))
            except Exception as e:
                print(f"⚠️ Could not load {angle_name} image '{path}': {e}")

    if not loaded_imgs:
        raise ValueError("No valid perspective images provided to build turnaround sheet.")

    # Resize all loaded images to target_height preserving aspect ratio
    resized_panels = []
    for angle_name, img in loaded_imgs:
        orig_w, orig_h = img.size
        aspect = orig_w / float(orig_h)
        new_w = max(1, int(round(target_height * aspect)))
        resized = img.resize((new_w, target_height), Image.Resampling.LANCZOS)
        resized_panels.append(resized)

    # Calculate total width including dividers
    num_panels = len(resized_panels)
    total_dividers_w = (num_panels - 1) * divider_width if num_panels > 1 else 0
    total_w = sum(p.width for p in resized_panels) + total_dividers_w

    # Create composite canvas (RGBA)
    composite = Image.new("RGBA", (total_w, target_height), (0, 0, 0, 0))

    # Paste panels and dividers
    current_x = 0
    for idx, panel in enumerate(resized_panels):
        composite.paste(panel, (current_x, 0), panel)
        current_x += panel.width
        
        # Draw divider if not last panel
        if idx < num_panels - 1 and divider_width > 0:
            divider = Image.new("RGBA", (divider_width, target_height), divider_color)
            composite.paste(divider, (current_x, 0))
            current_x += divider_width

    # Save to output_path if provided
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        composite.save(output_path, "PNG")

    return {
        "success": True,
        "output_path": output_path,
        "width": total_w,
        "height": target_height,
        "panel_count": num_panels
    }
