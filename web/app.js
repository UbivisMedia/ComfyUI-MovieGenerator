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
    lang: 'de', // 'de' or 'en'
    activeModelTargetCharIndex: null,
    modelFilterCategory: 'all',
    pendingStoryGen: null, // Holds preview of generated batch scenes & new characters
    wizard: {
      premise: '',
      maxDuration: 6,
      maxTokens: 4000,
      currentStepIndex: 1,
      currentScene: null,
      currentNewChars: [],
      hooks: []
    }
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
      music: document.getElementById('tabContentMusic'),
      json: document.getElementById('tabContentJson')
    },

    // Music Studio
    chkMusicEnabled: document.getElementById('chkMusicEnabled'),
    musicSettingsBody: document.getElementById('musicSettingsBody'),
    musicModelSelect: document.getElementById('musicModelSelect'),
    musicPromptInput: document.getElementById('musicPromptInput'),
    btnSuggestMusicTags: document.getElementById('btnSuggestMusicTags'),
    musicVolumeSelect: document.getElementById('musicVolumeSelect'),
    chkMusicDucking: document.getElementById('chkMusicDucking'),
    btnScoreMovie: document.getElementById('btnScoreMovie'),
    musicScoreStatus: document.getElementById('musicScoreStatus'),
    musicPlayerWrapper: document.getElementById('musicPlayerWrapper'),
    audioSoundtrackPlayer: document.getElementById('audioSoundtrackPlayer'),
    linkDownloadSoundtrack: document.getElementById('linkDownloadSoundtrack'),

    // Containers
    charactersContainer: document.getElementById('charactersContainer'),
    scenesContainer: document.getElementById('scenesContainer'),
    btnAddCharacter: document.getElementById('btnAddCharacter'),
    btnAddScene: document.getElementById('btnAddScene'),
    storyboardTimelineContainer: document.getElementById('storyboardTimelineContainer'),
    timelineStatsBadge: document.getElementById('timelineStatsBadge'),
    btnPlayFullMovie: document.getElementById('btnPlayFullMovie'),
    filmstripTrack: document.getElementById('filmstripTrack'),
    btnToggleVideoPlayer: document.getElementById('btnToggleVideoPlayer'),
    videoPlayerModal: document.getElementById('videoPlayerModal'),
    btnCloseVideoModal: document.getElementById('btnCloseVideoModal'),
    btnCloseVideoModalBtn: document.getElementById('btnCloseVideoModalBtn'),
    videoModalTitle: document.getElementById('videoModalTitle'),
    modalVideoElement: document.getElementById('modalVideoElement'),
    videoMetaTitle: document.getElementById('videoMetaTitle'),
    videoMetaDuration: document.getElementById('videoMetaDuration'),
    videoDownloadLink: document.getElementById('videoDownloadLink'),
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

    // Model Modal
    modelModal: document.getElementById('modelModal'),
    btnCloseModelModal: document.getElementById('btnCloseModelModal'),
    modelSearchInput: document.getElementById('modelSearchInput'),
    modelFilterTabs: document.getElementById('modelFilterTabs'),
    modalActiveCharName: document.getElementById('modalActiveCharName'),
    modalCurrentModelKey: document.getElementById('modalCurrentModelKey'),
    modelCardsList: document.getElementById('modelCardsList'),

    // Render Modal
    renderModal: document.getElementById('renderModal'),
    btnCloseRenderModal: document.getElementById('btnCloseRenderModal'),
    btnCloseRenderModalBtn: document.getElementById('btnCloseRenderModalBtn'),
    renderCliCommand: document.getElementById('renderCliCommand'),
    btnCopyCli: document.getElementById('btnCopyCli'),

    // In-App Guide Modal Elements
    btnGuide: document.getElementById('btnGuide'),
    guideModal: document.getElementById('guideModal'),
    btnCloseGuideModal: document.getElementById('btnCloseGuideModal'),
    btnCloseGuideModalBtn: document.getElementById('btnCloseGuideModalBtn'),
    btnOpenGuideFromWizard: document.getElementById('btnOpenGuideFromWizard'),
    btnOpenGuideFromWizardInteractive: document.getElementById('btnOpenGuideFromWizardInteractive'),
    guideNav: document.getElementById('guideNav'),

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
    btnApplyAiModal: document.getElementById('btnApplyAiModal'),

    // Story Generator Elements
    btnStoryGenerator: document.getElementById('btnStoryGenerator'),
    storyGeneratorModal: document.getElementById('storyGeneratorModal'),
    btnCloseStoryGenModal: document.getElementById('btnCloseStoryGenModal'),
    storyGenPlot: document.getElementById('storyGenPlot'),
    storyGenMaxDuration: document.getElementById('storyGenMaxDuration'),
    storyGenMaxDurationVal: document.getElementById('storyGenMaxDurationVal'),
    storyGenMaxTokens: document.getElementById('storyGenMaxTokens'),
    storyGenMaxTokensVal: document.getElementById('storyGenMaxTokensVal'),
    btnExecuteStoryGen: document.getElementById('btnExecuteStoryGen'),
    storyGenPreviewContainer: document.getElementById('storyGenPreviewContainer'),
    storyGenNewCharsBox: document.getElementById('storyGenNewCharsBox'),
    storyGenSummaryBadge: document.getElementById('storyGenSummaryBadge'),
    storyGenShotsList: document.getElementById('storyGenShotsList'),
    storyGenFooter: document.getElementById('storyGenFooter'),
    btnCancelStoryGen: document.getElementById('btnCancelStoryGen'),
    btnApplyStoryGen: document.getElementById('btnApplyStoryGen'),

    // Story Wizard Elements
    btnStoryWizard: document.getElementById('btnStoryWizard'),
    storyWizardModal: document.getElementById('storyWizardModal'),
    btnCloseWizardModal: document.getElementById('btnCloseWizardModal'),
    wizardStepBadge: document.getElementById('wizardStepBadge'),
    wizardSetupView: document.getElementById('wizardSetupView'),
    wizardPremiseInput: document.getElementById('wizardPremiseInput'),
    wizardProducerInstructions: document.getElementById('wizardProducerInstructions'),
    wizardProducerDetails: document.getElementById('wizardProducerDetails'),
    wizardInteractiveProducerInstructions: document.getElementById('wizardInteractiveProducerInstructions'),
    wizardMaxDuration: document.getElementById('wizardMaxDuration'),
    wizardMaxDurationVal: document.getElementById('wizardMaxDurationVal'),
    wizardMaxTokens: document.getElementById('wizardMaxTokens'),
    wizardMaxTokensVal: document.getElementById('wizardMaxTokensVal'),
    btnWizardStart: document.getElementById('btnWizardStart'),
    wizardInteractiveView: document.getElementById('wizardInteractiveView'),
    wizardTimeline: document.getElementById('wizardTimeline'),
    wizardCurrentShotBox: document.getElementById('wizardCurrentShotBox'),
    wizardNewCharAlert: document.getElementById('wizardNewCharAlert'),
    wizardUserInstruction: document.getElementById('wizardUserInstruction'),
    wizardHooksBox: document.getElementById('wizardHooksBox'),
    wizardHooksList: document.getElementById('wizardHooksList'),
    wizardFooter: document.getElementById('wizardFooter'),
    btnWizardFinish: document.getElementById('btnWizardFinish'),
    wizardInteractiveActions: document.getElementById('wizardInteractiveActions'),
    btnWizardRegenerate: document.getElementById('btnWizardRegenerate'),
    btnWizardApplyAndNext: document.getElementById('btnWizardApplyAndNext'),
    btnWizardSaveEdits: document.getElementById('btnWizardSaveEdits'),
    btnWizardRecreateScene: document.getElementById('btnWizardRecreateScene'),
    btnHarmonizeScript: document.getElementById('btnHarmonizeScript'),

    // Settings Modal Elements
    btnSettings: document.getElementById('btnSettings'),
    settingsModal: document.getElementById('settingsModal'),
    btnCloseSettingsModal: document.getElementById('btnCloseSettingsModal'),
    btnCloseSettingsModalBtn: document.getElementById('btnCloseSettingsModalBtn'),
    btnSaveSettings: document.getElementById('btnSaveSettings'),
    btnPickTurboLora: document.getElementById('btnPickTurboLora'),
    btnRefreshLmsModels: document.getElementById('btnRefreshLmsModels'),

    settingMinimaxUnetSelect: document.getElementById('settingMinimaxUnetSelect'),
    settingMinimaxUnetInput: document.getElementById('settingMinimaxUnetInput'),
    settingTurboLoraSelect: document.getElementById('settingTurboLoraSelect'),
    settingTurboLoraInput: document.getElementById('settingTurboLoraInput'),
    settingMinimaxSteps: document.getElementById('settingMinimaxSteps'),
    settingTurboStrength: document.getElementById('settingTurboStrength'),
    valTurboStrength: document.getElementById('valTurboStrength'),
    settingMinimaxVae: document.getElementById('settingMinimaxVae'),
    settingMinimaxClip: document.getElementById('settingMinimaxClip'),

    settingMusicEnabled: document.getElementById('settingMusicEnabled'),
    settingMusicModel: document.getElementById('settingMusicModel'),
    settingMusicSteps: document.getElementById('settingMusicSteps'),
    settingMusicCfg: document.getElementById('settingMusicCfg'),
    settingMusicVolume: document.getElementById('settingMusicVolume'),
    valMusicVolume: document.getElementById('valMusicVolume'),
    settingMusicDucking: document.getElementById('settingMusicDucking'),

    settingLmsUrl: document.getElementById('settingLmsUrl'),
    settingLmsModel: document.getElementById('settingLmsModel'),
    settingLmsTemp: document.getElementById('settingLmsTemp'),
    valLmsTemp: document.getElementById('valLmsTemp'),

    settingComfyUrl: document.getElementById('settingComfyUrl'),
    settingModelsDir: document.getElementById('settingModelsDir'),
    settingDefaultLang: document.getElementById('settingDefaultLang'),
    settingWebmExport: document.getElementById('settingWebmExport')
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
    renderMusicStudio();
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
    },

    async uploadCharacterImage(project, name, imageBase64, removeBackground = true) {
      const res = await fetch('/api/characters/upload_image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project,
          name,
          image_base64: imageBase64,
          remove_background: removeBackground
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Fehler beim Hochladen des Charakterbildes');
      }
      return data;
    },

    async deleteCharacterImage(project, name) {
      const res = await fetch('/api/characters/delete_image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project, name })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Fehler beim Löschen des Charakterbildes');
      }
      return data;
    },

    async generateCharacterPortrait(project, character, variables, removeBackground = true) {
      const res = await fetch('/api/characters/generate_image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project,
          character,
          variables,
          remove_background: removeBackground
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Fehler beim Generieren des Charakterbildes');
      }
      return data;
    },

    async getMusicModels() {
      const res = await fetch('/api/music/models');
      if (!res.ok) throw new Error('Fehler beim Laden der Musik-Modelle');
      return await res.json();
    },

    async suggestMusicTags(project, title, description, scenes = []) {
      const res = await fetch('/api/music/suggest-tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project, title, description, scenes })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Fehler beim Abrufen von Musik-Tags');
      }
      return data;
    },

    async scoreMovie(payload) {
      const res = await fetch('/api/music/score-movie', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Fehler bei der Filmmusik-Generierung');
      }
      return data;
    },

    async getScenesStatus(project) {
      const res = await fetch(`/api/scenes/status?project=${encodeURIComponent(project)}`);
      if (!res.ok) throw new Error('Fehler beim Laden des Szenen-Status');
      return await res.json();
    },

    async reshootScene(project, sceneId) {
      const res = await fetch('/api/scene/rerender', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project, scene_id: sceneId })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Fehler beim Starten des Szenen-Drehs');
      }
      return data;
    },

    async getSettings() {
      const res = await fetch('/api/settings');
      if (!res.ok) throw new Error('Fehler beim Laden der Einstellungen');
      return await res.json();
    },

    async saveSettings(settingsData) {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settingsData)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Fehler beim Speichern der Einstellungen');
      }
      return data;
    },

    async getSettingsModels(lmUrl = '') {
      let url = '/api/settings/models';
      if (lmUrl) {
        url += `?lm_studio_url=${encodeURIComponent(lmUrl)}`;
      }
      const res = await fetch(url);
      if (!res.ok) throw new Error('Fehler beim Laden der Modell-Informationen');
      return await res.json();
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
        if (locData && locData.version) {
          document.querySelectorAll('.version-tag').forEach(el => {
            el.textContent = `v${locData.version}`;
          });
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

      // Load Music Models
      await loadMusicModels();

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

  // --- Normalize Legacy Screenplay Data ---
  function normalizeScreenplay(data, filename = '') {
    if (!data || typeof data !== 'object') data = {};

    const norm = {};
    const defaultTitle = filename ? filename.replace(/\.json$/i, '').replace(/[_-]/g, ' ') : 'Untitled Movie';
    norm.title = data.title || data.titel || defaultTitle;
    norm.description = data.description || data.beschreibung || '';
    norm.producer_instructions = data.producer_instructions || '';

    // Variables
    norm.variables = data.variables || data.variablen || {};
    if (typeof norm.variables !== 'object' || Array.isArray(norm.variables)) {
      norm.variables = {};
    }

    // Music Studio Configuration
    const m = data.music || data.music_studio || {};
    norm.music = {
      enabled: m.enabled !== undefined ? Boolean(m.enabled) : false,
      model: m.model || m.checkpoint || '',
      prompt: m.prompt || m.tags || '',
      volume: m.volume !== undefined ? parseFloat(m.volume) : 0.22,
      ducking: m.ducking !== undefined ? Boolean(m.ducking) : true
    };

    // Characters
    let rawChars = data.characters || data.charaktere || [];
    if (!Array.isArray(rawChars) && data.charakter_prompt) {
      rawChars = [{ id: 1, name: 'Hero', prompt: data.charakter_prompt }];
    } else if (!Array.isArray(rawChars)) {
      rawChars = [];
    }

    const defaultModel = (state.presetsData && state.presetsData.default) || 'anima_catpony';
    norm.characters = rawChars.map((c, idx) => {
      if (!c || typeof c !== 'object') c = { name: String(c) };
      const cId = c.id || (idx + 1);
      const cName = c.name || c.charakter || `Actor_${cId}`;
      const cModel = c.model || c.modell || c.preset || defaultModel;
      let cLoras = c.loras || c.lora || [];
      if (typeof cLoras === 'string') {
        cLoras = cLoras.split(',').map(s => s.trim()).filter(Boolean);
      } else if (!Array.isArray(cLoras)) {
        cLoras = [];
      }
      const cDesc = c.description || c.beschreibung || c.prompt || '';
      const cPrompt = c.prompt || c.description || '';
      const autoPrompt = c.auto_prompt !== undefined ? c.auto_prompt : (c.ki_prompt_generieren !== undefined ? c.ki_prompt_generieren : !Boolean(c.prompt));

      const charObj = {
        id: cId,
        name: cName,
        model: cModel,
        loras: cLoras,
        description: cDesc,
        prompt: cPrompt,
        auto_prompt: autoPrompt
      };
      if (c.image) charObj.image = c.image;
      if (c.image_url) charObj.image_url = c.image_url;
      if (c.bild) charObj.image = c.bild;
      if (c.reference_image) charObj.image = c.reference_image;
      if (charObj.image && !charObj.image_url) {
        const projName = (el.movieFilename && el.movieFilename.value.trim()) || (filename ? filename.replace('.json', '') : 'film');
        const cleanName = cName.replace(/[\\/*?:"<>| ]/g, '_');
        charObj.image_url = `/api/characters/image?project=${encodeURIComponent(projName)}&name=${encodeURIComponent(cleanName)}&t=${Date.now()}`;
      }
      if (c.reference_id !== undefined) charObj.reference_id = c.reference_id;
      if (c.reference_character !== undefined) charObj.reference_character = c.reference_character;
      if (c.denoise !== undefined) charObj.denoise = c.denoise;
      return charObj;
    });

    // Scenes
    let rawScenes = data.scenes || data.szenen || [];
    if (!Array.isArray(rawScenes)) rawScenes = [];

    norm.scenes = rawScenes.map((s, idx) => {
      if (!s || typeof s !== 'object') s = { idea: String(s) };
      const sId = s.id || (idx + 1);
      const sSeq = s.sequence || s.sequenz || s.scene_group || s.group || '';
      const sLoc = s.location || s.ort || s.setting || '';
      const sDur = parseInt(s.duration || s.dauer_sekunden || s.duration_seconds || s.dauer || 6, 10) || 6;
      let sIdea = s.idea || s.idee || s.prompt || '';
      let sPrompt = s.prompt || sIdea;
      let sSummary = s.summary || '';
      let sSoundscape = s.soundscape || s.overall_soundscape || '';

      // De-clutter legacy multi-section prompts so textarea only contains the pure [Shot 1]: ...
      const cand = (sPrompt.includes('detailed_description:') || sPrompt.includes('summary:')) ? sPrompt : ((sIdea.includes('detailed_description:') || sIdea.includes('summary:')) ? sIdea : '');
      if (cand) {
        const sumMatch = cand.match(/summary:\s*([\s\S]*?)(?=\n\s*(?:detailed_description:|overall_soundscape:|non_diegetic_music:|$))/i);
        if (sumMatch && !sSummary) {
          sSummary = sumMatch[1].replace(/^\[reference generation\]\s*/i, '').trim();
        }
        const detMatch = cand.match(/detailed_description:\s*([\s\S]*?)(?=\n\s*(?:overall_soundscape:|non_diegetic_music:|$))/i);
        if (detMatch) {
          sIdea = detMatch[1].trim();
          sPrompt = sIdea;
        } else {
          const shotMatch = cand.match(/(\[Shot \d+\]:?[\s\S]*?)(?=\n\s*(?:overall_soundscape:|non_diegetic_music:|$))/i);
          if (shotMatch) {
            sIdea = shotMatch[1].trim();
            sPrompt = sIdea;
          }
        }
        const soundMatch = cand.match(/overall_soundscape:\s*([\s\S]*?)(?=\n\s*(?:non_diegetic_music:|$))/i);
        if (soundMatch && !sSoundscape) {
          sSoundscape = soundMatch[1].trim();
        }
      }

      sIdea = sIdea.replace(/^\[Shot \d+\]:?\s*/i, '').trim();
      sPrompt = sPrompt.replace(/^\[Shot \d+\]:?\s*/i, '').trim();

      const sMatchCut = Boolean(s.match_cut || s.direkter_anschluss || s.direct_continuation);
      const sSameScene = Boolean(s.same_scene || s.gleiche_szene || s.angle_change);
      const sRefPrev = Boolean(s.use_previous_scene || s.nutze_vorherige_szene || s.anschluss_an_vorherige_szene || s.continuity_environment);

      let sChars = s.characters || s.charaktere;
      if (!sChars && s.character) sChars = [s.character];
      else if (!sChars && s.charakter) sChars = [s.charakter];
      if (!Array.isArray(sChars)) sChars = [];

      let sVarUpd = s.variables_update || s.variablen_update || s.set_variables || {};
      if (typeof sVarUpd === 'string' && sVarUpd.trim()) {
        try {
          sVarUpd = JSON.parse(sVarUpd);
        } catch {
          const parts = sVarUpd.split(':');
          if (parts.length >= 2) {
            sVarUpd = { [parts[0].trim()]: parts.slice(1).join(':').trim() };
          } else {
            sVarUpd = {};
          }
        }
      }
      if (typeof sVarUpd !== 'object' || Array.isArray(sVarUpd)) sVarUpd = {};

      let sLoras = s.loras || s.lora || [];
      if (typeof sLoras === 'string') {
        sLoras = sLoras.split(',').map(str => str.trim()).filter(Boolean);
      } else if (!Array.isArray(sLoras)) {
        sLoras = [];
      }

      const sceneObj = {
        id: sId,
        sequence: sSeq,
        location: sLoc,
        duration: sDur,
        idea: sIdea,
        prompt: sPrompt
      };
      if (sSummary) sceneObj.summary = sSummary;
      if (sSoundscape) sceneObj.soundscape = sSoundscape;
      if (sChars.length > 0) sceneObj.characters = sChars;
      if (sMatchCut) sceneObj.match_cut = true;
      if (sSameScene) sceneObj.same_scene = true;
      if (sRefPrev) sceneObj.use_previous_scene = true;
      if (Object.keys(sVarUpd).length > 0) sceneObj.variables_update = sVarUpd;
      if (sLoras.length > 0) sceneObj.loras = sLoras;

      // Cinematic scene transition & duration
      const sTrans = s.transition || s.uebergang || s.blende || 'cut';
      const sTransDur = parseFloat(s.transition_duration || s.uebergang_dauer || 0.75) || 0.75;
      sceneObj.transition = sTrans;
      sceneObj.transition_duration = sTransDur;

      return sceneObj;
    });

    return norm;
  }

  // --- Load / New / Save Project ---
  async function loadProject(filename) {
    try {
      markSaving();
      const proj = await API.getProject(filename);
      state.currentFilename = filename;
      state.screenplay = normalizeScreenplay(proj.data, filename);

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
      renderMusicStudio();
      fetchAndRenderTimeline();
      updateStats();
      renderJsonPreview();
      markClean();

      if (proj.converted_legacy) {
        showToast(state.lang === 'en' ? `Legacy format auto-converted to current standard!` : `Älteres Format automatisch in aktuellen Standard konvertiert!`, 'info');
        markDirty();
      } else {
        showToast(t('screenplayLoaded').replace('{name}', filename), 'info');
      }
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
        hero_top: state.lang === 'en' ? 'dark worn leather jacket over grey shirt' : 'dunkle abgetragene Lederjacke über grauem T-Shirt',
        hero_bottom: state.lang === 'en' ? 'rugged blue denim jeans' : 'robuste blaue Denim-Jeans',
        hero_shoes: state.lang === 'en' ? 'black waterproof combat boots' : 'schwarze wetterfeste Lederstiefel',
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
            ? '<Subject 1> (Hero) steps cautiously out of the shadows into {location_alley}, his {hero_top} and {hero_bottom} reflecting wet puddles.'
            : '<Subject 1> (Hero) tritt langsam aus dem Schatten in {location_alley}, seine {hero_top} und {hero_bottom} reflektieren das nasse Pflaster.'
        }
      ],
      music: {
        enabled: false,
        model: '',
        prompt: '',
        volume: 0.22,
        ducking: true
      }
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

      if (!state.screenplay.music) state.screenplay.music = {};
      if (el.chkMusicEnabled) state.screenplay.music.enabled = el.chkMusicEnabled.checked;
      if (el.musicModelSelect) state.screenplay.music.model = el.musicModelSelect.value;
      if (el.musicPromptInput) state.screenplay.music.prompt = el.musicPromptInput.value.trim();
      if (el.musicVolumeSelect) state.screenplay.music.volume = parseFloat(el.musicVolumeSelect.value);
      if (el.chkMusicDucking) state.screenplay.music.ducking = el.chkMusicDucking.checked;

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

  // --- Character Continuity Helpers ---
  function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function getCharacterFirstScene(char, scenes) {
    if (!char) return 1;
    if (char.first_scene && parseInt(char.first_scene) > 0) {
      return parseInt(char.first_scene);
    }
    if (!scenes || !Array.isArray(scenes) || scenes.length === 0) return 1;

    const charId = char.id;
    const charName = (char.name || '').trim().toLowerCase();
    const cleanName = charName.replace(/[^a-z0-9]/gi, '');

    for (let idx = 0; idx < scenes.length; idx++) {
      const scene = scenes[idx];
      const sId = parseInt(scene.id) || (idx + 1);
      const sceneChars = scene.characters || scene.charaktere || scene.actors || [];

      if (Array.isArray(sceneChars)) {
        for (const sc of sceneChars) {
          if (sc === null || sc === undefined) continue;
          if (charId !== undefined && (String(sc).trim() === String(charId))) return sId;
          const subMatch = String(sc).match(/<Subject\s*(\d+)>/i);
          if (subMatch && parseInt(subMatch[1]) === parseInt(charId)) return sId;

          const scStr = String(sc).trim().toLowerCase();
          if (charName && (scStr.includes(charName) || charName.includes(scStr))) return sId;
          const scClean = scStr.replace(/[^a-z0-9]/gi, '');
          if (cleanName && (scClean.includes(cleanName) || cleanName.includes(scClean))) return sId;
        }
      }

      const text = `${scene.idea || ''} ${scene.prompt || ''} ${scene.idee || ''}`;
      if (charId !== undefined && text.includes(`<Subject ${charId}>`)) return sId;
      if (charName && charName.length >= 3) {
        const regex = new RegExp(`\\b${escapeRegExp(charName)}\\b`, 'i');
        if (regex.test(text)) return sId;
      }
    }

    return parseInt(scenes[0].id) || 1;
  }

  function getVariablesForScene(screenplay, targetSceneId) {
    const vars = {};
    if (!screenplay) return vars;
    const rootVars = screenplay.variables || screenplay.variablen || {};
    Object.assign(vars, rootVars);

    // Initial character outfits
    (screenplay.characters || screenplay.charaktere || []).forEach(c => {
      const cName = (c.name || '').trim();
      const cOutfit = c.outfit || c.kleidung || c.status || c.wardrobe;
      if (cOutfit && cName) {
        const varKey = `outfit_${cName.toLowerCase().replace(/[^a-z0-9]/g, '_')}`;
        if (!vars[varKey]) vars[varKey] = String(cOutfit);
      }
    });

    if (!targetSceneId || targetSceneId <= 0) return vars;

    const scenes = screenplay.scenes || screenplay.szenen || [];
    for (let idx = 0; idx < scenes.length; idx++) {
      const scene = scenes[idx];
      const sId = parseInt(scene.id) || (idx + 1);
      if (sId > targetSceneId) break;

      const updates = scene.variables_update || scene.variablen_update || scene.set_variables || scene.variables || scene.variablen;
      if (updates && typeof updates === 'object') {
        Object.assign(vars, updates);
      }
    }

    return vars;
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

    // First appearance scene (continuity check)
    const scenes = state.screenplay.scenes || [];
    const detectedFirstScene = getCharacterFirstScene(char, scenes);

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
      const descPart = mVal.beschreibung ? ` — ${mVal.beschreibung.substring(0, 65)}${mVal.beschreibung.length > 65 ? '...' : ''}` : '';
      const label = `${mKey}${descPart}`;
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

      <!-- Charakter-Porträt & Referenzbild Sektion (Optionaler Upload mit Freistellen) -->
      <div class="char-portrait-section">
        <div class="char-portrait-header">
          <label>📸 ${escapeHtml(t('charPortraitLabel'))}</label>
          ${char.image ? `<span class="badge-char-ref-active">✔ ${escapeHtml(t('charImgActiveBadge'))}</span>` : ''}
        </div>

        <div class="char-portrait-content ${char.image ? 'has-image' : 'empty'}">
          ${char.image ? `
            <div class="char-portrait-preview-box" title="${escapeHtml(char.name)}">
              <img src="${char.image_url || ('/api/characters/image?project=' + encodeURIComponent((el.movieFilename && el.movieFilename.value.trim()) ? el.movieFilename.value.trim() : 'film') + '&name=' + encodeURIComponent(char.name || '') + '&t=' + Date.now())}" alt="${escapeHtml(char.name)}" class="char-portrait-thumb">
            </div>
            <div class="char-portrait-info">
              <span class="char-portrait-hint">${escapeHtml(t('charImgT2iSkipped'))}</span>
              <div style="display:flex;gap:6px;align-items:center;margin-top:4px;flex-wrap:wrap;">
                <button type="button" class="btn btn-primary-outline btn-xs btn-trigger-generate-portrait" title="Mit aktuellen Einstellungen neu in ComfyUI generieren">
                  🎨 ${escapeHtml(t('btnRegenerateCharPortrait'))}
                </button>
                <input type="file" class="char-img-file-input" accept="image/png, image/jpeg, image/webp" style="display:none;">
                <button type="button" class="btn btn-secondary btn-xs btn-trigger-upload-img">
                  🔄 ${escapeHtml(t('btnChangeCharImg'))}
                </button>
                <button type="button" class="btn btn-danger-outline btn-xs btn-remove-char-img" title="${escapeHtml(t('btnRemoveCharImg'))}">
                  🗑️ ${escapeHtml(t('btnRemoveCharImg'))}
                </button>
              </div>
            </div>
          ` : `
            <div class="char-portrait-upload-area">
              <input type="file" class="char-img-file-input" accept="image/png, image/jpeg, image/webp" style="display:none;">
              <div class="char-portrait-upload-controls" style="flex-wrap:wrap;">
                <button type="button" class="btn btn-primary btn-sm btn-trigger-generate-portrait" title="Porträt jetzt direkt in ComfyUI generieren">
                  <span>🎨</span> <span>${escapeHtml(t('btnGenerateCharPortrait'))}</span>
                </button>
                <button type="button" class="btn btn-secondary btn-sm btn-trigger-upload-img">
                  <span>📤</span> <span>${escapeHtml(t('btnUploadCharImg'))}</span>
                </button>
                <label class="char-removebg-chk-label" title="${escapeHtml(t('chkRemoveBgTitle'))}">
                  <input type="checkbox" class="char-removebg-chk" checked>
                  <span>✨ ${escapeHtml(t('chkRemoveBg'))}</span>
                </label>
              </div>
              <span class="char-portrait-hint">${escapeHtml(t('charImgHint'))}</span>
            </div>
          `}
        </div>

        <div class="char-portrait-upload-status" style="display:none;">
          <span class="ai-loading-spinner"></span>
          <span class="char-upload-status-text">${escapeHtml(t('charImgUploading'))}</span>
        </div>
      </div>

      <!-- Basis Modell Auswahl -->
      <div class="char-model-group">
        <div class="char-model-header">
          <label>${escapeHtml(t('charModelLabel'))}</label>
          <button type="button" class="btn btn-secondary btn-xs btn-pick-model" title="${escapeHtml(t('btnPickModelTitle') || 'Modell auswählen')}">
            <span>🎨</span> <span>${escapeHtml(t('btnPickModel') || 'Modell wählen')}</span>
          </button>
        </div>
        <div class="char-selected-model-card" title="${escapeHtml(t('btnPickModelTitle') || 'Klicken, um Modell zu wechseln')}">
          ${currentModelInfo.preview_url ? `
            <div class="char-selected-model-thumb-box">
              ${currentModelInfo.media_type === 'video' ? `
                <video src="${escapeHtml(currentModelInfo.preview_url)}" class="char-selected-model-thumb" muted loop playsinline autoplay></video>
              ` : `
                <img src="${escapeHtml(currentModelInfo.preview_url)}" class="char-selected-model-thumb" alt="${escapeHtml(selectedModel)}">
              `}
            </div>
          ` : `
            <div class="char-selected-model-thumb-placeholder">🎨</div>
          `}
          <div class="char-selected-model-details">
            <div class="char-selected-model-top">
              <span class="char-selected-model-title">${escapeHtml(selectedModel)}</span>
              <span class="badge-base-family">${escapeHtml(extractModelFamily(selectedModel, currentModelInfo))}</span>
            </div>
            <div class="char-model-desc">${escapeHtml(modelDesc)}</div>
            <div class="char-model-specs">
              <span class="spec-tag">⚡ ${currentModelInfo.steps || 30} Steps</span>
              <span class="spec-tag">🎯 CFG ${currentModelInfo.cfg || 4.0}</span>
              <span class="spec-tag">📐 ${escapeHtml(currentModelInfo.aspect_ratio || '3:4')}</span>
            </div>
          </div>
        </div>
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

      <!-- Erster Auftritt & Kontinuitäts-Verankerung -->
      <div class="form-group char-first-scene-group">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
          <label style="font-size:12px;font-weight:600;display:flex;align-items:center;gap:6px;" title="${escapeHtml(t('charFirstSceneTooltip'))}">
            <span>🎬</span> <span>${escapeHtml(t('charFirstSceneLabel'))}</span>
          </label>
          <span class="badge ${char.first_scene ? 'badge-accent' : 'badge-subtle'}" style="font-size:10px;">
            ${char.first_scene ? `${escapeHtml(t('charFirstSceneManual'))}: #${char.first_scene}` : `${escapeHtml(t('charFirstSceneAuto'))}: #${detectedFirstScene}`}
          </span>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
          <input type="number" class="form-control char-first-scene-input" min="1" max="999" value="${char.first_scene || ''}" placeholder="${detectedFirstScene ? `Auto (#${detectedFirstScene})` : '1'}" style="width:120px;">
          <span style="font-size:11px;color:var(--text-dim);">${escapeHtml(t('charFirstSceneDesc'))}</span>
        </div>
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

    const firstSceneInput = card.querySelector('.char-first-scene-input');
    if (firstSceneInput) {
      firstSceneInput.addEventListener('change', () => {
        const val = parseInt(firstSceneInput.value);
        if (!isNaN(val) && val > 0) {
          char.first_scene = val;
        } else {
          delete char.first_scene;
        }
        markDirty();
        renderCharacters();
      });
    }

    // Pick Model Button & Card click
    const pickModelBtn = card.querySelector('.btn-pick-model');
    const selectedModelCard = card.querySelector('.char-selected-model-card');
    const onOpenModelPicker = () => {
      openModelPickerModal(idx, char.model || selectedModel);
    };
    if (pickModelBtn) pickModelBtn.addEventListener('click', onOpenModelPicker);
    if (selectedModelCard) selectedModelCard.addEventListener('click', (e) => {
      if (e.target.closest('.btn-pick-model')) return;
      onOpenModelPicker();
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
            description: state.screenplay.description,
            variables: state.screenplay.variables || state.screenplay.variablen || {}
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

    // Image Upload & Background Removal Handlers
    const fileInput = card.querySelector('.char-img-file-input');
    const uploadBtn = card.querySelector('.btn-trigger-upload-img');
    const removeBtn = card.querySelector('.btn-remove-char-img');
    const removeBgChk = card.querySelector('.char-removebg-chk');
    const uploadStatus = card.querySelector('.char-portrait-upload-status');

    if (uploadBtn && fileInput) {
      uploadBtn.addEventListener('click', () => fileInput.click());

      fileInput.addEventListener('change', async () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (event) => {
          const base64Data = event.target.result;
          const projectName = (el.movieFilename && el.movieFilename.value.trim()) ? el.movieFilename.value.trim() : 'film';
          const doRemoveBg = removeBgChk ? removeBgChk.checked : true;

          try {
            if (uploadStatus) {
              uploadStatus.style.display = 'flex';
            }
            if (uploadBtn) uploadBtn.disabled = true;

            const res = await API.uploadCharacterImage(projectName, char.name || `actor_${idx + 1}`, base64Data, doRemoveBg);
            if (res && res.success) {
              char.image = res.relative_path;
              char.image_url = res.image_url;
              char.auto_prompt = false;
              char.ki_prompt_generieren = false;

              renderCharacters();
              markDirty();
              showToast(t('charImgUploadSuccess').replace('{name}', char.name || ''), 'success');
            }
          } catch (err) {
            console.error('Image upload failed:', err);
            showToast(err.message || 'Fehler beim Hochladen des Charakterbildes', 'error');
            if (uploadStatus) uploadStatus.style.display = 'none';
            if (uploadBtn) uploadBtn.disabled = false;
          }
        };
        reader.readAsDataURL(file);
      });
    }

    if (removeBtn) {
      removeBtn.addEventListener('click', async () => {
        if (!confirm(t('confirmDeleteCharImg'))) return;
        const projectName = (el.movieFilename && el.movieFilename.value.trim()) ? el.movieFilename.value.trim() : 'film';

        try {
          await API.deleteCharacterImage(projectName, char.name || `actor_${idx + 1}`);
        } catch (e) {
          console.warn('Could not delete image file on server:', e);
        }

        delete char.image;
        delete char.image_url;
        char.auto_prompt = true;
        char.ki_prompt_generieren = true;

        renderCharacters();
        markDirty();
        showToast(t('charImgRemoved'), 'info');
      });
    }

    // Generate Character Portrait in ComfyUI Button Handler
    const generatePortraitBtns = card.querySelectorAll('.btn-trigger-generate-portrait');
    generatePortraitBtns.forEach(gBtn => {
      gBtn.addEventListener('click', async () => {
        const projectName = (el.movieFilename && el.movieFilename.value.trim()) ? el.movieFilename.value.trim() : 'film';
        const doRemoveBg = removeBgChk ? removeBgChk.checked : true;
        const targetSceneId = (char.first_scene && parseInt(char.first_scene) > 0) ? parseInt(char.first_scene) : detectedFirstScene;
        const vars = getVariablesForScene(state.screenplay, targetSceneId);

        try {
          if (uploadStatus) {
            uploadStatus.style.display = 'flex';
            const statusText = uploadStatus.querySelector('.char-upload-status-text');
            if (statusText) statusText.textContent = t('charGenerating') || 'Generiere Charakter-Porträt in ComfyUI...';
          }
          gBtn.disabled = true;

          const res = await API.generateCharacterPortrait(projectName, char, vars, doRemoveBg);
          if (res && res.success) {
            char.image = res.image;
            char.image_url = res.image_url;
            if (res.generated_prompt) {
              char.prompt = res.generated_prompt;
            }
            renderCharacters();
            markDirty();
            showToast((t('charGeneratedSuccess') || "Porträt für '{name}' erfolgreich in ComfyUI generiert!").replace('{name}', char.name || ''), 'success');
          }
        } catch (err) {
          console.error('Character generation failed:', err);
          showToast(err.message || 'Fehler beim Generieren des Charakterbildes', 'error');
        } finally {
          if (uploadStatus) uploadStatus.style.display = 'none';
          gBtn.disabled = false;
        }
      });
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

  function openLoraPickerModalForTurbo() {
    state.activeLoraTarget = {
      type: 'turbo',
      model: 'minimax_h3'
    };
    const modalTitleElem = el.loraModal.querySelector('.modal-title');
    if (modalTitleElem) {
      modalTitleElem.textContent = t('btnPickTurboLora') || '⚡ Turbo-LoRA auswählen';
    }
    el.modalActiveModelName.textContent = 'Minimax H3 / Turbo';
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
    } else if (target.type === 'turbo') {
      const cur = el.settingTurboLoraInput ? el.settingTurboLoraInput.value.toLowerCase().trim() : '';
      if (cur) currentAssignedLoras = [cur];
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
        const tModel = (target.model || '').toLowerCase();
        isCompat = compatList.length === 0 ||
          compatList.includes(target.model) ||
          compatList.some(m => {
            const mLow = m.toLowerCase();
            if (mLow === 'all' || mLow === '*' || mLow === tModel) return true;
            if (mLow.startsWith('anima') && tModel.startsWith('anima')) return true;
            if (mLow.startsWith('krea') && tModel.startsWith('krea')) return true;
            if (mLow.startsWith('sdxl') && (tModel.startsWith('anima') || tModel.startsWith('sdxl'))) return true;
            if (mLow.startsWith('zimage') && tModel.startsWith('zimage')) return true;
            return false;
          });
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
      } else if (target.type === 'turbo') {
        const isTurbo = turboExcludes.includes(lKeyLower) ||
          lKeyLower.includes('turbo') ||
          lNameLower.includes('turbo') ||
          lKeyLower.includes('lightx2v') ||
          lNameLower.includes('lightx2v') ||
          lKeyLower.includes('step') ||
          lNameLower.includes('step') ||
          compatList.includes('minimax_h3') ||
          lNameLower.includes('minimax');
        isCompat = isTurbo;
      }

      if (!isCompat && !showAll) {
        continue;
      }

      const searchHaystack = `${lKey} ${lora.beschreibung || ''} ${lora.trigger_words || ''} ${lora.published_at || ''} ${compatList.join(' ')}`.toLowerCase();
      if (query && !searchHaystack.includes(query)) {
        continue;
      }

      countShown++;
      const isAlreadyAssigned = target.type === 'turbo'
        ? (currentAssignedLoras.some(c => c && (c === lKeyLower || (lora.lora_name && c.includes(lora.lora_name.toLowerCase())) || lKeyLower.includes(c))))
        : currentAssignedLoras.includes(lKey);
      const card = document.createElement('div');
      card.className = `lora-card-item ${isCompat ? 'compatible' : ''} ${isAlreadyAssigned ? 'selected' : ''}`;

      const strengthModel = lora.strength_model !== undefined ? lora.strength_model : (target.type === 'scene' ? 1.0 : 0.8);
      const triggers = lora.trigger_words ? `<div style="font-size:10px;color:var(--accent-cyan);margin-top:2px;">Triggers: <code>${escapeHtml(lora.trigger_words)}</code></div>` : '';

      const compatBadgeText = target.type === 'turbo'
        ? (isCompat ? '⚡ Turbo LoRA' : escapeHtml(t('otherModelBadge')))
        : target.type === 'scene'
          ? (isCompat ? escapeHtml(t('videoCompatBadge')) : escapeHtml(t('otherModelBadge')))
          : (isCompat ? escapeHtml(t('compatBadge')) : escapeHtml(t('otherModelBadge')));

      const itemIcon = target.type === 'turbo' ? '⚡' : (target.type === 'scene' ? '🎬' : '✨');

      let mediaHtml = '';
      if (lora.preview_url) {
        if (lora.media_type === 'video') {
          mediaHtml = `
            <div class="lora-card-media">
              <video class="lora-media-thumb lora-media-video" src="${escapeHtml(lora.preview_url)}" muted loop playsinline preload="metadata"></video>
              <span class="lora-video-badge">▶ ${escapeHtml(t('videoBadge') || 'Video')}</span>
              ${lora.published_at ? `<span class="lora-date-badge" title="${escapeHtml(t('loraPublishedDate') || 'Published:')} ${escapeHtml(lora.published_at)}">📅 ${escapeHtml(lora.published_at)}</span>` : ''}
            </div>
          `;
        } else {
          mediaHtml = `
            <div class="lora-card-media">
              <img class="lora-media-thumb" src="${escapeHtml(lora.preview_url)}" alt="${escapeHtml(lKey)}" loading="lazy">
              ${lora.published_at ? `<span class="lora-date-badge" title="${escapeHtml(t('loraPublishedDate') || 'Published:')} ${escapeHtml(lora.published_at)}">📅 ${escapeHtml(lora.published_at)}</span>` : ''}
            </div>
          `;
        }
      } else {
        mediaHtml = `
          <div class="lora-card-media lora-media-placeholder">
            <span class="lora-placeholder-icon">${itemIcon}</span>
            ${lora.published_at ? `<span class="lora-date-badge" title="${escapeHtml(t('loraPublishedDate') || 'Published:')} ${escapeHtml(lora.published_at)}">📅 ${escapeHtml(lora.published_at)}</span>` : ''}
          </div>
        `;
      }

      card.innerHTML = `
        ${mediaHtml}
        <div class="lora-card-body">
          <div class="lora-card-title">
            <span>${itemIcon} ${escapeHtml(lKey)}</span>
            <span style="font-size:11px;">${isAlreadyAssigned ? escapeHtml(t('activeBadge')) : '➕'}</span>
          </div>
          <div class="lora-card-desc" title="${escapeHtml(lora.beschreibung || '')}">${escapeHtml(lora.beschreibung || '')}</div>
          ${triggers}
          <div class="lora-card-footer">
            <span class="${isCompat ? 'lora-badge-compat' : ''}">
              ${compatBadgeText}
            </span>
            <span>${escapeHtml(t('strengthLabel'))}: ${strengthModel}</span>
          </div>
        </div>
      `;

      const vidEl = card.querySelector('video');
      if (vidEl) {
        card.addEventListener('mouseenter', () => {
          vidEl.play().catch(() => {});
        });
        card.addEventListener('mouseleave', () => {
          vidEl.pause();
          vidEl.currentTime = 0;
        });
      }

      card.addEventListener('click', () => {
        if (target.type === 'turbo') {
          const selectedLoraPath = lora.lora_name || lKey;
          if (el.settingTurboLoraInput) el.settingTurboLoraInput.value = selectedLoraPath;
          if (el.settingTurboLoraSelect) {
            let matched = false;
            for (const opt of el.settingTurboLoraSelect.options) {
              if (opt.value === selectedLoraPath || opt.value.toLowerCase().includes(lKey.toLowerCase()) || (lora.lora_name && opt.value.toLowerCase().includes(lora.lora_name.toLowerCase()))) {
                el.settingTurboLoraSelect.value = opt.value;
                matched = true;
                break;
              }
            }
            if (!matched && selectedLoraPath) {
              const newOpt = document.createElement('option');
              newOpt.value = selectedLoraPath;
              newOpt.textContent = selectedLoraPath;
              el.settingTurboLoraSelect.appendChild(newOpt);
              el.settingTurboLoraSelect.value = selectedLoraPath;
            }
          }
          // Auto-detect steps (4 or 8)
          const combined = (lKey + ' ' + (lora.lora_name || '')).toLowerCase();
          if (combined.includes('4step') || combined.includes('4_step') || combined.includes('4 step') || combined.includes('4-step') || combined.includes('4s')) {
            if (el.settingMinimaxSteps) el.settingMinimaxSteps.value = 4;
          } else if (combined.includes('8step') || combined.includes('8_step') || combined.includes('8 step') || combined.includes('8-step') || combined.includes('8s')) {
            if (el.settingMinimaxSteps) el.settingMinimaxSteps.value = 8;
          }
          closeLoraPickerModal();
          return;
        }

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

  // --- Model Picker Modal ---
  function extractModelFamily(key, info) {
    const k = (key || '').toLowerCase();
    if (k.includes('anima')) return 'Anima';
    if (k.includes('krea')) return 'Krea';
    if (k.includes('sdxl')) return 'SDXL';
    if (k.includes('zimage') || k.includes('zit') || k.includes('z-image')) return 'Z-Image';
    if (k.includes('flux')) return 'Flux';
    if (k.includes('wan') || k.includes('i2v')) return 'Video';
    if (k.includes('minimax') || k.includes('mmh3')) return 'Minimax';
    if (info && info.clip_type) return info.clip_type;
    return 'Base';
  }

  function openModelPickerModal(charIndex, activeModelKey) {
    state.activeModelTargetCharIndex = charIndex;
    state.modelFilterCategory = 'all';

    const char = state.screenplay.characters[charIndex];
    const charName = char ? (char.name || `#${charIndex + 1}`) : '';
    const modalTitleElem = el.modelModal.querySelector('.modal-title');
    if (modalTitleElem) {
      modalTitleElem.textContent = t('modalModelTitle') + (charName ? ` (${charName})` : '');
    }
    if (el.modalActiveCharName) {
      el.modalActiveCharName.textContent = charName || '-';
    }
    if (el.modalCurrentModelKey) {
      el.modalCurrentModelKey.textContent = activeModelKey || '-';
    }
    if (el.modelSearchInput) {
      el.modelSearchInput.value = '';
    }

    // Reset filter tabs
    if (el.modelFilterTabs) {
      el.modelFilterTabs.querySelectorAll('.btn-filter-pill').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filter === 'all');
      });
    }

    renderModelModalCards();
    el.modelModal.classList.add('open');
  }

  function closeModelPickerModal() {
    if (el.modelModal) el.modelModal.classList.remove('open');
    state.activeModelTargetCharIndex = null;
  }

  function renderModelModalCards() {
    if (state.activeModelTargetCharIndex === null) return;
    const charIndex = state.activeModelTargetCharIndex;
    const char = state.screenplay.characters[charIndex];
    if (!char) return;

    const currentModel = char.model || state.presetsData.default || 'anima_catpony';
    el.modelCardsList.innerHTML = '';
    const presets = state.presetsData.presets || {};
    const query = el.modelSearchInput ? el.modelSearchInput.value.toLowerCase().trim() : '';
    const category = state.modelFilterCategory || 'all';

    const keys = Object.keys(presets);
    if (keys.length === 0) {
      el.modelCardsList.innerHTML = `<div style="color:var(--text-dim);font-style:italic;">${escapeHtml(t('noModelsFound'))}</div>`;
      return;
    }

    let countShown = 0;

    for (const mKey of keys) {
      const mVal = presets[mKey] || {};
      const family = extractModelFamily(mKey, mVal);
      const mKeyLower = mKey.toLowerCase();
      const descLower = (mVal.beschreibung || '').toLowerCase();
      const unetLower = (mVal.unet_name || '').toLowerCase();

      // Category filter
      if (category !== 'all') {
        const famLower = family.toLowerCase();
        if (category === 'anima' && !famLower.includes('anima') && !mKeyLower.includes('anima')) continue;
        if (category === 'krea' && !famLower.includes('krea') && !mKeyLower.includes('krea')) continue;
        if (category === 'sdxl' && !famLower.includes('sdxl') && !mKeyLower.includes('sdxl')) continue;
        if (category === 'zimage' && !famLower.includes('zimage') && !mKeyLower.includes('zimage') && !mKeyLower.includes('zit')) continue;
        if (category === 'other') {
          if (mKeyLower.includes('anima') || mKeyLower.includes('krea') || mKeyLower.includes('sdxl') || mKeyLower.includes('zimage') || mKeyLower.includes('zit')) {
            continue;
          }
        }
      }

      // Search query filter
      if (query) {
        const searchHaystack = `${mKeyLower} ${descLower} ${unetLower} ${family.toLowerCase()} ${mVal.sampler_name || ''} ${mVal.scheduler || ''}`;
        if (!searchHaystack.includes(query)) continue;
      }

      countShown++;
      const isSelected = mKey === currentModel;
      const card = document.createElement('div');
      card.className = `model-card-item ${isSelected ? 'selected' : ''}`;

      let mediaHtml = '';
      if (mVal.preview_url) {
        if (mVal.media_type === 'video') {
          mediaHtml = `
            <div class="model-card-media">
              <video class="model-media-thumb" src="${escapeHtml(mVal.preview_url)}" muted loop playsinline preload="metadata"></video>
              <span class="model-video-badge">▶ ${escapeHtml(t('videoBadge') || 'Video')}</span>
              ${mVal.published_at ? `<span class="model-date-badge">📅 ${escapeHtml(mVal.published_at)}</span>` : ''}
            </div>
          `;
        } else {
          mediaHtml = `
            <div class="model-card-media">
              <img class="model-media-thumb" src="${escapeHtml(mVal.preview_url)}" alt="${escapeHtml(mKey)}" loading="lazy">
              ${mVal.published_at ? `<span class="model-date-badge">📅 ${escapeHtml(mVal.published_at)}</span>` : ''}
            </div>
          `;
        }
      } else {
        mediaHtml = `
          <div class="model-card-media model-media-placeholder">
            <span class="model-placeholder-icon">🎨</span>
            ${mVal.published_at ? `<span class="model-date-badge">📅 ${escapeHtml(mVal.published_at)}</span>` : ''}
          </div>
        `;
      }

      card.innerHTML = `
        ${mediaHtml}
        <div class="model-card-body">
          <div class="model-card-title">
            <span>🎨 ${escapeHtml(mKey)}</span>
            ${isSelected ? `<span class="model-badge-selected">✔ ${escapeHtml(t('modelSelectedBadge') || 'Aktiv')}</span>` : `<span class="badge-base-family">${escapeHtml(family)}</span>`}
          </div>
          <div class="model-card-desc" title="${escapeHtml(mVal.beschreibung || '')}">${escapeHtml(mVal.beschreibung || '')}</div>
          <div class="model-card-footer">
            <span>⚡ ${mVal.steps || 30} Steps | CFG ${mVal.cfg || 4.0}</span>
            <span>📐 ${escapeHtml(mVal.aspect_ratio || '3:4')}</span>
          </div>
        </div>
      `;

      const vidEl = card.querySelector('video');
      if (vidEl) {
        card.addEventListener('mouseenter', () => {
          vidEl.play().catch(() => {});
        });
        card.addEventListener('mouseleave', () => {
          vidEl.pause();
          vidEl.currentTime = 0;
        });
      }

      // Single Choice Click Handler: select this model, update character and close modal
      card.addEventListener('click', () => {
        char.model = mKey;
        renderCharacters();
        markDirty();
        closeModelPickerModal();
        showToast(t('modelSelected').replace('{name}', mKey).replace('{char}', char.name || `#${charIndex + 1}`), 'success');
      });

      el.modelCardsList.appendChild(card);
    }

    if (countShown === 0) {
      el.modelCardsList.innerHTML = `<div style="color:var(--text-dim);font-style:italic;padding:12px;">${escapeHtml(t('noModelsFound'))}</div>`;
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
      renderStoryboardTimeline();
      return;
    }

    scenes.forEach((scene, idx) => {
      const card = createSceneCard(scene, idx, scenes);
      el.scenesContainer.appendChild(card);
    });
    renderStoryboardTimeline();
  }

  function createSceneCard(scene, idx, allScenes) {
    const card = document.createElement('div');
    card.className = 'scene-card';
    card.id = `sceneCard_${scene.id || (idx + 1)}`;
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
          <button class="btn btn-primary-outline btn-xs btn-play-scene" title="${escapeHtml(t('btn_preview_scene') || 'Clip ansehen')}">▶️</button>
          <button class="btn btn-secondary btn-xs btn-reshoot-scene" title="${escapeHtml(t('btn_reshoot_scene') || 'Szene neu drehen')}">🔄</button>
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

      <!-- Regie & Render-Einstellungen (Director's Control) -->
      <div class="scene-render-settings">
        <div class="scene-render-settings-header">
          <label>⚙️ ${escapeHtml(t('sceneRenderSettings'))}</label>
        </div>
        <div class="scene-render-grid">
          <div class="render-field">
            <span class="render-field-label">${escapeHtml(t('sceneTurboLabel'))}:</span>
            <select class="select-input select-xs scene-turbo-select">
              <option value="auto" ${scene.turbo === undefined || scene.turbo === null ? 'selected' : ''}>${escapeHtml(t('sceneTurboAuto'))}</option>
              <option value="on" ${scene.turbo === true ? 'selected' : ''}>${escapeHtml(t('sceneTurboOn'))}</option>
              <option value="off" ${scene.turbo === false ? 'selected' : ''}>${escapeHtml(t('sceneTurboOff'))}</option>
            </select>
          </div>
          <div class="render-field">
            <span class="render-field-label">${escapeHtml(t('sceneResolutionLabel'))}:</span>
            <select class="select-input select-xs scene-res-select">
              <option value="auto" ${!scene.megapixels || scene.megapixels === 0.25 ? 'selected' : ''}>${escapeHtml(t('sceneResAuto'))}</option>
              <option value="0.45" ${scene.megapixels === 0.45 || scene.megapixels === '0.45' ? 'selected' : ''}>${escapeHtml(t('sceneResHigh'))}</option>
              <option value="0.75" ${scene.megapixels === 0.75 || scene.megapixels === '0.75' ? 'selected' : ''}>${escapeHtml(t('sceneResNativeHd'))}</option>
            </select>
          </div>
          <div class="render-field">
            <span class="render-field-label">${escapeHtml(t('sceneUpscaleLabel'))}:</span>
            <select class="select-input select-xs scene-upscale-select">
              <option value="auto" ${scene.upscale !== false ? 'selected' : ''}>${escapeHtml(t('sceneUpscaleAuto'))}</option>
              <option value="off" ${scene.upscale === false ? 'selected' : ''}>${escapeHtml(t('sceneUpscaleOff'))}</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Szenenübergänge / Cinematic Transitions -->
      <div class="scene-transition-section">
        <div class="scene-transition-header">
          <label>🎬 ${escapeHtml(t('transition_label') || 'Übergang zur nächsten Szene')}</label>
        </div>
        <div class="scene-transition-grid">
          <div class="transition-field">
            <select class="select-input select-xs scene-transition-select">
              <option value="cut" ${scene.transition === 'cut' || !scene.transition ? 'selected' : ''}>${escapeHtml(t('transition_cut') || 'Harter Schnitt (Cut)')}</option>
              <option value="dissolve" ${scene.transition === 'dissolve' || scene.transition === 'fade' ? 'selected' : ''}>${escapeHtml(t('transition_dissolve') || 'Weiche Blende (Crossfade / Dissolve)')}</option>
              <option value="fadeblack" ${scene.transition === 'fadeblack' || scene.transition === 'fade_to_black' ? 'selected' : ''}>${escapeHtml(t('transition_fadeblack') || 'Schwarzblende (Fade to Black)')}</option>
              <option value="fadewhite" ${scene.transition === 'fadewhite' || scene.transition === 'dip_to_white' ? 'selected' : ''}>${escapeHtml(t('transition_fadewhite') || 'Weißblende (Dip to White)')}</option>
              <option value="wipeleft" ${scene.transition === 'wipeleft' ? 'selected' : ''}>${escapeHtml(t('transition_wipeleft') || 'Wischblende Links (Wipe Left)')}</option>
              <option value="wiperight" ${scene.transition === 'wiperight' ? 'selected' : ''}>${escapeHtml(t('transition_wiperight') || 'Wischblende Rechts (Wipe Right)')}</option>
            </select>
          </div>
          <div class="transition-duration-field">
            <span class="render-field-label">${escapeHtml(t('transition_duration_label') || 'Dauer (s):')}</span>
            <input type="number" class="scene-transition-duration-input" min="0.2" max="3.0" step="0.1" value="${scene.transition_duration || 0.75}">
          </div>
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
      if ('prompt' in scene || ideaTextarea.value.includes('summary:')) {
        scene.prompt = ideaTextarea.value;
      }
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
        if ('prompt' in scene || ideaTextarea.value.includes('summary:')) {
          scene.prompt = ideaTextarea.value;
        }
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

          // Calculate cumulative variables up to this scene from global variables + preceding scene updates
          const cumulativeVars = Object.assign({}, state.screenplay.variables || {});
          for (let i = 0; i < idx; i++) {
            const sc = allScenes[i];
            const up = sc.variables_update || sc.variablen_update || sc.set_variables;
            if (up && typeof up === 'object') {
              Object.assign(cumulativeVars, up);
            } else if (typeof up === 'string' && up.trim()) {
              try {
                const parsed = JSON.parse(up);
                if (typeof parsed === 'object') Object.assign(cumulativeVars, parsed);
              } catch (e) {
                const parts = up.split(':');
                if (parts.length >= 2) {
                  cumulativeVars[parts[0].trim()] = parts.slice(1).join(':').trim();
                }
              }
            }
          }

          // Extract preceding scenes for continuity context (including variable updates)
          const precedingScenes = allScenes.slice(0, idx).map(s => ({
            id: s.id,
            sequence: s.sequence || '',
            location: s.location || '',
            idea: s.idea || '',
            duration: s.duration || 6,
            match_cut: Boolean(s.match_cut),
            same_scene: Boolean(s.same_scene),
            use_previous_scene: Boolean(s.use_previous_scene),
            variables_update: s.variables_update || {}
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
            variables: cumulativeVars,
            active_variables: cumulativeVars,
            global_variables: state.screenplay.variables,
            characters: scene.characters || state.screenplay.characters
          });
          if (res && (res.scene || res.elaborated_idea)) {
            const sc = res.scene || {};
            let newIdea = sc.idea || res.elaborated_idea;
            if (newIdea) {
              newIdea = newIdea.replace(/^\[Shot \d+\]:?\s*/i, '').trim();
              scene.idea = newIdea;
              scene.prompt = newIdea;
            }
            const newSummary = sc.summary || res.summary;
            if (newSummary) scene.summary = newSummary;
            const newSoundscape = sc.soundscape || res.soundscape;
            if (newSoundscape) scene.soundscape = newSoundscape;
            const newDur = sc.duration || res.duration;
            if (newDur) scene.duration = newDur;
            const newLoras = sc.loras || res.loras;
            if (Array.isArray(newLoras) && newLoras.length > 0) {
              scene.loras = newLoras;
            }
            const newVars = sc.variables_update || res.variables_update;
            if (newVars && typeof newVars === 'object' && Object.keys(newVars).length > 0) {
              scene.variables_update = Object.assign({}, scene.variables_update || {}, newVars);
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

    // Render Settings Listeners
    const turboSelect = card.querySelector('.scene-turbo-select');
    if (turboSelect) {
      turboSelect.addEventListener('change', () => {
        const val = turboSelect.value;
        if (val === 'auto') {
          delete scene.turbo;
          delete scene.steps;
        } else if (val === 'on') {
          scene.turbo = true;
          scene.steps = 8;
        } else if (val === 'off') {
          scene.turbo = false;
          scene.steps = 20;
        }
        markDirty();
      });
    }

    const resSelect = card.querySelector('.scene-res-select');
    if (resSelect) {
      resSelect.addEventListener('change', () => {
        const val = resSelect.value;
        if (val === 'auto') {
          delete scene.megapixels;
        } else {
          scene.megapixels = parseFloat(val);
        }
        markDirty();
      });
    }

    const upscaleSelect = card.querySelector('.scene-upscale-select');
    if (upscaleSelect) {
      upscaleSelect.addEventListener('change', () => {
        const val = upscaleSelect.value;
        if (val === 'auto') {
          delete scene.upscale;
        } else if (val === 'off') {
          scene.upscale = false;
        }
        markDirty();
      });
    }

    // Transition Listeners
    const transSelect = card.querySelector('.scene-transition-select');
    if (transSelect) {
      transSelect.addEventListener('change', () => {
        scene.transition = transSelect.value;
        renderStoryboardTimeline();
        markDirty();
      });
    }

    const transDurInput = card.querySelector('.scene-transition-duration-input');
    if (transDurInput) {
      transDurInput.addEventListener('change', () => {
        scene.transition_duration = parseFloat(transDurInput.value) || 0.75;
        renderStoryboardTimeline();
        markDirty();
      });
    }

    // Play Clip in Player Modal
    const playBtn = card.querySelector('.btn-play-scene');
    if (playBtn) {
      playBtn.addEventListener('click', () => {
        const projName = (el.movieFilename && el.movieFilename.value.trim()) || 'film';
        const videoUrl = `/api/scene/video?project=${encodeURIComponent(projName)}&scene=${sceneId}&t=${Date.now()}`;
        openVideoPlayerModal(videoUrl, `Szene #${sceneId} (${duration}s)`, duration);
      });
    }

    // Re-shoot Scene Button
    const reshootBtn = card.querySelector('.btn-reshoot-scene');
    if (reshootBtn) {
      reshootBtn.addEventListener('click', async () => {
        const confirmMsg = (t('reshoot_confirm') || 'Möchtest du Szene {id} wirklich neu rendern?').replace('{id}', sceneId);
        if (!confirm(confirmMsg)) return;

        const projName = (el.movieFilename && el.movieFilename.value.trim()) || 'film';
        try {
          reshootBtn.disabled = true;
          reshootBtn.innerHTML = '⏳';
          if (state.isDirty) {
            await saveCurrentProject();
          }
          const res = await API.reshootScene(projName, sceneId);
          showToast(res.message || (t('reshoot_started') || 'Dreh gestartet...').replace('{id}', sceneId), 'info');
          setTimeout(() => {
            fetchAndRenderTimeline();
          }, 3000);
        } catch (err) {
          showToast(err.message, 'error');
        } finally {
          reshootBtn.disabled = false;
          reshootBtn.innerHTML = '🔄';
        }
      });
    }

    return card;
  }

  function reindexScenes() {
    const scenes = state.screenplay.scenes || [];
    scenes.forEach((s, idx) => {
      s.id = idx + 1;
    });
  }

  // --- Storyboard Filmstrip Timeline & Video Player Methods ---
  async function fetchAndRenderTimeline() {
    const projName = (el.movieFilename && el.movieFilename.value.trim()) || 'film';
    if (!projName) return;

    try {
      const statusData = await API.getScenesStatus(projName);
      if (statusData && statusData.success) {
        state.scenesStatus = statusData;
        renderStoryboardTimeline();
      }
    } catch (err) {
      console.warn('Could not fetch scene render status:', err);
      renderStoryboardTimeline();
    }
  }

  function renderStoryboardTimeline() {
    if (!el.filmstripTrack) return;
    el.filmstripTrack.innerHTML = '';

    const scenes = state.screenplay.scenes || [];
    const statusMap = {};
    if (state.scenesStatus && Array.isArray(state.scenesStatus.scenes)) {
      for (const sc of state.scenesStatus.scenes) {
        statusMap[sc.id] = sc;
      }
    }

    const projName = (el.movieFilename && el.movieFilename.value.trim()) || 'film';

    let totalSecs = 0;
    let renderedCount = 0;

    scenes.forEach((sc, idx) => {
      const d = parseFloat(sc.duration || 6);
      totalSecs += d;
      if (idx < scenes.length - 1 && sc.transition && sc.transition !== 'cut' && sc.transition !== 'none') {
        const td = parseFloat(sc.transition_duration || 0.75);
        totalSecs -= Math.min(td, d / 2.0);
      }
      const st = statusMap[sc.id || (idx + 1)];
      if (st && st.has_video) renderedCount++;
    });

    if (el.timelineStatsBadge) {
      el.timelineStatsBadge.textContent = `${totalSecs.toFixed(1)}s • ${renderedCount}/${scenes.length} ${t('timeline_ready') || 'Gerendert'}`;
    }

    if (el.btnPlayFullMovie) {
      if (state.scenesStatus && state.scenesStatus.movie_ready) {
        el.btnPlayFullMovie.style.display = 'inline-flex';
        el.btnPlayFullMovie.onclick = () => {
          const mUrl = state.scenesStatus.movie_url + '&t=' + Date.now();
          const title = state.screenplay.title || projName;
          openVideoPlayerModal(mUrl, `🎬 ${title} (FINAL)`, totalSecs.toFixed(1));
        };
      } else {
        el.btnPlayFullMovie.style.display = 'none';
      }
    }

    if (scenes.length === 0) {
      el.filmstripTrack.innerHTML = `<span style="color:var(--text-dim);font-size:12px;font-style:italic;">${escapeHtml(t('timeline_no_scenes') || 'Noch keine Szenen im Drehbuch.')}</span>`;
      return;
    }

    scenes.forEach((scene, idx) => {
      const sceneId = scene.id || (idx + 1);
      const st = statusMap[sceneId];
      const hasVid = st && st.has_video;
      const hasPrev = st && st.has_preview;
      const duration = scene.duration || 6;
      const seq = scene.sequence || scene.sequenz || `Szene ${sceneId}`;

      const cell = document.createElement('div');
      cell.className = `filmstrip-cell ${hasVid ? 'rendered' : ''}`;
      cell.title = `${t('timeline_jump_to_scene') || 'Zu Szene {id} springen'}`.replace('{id}', sceneId);

      const previewUrl = (st && st.preview_url) ? st.preview_url : `/api/scene/preview?project=${encodeURIComponent(projName)}&scene=${sceneId}&t=${Date.now()}`;
      const videoUrl = (st && st.video_url) ? st.video_url : `/api/scene/video?project=${encodeURIComponent(projName)}&scene=${sceneId}&t=${Date.now()}`;

      let thumbHtml = '';
      if (hasPrev) {
        thumbHtml = `<img src="${previewUrl}" class="filmstrip-thumb-img" alt="Szene ${sceneId}" onerror="this.style.display='none'">`;
      } else {
        thumbHtml = `
          <div class="filmstrip-placeholder">
            <span style="font-size:14px;margin-bottom:2px;">🎬</span>
            <span style="font-weight:600;font-size:10px;">${escapeHtml(seq)}</span>
          </div>
        `;
      }

      cell.innerHTML = `
        ${thumbHtml}
        <div class="filmstrip-cell-topbar">
          <span class="filmstrip-scene-badge">#${sceneId}</span>
          <span class="filmstrip-status-pill ${hasVid ? 'ready' : 'pending'}">${hasVid ? (t('timeline_ready') || 'Gerendert') : (t('timeline_not_rendered') || 'Offen')}</span>
        </div>
        ${hasVid ? `<div class="filmstrip-play-overlay" title="${escapeHtml(t('timeline_play_scene') || 'Szene im Player ansehen')}">▶</div>` : ''}
        <div class="filmstrip-cell-bottombar">
          <span class="filmstrip-cell-seq">${escapeHtml(seq)}</span>
          <span class="filmstrip-cell-dur">${duration}s</span>
        </div>
      `;

      cell.addEventListener('click', (e) => {
        if (e.target.closest('.filmstrip-play-overlay') || (hasVid && e.shiftKey)) {
          openVideoPlayerModal(videoUrl, `Szene #${sceneId}: ${seq}`, duration);
        } else {
          const targetCard = document.getElementById(`sceneCard_${sceneId}`);
          if (targetCard) {
            targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            targetCard.style.outline = '2px solid var(--accent-blue, #38bdf8)';
            targetCard.style.boxShadow = '0 0 20px rgba(56, 189, 248, 0.5)';
            setTimeout(() => {
              targetCard.style.outline = '';
              targetCard.style.boxShadow = '';
            }, 1600);
          }
        }
      });

      el.filmstripTrack.appendChild(cell);

      // Add Transition Badge between scene idx and idx + 1
      if (idx < scenes.length - 1) {
        const transType = scene.transition || 'cut';
        const transDur = scene.transition_duration || 0.75;
        const isCut = transType === 'cut' || transType === 'none';

        const transBadge = document.createElement('div');
        transBadge.className = `filmstrip-transition-badge ${isCut ? '' : 'custom'}`;

        let transIcon = '✂️';
        let transName = 'CUT';
        if (transType === 'dissolve' || transType === 'fade') {
          transIcon = '🌫️';
          transName = `DISSOLVE (${transDur}s)`;
        } else if (transType === 'fadeblack') {
          transIcon = '🌑';
          transName = `FADE BLACK (${transDur}s)`;
        } else if (transType === 'fadewhite') {
          transIcon = '⚪';
          transName = `DIP WHITE (${transDur}s)`;
        } else if (transType === 'wipeleft') {
          transIcon = '◀️';
          transName = `WIPE LEFT (${transDur}s)`;
        } else if (transType === 'wiperight') {
          transIcon = '▶️';
          transName = `WIPE RIGHT (${transDur}s)`;
        }

        transBadge.innerHTML = `<span>${transIcon}</span> <span>${escapeHtml(transName)}</span>`;
        transBadge.title = `${escapeHtml(t('transition_label') || 'Übergang')}: ${transName}`;

        transBadge.addEventListener('click', () => {
          const sequence = ['cut', 'dissolve', 'fadeblack', 'fadewhite', 'wipeleft'];
          const currentIdx = sequence.indexOf(scene.transition || 'cut');
          const nextTrans = sequence[(currentIdx + 1) % sequence.length];
          scene.transition = nextTrans;
          if (!scene.transition_duration) scene.transition_duration = 0.75;

          const cardElem = document.getElementById(`sceneCard_${sceneId}`);
          if (cardElem) {
            const sel = cardElem.querySelector('.scene-transition-select');
            if (sel) sel.value = nextTrans;
          }

          renderStoryboardTimeline();
          markDirty();
          showToast(`Übergang Szene #${sceneId} -> #${sceneId + 1}: ${nextTrans}`, 'info');
        });

        el.filmstripTrack.appendChild(transBadge);
      }
    });
  }

  function openVideoPlayerModal(videoUrl, title, duration) {
    if (!el.videoPlayerModal || !el.modalVideoElement) return;
    if (el.videoModalTitle) el.videoModalTitle.textContent = `▶️ ${title}`;
    if (el.videoMetaTitle) el.videoMetaTitle.textContent = title;
    if (el.videoMetaDuration) el.videoMetaDuration.textContent = duration ? `${duration}s` : '';
    if (el.videoDownloadLink) el.videoDownloadLink.href = videoUrl;

    el.modalVideoElement.src = videoUrl;
    el.modalVideoElement.load();
    el.videoPlayerModal.classList.add('open');
    el.modalVideoElement.play().catch(() => {});
  }

  function closeVideoPlayerModal() {
    if (!el.videoPlayerModal || !el.modalVideoElement) return;
    el.modalVideoElement.pause();
    el.modalVideoElement.removeAttribute('src');
    el.modalVideoElement.load();
    el.videoPlayerModal.classList.remove('open');
  }

  function toggleVideoPlayer() {
    if (!el.videoPlayerModal) return;
    if (el.videoPlayerModal.classList.contains('open')) {
      closeVideoPlayerModal();
      return;
    }

    const projName = (el.movieFilename && el.movieFilename.value.trim()) || 'film';
    const title = (el.movieTitle && el.movieTitle.value.trim()) || projName;

    // 1. If full movie is ready, play full movie
    if (state.scenesStatus && state.scenesStatus.movie_ready && state.scenesStatus.movie_url) {
      const mUrl = state.scenesStatus.movie_url + '&t=' + Date.now();
      const totalSecs = (state.scenesStatus.scenes || []).reduce((acc, s) => acc + (s.duration || 6), 0);
      openVideoPlayerModal(mUrl, `🎬 ${title} (FINAL)`, totalSecs.toFixed(1));
      return;
    }

    // 2. If any rendered scene exists, play first available rendered scene
    const scenes = state.screenplay.scenes || [];
    const statusMap = (state.scenesStatus && state.scenesStatus.scenes)
      ? Object.fromEntries(state.scenesStatus.scenes.map(s => [s.id, s]))
      : {};

    const readyScene = scenes.find(s => statusMap[s.id] && statusMap[s.id].has_video);
    if (readyScene) {
      const st = statusMap[readyScene.id];
      const videoUrl = (st && st.video_url) ? st.video_url : `/api/scene/video?project=${encodeURIComponent(projName)}&scene=${readyScene.id}&t=${Date.now()}`;
      const seq = readyScene.sequence || readyScene.sequenz || `Szene ${readyScene.id}`;
      openVideoPlayerModal(videoUrl, `Szene #${readyScene.id}: ${seq}`, readyScene.duration || 6);
      return;
    }

    // 3. If there is already a source in modalVideoElement
    if (el.modalVideoElement && el.modalVideoElement.src) {
      el.videoPlayerModal.classList.add('open');
      el.modalVideoElement.play().catch(() => {});
      return;
    }

    // 4. No video available yet
    showToast(t('video_no_rendered_found') || 'Noch kein Video gerendert. Klicke auf "Film rendern" oder starte das Rendering im Storyboard.', 'info');
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

  // --- Music Studio Methods ---
  let availableMusicModels = [];

  async function loadMusicModels() {
    if (!el.musicModelSelect) return;
    try {
      const data = await API.getMusicModels();
      availableMusicModels = data.models || [];
      el.musicModelSelect.innerHTML = '';

      if (availableMusicModels.length === 0) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = state.lang === 'en' ? 'No music models found' : 'Keine Musik-Modelle gefunden';
        el.musicModelSelect.appendChild(opt);
        return;
      }

      for (const m of availableMusicModels) {
        const opt = document.createElement('option');
        opt.value = m.filename;
        opt.textContent = `${m.title} (${m.type}) - ${m.filename}`;
        el.musicModelSelect.appendChild(opt);
      }

      // If current screenplay has a music model configured, select it
      if (state.screenplay.music && state.screenplay.music.model) {
        el.musicModelSelect.value = state.screenplay.music.model;
      } else if (data.default_model) {
        el.musicModelSelect.value = data.default_model;
        if (state.screenplay.music) state.screenplay.music.model = data.default_model;
      }
    } catch (e) {
      console.warn('Fehler beim Laden der Musik-Modelle:', e);
    }
  }

  async function renderMusicStudio() {
    if (!state.screenplay.music) {
      state.screenplay.music = {
        enabled: false,
        model: availableMusicModels[0]?.filename || '',
        prompt: '',
        volume: 0.22,
        ducking: true
      };
    }
    const m = state.screenplay.music;

    if (el.chkMusicEnabled) {
      el.chkMusicEnabled.checked = Boolean(m.enabled);
    }
    if (el.musicModelSelect && m.model) {
      el.musicModelSelect.value = m.model;
    }
    if (el.musicPromptInput) {
      el.musicPromptInput.value = m.prompt || '';
    }
    if (el.musicVolumeSelect && m.volume !== undefined) {
      el.musicVolumeSelect.value = String(m.volume);
    }
    if (el.chkMusicDucking) {
      el.chkMusicDucking.checked = m.ducking !== undefined ? Boolean(m.ducking) : true;
    }

    // Check if soundtrack file exists for current project
    const projName = (el.movieFilename && el.movieFilename.value.trim()) || (state.currentFilename ? state.currentFilename.replace('.json', '') : '');
    if (projName && el.musicPlayerWrapper && el.audioSoundtrackPlayer && el.linkDownloadSoundtrack) {
      const audioUrl = `/api/music/soundtrack?project=${encodeURIComponent(projName)}&t=${Date.now()}`;
      try {
        const resp = await fetch(audioUrl, { method: 'HEAD' });
        if (resp.ok) {
          el.audioSoundtrackPlayer.src = audioUrl;
          el.linkDownloadSoundtrack.href = audioUrl;
          el.linkDownloadSoundtrack.download = `${projName}_soundtrack.wav`;
          el.musicPlayerWrapper.style.display = 'block';
        } else {
          el.musicPlayerWrapper.style.display = 'none';
        }
      } catch {
        el.musicPlayerWrapper.style.display = 'none';
      }
    }
  }

  async function handleSuggestMusicTags() {
    if (!el.btnSuggestMusicTags || !el.musicPromptInput) return;
    const projName = (el.movieFilename && el.movieFilename.value.trim()) || (state.currentFilename ? state.currentFilename.replace('.json', '') : '');
    const title = (el.movieTitle && el.movieTitle.value.trim()) || state.screenplay.title || 'Movie';
    const description = (el.movieDescription && el.movieDescription.value.trim()) || state.screenplay.description || '';
    const scenes = state.screenplay.scenes || [];

    const origBtnHtml = el.btnSuggestMusicTags.innerHTML;
    el.btnSuggestMusicTags.disabled = true;
    el.btnSuggestMusicTags.innerHTML = `<span>⏳</span> <span>${t('aiGenerating') || 'Generiere...'}</span>`;

    try {
      const res = await API.suggestMusicTags(projName, title, description, scenes);
      const tags = res?.prompt_tags || res?.tags;
      if (tags) {
        el.musicPromptInput.value = tags;
        if (!state.screenplay.music) state.screenplay.music = {};
        state.screenplay.music.prompt = tags;
        markDirty();
        showToast(state.lang === 'en' ? 'Music score prompt synchronized with scenes!' : 'Film-Score mit Szenen-Zeitleiste synchronisiert!', 'success');
      }
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      el.btnSuggestMusicTags.disabled = false;
      el.btnSuggestMusicTags.innerHTML = origBtnHtml;
    }
  }

  async function handleScoreMovie() {
    if (!el.btnScoreMovie) return;
    const projName = (el.movieFilename && el.movieFilename.value.trim()) || (state.currentFilename ? state.currentFilename.replace('.json', '') : '');
    if (!projName) {
      showToast(state.lang === 'en' ? 'No project active!' : 'Kein Projekt geladen!', 'error');
      return;
    }

    // Save project changes first so settings are on disk
    await saveCurrentProject();

    const origBtnHtml = el.btnScoreMovie.innerHTML;
    el.btnScoreMovie.disabled = true;
    el.btnScoreMovie.innerHTML = `<span>⏳</span> <span>${t('scoringInProgress') || 'Komponiere Soundtrack & mische Audio...'}</span>`;
    if (el.musicScoreStatus) {
      el.musicScoreStatus.textContent = state.lang === 'en' ? 'Composing music in ComfyUI & mixing with auto-ducking... Please wait...' : 'Komponiere Musik in ComfyUI & mische mit Auto-Ducking... Bitte warten...';
      el.musicScoreStatus.className = 'music-status-text loading';
    }

    try {
      const payload = {
        project: projName,
        prompt_tags: (el.musicPromptInput && el.musicPromptInput.value.trim()) || (state.screenplay.music && state.screenplay.music.prompt) || '',
        checkpoint: (el.musicModelSelect && el.musicModelSelect.value) || (state.screenplay.music && state.screenplay.music.model) || '',
        volume: el.musicVolumeSelect ? parseFloat(el.musicVolumeSelect.value) : 0.22,
        ducking: el.chkMusicDucking ? el.chkMusicDucking.checked : true
      };

      const res = await API.scoreMovie(payload);
      if (res && res.success) {
        showToast(state.lang === 'en' ? 'Soundtrack generated and movie scored!' : 'Soundtrack generiert und Film erfolgreich nachvertont!', 'success');
        if (el.musicScoreStatus) {
          el.musicScoreStatus.textContent = state.lang === 'en' ? '✅ Completed! Film scored with auto-ducking.' : '✅ Fertiggestellt! Film erfolgreich nachvertont.';
          el.musicScoreStatus.className = 'music-status-text success';
        }
        // Update audio preview
        if (el.musicPlayerWrapper && el.audioSoundtrackPlayer && el.linkDownloadSoundtrack) {
          const audioUrl = `/api/music/soundtrack?project=${encodeURIComponent(projName)}&t=${Date.now()}`;
          el.audioSoundtrackPlayer.src = audioUrl;
          el.linkDownloadSoundtrack.href = audioUrl;
          el.linkDownloadSoundtrack.download = `${projName}_soundtrack.wav`;
          el.musicPlayerWrapper.style.display = 'block';
          el.audioSoundtrackPlayer.play().catch(() => {});
        }
      }
    } catch (err) {
      showToast(err.message, 'error');
      if (el.musicScoreStatus) {
        el.musicScoreStatus.textContent = `❌ ${err.message}`;
        el.musicScoreStatus.className = 'music-status-text error';
      }
    } finally {
      el.btnScoreMovie.disabled = false;
      el.btnScoreMovie.innerHTML = origBtnHtml;
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

  // =============================================================
  // STORY GENERATOR (Batch)
  // =============================================================

  function openStoryGeneratorModal() {
    if (!el.storyGeneratorModal) return;
    if (el.storyGenPlot) {
      el.storyGenPlot.value = state.screenplay.description || '';
    }
    if (el.storyGenMaxDuration) {
      el.storyGenMaxDuration.value = 6;
      if (el.storyGenMaxDurationVal) el.storyGenMaxDurationVal.textContent = '6s';
    }
    if (el.storyGenMaxTokens) {
      el.storyGenMaxTokens.value = 6000;
      if (el.storyGenMaxTokensVal) el.storyGenMaxTokensVal.textContent = '6.000';
    }
    if (el.storyGenPreviewContainer) el.storyGenPreviewContainer.style.display = 'none';
    if (el.storyGenFooter) el.storyGenFooter.style.display = 'none';
    state.pendingStoryGen = null;
    el.storyGeneratorModal.classList.add('open');
  }

  function closeStoryGeneratorModal() {
    if (el.storyGeneratorModal) {
      el.storyGeneratorModal.classList.remove('open');
    }
    state.pendingStoryGen = null;
  }

  async function executeStoryGenerator() {
    if (!el.btnExecuteStoryGen) return;
    const plot = (el.storyGenPlot ? el.storyGenPlot.value : '').trim();
    if (!plot) {
      showToast(t('storylineInputPlaceholder'), 'warning');
      return;
    }

    const maxDuration = el.storyGenMaxDuration ? parseInt(el.storyGenMaxDuration.value, 10) : 6;
    const maxTokens = el.storyGenMaxTokens ? parseInt(el.storyGenMaxTokens.value, 10) : 6000;
    const modeRadio = document.querySelector('input[name="storyGenMode"]:checked');
    const mode = modeRadio ? modeRadio.value : 'append';

    const btn = el.btnExecuteStoryGen;
    try {
      btn.disabled = true;
      btn.innerHTML = `<span class="ai-loading-spinner"></span> <span>${escapeHtml(t('generatingShots'))}</span>`;

      const res = await API.generateLlm('generate_story_scenes', {
        storyline: plot,
        max_shot_duration: maxDuration,
        max_tokens: maxTokens,
        mode: mode,
        screenplay: state.screenplay
      });

      if (!res || !res.success || !Array.isArray(res.scenes) || res.scenes.length === 0) {
        showToast(res && res.error ? res.error : 'Keine Szenen generiert', 'error');
        return;
      }

      state.pendingStoryGen = {
        scenes: res.scenes,
        new_characters: res.new_characters || [],
        mode: mode
      };

      renderStoryGenPreview();
      if (el.storyGenPreviewContainer) el.storyGenPreviewContainer.style.display = 'block';
      if (el.storyGenFooter) el.storyGenFooter.style.display = 'flex';
      showToast(`${res.scenes.length} Shots generiert!`, 'success');
    } catch (err) {
      showToast(err.message || t('aiErrorOffline'), 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<span class="ai-sparkle">⚡</span> <span data-i18n="btnGenerateShots">${escapeHtml(t('btnGenerateShots'))}</span>`;
    }
  }

  function renderStoryGenPreview() {
    if (!state.pendingStoryGen) return;
    const { scenes, new_characters, mode } = state.pendingStoryGen;

    // Total duration
    const totalSec = scenes.reduce((acc, s) => acc + (parseInt(s.duration, 10) || 0), 0);
    if (el.storyGenSummaryBadge) {
      el.storyGenSummaryBadge.textContent = `${scenes.length} Shots • ${totalSec}s`;
    }

    // New characters box
    if (el.storyGenNewCharsBox) {
      if (new_characters && new_characters.length > 0) {
        let charsHtml = `
          <div style="font-size:12px;font-weight:700;color:var(--accent-gold);margin-bottom:4px;">
            🎭 ${escapeHtml(t('storyNewCharsDetected'))}
          </div>
          <div class="new-chars-list">
        `;
        new_characters.forEach(c => {
          charsHtml += `
            <div class="new-char-chip">
              <div>
                <strong>${escapeHtml(c.name)}</strong>
                <span style="color:var(--text-muted);font-size:11px;margin-left:6px;">${escapeHtml(c.description || '')}</span>
              </div>
              <div style="display:flex;gap:6px;align-items:center;">
                <span style="font-size:11px;color:var(--accent-cyan);background:rgba(56,189,248,0.15);padding:2px 6px;border-radius:4px;">${escapeHtml(c.model || 'Default')}</span>
                ${(c.loras && c.loras.length) ? `<span style="font-size:10px;color:var(--text-dim);">${escapeHtml(c.loras.join(', '))}</span>` : ''}
              </div>
            </div>
          `;
        });
        charsHtml += `</div>`;
        el.storyGenNewCharsBox.innerHTML = charsHtml;
        el.storyGenNewCharsBox.style.display = 'block';
      } else {
        el.storyGenNewCharsBox.style.display = 'none';
      }
    }

    // Shots list
    if (el.storyGenShotsList) {
      let shotsHtml = '';
      const startId = (mode === 'replace' ? 1 : ((state.screenplay.scenes || []).length + 1));
      scenes.forEach((s, idx) => {
        const shotNum = startId + idx;
        const charBadge = (s.characters && s.characters.length) ? `<span style="color:var(--accent-gold);">🎭 ${escapeHtml(s.characters.join(', '))}</span>` : '';
        shotsHtml += `
          <div class="preview-shot-item">
            <div class="preview-shot-header">
              <div class="preview-shot-title">
                <span style="color:var(--accent-cyan);">#${shotNum}</span>
                <span>${escapeHtml(s.sequence || 'Szene')}</span>
                <span style="font-weight:normal;color:var(--text-muted);font-size:11px;">📍 ${escapeHtml(s.location || 'Set')}</span>
              </div>
              <div class="preview-shot-meta">
                ${charBadge}
                <span class="badge-value" style="color:var(--accent-cyan);background:rgba(0,0,0,0.3);">⏱️ ${s.duration}s</span>
              </div>
            </div>
            <div class="preview-shot-idea">${escapeHtml(s.idea || '')}</div>
          </div>
        `;
      });
      el.storyGenShotsList.innerHTML = shotsHtml;
    }
  }

  function applyStoryGeneratorResults() {
    if (!state.pendingStoryGen) return;
    const { scenes, new_characters, mode } = state.pendingStoryGen;

    if (!state.screenplay.scenes) state.screenplay.scenes = [];
    if (!state.screenplay.characters) state.screenplay.characters = [];

    // 1. Add new characters if any
    let addedCharsCount = 0;
    if (new_characters && Array.isArray(new_characters)) {
      new_characters.forEach(nc => {
        const exists = state.screenplay.characters.some(c => (c.name || '').toLowerCase() === (nc.name || '').toLowerCase());
        if (!exists) {
          const nextCharId = state.screenplay.characters.reduce((max, c) => Math.max(max, c.id || 0), 0) + 1;
          state.screenplay.characters.push({
            id: nextCharId,
            name: nc.name,
            model: nc.model || 'anima_cyberrealistic',
            loras: nc.loras || [],
            description: nc.description || '',
            charakter_prompt: nc.charakter_prompt || ''
          });
          addedCharsCount++;
        }
      });
    }

    // 2. Add or replace scenes
    if (mode === 'replace') {
      state.screenplay.scenes = [];
    }

    const startId = state.screenplay.scenes.length + 1;
    scenes.forEach((s, idx) => {
      state.screenplay.scenes.push({
        id: startId + idx,
        sequence: s.sequence || `Sequenz ${startId + idx}`,
        location: s.location || 'Set',
        duration: s.duration || 6,
        characters: s.characters || [],
        idea: s.idea || '',
        same_scene: Boolean(s.same_scene),
        match_cut: Boolean(s.match_cut),
        variables_update: s.variables_update || {}
      });
    });

    closeStoryGeneratorModal();
    markDirty();
    renderCharacters();
    renderScenes();
    updateStats();
    renderJsonPreview();

    const msg = t('shotsAppliedSuccess')
      .replace('{count}', scenes.length)
      .replace('{charCount}', addedCharsCount);
    showToast(msg, 'success');

    // Trigger subtle harmonization in background to ensure character tags and outfit variables are aligned
    handleHarmonizeScreenplay(true);
  }

  // =============================================================
  // IN-APP GUIDE & BEST PRACTICES MODAL
  // =============================================================

  function openGuideModal(targetSectionId = 'section-workflow') {
    if (!el.guideModal) return;
    switchGuideSection(targetSectionId);
    el.guideModal.classList.add('open');
  }

  function closeGuideModal() {
    if (el.guideModal) {
      el.guideModal.classList.remove('open');
    }
  }

  function switchGuideSection(targetId) {
    const navButtons = document.querySelectorAll('.guide-nav-item');
    const sections = document.querySelectorAll('.guide-section');

    navButtons.forEach(btn => {
      const target = btn.getAttribute('data-guide-target');
      if (target === targetId) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    sections.forEach(sec => {
      if (sec.id === targetId) {
        sec.classList.add('active');
      } else {
        sec.classList.remove('active');
      }
    });

    const contentPane = document.getElementById('guideContentPane');
    if (contentPane) contentPane.scrollTop = 0;
  }

  // =============================================================
  // STORY WIZARD (Interactive Step-by-Step)
  // =============================================================

  function openStoryWizardModal() {
    if (!el.storyWizardModal) return;

    state.wizard = {
      premise: state.screenplay.description || '',
      producerInstructions: state.screenplay.producer_instructions || '',
      maxDuration: 6,
      maxTokens: 4000,
      currentStepIndex: (state.screenplay.scenes || []).length + 1,
      currentScene: null,
      currentNewChars: [],
      hooks: [],
      selectedSceneId: null
    };

    if (el.wizardPremiseInput) {
      el.wizardPremiseInput.value = state.wizard.premise;
    }
    if (el.wizardProducerInstructions) {
      el.wizardProducerInstructions.value = state.wizard.producerInstructions;
    }
    if (el.wizardInteractiveProducerInstructions) {
      el.wizardInteractiveProducerInstructions.value = state.wizard.producerInstructions;
    }
    if (el.wizardMaxDuration) {
      el.wizardMaxDuration.value = 6;
      if (el.wizardMaxDurationVal) el.wizardMaxDurationVal.textContent = '6s';
    }
    if (el.wizardMaxTokens) {
      el.wizardMaxTokens.value = 4000;
      if (el.wizardMaxTokensVal) el.wizardMaxTokensVal.textContent = '4.000';
    }

    // Reset button display to drafting mode
    if (el.btnWizardRegenerate) el.btnWizardRegenerate.style.display = 'inline-flex';
    if (el.btnWizardApplyAndNext) el.btnWizardApplyAndNext.style.display = 'inline-flex';
    if (el.btnWizardRecreateScene) el.btnWizardRecreateScene.style.display = 'none';
    if (el.btnWizardSaveEdits) el.btnWizardSaveEdits.style.display = 'none';
    if (el.btnWizardBackToNext) el.btnWizardBackToNext.style.display = 'none';

    // Show setup view first if no premise or new start, or go direct to interactive if scenes exist
    if ((state.screenplay.scenes || []).length > 0) {
      if (el.wizardSetupView) el.wizardSetupView.style.display = 'none';
      if (el.wizardInteractiveView) el.wizardInteractiveView.style.display = 'block';
      if (el.wizardInteractiveActions) el.wizardInteractiveActions.style.display = 'flex';
      generateNextWizardStep();
    } else {
      if (el.wizardSetupView) el.wizardSetupView.style.display = 'block';
      if (el.wizardInteractiveView) el.wizardInteractiveView.style.display = 'none';
      if (el.wizardInteractiveActions) el.wizardInteractiveActions.style.display = 'none';
    }

    el.storyWizardModal.classList.add('open');
  }

  function closeStoryWizardModal() {
    if (el.storyWizardModal) {
      el.storyWizardModal.classList.remove('open');
    }
    if (state.wizard) {
      state.wizard.selectedSceneId = null;
    }
  }

  function startStoryWizardFromSetup() {
    const premise = (el.wizardPremiseInput ? el.wizardPremiseInput.value : '').trim();
    if (!premise) {
      showToast(t('wizardPremisePlaceholder'), 'warning');
      return;
    }
    const prodInstructions = (el.wizardProducerInstructions ? el.wizardProducerInstructions.value : '').trim();
    state.wizard.premise = premise;
    state.wizard.producerInstructions = prodInstructions;
    state.screenplay.producer_instructions = prodInstructions;
    if (el.wizardInteractiveProducerInstructions) {
      el.wizardInteractiveProducerInstructions.value = prodInstructions;
    }

    state.wizard.maxDuration = el.wizardMaxDuration ? parseInt(el.wizardMaxDuration.value, 10) : 6;
    state.wizard.maxTokens = el.wizardMaxTokens ? parseInt(el.wizardMaxTokens.value, 10) : 4000;

    // Update screenplay description if empty
    if (!state.screenplay.description) {
      state.screenplay.description = premise;
      if (el.movieDescription) el.movieDescription.value = premise;
    }
    markDirty();

    if (el.wizardSetupView) el.wizardSetupView.style.display = 'none';
    if (el.wizardInteractiveView) el.wizardInteractiveView.style.display = 'block';
    if (el.wizardInteractiveActions) el.wizardInteractiveActions.style.display = 'flex';

    generateNextWizardStep();
  }

  async function generateNextWizardStep(customInstruction = '') {
    const nextStepNum = (state.screenplay.scenes || []).length + 1;
    state.wizard.currentStepIndex = nextStepNum;
    state.wizard.selectedSceneId = null;

    // Restore drafting buttons
    if (el.btnWizardRegenerate) el.btnWizardRegenerate.style.display = 'inline-flex';
    if (el.btnWizardApplyAndNext) el.btnWizardApplyAndNext.style.display = 'inline-flex';
    if (el.btnWizardRecreateScene) el.btnWizardRecreateScene.style.display = 'none';
    if (el.btnWizardSaveEdits) el.btnWizardSaveEdits.style.display = 'none';
    if (el.btnWizardBackToNext) el.btnWizardBackToNext.style.display = 'none';

    if (el.wizardStepBadge) {
      el.wizardStepBadge.textContent = t('wizardStepBadge').replace('{step}', nextStepNum);
    }

    renderWizardTimeline();

    if (el.wizardCurrentShotBox) {
      el.wizardCurrentShotBox.innerHTML = `
        <div style="text-align:center;padding:30px;color:var(--text-muted);">
          <span class="ai-loading-spinner" style="width:28px;height:28px;display:inline-block;margin-bottom:10px;"></span>
          <div style="font-size:13px;font-weight:600;color:var(--text-main);">${escapeHtml(t('aiThinking'))}</div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:4px;">Brainstorme Shot #${nextStepNum}...</div>
        </div>
      `;
    }
    if (el.wizardNewCharAlert) el.wizardNewCharAlert.style.display = 'none';
    if (el.wizardHooksBox) el.wizardHooksBox.style.display = 'none';

    setWizardButtonsLoading(true);

    try {
      const res = await API.generateLlm('wizard_step_scene', {
        premise: state.wizard.premise || state.screenplay.description,
        producer_instructions: state.wizard.producerInstructions || state.screenplay.producer_instructions || '',
        max_shot_duration: state.wizard.maxDuration,
        max_tokens: state.wizard.maxTokens,
        user_instruction: customInstruction,
        screenplay: state.screenplay
      });

      if (!res || !res.success || !res.scene) {
        showToast(res && res.error ? res.error : 'Fehler beim Abrufen des Szenenvorschlags', 'error');
        return;
      }

      state.wizard.currentScene = res.scene;
      state.wizard.currentNewChars = res.new_characters || [];
      state.wizard.hooks = res.next_hooks || [];

      renderWizardCurrentShot();
      renderWizardNewCharsAlert();
      renderWizardHooks();
    } catch (err) {
      showToast(err.message || t('aiErrorOffline'), 'error');
    } finally {
      setWizardButtonsLoading(false);
    }
  }

  function setWizardButtonsLoading(loading) {
    if (el.btnWizardRegenerate) el.btnWizardRegenerate.disabled = loading;
    if (el.btnWizardApplyAndNext) {
      el.btnWizardApplyAndNext.disabled = loading;
      if (loading) {
        el.btnWizardApplyAndNext.innerHTML = `<span class="ai-loading-spinner"></span> <span>${escapeHtml(t('aiThinking'))}</span>`;
      } else {
        el.btnWizardApplyAndNext.innerHTML = `<span data-i18n="btnWizardApplyAndNext">${escapeHtml(t('btnWizardApplyAndNext'))}</span>`;
      }
    }
  }

  function renderWizardTimeline() {
    if (!el.wizardTimeline) return;
    const scenes = state.screenplay.scenes || [];
    if (scenes.length === 0) {
      el.wizardTimeline.innerHTML = `<span style="font-size:11px;color:var(--text-dim);padding:2px 4px;">Start des Drehbuchs</span>`;
      return;
    }
    let html = '';
    scenes.forEach(s => {
      const isSelected = state.wizard && state.wizard.selectedSceneId === s.id;
      html += `
        <div class="wizard-timeline-chip ${isSelected ? 'editing-selected' : ''}" data-scene-id="${s.id}" title="${escapeHtml(s.idea || '')}">
          <strong style="color:var(--accent-cyan);">#${s.id}</strong>
          <span>${escapeHtml(s.sequence || 'Szene')}</span>
          <span style="color:var(--text-dim);">(${s.duration}s)</span>
        </div>
      `;
    });
    const isNextSelected = !state.wizard || !state.wizard.selectedSceneId;
    html += `
      <div class="wizard-timeline-chip current ${isNextSelected ? 'editing-selected' : ''}" data-next-step="true" title="${escapeHtml(t('wizardDraftingNextTitle'))}">
        <span>➡️ #${state.wizard.currentStepIndex} (${escapeHtml(t('wizardCurrentShotTitle'))})</span>
      </div>
    `;
    el.wizardTimeline.innerHTML = html;

    // Attach click listeners to all chips
    el.wizardTimeline.querySelectorAll('.wizard-timeline-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const scId = chip.getAttribute('data-scene-id');
        if (scId) {
          selectWizardScene(parseInt(scId, 10));
        } else if (chip.getAttribute('data-next-step')) {
          returnToDraftingNextScene();
        }
      });
    });

    if (!state.wizard.selectedSceneId) {
      el.wizardTimeline.scrollLeft = el.wizardTimeline.scrollWidth;
    }
  }

  function renderWizardCurrentShot() {
    if (!el.wizardCurrentShotBox || !state.wizard.currentScene) return;
    const sc = state.wizard.currentScene;
    const shotNum = state.wizard.currentStepIndex;

    const charsVal = Array.isArray(sc.characters) ? sc.characters.join(', ') : (sc.characters || '');

    el.wizardCurrentShotBox.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--border);padding-bottom:8px;">
        <span style="font-size:13px;font-weight:700;color:var(--accent-gold);">🎬 Shot #${shotNum}</span>
        <div style="display:flex;align-items:center;gap:6px;">
          <label style="font-size:11px;color:var(--text-dim);">Dauer:</label>
          <input type="number" id="wizardInputDur" min="3" max="15" value="${sc.duration || 6}" style="width:60px;padding:3px 6px;background:var(--bg-input);border:1px solid var(--border);border-radius:4px;color:var(--accent-cyan);font-weight:700;font-size:12px;">
          <span style="font-size:11px;color:var(--text-muted);">${escapeHtml(t('secondsUnit'))}</span>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px;">
        <div>
          <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">Sequenz:</label>
          <input type="text" id="wizardInputSeq" value="${escapeHtml(sc.sequence || '')}" class="form-control" style="font-size:12px;padding:6px 8px;margin-top:2px;">
        </div>
        <div>
          <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">Ort / Location:</label>
          <input type="text" id="wizardInputLoc" value="${escapeHtml(sc.location || '')}" class="form-control" style="font-size:12px;padding:6px 8px;margin-top:2px;">
        </div>
      </div>

      <div style="margin-top:8px;">
        <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">Charaktere im Shot:</label>
        <input type="text" id="wizardInputChars" value="${escapeHtml(charsVal)}" class="form-control" style="font-size:12px;padding:6px 8px;margin-top:2px;" placeholder="z.B. Maya, Stone">
      </div>

      <div style="margin-top:8px;">
        <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">Handlungs- & Regieprompt:</label>
        <textarea id="wizardInputIdea" class="form-control" rows="3" style="font-size:12px;padding:6px 8px;margin-top:2px;line-height:1.4;">${escapeHtml(sc.idea || '')}</textarea>
      </div>
    `;
  }

  function selectWizardScene(sceneId) {
    const scenes = state.screenplay.scenes || [];
    const sc = scenes.find(s => s.id === sceneId);
    if (!sc) return;

    state.wizard.selectedSceneId = sceneId;

    if (el.wizardStepBadge) {
      el.wizardStepBadge.textContent = t('wizardEditingSceneTitle').replace('{id}', sceneId);
    }

    renderWizardTimeline();
    renderWizardSelectedScene(sc);

    if (el.wizardNewCharAlert) el.wizardNewCharAlert.style.display = 'none';
    if (el.wizardHooksBox) el.wizardHooksBox.style.display = 'none';

    // Show editing actions, hide drafting actions
    if (el.btnWizardRegenerate) el.btnWizardRegenerate.style.display = 'none';
    if (el.btnWizardApplyAndNext) el.btnWizardApplyAndNext.style.display = 'none';
    if (el.btnWizardRecreateScene) el.btnWizardRecreateScene.style.display = 'inline-flex';
    if (el.btnWizardSaveEdits) el.btnWizardSaveEdits.style.display = 'inline-flex';
    if (el.btnWizardBackToNext) el.btnWizardBackToNext.style.display = 'inline-flex';
  }

  function renderWizardSelectedScene(sc) {
    if (!el.wizardCurrentShotBox || !sc) return;
    const shotNum = sc.id;
    const charsVal = Array.isArray(sc.characters) ? sc.characters.join(', ') : (sc.characters || '');

    el.wizardCurrentShotBox.innerHTML = `
      <div class="wizard-editing-badge">${escapeHtml(t('wizardEditingSceneTitle').replace('{id}', shotNum))}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--border);padding-bottom:8px;margin-top:8px;">
        <span style="font-size:13px;font-weight:700;color:var(--accent-gold);">🎬 Shot #${shotNum}</span>
        <div style="display:flex;align-items:center;gap:6px;">
          <label style="font-size:11px;color:var(--text-dim);">Dauer:</label>
          <input type="number" id="wizardInputDur" min="3" max="15" value="${sc.duration || 6}" style="width:60px;padding:3px 6px;background:var(--bg-input);border:1px solid var(--border);border-radius:4px;color:var(--accent-cyan);font-weight:700;font-size:12px;">
          <span style="font-size:11px;color:var(--text-muted);">${escapeHtml(t('secondsUnit'))}</span>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px;">
        <div>
          <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">Sequenz:</label>
          <input type="text" id="wizardInputSeq" value="${escapeHtml(sc.sequence || '')}" class="form-control" style="font-size:12px;padding:6px 8px;margin-top:2px;">
        </div>
        <div>
          <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">Ort / Location:</label>
          <input type="text" id="wizardInputLoc" value="${escapeHtml(sc.location || '')}" class="form-control" style="font-size:12px;padding:6px 8px;margin-top:2px;">
        </div>
      </div>

      <div style="margin-top:8px;">
        <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">Charaktere im Shot:</label>
        <input type="text" id="wizardInputChars" value="${escapeHtml(charsVal)}" class="form-control" style="font-size:12px;padding:6px 8px;margin-top:2px;" placeholder="z.B. Maya, Stone">
      </div>

      <div style="margin-top:8px;">
        <label style="font-size:11px;font-weight:600;color:var(--text-dim);text-transform:uppercase;">Handlungs- & Regieprompt:</label>
        <textarea id="wizardInputIdea" class="form-control" rows="3" style="font-size:12px;padding:6px 8px;margin-top:2px;line-height:1.4;">${escapeHtml(sc.idea || '')}</textarea>
      </div>
    `;
  }

  function returnToDraftingNextScene() {
    state.wizard.selectedSceneId = null;

    if (el.wizardStepBadge) {
      el.wizardStepBadge.textContent = t('wizardStepBadge').replace('{step}', state.wizard.currentStepIndex);
    }

    // Restore buttons
    if (el.btnWizardRegenerate) el.btnWizardRegenerate.style.display = 'inline-flex';
    if (el.btnWizardApplyAndNext) el.btnWizardApplyAndNext.style.display = 'inline-flex';
    if (el.btnWizardRecreateScene) el.btnWizardRecreateScene.style.display = 'none';
    if (el.btnWizardSaveEdits) el.btnWizardSaveEdits.style.display = 'none';
    if (el.btnWizardBackToNext) el.btnWizardBackToNext.style.display = 'none';

    renderWizardTimeline();
    renderWizardCurrentShot();
    renderWizardNewCharsAlert();
    renderWizardHooks();
  }

  function saveCurrentWizardSceneEdits() {
    if (!state.wizard.selectedSceneId) return;
    const sceneId = state.wizard.selectedSceneId;
    const sc = (state.screenplay.scenes || []).find(s => s.id === sceneId);
    if (!sc) return;

    const seqInput = document.getElementById('wizardInputSeq');
    const locInput = document.getElementById('wizardInputLoc');
    const durInput = document.getElementById('wizardInputDur');
    const charsInput = document.getElementById('wizardInputChars');
    const ideaInput = document.getElementById('wizardInputIdea');

    if (seqInput) sc.sequence = seqInput.value.trim();
    if (locInput) sc.location = locInput.value.trim();
    if (durInput) sc.duration = parseInt(durInput.value, 10) || 6;
    if (charsInput) sc.characters = charsInput.value.split(',').map(s => s.trim()).filter(Boolean);
    if (ideaInput) sc.idea = ideaInput.value.trim();

    markDirty();
    renderScenes();
    updateStats();
    renderJsonPreview();
    renderWizardTimeline();

    showToast(t('wizardSceneSavedToast').replace('{id}', sceneId), 'success');
  }

  async function recreateCurrentWizardScene() {
    if (!state.wizard.selectedSceneId) return;
    const targetId = state.wizard.selectedSceneId;
    const customInstruction = el.wizardUserInstruction ? el.wizardUserInstruction.value.trim() : '';

    if (el.btnWizardRecreateScene) {
      el.btnWizardRecreateScene.disabled = true;
      el.btnWizardRecreateScene.innerHTML = `<span class="ai-loading-spinner"></span> <span>${escapeHtml(t('aiThinking'))}</span>`;
    }
    if (el.btnWizardSaveEdits) el.btnWizardSaveEdits.disabled = true;
    if (el.btnWizardBackToNext) el.btnWizardBackToNext.disabled = true;

    try {
      const res = await API.generateLlm('wizard_step_scene', {
        premise: state.wizard.premise || state.screenplay.description,
        producer_instructions: state.wizard.producerInstructions || state.screenplay.producer_instructions || '',
        max_shot_duration: state.wizard.maxDuration,
        max_tokens: state.wizard.maxTokens,
        user_instruction: customInstruction,
        target_scene_id: targetId,
        screenplay: state.screenplay
      });

      if (!res || !res.success || !res.scene) {
        showToast(res && res.error ? res.error : 'Fehler beim Neugenerieren der Szene', 'error');
        return;
      }

      const idx = (state.screenplay.scenes || []).findIndex(s => s.id === targetId);
      if (idx !== -1) {
        state.screenplay.scenes[idx] = {
          ...state.screenplay.scenes[idx],
          ...res.scene,
          id: targetId
        };
      }

      // Add new characters if discovered during recreation
      const newChars = res.new_characters || [];
      if (newChars.length > 0) {
        if (!state.screenplay.characters) state.screenplay.characters = [];
        newChars.forEach(nc => {
          const exists = state.screenplay.characters.some(c => (c.name || '').toLowerCase() === (nc.name || '').toLowerCase());
          if (!exists) {
            const nextCharId = state.screenplay.characters.reduce((max, c) => Math.max(max, c.id || 0), 0) + 1;
            state.screenplay.characters.push({
              id: nextCharId,
              name: nc.name,
              model: nc.model || 'anima_cyberrealistic',
              loras: nc.loras || [],
              description: nc.description || '',
              charakter_prompt: nc.charakter_prompt || ''
            });
          }
        });
        renderCharacters();
      }

      const updatedScene = state.screenplay.scenes[idx];
      renderWizardSelectedScene(updatedScene);
      renderWizardTimeline();
      markDirty();
      renderScenes();
      updateStats();
      renderJsonPreview();

      if (el.wizardUserInstruction) el.wizardUserInstruction.value = '';
      showToast(t('wizardSceneRecreatedToast').replace('{id}', targetId), 'success');
    } catch (err) {
      showToast(err.message || t('aiErrorOffline'), 'error');
    } finally {
      if (el.btnWizardRecreateScene) {
        el.btnWizardRecreateScene.disabled = false;
        el.btnWizardRecreateScene.innerHTML = `<span data-i18n="btnWizardRecreateScene">${escapeHtml(t('btnWizardRecreateScene'))}</span>`;
      }
      if (el.btnWizardSaveEdits) el.btnWizardSaveEdits.disabled = false;
      if (el.btnWizardBackToNext) el.btnWizardBackToNext.disabled = false;
    }
  }

  function renderWizardNewCharsAlert() {
    if (!el.wizardNewCharAlert) return;
    const newChars = state.wizard.currentNewChars || [];
    if (newChars.length === 0) {
      el.wizardNewCharAlert.style.display = 'none';
      return;
    }
    let html = `
      <div style="font-size:12px;font-weight:700;color:var(--accent-gold);margin-bottom:4px;">
        ✨ ${escapeHtml(t('wizardNewCharsFound'))}
      </div>
      <div class="new-chars-list">
    `;
    newChars.forEach(c => {
      html += `
        <div class="new-char-chip">
          <div>
            <strong>${escapeHtml(c.name)}</strong>
            <span style="color:var(--text-muted);font-size:11px;margin-left:6px;">${escapeHtml(c.description || '')}</span>
          </div>
          <div style="display:flex;gap:6px;align-items:center;">
            <span style="font-size:11px;color:var(--accent-cyan);background:rgba(56,189,248,0.15);padding:2px 6px;border-radius:4px;">${escapeHtml(c.model || 'Model')}</span>
            ${(c.loras && c.loras.length) ? `<span style="font-size:10px;color:var(--text-dim);">${escapeHtml(c.loras.join(', '))}</span>` : ''}
          </div>
        </div>
      `;
    });
    html += `</div>`;
    el.wizardNewCharAlert.innerHTML = html;
    el.wizardNewCharAlert.style.display = 'block';
  }

  function renderWizardHooks() {
    if (!el.wizardHooksBox || !el.wizardHooksList) return;
    const hooks = state.wizard.hooks || [];
    if (hooks.length === 0) {
      el.wizardHooksBox.style.display = 'none';
      return;
    }
    let html = '';
    hooks.forEach(h => {
      html += `<span class="hook-chip" title="Klicken, um als Regie-Hinweis zu nutzen">💡 ${escapeHtml(h)}</span>`;
    });
    el.wizardHooksList.innerHTML = html;
    el.wizardHooksBox.style.display = 'block';

    // Click on hook chip fills it into wizardUserInstruction
    el.wizardHooksList.querySelectorAll('.hook-chip').forEach((chip, i) => {
      chip.addEventListener('click', () => {
        if (el.wizardUserInstruction) {
          el.wizardUserInstruction.value = hooks[i];
          el.wizardUserInstruction.focus();
        }
      });
    });
  }

  function applyWizardStepAndNext() {
    if (!state.wizard.currentScene) return;

    // Read modified values from inputs if user edited them
    const seqInput = document.getElementById('wizardInputSeq');
    const locInput = document.getElementById('wizardInputLoc');
    const durInput = document.getElementById('wizardInputDur');
    const charsInput = document.getElementById('wizardInputChars');
    const ideaInput = document.getElementById('wizardInputIdea');

    const sequence = seqInput ? seqInput.value.trim() : state.wizard.currentScene.sequence;
    const location = locInput ? locInput.value.trim() : state.wizard.currentScene.location;
    const duration = durInput ? parseInt(durInput.value, 10) : state.wizard.currentScene.duration;
    const idea = ideaInput ? ideaInput.value.trim() : state.wizard.currentScene.idea;

    let chars = state.wizard.currentScene.characters || [];
    if (charsInput) {
      chars = charsInput.value.split(',').map(s => s.trim()).filter(Boolean);
    }

    if (!state.screenplay.scenes) state.screenplay.scenes = [];
    if (!state.screenplay.characters) state.screenplay.characters = [];

    // Add new characters from this step if any
    const newChars = state.wizard.currentNewChars || [];
    newChars.forEach(nc => {
      const exists = state.screenplay.characters.some(c => (c.name || '').toLowerCase() === (nc.name || '').toLowerCase());
      if (!exists) {
        const nextCharId = state.screenplay.characters.reduce((max, c) => Math.max(max, c.id || 0), 0) + 1;
        state.screenplay.characters.push({
          id: nextCharId,
          name: nc.name,
          model: nc.model || 'anima_cyberrealistic',
          loras: nc.loras || [],
          description: nc.description || '',
          charakter_prompt: nc.charakter_prompt || ''
        });
      }
    });

    const newShotId = state.screenplay.scenes.length + 1;
    state.screenplay.scenes.push({
      id: newShotId,
      sequence: sequence || `Sequenz ${newShotId}`,
      location: location || 'Set',
      duration: duration || 6,
      characters: chars,
      idea: idea,
      same_scene: Boolean(state.wizard.currentScene.same_scene),
      match_cut: Boolean(state.wizard.currentScene.match_cut),
      variables_update: state.wizard.currentScene.variables_update || {}
    });

    markDirty();
    renderCharacters();
    renderScenes();
    updateStats();
    renderJsonPreview();

    showToast(`Shot #${newShotId} angelegt!`, 'success');

    // Proceed to next step: pass user instruction if typed
    const nextInstruction = el.wizardUserInstruction ? el.wizardUserInstruction.value.trim() : '';
    if (el.wizardUserInstruction) el.wizardUserInstruction.value = '';

    generateNextWizardStep(nextInstruction);
  }

  async function finishStoryWizard() {
    closeStoryWizardModal();
    const count = (state.screenplay.scenes || []).length;
    showToast(t('wizardFinishedToast').replace('{count}', count), 'success');
    if (count > 0) {
      showToast(t('wizardFinishingHarmonizing'), 'info');
      await handleHarmonizeScreenplay(false);
    }
  }

  // --- Holistic Screenplay Harmonizer ---
  async function handleHarmonizeScreenplay(silent = false) {
    const btn = el.btnHarmonizeScript;
    if (!state.screenplay || !Array.isArray(state.screenplay.scenes) || state.screenplay.scenes.length === 0) {
      if (!silent) showToast(t('noScenes'), 'info');
      return;
    }

    try {
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="ai-loading-spinner"></span> <span>${escapeHtml(t('harmonizingScript'))}</span>`;
      }
      if (!silent) {
        showToast(t('harmonizingScript'), 'info');
      }

      const res = await API.generateLlm('harmonize_screenplay', {
        screenplay: state.screenplay
      });

      if (!res || !res.success || !res.harmonized_screenplay) {
        throw new Error(res && res.error ? res.error : 'Harmonisierung fehlgeschlagen');
      }

      const harm = res.harmonized_screenplay;
      if (harm.variables && typeof harm.variables === 'object') {
        state.screenplay.variables = harm.variables;
      }
      if (Array.isArray(harm.scenes) && harm.scenes.length > 0) {
        state.screenplay.scenes = harm.scenes;
      }

      renderVariables();
      renderScenes();
      updateStats();
      renderJsonPreview();
      markDirty();

      showToast(t('scriptHarmonizedSuccess'), 'success');
    } catch (err) {
      console.error('Harmonize error:', err);
      if (!silent) {
        showToast(err.message || t('aiErrorOffline'), 'error');
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<span>✨</span> <span data-i18n="btnHarmonizeScript">${escapeHtml(t('btnHarmonizeScript'))}</span>`;
      }
    }
  }

  // --- Studio Settings Modal & Management ---
  let cachedSettingsModels = null;

  async function openSettingsModal() {
    if (!el.settingsModal) return;
    el.settingsModal.classList.add('open');
    switchSettingsTab('minimax');
    await loadSettingsData();
  }

  function closeSettingsModal() {
    if (!el.settingsModal) return;
    el.settingsModal.classList.remove('open');
  }

  function switchSettingsTab(tabName) {
    const tabBtns = document.querySelectorAll('.settings-tab-btn');
    const panes = document.querySelectorAll('.settings-pane');
    tabBtns.forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === tabName);
    });
    panes.forEach(pane => {
      pane.classList.toggle('active', pane.id === `settingsPane-${tabName}`);
    });
  }

  async function loadSettingsData() {
    try {
      const [settingsRes, modelsRes] = await Promise.all([
        API.getSettings().catch(err => {
          console.error('Failed to load settings:', err);
          return { success: false };
        }),
        API.getSettingsModels().catch(err => {
          console.error('Failed to load settings models:', err);
          return { success: false };
        })
      ]);

      const s = (settingsRes && settingsRes.success && settingsRes.settings) ? settingsRes.settings : {};
      cachedSettingsModels = (modelsRes && modelsRes.success) ? modelsRes : null;

      populateSettingsModelDropdowns(cachedSettingsModels, s);

      // Minimax
      const mm = s.minimax_i2v || s.minimax || {};
      const unetVal = mm.unet_name || mm.unet_model || '';
      if (el.settingMinimaxUnetInput) el.settingMinimaxUnetInput.value = unetVal;
      if (el.settingMinimaxUnetSelect) {
        if (unetVal && !Array.from(el.settingMinimaxUnetSelect.options).some(o => o.value === unetVal)) {
          const opt = document.createElement('option');
          opt.value = unetVal;
          opt.textContent = unetVal;
          el.settingMinimaxUnetSelect.appendChild(opt);
        }
        el.settingMinimaxUnetSelect.value = unetVal;
      }

      const turboLoraVal = mm.turbo_lora || '';
      if (el.settingTurboLoraInput) el.settingTurboLoraInput.value = turboLoraVal;
      if (el.settingTurboLoraSelect) {
        if (turboLoraVal && !Array.from(el.settingTurboLoraSelect.options).some(o => o.value === turboLoraVal)) {
          const opt = document.createElement('option');
          opt.value = turboLoraVal;
          opt.textContent = turboLoraVal;
          el.settingTurboLoraSelect.appendChild(opt);
        }
        el.settingTurboLoraSelect.value = turboLoraVal;
      }

      if (el.settingMinimaxSteps) el.settingMinimaxSteps.value = mm.steps !== undefined ? mm.steps : 8;
      if (el.settingTurboStrength) {
        el.settingTurboStrength.value = mm.turbo_strength !== undefined ? mm.turbo_strength : 1.0;
        if (el.valTurboStrength) el.valTurboStrength.textContent = Number(el.settingTurboStrength.value).toFixed(2);
      }
      if (el.settingMinimaxVae) el.settingMinimaxVae.value = mm.video_vae_name || mm.vae || '';
      if (el.settingMinimaxClip) el.settingMinimaxClip.value = mm.clip_name || '';

      // Music
      const music = s.music_studio || s.music || {};
      if (el.settingMusicEnabled) el.settingMusicEnabled.checked = music.enabled !== false;
      const ckptVal = music.checkpoint || '';
      if (el.settingMusicModel) {
        if (ckptVal && !Array.from(el.settingMusicModel.options).some(o => o.value === ckptVal)) {
          const opt = document.createElement('option');
          opt.value = ckptVal;
          opt.textContent = ckptVal;
          el.settingMusicModel.appendChild(opt);
        }
        el.settingMusicModel.value = ckptVal;
      }
      if (el.settingMusicSteps) el.settingMusicSteps.value = music.steps !== undefined ? music.steps : 25;
      if (el.settingMusicCfg) el.settingMusicCfg.value = music.cfg !== undefined ? music.cfg : 4.0;
      if (el.settingMusicVolume) {
        const volPercent = music.volume !== undefined ? Math.round(music.volume * 100) : 35;
        el.settingMusicVolume.value = volPercent;
        if (el.valMusicVolume) el.valMusicVolume.textContent = `${volPercent}%`;
      }
      if (el.settingMusicDucking) el.settingMusicDucking.checked = music.ducking !== false;

      // LM Studio
      const lms = s.lm_studio || {};
      if (el.settingLmsUrl) el.settingLmsUrl.value = lms.url || 'http://127.0.0.1:1234/v1/chat/completions';
      const lmsModelVal = lms.model_name || lms.model || '';
      if (el.settingLmsModel) {
        if (lmsModelVal && !Array.from(el.settingLmsModel.options).some(o => o.value === lmsModelVal)) {
          const opt = document.createElement('option');
          opt.value = lmsModelVal;
          opt.textContent = lmsModelVal;
          el.settingLmsModel.appendChild(opt);
        }
        el.settingLmsModel.value = lmsModelVal;
      }
      if (el.settingLmsTemp) {
        el.settingLmsTemp.value = lms.temperature !== undefined ? lms.temperature : 0.7;
        if (el.valLmsTemp) el.valLmsTemp.textContent = Number(el.settingLmsTemp.value).toFixed(2);
      }

      // System
      const comfy = s.comfyui || {};
      if (el.settingComfyUrl) el.settingComfyUrl.value = comfy.server_address || s.comfyui_server_address || '127.0.0.1:8188';
      if (el.settingModelsDir) el.settingModelsDir.value = comfy.models_dir || s.models_dir || '';
      if (el.settingDefaultLang) el.settingDefaultLang.value = s.language || s.default_language || 'auto';
      if (el.settingWebmExport) el.settingWebmExport.checked = s.export_webm !== false;

    } catch (err) {
      console.error('Error loading settings into modal:', err);
      showToast(err.message || 'Fehler beim Laden der Einstellungen', 'error');
    }
  }

  function populateSettingsModelDropdowns(modelsData, currentSettings) {
    if (!modelsData) return;

    if (el.settingMinimaxUnetSelect && Array.isArray(modelsData.minimax_unets)) {
      const cur = el.settingMinimaxUnetInput ? el.settingMinimaxUnetInput.value : '';
      el.settingMinimaxUnetSelect.innerHTML = `<option value="">-- ${escapeHtml(t('optSelectModel'))} --</option>`;
      modelsData.minimax_unets.forEach(u => {
        const opt = document.createElement('option');
        const fn = typeof u === 'string' ? u : (u.filename || u.name);
        const title = typeof u === 'string' ? u : (u.title || u.name);
        opt.value = fn;
        opt.textContent = title;
        el.settingMinimaxUnetSelect.appendChild(opt);
      });
      if (cur) el.settingMinimaxUnetSelect.value = cur;
    }

    const turboList = modelsData.minimax_turbo_loras || modelsData.turbo_loras || [];
    if (el.settingTurboLoraSelect && Array.isArray(turboList)) {
      const cur = el.settingTurboLoraInput ? el.settingTurboLoraInput.value : '';
      el.settingTurboLoraSelect.innerHTML = `<option value="">-- Kein Turbo / Standard --</option>`;
      turboList.forEach(tl => {
        const opt = document.createElement('option');
        const fn = typeof tl === 'string' ? tl : (tl.filename || tl.name);
        const title = typeof tl === 'string' ? tl : (tl.title || tl.name);
        const steps = typeof tl === 'object' && (tl.steps !== undefined ? tl.steps : tl.detected_steps);
        const stepLabel = steps ? ` [${steps} Steps]` : '';
        opt.value = fn;
        opt.textContent = title + stepLabel;
        opt.dataset.steps = steps || '';
        el.settingTurboLoraSelect.appendChild(opt);
      });
      if (cur) el.settingTurboLoraSelect.value = cur;
    }

    if (el.settingMusicModel && Array.isArray(modelsData.music_checkpoints)) {
      const cur = el.settingMusicModel.value;
      el.settingMusicModel.innerHTML = `<option value="">-- ${escapeHtml(t('optSelectModel'))} --</option>`;
      modelsData.music_checkpoints.forEach(mc => {
        const opt = document.createElement('option');
        const fn = typeof mc === 'string' ? mc : (mc.filename || mc.name);
        const title = typeof mc === 'string' ? mc : (mc.title || mc.name);
        opt.value = fn;
        opt.textContent = title;
        el.settingMusicModel.appendChild(opt);
      });
      if (cur) el.settingMusicModel.value = cur;
    }

    if (el.settingLmsModel && Array.isArray(modelsData.lm_studio_models)) {
      const cur = el.settingLmsModel.value;
      el.settingLmsModel.innerHTML = `<option value="">-- ${escapeHtml(t('optSelectModel'))} --</option>`;
      modelsData.lm_studio_models.forEach(m => {
        const opt = document.createElement('option');
        const mId = typeof m === 'string' ? m : (m.id || m.name);
        opt.value = mId;
        opt.textContent = mId;
        el.settingLmsModel.appendChild(opt);
      });
      if (cur) el.settingLmsModel.value = cur;
    }
  }

  async function refreshLmStudioModels() {
    const url = el.settingLmsUrl ? el.settingLmsUrl.value.trim() : '';
    try {
      if (el.btnRefreshLmsModels) el.btnRefreshLmsModels.disabled = true;
      const res = await API.getSettingsModels(url);
      if (res && res.success && Array.isArray(res.lm_studio_models)) {
        if (el.settingLmsModel) {
          const currentVal = el.settingLmsModel.value;
          el.settingLmsModel.innerHTML = `<option value="">-- ${escapeHtml(t('optSelectModel'))} --</option>`;
          res.lm_studio_models.forEach(m => {
            const opt = document.createElement('option');
            const mId = typeof m === 'string' ? m : (m.id || m.name);
            opt.value = mId;
            opt.textContent = mId;
            el.settingLmsModel.appendChild(opt);
          });
          el.settingLmsModel.value = currentVal;
        }
        showToast(t('lmModelsRefreshed') || `${res.lm_studio_models.length} LM Studio Modelle geladen`, 'success');
      } else {
        showToast('Keine Modelle von LM Studio gefunden oder LM Studio nicht erreichbar.', 'warning');
      }
    } catch (err) {
      showToast(err.message || 'Fehler beim Abrufen der LM Studio Modelle', 'error');
    } finally {
      if (el.btnRefreshLmsModels) el.btnRefreshLmsModels.disabled = false;
    }
  }

  async function saveSettingsData() {
    try {
      if (el.btnSaveSettings) el.btnSaveSettings.disabled = true;

      const payload = {
        language: el.settingDefaultLang ? el.settingDefaultLang.value : 'auto',
        export_webm: el.settingWebmExport ? el.settingWebmExport.checked : true,
        comfyui: {
          server_address: el.settingComfyUrl ? el.settingComfyUrl.value.trim() : '127.0.0.1:8188',
          models_dir: el.settingModelsDir ? el.settingModelsDir.value.trim() : '',
          models_search_paths: [
            "../ComfyUI/models",
            "../ComfyUI_windows_portable/ComfyUI/models"
          ]
        },
        minimax_i2v: {
          unet_name: el.settingMinimaxUnetInput ? el.settingMinimaxUnetInput.value.trim() : '',
          turbo_lora: el.settingTurboLoraInput ? el.settingTurboLoraInput.value.trim() : '',
          turbo_strength: el.settingTurboStrength ? parseFloat(el.settingTurboStrength.value) || 1.0 : 1.0,
          steps: el.settingMinimaxSteps ? parseInt(el.settingMinimaxSteps.value, 10) || 8 : 8,
          clip_name: el.settingMinimaxClip ? el.settingMinimaxClip.value.trim() : '',
          video_vae_name: el.settingMinimaxVae ? el.settingMinimaxVae.value.trim() : '',
          audio_vae_name: 'minimax_h3_audio_vae_fp32.safetensors'
        },
        music_studio: {
          enabled: el.settingMusicEnabled ? el.settingMusicEnabled.checked : false,
          checkpoint: el.settingMusicModel ? el.settingMusicModel.value.trim() : '',
          steps: el.settingMusicSteps ? parseInt(el.settingMusicSteps.value, 10) || 25 : 25,
          cfg: el.settingMusicCfg ? parseFloat(el.settingMusicCfg.value) || 4.0 : 4.0,
          volume: el.settingMusicVolume ? (parseInt(el.settingMusicVolume.value, 10) || 35) / 100.0 : 0.35,
          ducking: el.settingMusicDucking ? el.settingMusicDucking.checked : true
        },
        lm_studio: {
          url: el.settingLmsUrl ? el.settingLmsUrl.value.trim() : 'http://127.0.0.1:1234/v1/chat/completions',
          model_name: el.settingLmsModel ? el.settingLmsModel.value.trim() : '',
          temperature: el.settingLmsTemp ? parseFloat(el.settingLmsTemp.value) || 0.7 : 0.7
        }
      };

      const res = await API.saveSettings(payload);
      if (res && res.success) {
        showToast(t('settingsSavedSuccess') || 'Einstellungen erfolgreich gespeichert!', 'success');
        closeSettingsModal();
      } else {
        throw new Error((res && res.error) || 'Speichern fehlgeschlagen');
      }
    } catch (err) {
      console.error('Failed to save settings:', err);
      showToast(err.message || 'Fehler beim Speichern der Einstellungen', 'error');
    } finally {
      if (el.btnSaveSettings) el.btnSaveSettings.disabled = false;
    }
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

        Object.values(el.tabContents).forEach(content => content && content.classList.remove('active'));
        if (el.tabContents[tab]) el.tabContents[tab].classList.add('active');

        if (tab === 'scenes') fetchAndRenderTimeline();
        if (tab === 'json') renderJsonPreview();
        if (tab === 'music') renderMusicStudio();
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

    // Model Modal Events
    if (el.btnCloseModelModal) el.btnCloseModelModal.addEventListener('click', closeModelPickerModal);
    if (el.modelSearchInput) {
      el.modelSearchInput.addEventListener('input', () => {
        renderModelModalCards();
      });
    }
    if (el.modelFilterTabs) {
      el.modelFilterTabs.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-filter-pill');
        if (!btn) return;
        el.modelFilterTabs.querySelectorAll('.btn-filter-pill').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.modelFilterCategory = btn.dataset.filter || 'all';
        renderModelModalCards();
      });
    }

    // LM Studio AI & Modals
    if (el.llmStatusPill) el.llmStatusPill.addEventListener('click', refreshLlmStatus);
    if (el.btnAiSuggestScene) el.btnAiSuggestScene.addEventListener('click', handleAiSuggestScene);
    if (el.btnAiExtractVars) el.btnAiExtractVars.addEventListener('click', handleAiExtractVariables);
    if (el.btnCloseAiModal) el.btnCloseAiModal.addEventListener('click', closeAiModal);
    if (el.btnDiscardAiModal) el.btnDiscardAiModal.addEventListener('click', closeAiModal);
    if (el.btnApplyAiModal) el.btnApplyAiModal.addEventListener('click', applyPendingAiScene);

    // Music Studio Events
    if (el.chkMusicEnabled) {
      el.chkMusicEnabled.addEventListener('change', () => {
        if (!state.screenplay.music) state.screenplay.music = {};
        state.screenplay.music.enabled = el.chkMusicEnabled.checked;
        markDirty();
      });
    }
    if (el.musicModelSelect) {
      el.musicModelSelect.addEventListener('change', () => {
        if (!state.screenplay.music) state.screenplay.music = {};
        state.screenplay.music.model = el.musicModelSelect.value;
        markDirty();
      });
    }
    if (el.musicPromptInput) {
      el.musicPromptInput.addEventListener('input', () => {
        if (!state.screenplay.music) state.screenplay.music = {};
        state.screenplay.music.prompt = el.musicPromptInput.value.trim();
        markDirty();
      });
    }
    if (el.musicVolumeSelect) {
      el.musicVolumeSelect.addEventListener('change', () => {
        if (!state.screenplay.music) state.screenplay.music = {};
        state.screenplay.music.volume = parseFloat(el.musicVolumeSelect.value);
        markDirty();
      });
    }
    if (el.chkMusicDucking) {
      el.chkMusicDucking.addEventListener('change', () => {
        if (!state.screenplay.music) state.screenplay.music = {};
        state.screenplay.music.ducking = el.chkMusicDucking.checked;
        markDirty();
      });
    }
    if (el.btnSuggestMusicTags) {
      el.btnSuggestMusicTags.addEventListener('click', handleSuggestMusicTags);
    }
    if (el.btnScoreMovie) {
      el.btnScoreMovie.addEventListener('click', handleScoreMovie);
    }

    // Story Generator Events
    if (el.btnStoryGenerator) el.btnStoryGenerator.addEventListener('click', openStoryGeneratorModal);
    if (el.btnCloseStoryGenModal) el.btnCloseStoryGenModal.addEventListener('click', closeStoryGeneratorModal);
    if (el.btnCancelStoryGen) el.btnCancelStoryGen.addEventListener('click', closeStoryGeneratorModal);
    if (el.btnExecuteStoryGen) el.btnExecuteStoryGen.addEventListener('click', executeStoryGenerator);
    if (el.btnApplyStoryGen) el.btnApplyStoryGen.addEventListener('click', applyStoryGeneratorResults);
    if (el.storyGenMaxDuration) {
      el.storyGenMaxDuration.addEventListener('input', () => {
        if (el.storyGenMaxDurationVal) el.storyGenMaxDurationVal.textContent = `${el.storyGenMaxDuration.value}s`;
      });
    }
    if (el.storyGenMaxTokens) {
      el.storyGenMaxTokens.addEventListener('input', () => {
        const val = parseInt(el.storyGenMaxTokens.value, 10).toLocaleString();
        if (el.storyGenMaxTokensVal) el.storyGenMaxTokensVal.textContent = val;
      });
    }

    // Story Wizard Events
    if (el.btnStoryWizard) el.btnStoryWizard.addEventListener('click', openStoryWizardModal);
    if (el.btnCloseWizardModal) el.btnCloseWizardModal.addEventListener('click', closeStoryWizardModal);
    if (el.btnWizardFinish) el.btnWizardFinish.addEventListener('click', finishStoryWizard);
    if (el.btnWizardStart) el.btnWizardStart.addEventListener('click', startStoryWizardFromSetup);
    if (el.btnWizardRegenerate) el.btnWizardRegenerate.addEventListener('click', () => {
      const instr = el.wizardUserInstruction ? el.wizardUserInstruction.value.trim() : '';
      generateNextWizardStep(instr);
    });
    if (el.btnWizardApplyAndNext) el.btnWizardApplyAndNext.addEventListener('click', applyWizardStepAndNext);
    if (el.btnWizardSaveEdits) el.btnWizardSaveEdits.addEventListener('click', saveCurrentWizardSceneEdits);
    if (el.btnWizardRecreateScene) el.btnWizardRecreateScene.addEventListener('click', recreateCurrentWizardScene);
    if (el.btnWizardBackToNext) el.btnWizardBackToNext.addEventListener('click', returnToDraftingNextScene);
    if (el.wizardInteractiveProducerInstructions) {
      el.wizardInteractiveProducerInstructions.addEventListener('input', () => {
        const val = el.wizardInteractiveProducerInstructions.value.trim();
        state.wizard.producerInstructions = val;
        state.screenplay.producer_instructions = val;
        if (el.wizardProducerInstructions) el.wizardProducerInstructions.value = val;
        markDirty();
      });
    }
    if (el.wizardProducerInstructions) {
      el.wizardProducerInstructions.addEventListener('input', () => {
        const val = el.wizardProducerInstructions.value.trim();
        state.wizard.producerInstructions = val;
        state.screenplay.producer_instructions = val;
        if (el.wizardInteractiveProducerInstructions) el.wizardInteractiveProducerInstructions.value = val;
        markDirty();
      });
    }
    if (el.wizardMaxDuration) {
      el.wizardMaxDuration.addEventListener('input', () => {
        if (el.wizardMaxDurationVal) el.wizardMaxDurationVal.textContent = `${el.wizardMaxDuration.value}s`;
      });
    }
    if (el.wizardMaxTokens) {
      el.wizardMaxTokens.addEventListener('input', () => {
        const val = parseInt(el.wizardMaxTokens.value, 10).toLocaleString();
        if (el.wizardMaxTokensVal) el.wizardMaxTokensVal.textContent = val;
      });
    }

    // Harmonize Screenplay Button
    if (el.btnHarmonizeScript) {
      el.btnHarmonizeScript.addEventListener('click', () => handleHarmonizeScreenplay(false));
    }

    // Backdrop click close for modals
    if (el.loraModal) {
      el.loraModal.addEventListener('click', (e) => {
        if (e.target === el.loraModal) closeLoraPickerModal();
      });
    }
    if (el.modelModal) {
      el.modelModal.addEventListener('click', (e) => {
        if (e.target === el.modelModal) closeModelPickerModal();
      });
    }

    // In-App Guide Events
    if (el.btnGuide) {
      el.btnGuide.addEventListener('click', () => openGuideModal('section-workflow'));
    }
    if (el.btnCloseGuideModal) {
      el.btnCloseGuideModal.addEventListener('click', closeGuideModal);
    }
    if (el.btnCloseGuideModalBtn) {
      el.btnCloseGuideModalBtn.addEventListener('click', closeGuideModal);
    }
    if (el.btnOpenGuideFromWizard) {
      el.btnOpenGuideFromWizard.addEventListener('click', () => {
        openGuideModal('section-continuity');
      });
    }
    if (el.btnOpenGuideFromWizardInteractive) {
      el.btnOpenGuideFromWizardInteractive.addEventListener('click', () => {
        openGuideModal('section-continuity');
      });
    }
    if (el.guideNav) {
      el.guideNav.addEventListener('click', (e) => {
        const item = e.target.closest('.guide-nav-item');
        if (item) {
          const targetId = item.getAttribute('data-guide-target');
          if (targetId) switchGuideSection(targetId);
        }
      });
    }
    if (el.guideModal) {
      el.guideModal.addEventListener('click', (e) => {
        if (e.target === el.guideModal) closeGuideModal();
      });
    }

    // Video Player Modal Events
    if (el.btnToggleVideoPlayer) {
      el.btnToggleVideoPlayer.addEventListener('click', toggleVideoPlayer);
    }
    if (el.btnCloseVideoModal) {
      el.btnCloseVideoModal.addEventListener('click', closeVideoPlayerModal);
    }
    if (el.btnCloseVideoModalBtn) {
      el.btnCloseVideoModalBtn.addEventListener('click', closeVideoPlayerModal);
    }
    if (el.videoPlayerModal) {
      el.videoPlayerModal.addEventListener('click', (e) => {
        if (e.target === el.videoPlayerModal) closeVideoPlayerModal();
      });
    }

    // Settings Modal Events
    if (el.btnSettings) {
      el.btnSettings.addEventListener('click', openSettingsModal);
    }
    if (el.btnCloseSettingsModal) {
      el.btnCloseSettingsModal.addEventListener('click', closeSettingsModal);
    }
    if (el.btnCloseSettingsModalBtn) {
      el.btnCloseSettingsModalBtn.addEventListener('click', closeSettingsModal);
    }
    if (el.btnSaveSettings) {
      el.btnSaveSettings.addEventListener('click', saveSettingsData);
    }
    if (el.settingsModal) {
      el.settingsModal.addEventListener('click', (e) => {
        if (e.target === el.settingsModal) closeSettingsModal();
      });
    }

    // Settings Tab Switching
    document.querySelectorAll('.settings-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.getAttribute('data-tab');
        if (tab) switchSettingsTab(tab);
      });
    });

    // Settings Model/LoRA Picker & Refresh
    if (el.btnPickTurboLora) {
      el.btnPickTurboLora.addEventListener('click', openLoraPickerModalForTurbo);
    }
    if (el.btnRefreshLmsModels) {
      el.btnRefreshLmsModels.addEventListener('click', refreshLmStudioModels);
    }

    // Minimax UNET Select & Input sync
    if (el.settingMinimaxUnetSelect) {
      el.settingMinimaxUnetSelect.addEventListener('change', () => {
        if (el.settingMinimaxUnetInput) el.settingMinimaxUnetInput.value = el.settingMinimaxUnetSelect.value;
      });
    }
    if (el.settingMinimaxUnetInput) {
      el.settingMinimaxUnetInput.addEventListener('input', () => {
        if (el.settingMinimaxUnetSelect) el.settingMinimaxUnetSelect.value = el.settingMinimaxUnetInput.value;
      });
    }

    // Turbo LoRA Select & Input sync with auto-detection of steps
    if (el.settingTurboLoraSelect) {
      el.settingTurboLoraSelect.addEventListener('change', () => {
        const selectedVal = el.settingTurboLoraSelect.value;
        if (el.settingTurboLoraInput) el.settingTurboLoraInput.value = selectedVal;
        const selectedOpt = el.settingTurboLoraSelect.options[el.settingTurboLoraSelect.selectedIndex];
        if (selectedOpt && selectedOpt.dataset.steps) {
          if (el.settingMinimaxSteps) el.settingMinimaxSteps.value = selectedOpt.dataset.steps;
        } else if (selectedVal) {
          const vLow = selectedVal.toLowerCase();
          if (vLow.includes('4step') || vLow.includes('4_step') || vLow.includes('4 step') || vLow.includes('4-step') || vLow.includes('4s')) {
            if (el.settingMinimaxSteps) el.settingMinimaxSteps.value = 4;
          } else if (vLow.includes('8step') || vLow.includes('8_step') || vLow.includes('8 step') || vLow.includes('8-step') || vLow.includes('8s')) {
            if (el.settingMinimaxSteps) el.settingMinimaxSteps.value = 8;
          }
        }
      });
    }
    if (el.settingTurboLoraInput) {
      el.settingTurboLoraInput.addEventListener('input', () => {
        if (el.settingTurboLoraSelect) el.settingTurboLoraSelect.value = el.settingTurboLoraInput.value;
      });
    }

    // Range Sliders Value Badges
    if (el.settingTurboStrength) {
      el.settingTurboStrength.addEventListener('input', () => {
        if (el.valTurboStrength) el.valTurboStrength.textContent = Number(el.settingTurboStrength.value).toFixed(2);
      });
    }
    if (el.settingMusicVolume) {
      el.settingMusicVolume.addEventListener('input', () => {
        if (el.valMusicVolume) el.valMusicVolume.textContent = `${el.settingMusicVolume.value}%`;
      });
    }
    if (el.settingLmsTemp) {
      el.settingLmsTemp.addEventListener('input', () => {
        if (el.valLmsTemp) el.valLmsTemp.textContent = Number(el.settingLmsTemp.value).toFixed(2);
      });
    }

    // Keyboard Shortcuts (Ctrl+S to save, Escape to close modals)
    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        saveCurrentProject();
      } else if (e.key === 'Escape') {
        closeModelPickerModal();
        closeLoraPickerModal();
        closeGuideModal();
        closeVideoPlayerModal();
        closeSettingsModal();
      }
    });
  }

  // Start Application
  window.addEventListener('DOMContentLoaded', initApp);
})();
