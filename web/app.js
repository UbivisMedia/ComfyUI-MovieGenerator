/**
 * SCRIPT AGENCY • MovieGenerator Visual Screenplay Studio
 * Client-side Reactive Application with Comprehensive Bilingual i18n
 */

(function () {
  'use strict';

  // --- State ---
  let state = {
    currentFilename: '',
    isDirty: false,
    screenplay: {
      title: 'Neues Drehbuch',
      description: '',
      variables: {},
      characters: [],
      scenes: []
    },
    presetsData: {
      default: 'anima_catpony',
      presets: {},
      lora_presets: {}
    },
    projectsList: [],
    activeTab: 'characters',
    activeLoraCharIndex: null, // Index of character currently picking a LoRA
    focusedIdeaTextarea: null, // For quick variable chip insertion
    lang: 'de' // 'de' or 'en'
  };

  // --- Localization Engine (Centralized via /api/localization from localization/de.json & en.json) ---
  let I18N = {
    de: {},
    en: {}
  };

  function t(key) {
    const dict = (I18N && I18N[state.lang]) || (I18N && I18N.de) || {};
    return dict[key] !== undefined ? dict[key] : key;
  }

  // --- DOM Elements Cache ---
  const el = {
    projectSelect: document.getElementById('projectSelect'),
    btnNewProject: document.getElementById('btnNewProject'),
    btnSave: document.getElementById('btnSave'),
    btnDuplicate: document.getElementById('btnDuplicate'),
    btnRescan: document.getElementById('btnRescan'),
    rescanIcon: document.getElementById('rescanIcon'),
    btnLaunchMovie: document.getElementById('btnLaunchMovie'),
    btnLangToggle: document.getElementById('btnLangToggle'),
    currentLangLabel: document.getElementById('currentLangLabel'),
    btnExit: document.getElementById('btnExit'),
    saveStatusPill: document.getElementById('saveStatusPill'),
    saveStatusText: document.getElementById('saveStatusText'),

    // Sidebar fields
    movieTitle: document.getElementById('movieTitle'),
    movieFilename: document.getElementById('movieFilename'),
    movieDescription: document.getElementById('movieDescription'),
    btnAddVariable: document.getElementById('btnAddVariable'),
    variableChipsList: document.getElementById('variableChipsList'),
    variablesEditorList: document.getElementById('variablesEditorList'),

    // Stats
    statCharsCount: document.getElementById('statCharsCount'),
    statScenesCount: document.getElementById('statScenesCount'),
    statTotalDuration: document.getElementById('statTotalDuration'),
    tabBadgeChars: document.getElementById('tabBadgeChars'),
    tabBadgeScenes: document.getElementById('tabBadgeScenes'),

    // Tabs
    tabButtons: document.querySelectorAll('.tab-btn'),
    tabContents: {
      characters: document.getElementById('tabContentCharacters'),
      scenes: document.getElementById('tabContentScenes'),
      json: document.getElementById('tabContentJson')
    },

    // Containers
    charactersContainer: document.getElementById('charactersContainer'),
    scenesContainer: document.getElementById('scenesContainer'),
    btnAddCharacter: document.getElementById('btnAddCharacter'),
    btnAddScene: document.getElementById('btnAddScene'),
    jsonPreview: document.getElementById('jsonPreview'),
    btnCopyJson: document.getElementById('btnCopyJson'),
    btnFormatJson: document.getElementById('btnFormatJson'),

    // LoRA Modal
    loraModal: document.getElementById('loraModal'),
    btnCloseLoraModal: document.getElementById('btnCloseLoraModal'),
    loraSearchInput: document.getElementById('loraSearchInput'),
    chkShowAllLoras: document.getElementById('chkShowAllLoras'),
    modalActiveModelName: document.getElementById('modalActiveModelName'),
    loraCardsList: document.getElementById('loraCardsList'),

    // Render Modal
    renderModal: document.getElementById('renderModal'),
    btnCloseRenderModal: document.getElementById('btnCloseRenderModal'),
    btnCloseRenderModalBtn: document.getElementById('btnCloseRenderModalBtn'),
    renderCliCommand: document.getElementById('renderCliCommand'),
    btnCopyCli: document.getElementById('btnCopyCli'),

    // Toast
    toastContainer: document.getElementById('toastContainer'),

    // LM Studio AI Elements
    llmStatusPill: document.getElementById('llmStatusPill'),
    llmStatusText: document.getElementById('llmStatusText'),
    btnAiExtractVars: document.getElementById('btnAiExtractVars'),
    btnAiSuggestScene: document.getElementById('btnAiSuggestScene'),

    // AI Suggestion Modal
    aiSuggestionModal: document.getElementById('aiSuggestionModal'),
    aiModalTitle: document.getElementById('aiModalTitle'),
    aiModalBody: document.getElementById('aiModalBody'),
    btnCloseAiModal: document.getElementById('btnCloseAiModal'),
    btnDiscardAiModal: document.getElementById('btnDiscardAiModal'),
    btnApplyAiModal: document.getElementById('btnApplyAiModal')
  };

  // --- Language Switching Engine ---
  function setLanguage(newLang) {
    state.lang = (newLang === 'en' || newLang === 'de') ? newLang : 'de';
    try {
      localStorage.setItem('script_agency_lang', state.lang);
    } catch { }

    el.currentLangLabel.textContent = state.lang.toUpperCase();
    document.documentElement.lang = state.lang;

    // 1. Translate all elements with [data-i18n]
    document.querySelectorAll('[data-i18n]').forEach(elem => {
      const key = elem.getAttribute('data-i18n');
      const text = t(key);
      if (text) elem.textContent = text;
    });

    // 2. Translate placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(elem => {
      const key = elem.getAttribute('data-i18n-placeholder');
      const text = t(key);
      if (text) elem.setAttribute('placeholder', text);
    });

    // 3. Translate tooltips / titles
    document.querySelectorAll('[data-i18n-title]').forEach(elem => {
      const key = elem.getAttribute('data-i18n-title');
      const text = t(key);
      if (text) elem.setAttribute('title', text);
    });

    // 4. Update save status pill
    if (state.isDirty) {
      el.saveStatusText.textContent = t('dirty');
    } else {
      el.saveStatusText.textContent = t('ready');
    }

    // 5. Re-render dynamic components with localized labels
    renderVariables();
    renderCharacters();
    renderScenes();
    updateStats();

    // 6. Update LLM status text
    if (el.llmStatusText) {
      if (state.llmOnline) {
        const modelLabel = state.llmModel ? (state.llmModel.length > 20 ? state.llmModel.substring(0, 18) + '...' : state.llmModel) : 'Online';
        el.llmStatusText.textContent = t('llmStatusOnline').replace('{model}', modelLabel);
      } else {
        el.llmStatusText.textContent = t('llmStatusOffline');
      }
    }
  }

  // --- API Client ---
  const API = {
    async getLocalization() {
      const res = await fetch('/api/localization');
      if (!res.ok) throw new Error('Fehler beim Laden der Lokalisierungsdaten');
      return await res.json();
    },

    async getPresets() {
      const res = await fetch('/api/presets');
      if (!res.ok) throw new Error('Fehler beim Laden der Presets');
      return await res.json();
    },

    async getProjects() {
      const res = await fetch('/api/projects');
      if (!res.ok) throw new Error('Fehler beim Laden der Projektliste');
      return await res.json();
    },

    async getProject(filename) {
      const res = await fetch(`/api/project?file=${encodeURIComponent(filename)}`);
      if (!res.ok) throw new Error(`Fehler beim Laden von ${filename}`);
      return await res.json();
    },

    async saveProject(filename, screenplay) {
      const res = await fetch('/api/project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, data: screenplay })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || 'Speichern fehlgeschlagen');
      }
      return await res.json();
    },

    async rescanCatalog() {
      const res = await fetch('/api/rescan_catalog', { method: 'POST' });
      if (!res.ok) throw new Error('Katalog-Scan fehlgeschlagen');
      return await res.json();
    },

    async shutdownServer() {
      await fetch('/api/shutdown', { method: 'POST' }).catch(() => { });
    },

    async getLlmStatus() {
      const res = await fetch('/api/llm/status');
      if (!res.ok) throw new Error('Fehler beim Abrufen des LLM-Status');
      return await res.json();
    },

    async generateLlm(task, payload) {
      const res = await fetch('/api/llm/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, ...payload })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Fehler bei der KI-Generierung');
      }
      return data;
    }
  };

  // --- Helpers ---
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
    toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
    el.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 250);
    }, 3500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function sanitizeFilename(name) {
    return name
      .toLowerCase()
      .replace(/[^a-z0-9_\-]/g, '_')
      .replace(/_+/g, '_')
      .replace(/^_+|_+$/g, '');
  }

  function markDirty() {
    state.isDirty = true;
    el.saveStatusPill.classList.remove('saving');
    el.saveStatusPill.classList.add('dirty');
    el.saveStatusText.textContent = t('dirty');
    updateStats();
    renderJsonPreview();
  }

  function markClean() {
    state.isDirty = false;
    el.saveStatusPill.classList.remove('dirty', 'saving');
    el.saveStatusText.textContent = t('ready');
  }

  function markSaving() {
    el.saveStatusPill.classList.add('saving');
    el.saveStatusText.textContent = t('saving');
  }

  // --- Stats Calculation ---
  function updateStats() {
    const chars = state.screenplay.characters || [];
    const scenes = state.screenplay.scenes || [];
    const charsCount = chars.length;
    const scenesCount = scenes.length;

    let totalSecs = 0;
    for (const s of scenes) {
      const d = parseInt(s.duration || s.dauer_sekunden || s.dauer || 5, 10);
      totalSecs += isNaN(d) ? 5 : d;
    }

    el.statCharsCount.textContent = charsCount;
    el.statScenesCount.textContent = scenesCount;
    el.statTotalDuration.textContent = `${totalSecs}s`;

    el.tabBadgeChars.textContent = charsCount;
    el.tabBadgeScenes.textContent = scenesCount;
  }

  // --- Initial Data Load ---
  async function initApp() {
    try {
      // 1. Load Centralized Localization from backend (localization/de.json & en.json)
      let initialLang = 'en';
      try {
        const locData = await API.getLocalization();
        if (locData && locData.translations) {
          I18N = locData.translations;
        }
        if (locData && locData.active_lang) {
          initialLang = locData.active_lang;
        }
      } catch (e) {
        console.warn('Backend localization load warning:', e);
      }

      // Check saved user choice from localStorage, fallback to backend active_lang
      let savedLang = null;
      try {
        savedLang = localStorage.getItem('script_agency_lang');
      } catch { }
      state.lang = (savedLang === 'en' || savedLang === 'de') ? savedLang : initialLang;

      // 2. Load Presets (Models & LoRAs)
      state.presetsData = await API.getPresets();

      // 3. Load Projects list
      await refreshProjectsList();

      // 3. Auto-load first project or create default template
      if (state.projectsList.length > 0) {
        const fav = state.projectsList.find(p => p.file === 'three_scenes_example.json') || state.projectsList[0];
        await loadProject(fav.file);
      } else {
        createNewProject();
      }

      setupEventListeners();
      setLanguage(state.lang);
      refreshLlmStatus();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function refreshProjectsList() {
    state.projectsList = await API.getProjects();
    el.projectSelect.innerHTML = '';

    if (state.projectsList.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = t('noProjectsFound');
      el.projectSelect.appendChild(opt);
      return;
    }

    for (const proj of state.projectsList) {
      const opt = document.createElement('option');
      opt.value = proj.file;
      const title = proj.title ? ` - "${proj.title}"` : '';
      opt.textContent = `${proj.file}${title} (${proj.scenes_count || 0} ${t('statScenes')})`;
      if (proj.file === state.currentFilename) {
        opt.selected = true;
      }
      el.projectSelect.appendChild(opt);
    }
  }

  // --- Load / New / Save Project ---
  async function loadProject(filename) {
    try {
      markSaving();
      const proj = await API.getProject(filename);
      state.currentFilename = filename;
      state.screenplay = proj.data;

      // Ensure expected fields exist
      if (!state.screenplay.variables) state.screenplay.variables = {};
      if (!state.screenplay.characters) state.screenplay.characters = [];
      if (!state.screenplay.scenes) state.screenplay.scenes = [];

      // Update UI form fields
      el.movieTitle.value = state.screenplay.title || filename.replace('.json', '');
      el.movieFilename.value = filename.replace('.json', '');
      el.movieDescription.value = state.screenplay.description || '';

      // Set select dropdown
      el.projectSelect.value = filename;

      // Render sections
      renderVariables();
      renderCharacters();
      renderScenes();
      updateStats();
      renderJsonPreview();
      markClean();
      showToast(t('screenplayLoaded').replace('{name}', filename), 'info');
    } catch (err) {
      showToast(err.message, 'error');
      markClean();
    }
  }

  function createNewProject() {
    if (state.isDirty && !confirm(t('confirmNewProject'))) {
      return;
    }

    const defaultModel = state.presetsData.default || 'anima_catpony';
    state.currentFilename = 'mein_neuer_film.json';
    state.screenplay = {
      title: state.lang === 'en' ? 'My New Movie' : 'Mein neuer Film',
      description: state.lang === 'en' ? 'A concise storyline description.' : 'Eine kurze Zusammenfassung der Handlung.',
      variables: {
        outfit_hero: state.lang === 'en' ? 'dark leather jacket and jeans' : 'dunkle Lederjacke und Jeans',
        location_alley: state.lang === 'en' ? 'a rain-slicked neon illuminated alley' : 'eine belebte neonbeleuchtete Gasse'
      },
      characters: [
        {
          id: 1,
          name: 'Hero',
          model: defaultModel,
          loras: [],
          description: state.lang === 'en' ? 'A brave protagonist with a determined expression.' : 'Ein mutiger Protagonist mit entschlossenem Blick.'
        }
      ],
      scenes: [
        {
          id: 1,
          sequence: state.lang === 'en' ? 'Prologue' : 'Auftakt',
          location: state.lang === 'en' ? 'Neon Alley' : 'Neon-Gasse',
          duration: 6,
          characters: ['Hero'],
          idea: state.lang === 'en'
            ? 'Hero (<Picture 1>) steps cautiously out of the shadows into {location_alley}, his {outfit_hero} reflecting wet puddles.'
            : 'Hero (<Picture 1>) tritt langsam aus dem Schatten in {location_alley}, seine {outfit_hero} reflektiert das nasse Pflaster.'
        }
      ]
    };

    el.movieTitle.value = state.screenplay.title;
    el.movieFilename.value = 'mein_neuer_film';
    el.movieDescription.value = state.screenplay.description;

    renderVariables();
    renderCharacters();
    renderScenes();
    updateStats();
    renderJsonPreview();
    markDirty();
    showToast(t('newProjectTitle'), 'info');
  }

  async function saveCurrentProject() {
    try {
      const rawBase = el.movieFilename.value.trim() || 'drehbuch';
      const cleanBase = sanitizeFilename(rawBase);
      const filename = cleanBase.endsWith('.json') ? cleanBase : `${cleanBase}.json`;

      // Synchronize metadata from inputs
      state.screenplay.title = el.movieTitle.value.trim();
      state.screenplay.description = el.movieDescription.value.trim();

      markSaving();
      await API.saveProject(filename, state.screenplay);
      state.currentFilename = filename;
      el.movieFilename.value = cleanBase;

      await refreshProjectsList();
      el.projectSelect.value = filename;
      markClean();
      showToast(`${t('saved')} (${filename})`, 'success');
    } catch (err) {
      showToast(err.message, 'error');
      markDirty();
    }
  }

  // --- Variables UI ---
  function renderVariables() {
    const vars = state.screenplay.variables || {};
    el.variableChipsList.innerHTML = '';
    el.variablesEditorList.innerHTML = '';

    const keys = Object.keys(vars);
    if (keys.length === 0) {
      el.variableChipsList.innerHTML = `<span style="font-size:11px;color:var(--text-dim);font-style:italic;">${escapeHtml(t('noVariables'))}</span>`;
    }

    for (const k of keys) {
      // 1. Quick-insert chip
      const chip = document.createElement('span');
      chip.className = 'var-chip';
      chip.textContent = `{${k}}`;
      chip.title = t('chipInsertTitle').replace('{name}', `{${k}}`);
      chip.addEventListener('click', () => insertVariableIntoFocusedIdea(k));
      el.variableChipsList.appendChild(chip);

      // 2. Variable editor row
      const row = document.createElement('div');
      row.className = 'var-row';
      row.innerHTML = `
        <input type="text" class="form-control var-key" value="${escapeHtml(k)}" placeholder="${escapeHtml(t('keyPlaceholder'))}">
        <input type="text" class="form-control var-val" value="${escapeHtml(vars[k])}" placeholder="${escapeHtml(t('valPlaceholder'))}">
        <button class="btn-remove-var" title="${escapeHtml(t('removeVarTitle'))}">✕</button>
      `;

      const keyInput = row.querySelector('.var-key');
      const valInput = row.querySelector('.var-val');
      const removeBtn = row.querySelector('.btn-remove-var');

      keyInput.addEventListener('change', () => {
        const newKey = sanitizeFilename(keyInput.value.trim());
        if (newKey && newKey !== k) {
          const val = state.screenplay.variables[k];
          delete state.screenplay.variables[k];
          state.screenplay.variables[newKey] = val;
          renderVariables();
          markDirty();
        }
      });

      valInput.addEventListener('input', () => {
        state.screenplay.variables[k] = valInput.value;
        markDirty();
      });

      removeBtn.addEventListener('click', () => {
        delete state.screenplay.variables[k];
        renderVariables();
        markDirty();
      });

      el.variablesEditorList.appendChild(row);
    }
  }

  function addVariable() {
    let base = state.lang === 'en' ? 'new_variable' : 'neue_variable';
    let idx = 1;
    let cand = base;
    while (state.screenplay.variables[cand]) {
      cand = `${base}_${idx++}`;
    }
    state.screenplay.variables[cand] = state.lang === 'en' ? 'Value or description' : 'Beschreibung oder Inhalt';
    renderVariables();
    markDirty();
  }

  function insertVariableIntoFocusedIdea(varKey) {
    const textarea = state.focusedIdeaTextarea || document.querySelector('.scene-idea-textarea');
    if (!textarea) return;

    const token = `{${varKey}}`;
    const start = textarea.selectionStart || 0;
    const end = textarea.selectionEnd || 0;
    const val = textarea.value;
    textarea.value = val.substring(0, start) + token + val.substring(end);
    textarea.selectionStart = textarea.selectionEnd = start + token.length;
    textarea.focus();

    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    showToast(t('tokenInserted').replace('{name}', `{${varKey}}`), 'info');
  }

  // --- Characters UI ---
  function renderCharacters() {
    el.charactersContainer.innerHTML = '';
    const chars = state.screenplay.characters || [];

    if (chars.length === 0) {
      el.charactersContainer.innerHTML = `
        <div style="grid-column: 1/-1; text-align:center; padding: 40px; color: var(--text-muted);">
          <p style="font-size: 16px; margin-bottom: 12px;">${escapeHtml(t('noCharsYet'))}</p>
          <button class="btn btn-primary" onclick="document.getElementById('btnAddCharacter').click()">
            ${escapeHtml(t('createFirstChar'))}
          </button>
        </div>
      `;
      return;
    }

    chars.forEach((char, idx) => {
      const card = createCharacterCard(char, idx, chars);
      el.charactersContainer.appendChild(card);
    });
  }

  function createCharacterCard(char, idx, allChars) {
    const card = document.createElement('div');
    card.className = 'character-card';
    card.dataset.charIndex = idx;

    const charId = char.id || (idx + 1);
    const charName = char.name || `actor_${charId}`;
    const selectedModel = char.model || char.modell || char.preset || state.presetsData.default || 'anima_catpony';
    const presets = state.presetsData.presets || {};
    const currentModelInfo = presets[selectedModel] || {};
    const modelDesc = currentModelInfo.beschreibung || t('charModelDefaultDesc');

    // LoRAs assigned to this character
    const charLoras = Array.isArray(char.loras) ? char.loras : (typeof char.loras === 'string' ? char.loras.split(',').map(s => s.trim()).filter(Boolean) : []);

    // Reference options (for I2I / aging / style transfer)
    const otherChars = allChars.filter(c => (c.id || 0) !== charId && c.name !== charName);
    let refOptionsHtml = `<option value="">${escapeHtml(t('noRefOption'))}</option>`;
    for (const oc of otherChars) {
      const ocId = oc.id || '';
      const isSelected = String(char.reference_id) === String(ocId) || char.reference_character === oc.name;
      refOptionsHtml += `<option value="${ocId}" ${isSelected ? 'selected' : ''}>#${ocId} ${escapeHtml(oc.name)}</option>`;
    }

    // Model options list
    let modelOptionsHtml = '';
    for (const [mKey, mVal] of Object.entries(presets)) {
      const isSel = mKey === selectedModel ? 'selected' : '';
      const label = mVal.beschreibung ? `${mKey} — ${mVal.beschreibung.substring(0, 45)}...` : mKey;
      modelOptionsHtml += `<option value="${mKey}" ${isSel}>${escapeHtml(label)}</option>`;
    }

    // LoRA Badges HTML
    let lorasHtml = '';
    for (const loraKey of charLoras) {
      const loraData = state.presetsData.lora_presets && state.presetsData.lora_presets[loraKey];
      const desc = loraData ? loraData.beschreibung : '';
      const strength = loraData && loraData.strength_model ? ` [${loraData.strength_model}]` : '';
      lorasHtml += `
        <div class="lora-pill" title="${escapeHtml(desc)}">
          <span>✨ ${escapeHtml(loraKey)}${strength}</span>
          <span class="btn-remove-lora" data-lora="${escapeHtml(loraKey)}" title="${escapeHtml(t('removeVarTitle'))}">✕</span>
        </div>
      `;
    }

    if (charLoras.length === 0) {
      lorasHtml = `<span style="font-size:11px;color:var(--text-dim);font-style:italic;">${escapeHtml(t('noLorasAssigned'))}</span>`;
    }

    card.innerHTML = `
      <div class="char-header">
        <span class="char-id-badge">#${charId}</span>
        <div class="char-title-inputs">
          <input type="text" class="char-name-input" value="${escapeHtml(charName)}" placeholder="${escapeHtml(t('charNamePlaceholder'))}">
        </div>
        <div class="char-actions">
          <button class="btn btn-ghost btn-xs btn-duplicate-char" title="${escapeHtml(t('duplicateCharTitle'))}">📋</button>
          <button class="btn btn-danger-ghost btn-xs btn-delete-char" title="${escapeHtml(t('deleteCharTitle'))}">🗑️</button>
        </div>
      </div>

      <!-- Basis Modell Auswahl -->
      <div class="char-model-group">
        <label for="charModel_${idx}">${escapeHtml(t('charModelLabel'))}</label>
        <select id="charModel_${idx}" class="form-control char-model-select">
          ${modelOptionsHtml}
        </select>
        <div class="char-model-desc">${escapeHtml(modelDesc)}</div>
      </div>

      <!-- LoRA Auswahl Sektion -->
      <div class="char-loras-section">
        <div class="char-loras-header">
          <label>${escapeHtml(t('charLorasLabel'))}</label>
          <button class="btn btn-accent btn-xs btn-pick-lora" title="${escapeHtml(t('btnPickLora'))}">
            ${escapeHtml(t('btnPickLora'))}
          </button>
        </div>
        <div class="char-loras-list">
          ${lorasHtml}
        </div>
      </div>

      <!-- Referenz Charakter (I2I) -->
      <div class="char-reference-grid">
        <div class="form-group">
          <label>${escapeHtml(t('charRefLabel'))}</label>
          <select class="form-control char-ref-select">
            ${refOptionsHtml}
          </select>
        </div>
        <div class="form-group">
          <label>Denoise (<span class="denoise-val">${char.denoise !== undefined ? char.denoise : 0.65}</span>)</label>
          <input type="range" class="char-denoise-range" min="0.1" max="1.0" step="0.05" value="${char.denoise !== undefined ? char.denoise : 0.65}">
        </div>
      </div>

      <!-- Beschreibung -->
      <div class="form-group">
        <label>${escapeHtml(t('charDescLabel'))}</label>
        <textarea class="form-control char-desc-input" rows="2" placeholder="${escapeHtml(t('charDescPlaceholder'))}">${escapeHtml(char.description || '')}</textarea>
      </div>

      <!-- LM Studio AI Prompt Toggle & Override -->
      <div class="char-prompt-group">
        <label class="char-prompt-toggle">
          <input type="checkbox" class="char-autoprompt-chk" ${char.ki_prompt_generieren !== false && char.auto_prompt !== false ? 'checked' : ''}>
          <span>${escapeHtml(t('charAutoPrompt'))}</span>
        </label>
        <div class="char-prompt-box" style="${char.ki_prompt_generieren === false || char.auto_prompt === false ? 'display:block;' : 'display:none;'} margin-top: 6px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <span style="font-size:11px;color:var(--text-muted);">${escapeHtml(t('charFixedPromptPlaceholder'))}</span>
            <button class="btn btn-ai-magic btn-xs btn-ai-optimize-prompt" title="${escapeHtml(t('btnAiOptimizePromptTitle'))}">
              <span class="ai-sparkle">🪄</span> <span>${escapeHtml(t('btnAiOptimizePrompt'))}</span>
            </button>
          </div>
          <textarea class="form-control char-prompt-input" rows="2" placeholder="${escapeHtml(t('charFixedPromptPlaceholder'))}">${escapeHtml(char.prompt || '')}</textarea>
        </div>
      </div>
    `;

    // Hook listeners
    const nameInput = card.querySelector('.char-name-input');
    nameInput.addEventListener('input', () => {
      char.name = nameInput.value.trim();
      markDirty();
    });

    const modelSelect = card.querySelector('.char-model-select');
    const modelDescDiv = card.querySelector('.char-model-desc');
    modelSelect.addEventListener('change', () => {
      char.model = modelSelect.value;
      const mInfo = presets[char.model] || {};
      modelDescDiv.textContent = mInfo.beschreibung || t('charModelDefaultDesc');
      markDirty();
    });

    // Pick LoRA Button
    const pickLoraBtn = card.querySelector('.btn-pick-lora');
    pickLoraBtn.addEventListener('click', () => {
      openLoraPickerModal(idx, char.model || selectedModel);
    });

    // Remove LoRA Pills
    card.querySelectorAll('.btn-remove-lora').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const loraToRemove = e.target.dataset.lora;
        char.loras = (char.loras || []).filter(l => l !== loraToRemove);
        renderCharacters();
        markDirty();
      });
    });

    // Reference Select & Denoise
    const refSelect = card.querySelector('.char-ref-select');
    const denoiseRange = card.querySelector('.char-denoise-range');
    const denoiseValSpan = card.querySelector('.denoise-val');

    refSelect.addEventListener('change', () => {
      const val = refSelect.value;
      if (val) {
        char.reference_id = parseInt(val, 10) || val;
        char.denoise = parseFloat(denoiseRange.value) || 0.65;
      } else {
        delete char.reference_id;
        delete char.denoise;
      }
      markDirty();
    });

    denoiseRange.addEventListener('input', () => {
      denoiseValSpan.textContent = denoiseRange.value;
      if (char.reference_id) {
        char.denoise = parseFloat(denoiseRange.value);
        markDirty();
      }
    });

    // Description & Prompt
    const descInput = card.querySelector('.char-desc-input');
    descInput.addEventListener('input', () => {
      char.description = descInput.value;
      markDirty();
    });

    const autoPromptChk = card.querySelector('.char-autoprompt-chk');
    const promptBox = card.querySelector('.char-prompt-box');
    const promptInput = card.querySelector('.char-prompt-input');

    autoPromptChk.addEventListener('change', () => {
      char.auto_prompt = autoPromptChk.checked;
      char.ki_prompt_generieren = autoPromptChk.checked;
      promptBox.style.display = autoPromptChk.checked ? 'none' : 'block';
      markDirty();
    });

    promptInput.addEventListener('input', () => {
      char.prompt = promptInput.value;
      markDirty();
    });

    // AI Optimize Character Prompt Button
    const optimizePromptBtn = card.querySelector('.btn-ai-optimize-prompt');
    if (optimizePromptBtn) {
      optimizePromptBtn.addEventListener('click', async () => {
        try {
          optimizePromptBtn.disabled = true;
          optimizePromptBtn.innerHTML = `<span class="ai-loading-spinner"></span> <span>${escapeHtml(t('aiThinking'))}</span>`;
          const res = await API.generateLlm('optimize_character_prompt', {
            character: char,
            preset: char.model || selectedModel,
            title: state.screenplay.title,
            description: state.screenplay.description
          });
          if (res && res.prompt) {
            char.prompt = res.prompt;
            char.auto_prompt = false;
            char.ki_prompt_generieren = false;
            renderCharacters();
            markDirty();
            showToast(t('aiPromptOptimized').replace('{name}', charName), 'success');
          }
        } catch (err) {
          showToast(err.message, 'error');
        } finally {
          optimizePromptBtn.disabled = false;
        }
      });
    }

    // Duplicate & Delete
    card.querySelector('.btn-duplicate-char').addEventListener('click', () => {
      duplicateCharacter(idx);
    });

    card.querySelector('.btn-delete-char').addEventListener('click', () => {
      if (confirm(`${t('confirmDeleteChar')} (${charName})`)) {
        state.screenplay.characters.splice(idx, 1);
        renderCharacters();
        renderScenes();
        markDirty();
      }
    });

    return card;
  }

  function addCharacter() {
    const chars = state.screenplay.characters || [];
    let maxId = 0;
    for (const c of chars) {
      if (c.id && typeof c.id === 'number' && c.id > maxId) maxId = c.id;
    }
    const newId = maxId + 1;
    const defaultModel = state.presetsData.default || 'anima_catpony';

    const newChar = {
      id: newId,
      name: state.lang === 'en' ? `Character_${newId}` : `Charakter_${newId}`,
      model: defaultModel,
      loras: [],
      description: state.lang === 'en' ? 'Character visual description here' : 'Charakterbeschreibung hier eingeben'
    };

    chars.push(newChar);
    renderCharacters();
    markDirty();
    showToast(`${t('btnAddCharacter')} #${newId}`, 'info');
  }

  function duplicateCharacter(idx) {
    const chars = state.screenplay.characters || [];
    const source = chars[idx];
    if (!source) return;

    let maxId = 0;
    for (const c of chars) {
      if (c.id && typeof c.id === 'number' && c.id > maxId) maxId = c.id;
    }

    const clone = JSON.parse(JSON.stringify(source));
    clone.id = maxId + 1;
    clone.name = `${source.name}_${t('copySuffix')}`;
    chars.push(clone);

    renderCharacters();
    markDirty();
    showToast(t('charDuplicated').replace('{id}', clone.id), 'info');
  }

  // --- LoRA Picker Modal ---
  function openLoraPickerModal(charIndex, activeModelKey) {
    state.activeLoraTarget = {
      type: 'character',
      index: charIndex,
      model: activeModelKey
    };
    const char = state.screenplay.characters[charIndex];
    const charName = char ? (char.name || `#${charIndex + 1}`) : '';
    const modalTitleElem = el.loraModal.querySelector('.modal-title');
    if (modalTitleElem) {
      modalTitleElem.textContent = t('modalLoraTitle') + (charName ? ` (${charName})` : '');
    }
    el.modalActiveModelName.textContent = activeModelKey;
    el.loraSearchInput.value = '';
    el.chkShowAllLoras.checked = false;
    renderLoraModalCards();
    el.loraModal.classList.add('open');
  }

  function openLoraPickerModalForScene(sceneIndex) {
    const scene = state.screenplay.scenes[sceneIndex];
    const sceneId = scene ? (scene.id || sceneIndex + 1) : sceneIndex + 1;
    state.activeLoraTarget = {
      type: 'scene',
      index: sceneIndex,
      model: 'minimax_h3'
    };
    const modalTitleElem = el.loraModal.querySelector('.modal-title');
    if (modalTitleElem) {
      modalTitleElem.textContent = t('modalSceneLoraTitle').replace('{id}', sceneId);
    }
    el.modalActiveModelName.textContent = 'Minimax H3 (Video I2V)';
    el.loraSearchInput.value = '';
    el.chkShowAllLoras.checked = false;
    renderLoraModalCards();
    el.loraModal.classList.add('open');
  }

  function closeLoraPickerModal() {
    el.loraModal.classList.remove('open');
    state.activeLoraTarget = null;
  }

  function renderLoraModalCards() {
    if (!state.activeLoraTarget) return;
    const target = state.activeLoraTarget;
    el.loraCardsList.innerHTML = '';
    const loraPresets = state.presetsData.lora_presets || {};
    const query = el.loraSearchInput.value.toLowerCase().trim();
    const showAll = el.chkShowAllLoras.checked;

    let currentAssignedLoras = [];
    if (target.type === 'character') {
      const char = state.screenplay.characters[target.index];
      currentAssignedLoras = char && Array.isArray(char.loras) ? char.loras : [];
    } else if (target.type === 'scene') {
      const scene = state.screenplay.scenes[target.index];
      const raw = scene ? (scene.loras || scene.lora || []) : [];
      if (Array.isArray(raw)) {
        currentAssignedLoras = raw.map(l => (typeof l === 'string' ? l : (l.key || l.name || l.lora || ''))).filter(Boolean);
      } else if (typeof raw === 'string' && raw) {
        currentAssignedLoras = raw.split(',').map(s => s.trim()).filter(Boolean);
      }
    }

    const keys = Object.keys(loraPresets);
    if (keys.length === 0) {
      el.loraCardsList.innerHTML = `<div style="color:var(--text-dim);font-style:italic;">${escapeHtml(t('noLorasCatalog'))}</div>`;
      return;
    }

    // Exclude turbo base model checkpoints from scene LoRAs unless showAll is checked
    const turboExcludes = [
      'mmh3_fl2v_lightx2v_turbo',
      'mmh3_turbo_ckpt850',
      'mmh3_turbo_4step',
      'mmh3_minimax_h3_fl2v_turbo_4step_768p_comfyui',
      'mmh3_minimax_h3_fl2v_turbo_4step_768p_comfyui_2',
      'mmh3_minimax_h3_ref2v_turbo_8step_768p_comfyui',
      'mmh3_minimax_h3_taomate_fl2va_3step_ema_comfyui'
    ];

    let countShown = 0;

    for (const lKey of keys) {
      const lora = loraPresets[lKey];
      const compatList = Array.isArray(lora.kompatible_modelle) ? lora.kompatible_modelle : [];
      const lNameLower = (lora.lora_name || '').toLowerCase();
      const lKeyLower = lKey.toLowerCase();

      let isCompat = false;
      if (target.type === 'character') {
        isCompat = compatList.length === 0 || compatList.includes(target.model);
      } else if (target.type === 'scene') {
        if (turboExcludes.includes(lKeyLower) && !showAll) {
          continue;
        }
        isCompat = compatList.includes('minimax_h3') ||
          compatList.includes('minimax_h3_video') ||
          lNameLower.includes('minimax') ||
          lKeyLower.includes('mmh3') ||
          lNameLower.includes('video') ||
          lKeyLower.includes('video');
      }

      if (!isCompat && !showAll) {
        continue;
      }

      const searchHaystack = `${lKey} ${lora.beschreibung || ''} ${lora.trigger_words || ''} ${compatList.join(' ')}`.toLowerCase();
      if (query && !searchHaystack.includes(query)) {
        continue;
      }

      countShown++;
      const isAlreadyAssigned = currentAssignedLoras.includes(lKey);
      const card = document.createElement('div');
      card.className = `lora-card-item ${isCompat ? 'compatible' : ''} ${isAlreadyAssigned ? 'selected' : ''}`;

      const strengthModel = lora.strength_model !== undefined ? lora.strength_model : (target.type === 'scene' ? 1.0 : 0.8);
      const triggers = lora.trigger_words ? `<div style="font-size:10px;color:var(--accent-cyan);margin-top:2px;">Triggers: <code>${escapeHtml(lora.trigger_words)}</code></div>` : '';

      const compatBadgeText = target.type === 'scene'
        ? (isCompat ? escapeHtml(t('videoCompatBadge')) : escapeHtml(t('otherModelBadge')))
        : (isCompat ? escapeHtml(t('compatBadge')) : escapeHtml(t('otherModelBadge')));

      card.innerHTML = `
        <div class="lora-card-title">
          <span>${target.type === 'scene' ? '🎬' : '✨'} ${escapeHtml(lKey)}</span>
          <span style="font-size:11px;">${isAlreadyAssigned ? escapeHtml(t('activeBadge')) : '➕'}</span>
        </div>
        <div class="lora-card-desc">${escapeHtml(lora.beschreibung || '')}</div>
        ${triggers}
        <div class="lora-card-footer">
          <span class="${isCompat ? 'lora-badge-compat' : ''}">
            ${compatBadgeText}
          </span>
          <span>${escapeHtml(t('strengthLabel'))}: ${strengthModel}</span>
        </div>
      `;

      card.addEventListener('click', () => {
        if (target.type === 'character') {
          const char = state.screenplay.characters[target.index];
          if (!char) return;
          if (!Array.isArray(char.loras)) char.loras = [];
          if (char.loras.includes(lKey)) {
            char.loras = char.loras.filter(x => x !== lKey);
          } else {
            char.loras.push(lKey);
          }
          renderCharacters();
        } else if (target.type === 'scene') {
          const scene = state.screenplay.scenes[target.index];
          if (!scene) return;
          let currentList = [];
          if (Array.isArray(scene.loras)) {
            currentList = scene.loras.map(l => (typeof l === 'string' ? l : (l.key || l.name || l.lora || ''))).filter(Boolean);
          } else if (typeof scene.loras === 'string' && scene.loras) {
            currentList = scene.loras.split(',').map(s => s.trim()).filter(Boolean);
          }
          if (currentList.includes(lKey)) {
            currentList = currentList.filter(x => x !== lKey);
          } else {
            currentList.push(lKey);
          }
          if (currentList.length > 0) {
            scene.loras = currentList;
          } else {
            delete scene.loras;
            delete scene.lora;
          }
          renderScenes();
        }
        renderLoraModalCards();
        markDirty();
      });

      el.loraCardsList.appendChild(card);
    }

    if (countShown === 0) {
      el.loraCardsList.innerHTML = `<div style="color:var(--text-dim);font-style:italic;">${escapeHtml(t('noLorasFound'))}</div>`;
    }
  }

  // --- Scenes UI ---
  function renderScenes() {
    el.scenesContainer.innerHTML = '';
    const scenes = state.screenplay.scenes || [];

    if (scenes.length === 0) {
      el.scenesContainer.innerHTML = `
        <div style="text-align:center; padding: 40px; color: var(--text-muted);">
          <p style="font-size: 16px; margin-bottom: 12px;">${escapeHtml(t('noScenesYet'))}</p>
          <button class="btn btn-primary" onclick="document.getElementById('btnAddScene').click()">
            ${escapeHtml(t('createFirstScene'))}
          </button>
        </div>
      `;
      return;
    }

    scenes.forEach((scene, idx) => {
      const card = createSceneCard(scene, idx, scenes);
      el.scenesContainer.appendChild(card);
    });
  }

  function createSceneCard(scene, idx, allScenes) {
    const card = document.createElement('div');
    card.className = 'scene-card';
    card.dataset.sceneIndex = idx;

    const sceneId = scene.id || (idx + 1);
    const duration = parseInt(scene.duration || scene.dauer_sekunden || scene.dauer || 6, 10);
    const sequence = scene.sequence || scene.sequenz || '';
    const location = scene.location || scene.ort || '';
    const idea = scene.idea || scene.idee || scene.prompt || '';

    // Continuity flags
    const isMatchCut = Boolean(scene.match_cut || scene.direkter_anschluss);
    const isSameScene = Boolean(scene.same_scene || scene.gleiche_szene);
    const isRefPrev = Boolean(scene.use_previous_scene || scene.nutze_vorherige_szene || scene.anschluss_an_vorherige_szene);

    // Characters in scene
    const charsList = state.screenplay.characters || [];
    const activeCharsInScene = Array.isArray(scene.characters) ? scene.characters : (scene.character ? [scene.character] : []);

    let castChipsHtml = '';
    for (const c of charsList) {
      const cName = c.name || `actor_${c.id}`;
      const isSelected = activeCharsInScene.includes(cName) || activeCharsInScene.includes(c.id);
      castChipsHtml += `
        <span class="cast-chip ${isSelected ? 'selected' : ''}" data-char-name="${escapeHtml(cName)}">
          ${isSelected ? '✔' : '+'} ${escapeHtml(cName)}
        </span>
      `;
    }

    // Quick Variable chips for Idea Insertion
    const vars = state.screenplay.variables || {};
    let varChipsHtml = '';
    for (const k of Object.keys(vars)) {
      varChipsHtml += `<span class="idea-chip-insert" data-var-key="${escapeHtml(k)}">{${escapeHtml(k)}}</span>`;
    }

    // Video LoRAs assigned to this scene
    let sceneLoras = [];
    const rawSceneLoras = scene.loras || scene.lora || [];
    if (Array.isArray(rawSceneLoras)) {
      sceneLoras = rawSceneLoras.map(l => (typeof l === 'string' ? l : (l.key || l.name || l.lora || ''))).filter(Boolean);
    } else if (typeof rawSceneLoras === 'string' && rawSceneLoras) {
      sceneLoras = rawSceneLoras.split(',').map(s => s.trim()).filter(Boolean);
    }

    let sceneLorasHtml = '';
    for (const lKey of sceneLoras) {
      const loraData = state.presetsData.lora_presets && state.presetsData.lora_presets[lKey];
      const desc = loraData ? loraData.beschreibung : '';
      const strength = loraData && loraData.strength_model ? ` [${loraData.strength_model}]` : '';
      sceneLorasHtml += `
        <div class="lora-pill lora-pill-video" title="${escapeHtml(desc)}">
          <span>🎬 ${escapeHtml(lKey)}${strength}</span>
          <span class="btn-remove-scene-lora" data-lora="${escapeHtml(lKey)}" title="${escapeHtml(t('removeVarTitle'))}">✕</span>
        </div>
      `;
    }

    if (sceneLoras.length === 0) {
      sceneLorasHtml = `<span style="font-size:11px;color:var(--text-dim);font-style:italic;">${escapeHtml(t('noSceneLorasAssigned'))}</span>`;
    }

    card.innerHTML = `
      <div class="scene-header">
        <div class="scene-header-left">
          <span class="scene-id-badge">#${sceneId}</span>
          <div class="scene-header-inputs">
            <input type="text" class="scene-seq-input" value="${escapeHtml(sequence)}" placeholder="${escapeHtml(t('sceneSeqPlaceholder'))}">
            <input type="text" class="scene-loc-input" value="${escapeHtml(location)}" placeholder="${escapeHtml(t('sceneLocPlaceholder'))}">
          </div>
        </div>
        <div class="scene-header-right">
          <div class="scene-duration-wrapper" title="${escapeHtml(t('durationTitle'))}">
            <span>⏱️</span>
            <input type="number" class="scene-duration-input" min="3" max="15" value="${duration}">
            <span>${escapeHtml(t('secondsUnit'))}</span>
          </div>
          <button class="btn btn-ghost btn-xs btn-move-up" title="${escapeHtml(t('moveUp'))}" ${idx === 0 ? 'disabled' : ''}>▲</button>
          <button class="btn btn-ghost btn-xs btn-move-down" title="${escapeHtml(t('moveDown'))}" ${idx === allScenes.length - 1 ? 'disabled' : ''}>▼</button>
          <button class="btn btn-ghost btn-xs btn-dup-scene" title="${escapeHtml(t('duplicateSceneTitle'))}">📋</button>
          <button class="btn btn-danger-ghost btn-xs btn-del-scene" title="${escapeHtml(t('deleteSceneTitle'))}">🗑️</button>
        </div>
      </div>

      <!-- Kontinuität / Anschlüsse -->
      <div class="continuity-toggles-bar">
        <span class="toggle-pill ${isMatchCut ? 'active pill-cyan' : ''}" data-flag="match_cut" title="${escapeHtml(t('flagMatchCutTitle'))}">
          ${escapeHtml(t('flagMatchCut'))}
        </span>
        <span class="toggle-pill ${isSameScene ? 'active' : ''}" data-flag="same_scene" title="${escapeHtml(t('flagSameSceneTitle'))}">
          ${escapeHtml(t('flagSameScene'))}
        </span>
        <span class="toggle-pill ${isRefPrev ? 'active pill-green' : ''}" data-flag="use_previous_scene" title="${escapeHtml(t('flagRefPrevTitle'))}">
          ${escapeHtml(t('flagRefPrev'))}
        </span>
      </div>

      <!-- Cast in Szene -->
      <div class="scene-cast-bar">
        <span style="font-weight:600;">${escapeHtml(t('castInScene'))}</span>
        <div class="scene-cast-chips">
          ${castChipsHtml || `<span style="font-style:italic;color:var(--text-dim);">${escapeHtml(t('noCharsDefined'))}</span>`}
        </div>
      </div>

      <!-- Szene Regieanweisung / Idee -->
      <div class="idea-field-wrapper">
        <div class="idea-header-row">
          <div class="idea-chips-bar">
            <span class="insert-label">${escapeHtml(t('insertVar'))}</span>
            ${varChipsHtml || `<span style="font-size:10px;color:var(--text-dim);font-style:italic;">${escapeHtml(t('noVariables'))}</span>`}
          </div>
          <button class="btn btn-ai-magic btn-xs btn-ai-elaborate-scene" title="${escapeHtml(t('btnAiElaborateSceneTitle'))}">
            <span class="ai-sparkle">🪄</span> <span>${escapeHtml(t('btnAiElaborateScene'))}</span>
          </button>
        </div>
        <textarea class="form-control scene-idea-textarea" rows="3" placeholder="${escapeHtml(t('sceneIdeaPlaceholder'))}">${escapeHtml(idea)}</textarea>
      </div>

      <!-- Variablen Update in dieser Szene -->
      <div class="scene-vars-wrapper">
        <div class="scene-vars-header">
          <span>${escapeHtml(t('sceneVarsUpdate'))}</span>
          <button class="btn btn-ai-magic btn-xs btn-ai-suggest-scene-vars" title="${escapeHtml(t('btnAiSuggestSceneVarsTitle'))}">
            <span class="ai-sparkle">🪄</span> <span>${escapeHtml(t('btnAiSuggestSceneVars'))}</span>
          </button>
        </div>
        <input type="text" class="form-control scene-varupdate-input" placeholder="${escapeHtml(t('sceneVarsUpdatePlaceholder'))}" value="${escapeHtml(scene.variables_update ? JSON.stringify(scene.variables_update) : '')}">
      </div>

      <!-- Video LoRAs in dieser Szene (Kamera / Spezial-FX) -->
      <div class="scene-loras-section">
        <div class="scene-loras-header">
          <label>🎬 ${escapeHtml(t('sceneLorasLabel'))}</label>
          <button class="btn btn-accent btn-xs btn-pick-scene-lora" title="${escapeHtml(t('btnPickSceneLora'))}">
            ${escapeHtml(t('btnPickSceneLora'))}
          </button>
        </div>
        <div class="scene-loras-list">
          ${sceneLorasHtml}
        </div>
      </div>
    `;

    // Hook listeners
    const seqInput = card.querySelector('.scene-seq-input');
    seqInput.addEventListener('input', () => {
      scene.sequence = seqInput.value;
      markDirty();
    });

    const locInput = card.querySelector('.scene-loc-input');
    locInput.addEventListener('input', () => {
      scene.location = locInput.value;
      markDirty();
    });

    const durationInput = card.querySelector('.scene-duration-input');
    durationInput.addEventListener('change', () => {
      const d = parseInt(durationInput.value, 10) || 6;
      scene.duration = d;
      markDirty();
    });

    // Continuity Pills
    card.querySelectorAll('.toggle-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        const flag = pill.dataset.flag;
        const current = Boolean(scene[flag]);
        scene[flag] = !current;
        pill.classList.toggle('active', !current);
        if (flag === 'match_cut') pill.classList.toggle('pill-cyan', !current);
        if (flag === 'use_previous_scene') pill.classList.toggle('pill-green', !current);
        markDirty();
      });
    });

    // Cast Chips Toggle
    card.querySelectorAll('.cast-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const cName = chip.dataset.charName;
        if (!Array.isArray(scene.characters)) scene.characters = [];
        if (scene.characters.includes(cName)) {
          scene.characters = scene.characters.filter(x => x !== cName);
          chip.classList.remove('selected');
          chip.textContent = `+ ${cName}`;
        } else {
          scene.characters.push(cName);
          chip.classList.add('selected');
          chip.textContent = `✔ ${cName}`;
        }
        markDirty();
      });
    });

    // Idea Textarea & Variable chip insertion
    const ideaTextarea = card.querySelector('.scene-idea-textarea');
    ideaTextarea.addEventListener('focus', () => {
      state.focusedIdeaTextarea = ideaTextarea;
    });

    ideaTextarea.addEventListener('input', () => {
      scene.idea = ideaTextarea.value;
      markDirty();
    });

    card.querySelectorAll('.idea-chip-insert').forEach(chip => {
      chip.addEventListener('click', () => {
        const key = chip.dataset.varKey;
        const token = `{${key}}`;
        const start = ideaTextarea.selectionStart || 0;
        const end = ideaTextarea.selectionEnd || 0;
        const val = ideaTextarea.value;
        ideaTextarea.value = val.substring(0, start) + token + val.substring(end);
        ideaTextarea.selectionStart = ideaTextarea.selectionEnd = start + token.length;
        ideaTextarea.focus();
        scene.idea = ideaTextarea.value;
        markDirty();
      });
    });

    // Scene Variables Update parser
    const varUpdInput = card.querySelector('.scene-varupdate-input');
    varUpdInput.addEventListener('change', () => {
      const raw = varUpdInput.value.trim();
      if (!raw) {
        delete scene.variables_update;
      } else {
        try {
          scene.variables_update = JSON.parse(raw);
        } catch {
          const parts = raw.split(':');
          if (parts.length >= 2) {
            scene.variables_update = { [parts[0].trim()]: parts.slice(1).join(':').trim() };
          } else {
            scene.variables_update = { note: raw };
          }
        }
      }
      markDirty();
    });

    // AI Elaborate Scene Button
    const elaborateBtn = card.querySelector('.btn-ai-elaborate-scene');
    if (elaborateBtn) {
      elaborateBtn.addEventListener('click', async () => {
        try {
          elaborateBtn.disabled = true;
          elaborateBtn.innerHTML = `<span class="ai-loading-spinner"></span> <span>${escapeHtml(t('aiThinking'))}</span>`;
          // Extract preceding scenes for continuity context (especially same sequence / location)
          const precedingScenes = allScenes.slice(0, idx).map(s => ({
            id: s.id,
            sequence: s.sequence || '',
            location: s.location || '',
            idea: s.idea || '',
            duration: s.duration || 6,
            match_cut: Boolean(s.match_cut),
            same_scene: Boolean(s.same_scene),
            use_previous_scene: Boolean(s.use_previous_scene)
          }));

          const res = await API.generateLlm('elaborate_scene', {
            scene: scene,
            scene_index: idx,
            preceding_scenes: precedingScenes,
            idea: scene.idea || '',
            sequence: scene.sequence || '',
            location: scene.location || '',
            continuity: {
              match_cut: Boolean(scene.match_cut),
              same_scene: Boolean(scene.same_scene),
              use_previous_scene: Boolean(scene.use_previous_scene)
            },
            title: state.screenplay.title,
            description: state.screenplay.description,
            variables: state.screenplay.variables,
            characters: scene.characters || state.screenplay.characters
          });
          if (res && (res.scene || res.elaborated_idea)) {
            const sc = res.scene || {};
            const newIdea = sc.idea || res.elaborated_idea;
            if (newIdea) scene.idea = newIdea;
            const newDur = sc.duration || res.duration;
            if (newDur) scene.duration = newDur;
            const newLoras = sc.loras || res.loras;
            if (Array.isArray(newLoras) && newLoras.length > 0) {
              scene.loras = newLoras;
            }
            if (sc.variables_update && typeof sc.variables_update === 'object' && Object.keys(sc.variables_update).length > 0) {
              scene.variables_update = Object.assign({}, scene.variables_update || {}, sc.variables_update);
            }
            renderScenes();
            markDirty();
            showToast(t('aiSceneElaborated').replace('{id}', sceneId), 'success');
          } else {
            showToast(res.error || 'Fehler beim Ausarbeiten der Szene', 'error');
          }
        } catch (err) {
          showToast(err.message || t('aiErrorOffline'), 'error');
        } finally {
          elaborateBtn.disabled = false;
        }
      });
    }

    // AI Suggest Scene Variables Button
    const suggestVarsBtn = card.querySelector('.btn-ai-suggest-scene-vars');
    if (suggestVarsBtn) {
      suggestVarsBtn.addEventListener('click', async () => {
        try {
          suggestVarsBtn.disabled = true;
          suggestVarsBtn.innerHTML = `<span class="ai-loading-spinner"></span> <span>${escapeHtml(t('aiThinking'))}</span>`;
          const res = await API.generateLlm('suggest_variables', {
            scene: scene,
            screenplay: state.screenplay,
            title: state.screenplay.title,
            description: state.screenplay.description,
            variables: state.screenplay.variables,
            global_variables: state.screenplay.variables,
            characters: state.screenplay.characters,
            context: 'scene_update'
          });
          const newVars = res.scene_variables_update || res.variables;
          if (newVars && Object.keys(newVars).length > 0) {
            scene.variables_update = Object.assign({}, scene.variables_update || {}, newVars);
            renderScenes();
            markDirty();
            showToast(t('aiVarsExtracted').replace('{count}', Object.keys(newVars).length), 'success');
          } else {
            showToast(t('noVariables'), 'info');
          }
        } catch (err) {
          showToast(err.message || t('aiErrorOffline'), 'error');
        } finally {
          suggestVarsBtn.disabled = false;
        }
      });
    }

    // Video LoRA Pick & Remove Listeners
    const pickSceneLoraBtn = card.querySelector('.btn-pick-scene-lora');
    if (pickSceneLoraBtn) {
      pickSceneLoraBtn.addEventListener('click', () => {
        openLoraPickerModalForScene(idx);
      });
    }

    card.querySelectorAll('.btn-remove-scene-lora').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const loraToRemove = e.target.dataset.lora;
        let cur = [];
        if (Array.isArray(scene.loras)) {
          cur = scene.loras.map(l => (typeof l === 'string' ? l : (l.key || l.name || l.lora || ''))).filter(Boolean);
        } else if (typeof scene.loras === 'string' && scene.loras) {
          cur = scene.loras.split(',').map(s => s.trim()).filter(Boolean);
        }
        cur = cur.filter(l => l !== loraToRemove);
        if (cur.length > 0) {
          scene.loras = cur;
        } else {
          delete scene.loras;
          delete scene.lora;
        }
        renderScenes();
        markDirty();
      });
    });

    // Scene Operations (Move, Duplicate, Delete)
    card.querySelector('.btn-move-up').addEventListener('click', () => {
      if (idx > 0) {
        const item = allScenes.splice(idx, 1)[0];
        allScenes.splice(idx - 1, 0, item);
        reindexScenes();
        renderScenes();
        markDirty();
      }
    });

    card.querySelector('.btn-move-down').addEventListener('click', () => {
      if (idx < allScenes.length - 1) {
        const item = allScenes.splice(idx, 1)[0];
        allScenes.splice(idx + 1, 0, item);
        reindexScenes();
        renderScenes();
        markDirty();
      }
    });

    card.querySelector('.btn-dup-scene').addEventListener('click', () => {
      const clone = JSON.parse(JSON.stringify(scene));
      allScenes.splice(idx + 1, 0, clone);
      reindexScenes();
      renderScenes();
      markDirty();
      showToast(t('sceneDuplicated').replace('{id}', sceneId), 'info');
    });

    card.querySelector('.btn-del-scene').addEventListener('click', () => {
      if (confirm(t('confirmDeleteScene'))) {
        allScenes.splice(idx, 1);
        reindexScenes();
        renderScenes();
        markDirty();
      }
    });

    return card;
  }

  function reindexScenes() {
    const scenes = state.screenplay.scenes || [];
    scenes.forEach((s, idx) => {
      s.id = idx + 1;
    });
  }

  function addScene() {
    const scenes = state.screenplay.scenes || [];
    const newId = scenes.length + 1;

    const prevScene = scenes.length > 0 ? scenes[scenes.length - 1] : null;
    const newScene = {
      id: newId,
      sequence: prevScene ? (prevScene.sequence || prevScene.sequenz || 'Sequenz 1') : 'Sequenz 1',
      location: prevScene ? (prevScene.location || prevScene.ort || 'Drehort') : 'Hauptschauplatz',
      duration: 6,
      same_scene: prevScene ? true : false,
      characters: prevScene && Array.isArray(prevScene.characters) ? [...prevScene.characters] : [],
      idea: state.lang === 'en' ? 'Description of scene action and camera movement.' : 'Beschreibung der Handlung und Kamerabewegung.'
    };

    scenes.push(newScene);
    renderScenes();
    markDirty();
    showToast(`${t('btnAddScene')} #${newId}`, 'info');
  }

  // --- Live JSON Preview ---
  function renderJsonPreview() {
    if (el.jsonPreview) {
      el.jsonPreview.textContent = JSON.stringify(state.screenplay, null, 2);
    }
  }

  // --- LM Studio AI Methods ---
  async function refreshLlmStatus() {
    if (!el.llmStatusPill || !el.llmStatusText) return;
    el.llmStatusPill.className = 'llm-status-pill checking';
    el.llmStatusText.textContent = t('llmStatusChecking');
    try {
      const status = await API.getLlmStatus();
      if (status && status.online) {
        state.llmOnline = true;
        state.llmModel = status.model || 'Local Model';
        el.llmStatusPill.className = 'llm-status-pill online';
        const modelLabel = status.model ? (status.model.length > 20 ? status.model.substring(0, 18) + '...' : status.model) : 'Online';
        el.llmStatusText.textContent = t('llmStatusOnline').replace('{model}', modelLabel);
        el.llmStatusPill.title = `${t('llmStatusOnline').replace('{model}', status.model || '')} (${status.url || ''})`;
      } else {
        state.llmOnline = false;
        state.llmModel = null;
        el.llmStatusPill.className = 'llm-status-pill offline';
        el.llmStatusText.textContent = t('llmStatusOffline');
        el.llmStatusPill.title = t('aiErrorOffline');
      }
    } catch {
      state.llmOnline = false;
      state.llmModel = null;
      el.llmStatusPill.className = 'llm-status-pill offline';
      el.llmStatusText.textContent = t('llmStatusOffline');
      el.llmStatusPill.title = t('aiErrorOffline');
    }
  }

  async function handleAiExtractVariables() {
    if (!el.btnAiExtractVars) return;
    const btn = el.btnAiExtractVars;
    try {
      btn.disabled = true;
      btn.innerHTML = `<span class="ai-loading-spinner"></span> <span>${escapeHtml(t('aiThinking'))}</span>`;
      const res = await API.generateLlm('suggest_variables', {
        screenplay: state.screenplay,
        context: 'extract_global'
      });
      const extracted = res.variables || res.global_variables;
      if (extracted && typeof extracted === 'object' && Object.keys(extracted).length > 0) {
        if (!state.screenplay.variables) state.screenplay.variables = {};
        let countAdded = 0;
        for (const [k, v] of Object.entries(extracted)) {
          if (!state.screenplay.variables[k]) {
            state.screenplay.variables[k] = v;
            countAdded++;
          }
        }
        renderVariables();
        renderScenes();
        markDirty();
        showToast(t('aiVarsExtracted').replace('{count}', countAdded > 0 ? countAdded : Object.keys(extracted).length), 'success');
      } else {
        showToast(t('noVariables'), 'info');
      }
    } catch (err) {
      showToast(err.message || t('aiErrorOffline'), 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<span class="ai-sparkle">✨</span> <span data-i18n="btnAiExtractVars">${escapeHtml(t('btnAiExtractVars'))}</span>`;
    }
  }

  async function handleAiSuggestScene() {
    if (!el.btnAiSuggestScene) return;
    const btn = el.btnAiSuggestScene;
    try {
      btn.disabled = true;
      btn.innerHTML = `<span class="ai-loading-spinner"></span> <span>${escapeHtml(t('aiThinking'))}</span>`;
      const res = await API.generateLlm('suggest_next_scene', {
        screenplay: state.screenplay,
        title: state.screenplay.title,
        description: state.screenplay.description,
        scenes: state.screenplay.scenes,
        characters: state.screenplay.characters,
        variables: state.screenplay.variables
      });
      if (res && res.scene) {
        state.pendingAiScene = res.scene;
        showAiSceneModal(res.scene);
      } else {
        showToast('Kein Szenenvorschlag erhalten', 'error');
      }
    } catch (err) {
      showToast(err.message || t('aiErrorOffline'), 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<span class="ai-sparkle">🎬</span> <span data-i18n="btnAiSuggestScene">${escapeHtml(t('btnAiSuggestScene'))}</span>`;
    }
  }

  function showAiSceneModal(scene) {
    if (!el.aiSuggestionModal || !el.aiModalBody) return;
    const nextId = (state.screenplay.scenes || []).length + 1;
    const seq = scene.sequence || scene.sequenz || `Sequenz ${nextId}`;
    const loc = scene.location || scene.ort || 'Unbekannter Ort';
    const dur = scene.duration || scene.dauer || 6;
    const idea = scene.idea || scene.idee || '';
    const chars = Array.isArray(scene.characters) ? scene.characters.join(', ') : (scene.characters || '-');
    const loras = Array.isArray(scene.loras) ? scene.loras.join(', ') : '-';
    const varUpd = scene.variables_update ? JSON.stringify(scene.variables_update, null, 2) : null;

    el.aiModalTitle.textContent = `${t('aiModalTitleSuggest')} (#${nextId}: ${seq})`;
    el.aiModalBody.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:14px;padding:4px 0;">
        <div style="display:flex;gap:12px;flex-wrap:wrap;">
          <div style="flex:1;min-width:180px;">
            <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">${escapeHtml(t('sceneSeqPlaceholder'))}</label>
            <div style="font-weight:600;color:var(--accent);margin-top:2px;">${escapeHtml(seq)}</div>
          </div>
          <div style="flex:1;min-width:180px;">
            <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">${escapeHtml(t('sceneLocPlaceholder'))}</label>
            <div style="color:var(--text);margin-top:2px;">${escapeHtml(loc)}</div>
          </div>
          <div style="width:100px;">
            <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">${escapeHtml(t('durationTitle'))}</label>
            <div style="color:var(--cyan);margin-top:2px;">⏱️ ${dur} ${escapeHtml(t('secondsUnit'))}</div>
          </div>
        </div>

        <div>
          <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">${escapeHtml(t('castInScene'))}</label>
          <div style="color:var(--text);margin-top:2px;">🎭 ${escapeHtml(chars)}</div>
        </div>

        <div>
          <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">Regieanweisung & Prompt</label>
          <div style="margin-top:4px;padding:10px 12px;background:var(--bg-card);border:1px solid var(--border);border-radius:6px;color:var(--text);white-space:pre-wrap;line-height:1.5;font-size:13px;">${escapeHtml(idea)}</div>
        </div>

        ${loras !== '-' ? `
          <div>
            <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">🎬 ${escapeHtml(t('sceneLorasLabel'))}</label>
            <div style="color:var(--text-muted);margin-top:2px;">${escapeHtml(loras)}</div>
          </div>
        ` : ''}

        ${varUpd ? `
          <div>
            <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">${escapeHtml(t('sceneVarsUpdate'))}</label>
            <pre style="margin-top:4px;padding:6px 10px;background:rgba(0,0,0,0.3);border-radius:4px;font-size:12px;color:var(--cyan);">${escapeHtml(varUpd)}</pre>
          </div>
        ` : ''}
      </div>
    `;
    el.aiSuggestionModal.classList.add('open');
  }

  function closeAiModal() {
    if (el.aiSuggestionModal) {
      el.aiSuggestionModal.classList.remove('open');
    }
    state.pendingAiScene = null;
  }

  function applyPendingAiScene() {
    if (!state.pendingAiScene) return;
    if (!state.screenplay.scenes) state.screenplay.scenes = [];
    const scenes = state.screenplay.scenes;
    const newScene = Object.assign({}, state.pendingAiScene);
    newScene.id = scenes.length + 1;
    scenes.push(newScene);
    closeAiModal();
    renderScenes();
    markDirty();
    showToast(t('aiSceneSuggested').replace('{id}', newScene.id), 'success');
  }

  // --- Setup Event Listeners ---
  function setupEventListeners() {
    // Project Select
    el.projectSelect.addEventListener('change', () => {
      const sel = el.projectSelect.value;
      if (sel) loadProject(sel);
    });

    // New Project
    el.btnNewProject.addEventListener('click', createNewProject);

    // Save Project
    el.btnSave.addEventListener('click', saveCurrentProject);

    // Duplicate Project
    el.btnDuplicate.addEventListener('click', () => {
      const cur = el.movieFilename.value.trim();
      const newName = `${cur}_${t('copySuffixLower')}`;
      el.movieFilename.value = newName;
      el.movieTitle.value = `${el.movieTitle.value} (${t('copySuffix')})`;
      markDirty();
      saveCurrentProject();
    });

    // Rescan Catalog
    el.btnRescan.addEventListener('click', async () => {
      try {
        el.rescanIcon.textContent = '⏳';
        el.btnRescan.disabled = true;
        showToast(t('scanningCatalog'), 'info');
        const res = await API.rescanCatalog();
        state.presetsData = await API.getPresets();
        renderCharacters();
        el.rescanIcon.textContent = '🔄';
        el.btnRescan.disabled = false;
        showToast(res.message || t('catalogUpdated'), 'success');
      } catch (err) {
        el.rescanIcon.textContent = '🔄';
        el.btnRescan.disabled = false;
        showToast(err.message, 'error');
      }
    });

    // Launch Movie / Render Modal
    el.btnLaunchMovie.addEventListener('click', () => {
      const rawBase = el.movieFilename.value.trim() || 'film';
      const cleanBase = sanitizeFilename(rawBase);
      const filename = cleanBase.endsWith('.json') ? cleanBase : `${cleanBase}.json`;
      el.renderCliCommand.textContent = `python master_regisseur.py Projects/${filename}`;
      el.renderModal.classList.add('open');
    });

    el.btnCloseRenderModal.addEventListener('click', () => el.renderModal.classList.remove('open'));
    el.btnCloseRenderModalBtn.addEventListener('click', () => el.renderModal.classList.remove('open'));
    el.btnCopyCli.addEventListener('click', () => {
      navigator.clipboard.writeText(el.renderCliCommand.textContent);
      showToast(t('copied'), 'success');
    });

    // Language Toggle
    el.btnLangToggle.addEventListener('click', () => {
      const targetLang = state.lang === 'de' ? 'en' : 'de';
      setLanguage(targetLang);
      showToast(t('langSwitched'), 'info');
    });

    // Exit Button
    el.btnExit.addEventListener('click', async () => {
      if (state.isDirty && !confirm(t('exitConfirm'))) {
        return;
      }
      showToast(t('editorStopping'), 'info');
      await API.shutdownServer();
      document.body.innerHTML = `
        <div style="display:flex;height:100vh;align-items:center;justify-content:center;flex-direction:column;gap:16px;color:#f1f5f9;background:#0b0f17;font-family:sans-serif;">
          <h2 style="color:#f59e0b;">${escapeHtml(t('editorStoppedTitle'))}</h2>
          <p style="color:#94a3b8;">${escapeHtml(t('editorStoppedDesc'))}</p>
        </div>
      `;
    });

    // Metadata inputs
    el.movieTitle.addEventListener('input', () => {
      state.screenplay.title = el.movieTitle.value;
      markDirty();
    });

    el.movieFilename.addEventListener('input', markDirty);

    el.movieDescription.addEventListener('input', () => {
      state.screenplay.description = el.movieDescription.value;
      markDirty();
    });

    // Add Variable
    el.btnAddVariable.addEventListener('click', addVariable);

    // Add Character
    el.btnAddCharacter.addEventListener('click', addCharacter);

    // Add Scene
    el.btnAddScene.addEventListener('click', addScene);

    // Tab Navigation
    el.tabButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        el.tabButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        Object.values(el.tabContents).forEach(content => content.classList.remove('active'));
        if (el.tabContents[tab]) el.tabContents[tab].classList.add('active');

        if (tab === 'json') renderJsonPreview();
      });
    });

    // Copy JSON
    el.btnCopyJson.addEventListener('click', () => {
      navigator.clipboard.writeText(JSON.stringify(state.screenplay, null, 2));
      showToast(t('copied'), 'success');
    });

    el.btnFormatJson.addEventListener('click', () => {
      renderJsonPreview();
      showToast(t('jsonFormatted'), 'info');
    });

    // LoRA Modal Events
    el.btnCloseLoraModal.addEventListener('click', closeLoraPickerModal);
    el.loraSearchInput.addEventListener('input', () => {
      renderLoraModalCards();
    });
    el.chkShowAllLoras.addEventListener('change', () => {
      renderLoraModalCards();
    });

    // LM Studio AI & Modals
    if (el.llmStatusPill) el.llmStatusPill.addEventListener('click', refreshLlmStatus);
    if (el.btnAiSuggestScene) el.btnAiSuggestScene.addEventListener('click', handleAiSuggestScene);
    if (el.btnAiExtractVars) el.btnAiExtractVars.addEventListener('click', handleAiExtractVariables);
    if (el.btnCloseAiModal) el.btnCloseAiModal.addEventListener('click', closeAiModal);
    if (el.btnDiscardAiModal) el.btnDiscardAiModal.addEventListener('click', closeAiModal);
    if (el.btnApplyAiModal) el.btnApplyAiModal.addEventListener('click', applyPendingAiScene);

    // Keyboard Shortcuts (Ctrl+S to save)
    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        saveCurrentProject();
      }
    });
  }

  // Start Application
  window.addEventListener('DOMContentLoaded', initApp);
})();
