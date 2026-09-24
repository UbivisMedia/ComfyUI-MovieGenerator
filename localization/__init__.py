import os
import sys
import json
import locale

LOCALIZATION_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(LOCALIZATION_DIR)
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

_CURRENT_LANG = "en"
_ACTIVE_TRANSLATIONS = {}
_FALLBACK_TRANSLATIONS = {}

def _load_json_file(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def detect_system_language():
    """Erkennt den zweistelligen Sprachcode (z.B. 'de', 'en') des Betriebssystems."""
    # 1. Umgebungsvariablen prüfen (z.B. Linux/macOS/spezielle Terminals)
    for env_var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(env_var)
        if val:
            lang = val.split(".")[0].split("_")[0].lower()
            if len(lang) == 2:
                return lang

    # 2. Windows-spezifische UI-Sprache via ctypes
    if sys.platform == "win32":
        try:
            import ctypes
            # GetUserDefaultUILanguage() gibt die Windows-Anzeigesprache zurück (z.B. 0x0407 für de-DE)
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
            win_lang_map = {
                0x07: "de",  # German
                0x09: "en",  # English
                0x0C: "fr",  # French
                0x0A: "es",  # Spanish
                0x10: "it",  # Italian
                0x11: "ja",  # Japanese
                0x12: "ko",  # Korean
                0x04: "zh",  # Chinese
                0x19: "ru",  # Russian
                0x13: "nl",  # Dutch
                0x16: "pt",  # Portuguese
                0x15: "pl",  # Polish
            }
            if lang_id in win_lang_map:
                return win_lang_map[lang_id]
        except Exception:
            pass

    # 3. Standard Python locale
    try:
        loc = locale.getdefaultlocale()[0]
        if loc:
            return loc.split("_")[0].lower()
    except Exception:
        pass

    try:
        loc = locale.getlocale()[0]
        if loc:
            return loc.split("_")[0].lower()
    except Exception:
        pass

    return "en"

def init_localization():
    """Initialisiert die Lokalisierung basierend auf settings.json oder Systemsprache."""
    global _CURRENT_LANG, _ACTIVE_TRANSLATIONS, _FALLBACK_TRANSLATIONS

    # Immer englische Übersetzungen als ultimativen Fallback vorhalten
    en_file = os.path.join(LOCALIZATION_DIR, "en.json")
    _FALLBACK_TRANSLATIONS = _load_json_file(en_file)

    target_lang = "auto"
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as sf:
                settings = json.load(sf)
                target_lang = settings.get("language", "auto").strip().lower()
        except Exception:
            target_lang = "auto"

    if not target_lang or target_lang == "auto":
        target_lang = detect_system_language()

    # Prüfen, ob Sprachdatei existiert
    target_file = os.path.join(LOCALIZATION_DIR, f"{target_lang}.json")
    if os.path.exists(target_file):
        _CURRENT_LANG = target_lang
        _ACTIVE_TRANSLATIONS = _load_json_file(target_file)
    else:
        # Fallback auf Englisch
        _CURRENT_LANG = "en"
        _ACTIVE_TRANSLATIONS = _FALLBACK_TRANSLATIONS

def get_current_language():
    return _CURRENT_LANG

def set_language(lang_code):
    global _CURRENT_LANG, _ACTIVE_TRANSLATIONS
    target_file = os.path.join(LOCALIZATION_DIR, f"{lang_code.lower()}.json")
    if os.path.exists(target_file):
        _CURRENT_LANG = lang_code.lower()
        _ACTIVE_TRANSLATIONS = _load_json_file(target_file)
    else:
        _CURRENT_LANG = "en"
        _ACTIVE_TRANSLATIONS = _FALLBACK_TRANSLATIONS

def t(key, **kwargs):
    """Übersetzt einen Schlüssel in die aktive Sprache mit sicherem Fallback."""
    template = _ACTIVE_TRANSLATIONS.get(key)
    if template is None:
        template = _FALLBACK_TRANSLATIONS.get(key, key)

    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template

def get_all_editor_translations():
    """Gibt die Editor-Übersetzungen aller verfügbaren Sprachdateien zurück."""
    translations = {}
    if os.path.exists(LOCALIZATION_DIR):
        for fname in sorted(os.listdir(LOCALIZATION_DIR)):
            if fname.endswith(".json"):
                lang_code = fname[:-5]
                f_path = os.path.join(LOCALIZATION_DIR, fname)
                data = _load_json_file(f_path)
                editor_dict = data.get("editor", {})
                merged = {k: v for k, v in data.items() if k != "editor"}
                merged.update(editor_dict)
                translations[lang_code] = merged
    return translations

# Automatische Initialisierung beim Modulimport
init_localization()

