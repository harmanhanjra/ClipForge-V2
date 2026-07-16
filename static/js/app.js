/* ================================================================
   Jigarzzz❤️ — Premium Video Suite · app.js  v5
   ================================================================ */
'use strict';

// ─────────────────────────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────────────────────────
const state = {
    voiceData:    null,      // { voices, voice_styles, mood_labels }
    currentLang:  'ur-PK',
    currentVoice: '',
    currentStyle: '',        // selected mood key
    rateVal:      0,
    pitchVal:     0,
    statsFiles:   0,
    statsClips:   0,
    statsAudio:   0,
    outputs:      [],
    nvidiaMetadata: null,
};

// ─────────────────────────────────────────────────────────────────
// UTILITIES
// ─────────────────────────────────────────────────────────────────
function $(id)   { return document.getElementById(id); }
function $q(sel) { return document.querySelector(sel); }

function iconSvg(name) {
    const paths = {
        play: '<path d="M9 7v10l8-5-8-5Z" stroke-width="1.8" stroke-linejoin="round"/>',
        download: '<path d="M12 4v10m0 0 4-4m-4 4-4-4M5 19h14" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
        video: '<path d="M4 7h16v11H4zM8 7l2-3h4l2 3M9.5 11l5 3-5 3v-6Z" stroke-width="1.7" stroke-linejoin="round"/>',
        clip: '<path d="m8 4 8 16M16 4 8 20M5 8h14M5 16h14" stroke-width="1.7" stroke-linecap="round"/>',
        empty: '<path d="M4 6.5h16v12H4zM8 6.5l2-3h4l2 3M10 11l5 2.5-5 2.5v-5Z" stroke-width="1.6" stroke-linejoin="round"/>'
    };
    return `<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">${paths[name] || paths.video}</svg>`;
}

function showToast(msg, type = 'success', duration = 3500) {
    const t = $('toast');
    t.textContent = msg;
    t.className = `toast ${type} show`;
    setTimeout(() => t.classList.remove('show'), duration);
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 30000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        return await fetch(url, { ...options, signal: controller.signal });
    } catch (error) {
        if (error.name === 'AbortError') {
            throw new Error('The command timed out. Please try again or use a shorter video.');
        }
        throw error;
    } finally {
        clearTimeout(timer);
    }
}

function animateCount(el, target) {
    const start = parseInt(el.textContent) || 0;
    const diff  = target - start;
    if (diff === 0) return;
    const step  = Math.ceil(Math.abs(diff) / 20);
    const dir   = diff > 0 ? 1 : -1;
    let cur = start;
    const iv = setInterval(() => {
        cur += dir * step;
        if ((dir > 0 && cur >= target) || (dir < 0 && cur <= target)) {
            cur = target;
            clearInterval(iv);
        }
        el.textContent = cur;
    }, 40);
}

// ─────────────────────────────────────────────────────────────────
// GALLERY / LIBRARY
// ─────────────────────────────────────────────────────────────────
async function loadGallery() {
    const container = $('gallery-container');
    const searchVal = ($('library-search')?.value || '').toLowerCase();

    try {
        const res  = await fetchWithTimeout('/api/outputs', {}, 15000);
        const data = await res.json();
        state.outputs = data;
        syncNvidiaVideoOptions(data);

        const filtered = searchVal
            ? data.filter(f => f.filename.toLowerCase().includes(searchVal))
            : data;

        if (!filtered.length) {
            container.innerHTML = `
                <div class="empty-library">
                    <div class="library-empty-art">${iconSvg('empty')}</div>
                    <strong>${searchVal ? 'No matching exports' : 'No exports yet'}</strong>
                    <span>${searchVal ? 'Try a different filename.' : 'Your completed videos and clips will appear here.'}</span>
                </div>`;
            animateCount($('stat-files'), 0);
            return;
        }

        state.statsFiles = data.length;
        animateCount($('stat-files'), data.length);

        container.innerHTML = filtered.map(file => {
            const isClip  = file.filename.includes('clip_');
            const icon    = isClip ? iconSvg('clip') : iconSvg('video');
            const metadata = [file.duration, file.size].filter(Boolean).join(' · ');
            return `
            <div class="video-card" data-fn="${file.filename}">
                <div class="video-card-info">
                    <span class="video-card-title">${icon} ${file.filename}</span>
                    <span class="video-card-meta">${metadata}</span>
                </div>
                <div class="video-card-actions">
                    <button class="action-btn play-action" data-fn="${file.filename}">${iconSvg('play')}<span>Play</span></button>
                    <button class="action-btn download-action" data-fn="${file.filename}">${iconSvg('download')}<span>Save</span></button>
                </div>
            </div>`;
        }).join('');

        // Wire up play / download
        container.querySelectorAll('.play-action').forEach(btn => {
            btn.addEventListener('click', () => openVideoModal(btn.dataset.fn));
        });
        container.querySelectorAll('.download-action').forEach(btn => {
            btn.addEventListener('click', () => {
                const a = document.createElement('a');
                a.href = `/api/outputs/${btn.dataset.fn}`;
                a.download = btn.dataset.fn;
                a.click();
            });
        });

    } catch (e) {
        container.innerHTML = `<div class="empty-library"><span>Failed to load library.</span></div>`;
    }
}

// ─────────────────────────────────────────────────────────────────
// CLEAR LIBRARY
// ─────────────────────────────────────────────────────────────────
async function clearLibrary() {
    const confirmed = confirm('Delete all exported files from disk?\n\nThis cannot be undone.');
    if (!confirmed) return;

    const btn = $('clear-library-btn');
    btn.textContent = 'Clearing…';
    btn.disabled = true;

    try {
        const res  = await fetchWithTimeout('/api/clear-library', { method: 'POST' }, 30000);
        const data = await res.json();
        showToast(`✅ Cleared ${data.deleted} file${data.deleted !== 1 ? 's' : ''} from library`, 'success');
        animateCount($('stat-files'), 0);
        await loadGallery();
    } catch (e) {
        showToast('❌ Failed to clear library', 'error');
    } finally {
        btn.textContent = 'Clear all';
        btn.disabled = false;
    }
}

// ─────────────────────────────────────────────────────────────────
// VIDEO MODAL
// ─────────────────────────────────────────────────────────────────
function openVideoModal(filename) {
    $('modal-title').textContent = filename;
    $('modal-player').src = `/api/outputs/${filename}`;
    $('video-modal').classList.add('active');
    $('modal-player').play();
}
function closeVideoModal() {
    $('modal-player').pause();
    $('modal-player').src = '';
    $('video-modal').classList.remove('active');
}

// ─────────────────────────────────────────────────────────────────
// VOICE SYSTEM
// ─────────────────────────────────────────────────────────────────
async function loadVoices() {
    try {
        const res  = await fetchWithTimeout('/api/voices', {}, 15000);
        state.voiceData = await res.json();
        updateVoiceDropdown(state.currentLang, 'tts');
        updateVoiceDropdown(state.currentLang, 'ai');
    } catch (e) {
        console.error('Failed to load voices:', e);
    }
}

function updateVoiceDropdown(lang, prefix = 'tts') {
    const voiceSel = $(`${prefix}-voice`);
    if (!voiceSel || !state.voiceData) return;

    const voices = state.voiceData.voices[lang] || {};
    voiceSel.innerHTML = Object.entries(voices).map(([label, id]) =>
        `<option value="${id}">${label}</option>`
    ).join('');

    if (prefix === 'tts') {
        state.currentVoice = voiceSel.value;
        updateMoodGrid('tts');
        buildAgeGrid('tts');
    } else {
        state.aiCurrentVoice = voiceSel.value;
        updateMoodGrid('ai');
        buildAgeGrid('ai');
    }
}

function updateMoodGrid(prefix = 'tts') {
    const voice      = $(`${prefix}-voice`)?.value || '';
    const moodGrid   = $(`${prefix}-mood-grid`);
    const moodTag    = $(`${prefix}-mood-support-tag`);
    const moodData   = state.voiceData?.voice_styles || {};
    const moodLabels = state.voiceData?.mood_labels  || {};
    const supported  = moodData[voice] || [];

    if (prefix === 'tts') state.currentVoice = voice;
    else state.aiCurrentVoice = voice;

    if (!moodGrid) return;

    if (supported.length === 0) {
        if (moodTag) {
            moodTag.textContent   = '⚠ Default only — switch to Aria/Jenny/Tony/Nancy for moods';
            moodTag.className     = 'mood-support-tag unsupported';
        }
        const allMoods = Object.entries(moodLabels);
        moodGrid.innerHTML = allMoods.map(([key, label]) => {
            const active = key === '' ? 'active' : '';
            return `<span class="mood-chip disabled ${active}" data-mood="${key}">${label}</span>`;
        }).join('');
        if (prefix === 'tts') {
            state.currentStyle = '';
            $('tts-style').value = '';
        } else {
            state.aiCurrentStyle = '';
            $('ai-tts-style').value = '';
        }
    } else {
        if (moodTag) {
            moodTag.textContent = '✓ Mood supported';
            moodTag.className   = 'mood-support-tag supported';
        }
        const currentStyle = prefix === 'tts' ? state.currentStyle : state.aiCurrentStyle;
        const chips = [['', moodLabels[''] || '🎙️ Default Style'], ...supported.map(k => [k, moodLabels[k] || k])];
        moodGrid.innerHTML = chips.map(([key, label]) => {
            const active = key === currentStyle ? 'active' : '';
            return `<span class="mood-chip ${active}" data-mood="${key}">${label}</span>`;
        }).join('');
    }

    // Wire mood chip clicks
    moodGrid.querySelectorAll('.mood-chip:not(.disabled)').forEach(chip => {
        chip.addEventListener('click', () => {
            moodGrid.querySelectorAll('.mood-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            if (prefix === 'tts') {
                state.currentStyle       = chip.dataset.mood;
                $('tts-style').value     = chip.dataset.mood;
            } else {
                state.aiCurrentStyle     = chip.dataset.mood;
                $('ai-tts-style').value  = chip.dataset.mood;
            }
        });
    });
}

function buildAgeGrid(prefix = 'tts') {
    const grid     = $(`${prefix}-age-grid`);
    const presets  = state.voiceData?.age_presets || {};
    if (!grid) return;

    const currentAge = prefix === 'tts' ? (state.currentAge || 'adult') : (state.aiCurrentAge || 'adult');

    grid.innerHTML = Object.entries(presets).map(([key, p]) => {
        const active = key === currentAge ? 'active' : '';
        return `
        <span class="age-chip ${active}" data-age="${key}"
              data-rate="${p.rate}" data-pitch="${p.pitch}">
            ${p.label}
            <span class="age-desc">${p.desc}</span>
        </span>`;
    }).join('');

    grid.querySelectorAll('.age-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            grid.querySelectorAll('.age-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            if (prefix === 'tts') {
                state.currentAge = chip.dataset.age;
            } else {
                state.aiCurrentAge = chip.dataset.age;
            }

            const rateStr  = chip.dataset.rate;
            const pitchStr = chip.dataset.pitch;
            const rateNum  = parseInt(rateStr);
            const pitchNum = parseInt(pitchStr);

            // Update sliders (forms read from sliders on submit)
            const rSlider = $(`${prefix}-rate-slider`);
            const pSlider = $(`${prefix}-pitch-slider`);
            if (rSlider) {
                rSlider.value = rateNum;
                $(`${prefix}-rate-val`).textContent = formatRate(rateNum);
                // Dispatch input event so initSliders listeners also update state
                rSlider.dispatchEvent(new Event('input'));
            }
            if (pSlider) {
                pSlider.value = pitchNum;
                $(`${prefix}-pitch-val`).textContent = formatPitch(pitchNum);
                pSlider.dispatchEvent(new Event('input'));
            }
        });
    });

    if (prefix === 'tts' && !state.currentAge) state.currentAge = 'adult';
    if (prefix === 'ai' && !state.aiCurrentAge) state.aiCurrentAge = 'adult';
}

function formatRate(v)  {
    if (v === 0) return 'Normal';
    return v > 0 ? `+${v}% faster` : `${v}% slower`;
}
function formatPitch(v) {
    if (v === 0) return 'Normal';
    return v > 0 ? `+${v}Hz higher` : `${v}Hz lower`;
}

function initSliders(prefix = 'tts') {
    const rateSlider  = $(`${prefix}-rate-slider`);
    const pitchSlider = $(`${prefix}-pitch-slider`);
    if (!rateSlider || !pitchSlider) return;

    rateSlider.addEventListener('input', () => {
        const v = parseInt(rateSlider.value);
        if (prefix === 'tts') state.rateVal = v;
        else state.aiRateVal = v;
        $(`${prefix}-rate-val`).textContent = formatRate(v);
    });

    pitchSlider.addEventListener('input', () => {
        const v = parseInt(pitchSlider.value);
        if (prefix === 'tts') state.pitchVal = v;
        else state.aiPitchVal = v;
        $(`${prefix}-pitch-val`).textContent = formatPitch(v);
    });
}

async function previewVoice(prefix = 'tts') {
    const btn    = $(prefix === 'tts' ? 'preview-voice-btn' : 'ai-preview-voice-btn');
    const player = $(prefix === 'tts' ? 'voice-preview-player' : 'ai-voice-preview-player');
    const audio  = $(prefix === 'tts' ? 'preview-audio' : 'ai-preview-audio');
    const voice  = $(`${prefix}-voice`)?.value;
    const lang   = $(`${prefix}-language`)?.value || 'ur-PK';
    const style  = prefix === 'tts' ? state.currentStyle : state.aiCurrentStyle;
    const rateV  = parseInt($(`${prefix}-rate-slider`)?.value || 0);
    const pitchV = parseInt($(`${prefix}-pitch-slider`)?.value || 0);
    const rate   = rateV  >= 0 ? `+${rateV}%`   : `${rateV}%`;
    const pitch  = pitchV >= 0 ? `+${pitchV}Hz`  : `${pitchV}Hz`;

    if (!voice) return;

    btn.classList.add('loading');
    btn.textContent = '⏳ Generating…';

    try {
        const fd = new FormData();
        fd.append('voice', voice);
        fd.append('lang',  lang);
        fd.append('style', style);
        fd.append('style_degree', '1.5');
        fd.append('rate',  rate);
        fd.append('pitch', pitch);

        const res = await fetchWithTimeout('/api/preview-voice', { method: 'POST', body: fd }, 90000);
        if (!res.ok) throw new Error('Server error');

        const blob = await res.blob();
        const url  = URL.createObjectURL(blob);
        audio.src  = url;
        player.style.display = 'block';
        audio.play();

        showToast('🎧 Playing voice preview!', 'success', 2500);
    } catch (e) {
        showToast('❌ Preview failed — check server logs', 'error');
    } finally {
        btn.classList.remove('loading');
        btn.textContent = '▶ Preview';
    }
}

// ─────────────────────────────────────────────────────────────────
// TABS
// ─────────────────────────────────────────────────────────────────
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
                b.tabIndex = -1;
            });
            document.querySelectorAll('.tab-content').forEach(c => {
                c.classList.remove('active');
                c.hidden = true;
            });
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');
            btn.tabIndex = 0;
            const panel = $(btn.dataset.tab);
            panel?.classList.add('active');
            if (panel) panel.hidden = false;
        });
    });

    const tabs = Array.from(document.querySelectorAll('.tab-btn'));
    tabs.forEach((tab, index) => {
        tab.tabIndex = tab.classList.contains('active') ? 0 : -1;
        const panel = $(tab.dataset.tab);
        if (panel) panel.hidden = !tab.classList.contains('active');
        tab.addEventListener('keydown', event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
            event.preventDefault();
            let next = index;
            if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
            if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
            if (event.key === 'Home') next = 0;
            if (event.key === 'End') next = tabs.length - 1;
            tabs[next].focus();
            tabs[next].click();
        });
    });
}

function syncNvidiaVideoOptions(files = state.outputs) {
    const select = $('nvidia-video-select');
    if (!select) return;
    const previous = select.value;
    select.innerHTML = '';
    if (!files.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No exported videos found';
        select.appendChild(option);
        return;
    }
    files.forEach(file => {
        const option = document.createElement('option');
        option.value = file.filename;
        option.textContent = `${file.filename}${file.size ? ` · ${file.size}` : ''}`;
        select.appendChild(option);
    });
    if (files.some(file => file.filename === previous)) select.value = previous;
}

// ─────────────────────────────────────────────────────────────────
// AUDIO SOURCE TOGGLE (TTS / Upload / None)
// ─────────────────────────────────────────────────────────────────
function initAudioToggle() {
    const toggles = document.querySelectorAll('#merger-tab .toggle-btn');
    toggles.forEach(btn => {
        btn.addEventListener('click', () => {
            toggles.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const type = btn.dataset.type;
            $('tts-panel')?.classList.toggle('active', type === 'script');
            $('audio-upload-panel')?.classList.toggle('active', type === 'upload');
            $('no-audio-panel')?.classList.toggle('active', type === 'none');
        });
    });

    const clipToggles = document.querySelectorAll('#clipper-tab .toggle-btn');
    clipToggles.forEach(btn => {
        btn.addEventListener('click', () => {
            clipToggles.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const type = btn.dataset.type;
            $('auto-clip-panel')?.classList.toggle('active', type === 'auto');
            $('timestamps-clip-panel')?.classList.toggle('active', type === 'timestamps');
        });
    });
}

// ─────────────────────────────────────────────────────────────────
// DROPZONE
// ─────────────────────────────────────────────────────────────────
function initDropzone() {
    const dropzone  = $('video-dropzone');
    const fileInput = $('videos');
    const queue     = $('video-queue');
    const pill      = $('video-count-pill');
    if (!dropzone) return;

    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
    dropzone.addEventListener('drop', e => {
        e.preventDefault();
        dropzone.classList.remove('drag-over');
        handleFiles(e.dataTransfer.files);
    });
    fileInput.addEventListener('change', () => handleFiles(fileInput.files));

    function handleFiles(files) {
        const arr = Array.from(files).filter(f => f.type.startsWith('video/'));
        queue.innerHTML = arr.map(f =>
            `<div class="file-item"><span>🎞️ ${f.name}</span><span>${(f.size/1024/1024).toFixed(1)} MB</span></div>`
        ).join('');
        pill.style.display = arr.length ? 'inline-flex' : 'none';
        pill.textContent   = `${arr.length} file${arr.length !== 1 ? 's' : ''}`;
    }
}

// ─────────────────────────────────────────────────────────────────
// PROGRESS BAR ANIMATION
// ─────────────────────────────────────────────────────────────────
function startProgress(fillId, pctId, stepId, steps, onDone) {
    const fill = $(fillId);
    const pct  = $(pctId);
    const step = $(stepId);
    if (!fill || !pct || !step || !steps.length) return null;

    let idx = 0;
    let cur = 0;
    let stepStart = 0;
    let elapsed = 0;
    let waitingSince = null;

    step.textContent = steps[0].label;

    // Advance every stage with one timer. Creating a new inner timer from a
    // zero-delay interval caused hundreds of overlapping progress updates.
    const iv = setInterval(() => {
        const currentStep = steps[idx];
        if (!currentStep) {
            if (waitingSince === null) {
                waitingSince = Date.now();
                onDone?.();
            }
            const waitingSeconds = Math.floor((Date.now() - waitingSince) / 1000);
            const minutes = Math.floor(waitingSeconds / 60);
            const seconds = String(waitingSeconds % 60).padStart(2, '0');
            pct.textContent = `Working ${minutes}:${seconds}`;
            step.textContent = 'Server is still processing — long videos can take several minutes…';
            return;
        }

        elapsed += 120;
        const fraction = Math.min(elapsed / currentStep.dur, 1);
        cur = stepStart + ((currentStep.pct - stepStart) * fraction);
        fill.style.width = `${cur}%`;
        pct.textContent  = `${Math.round(cur)}%`;

        if (fraction >= 1) {
            stepStart = currentStep.pct;
            elapsed = 0;
            idx++;
            if (steps[idx]) step.textContent = steps[idx].label;
        }
    }, 120);

    return iv;
}

function showProgress(progressId) {
    $(progressId)?.classList.add('visible');
}
function hideProgress(progressId) {
    $(progressId)?.classList.remove('visible');
}

// ─────────────────────────────────────────────────────────────────
// MERGE FORM
// ─────────────────────────────────────────────────────────────────
function initMergeForm() {
    const form = $('merge-form');
    if (!form) return;

    form.addEventListener('submit', async e => {
        e.preventDefault();
        const audioType = $q('#merger-tab .toggle-btn.active')?.dataset.type || 'none';

        if (audioType === 'script' && !$('script_text').value.trim()) {
            showToast('⚠️ Please enter a voiceover script', 'error'); return;
        }

        const fd = new FormData(form);
        fd.set('audio_source', audioType);

        // Sync slider values to form data (use tts- prefix for merge tab)
        const rateV  = parseInt($('tts-rate-slider')?.value || 0);
        const pitchV = parseInt($('tts-pitch-slider')?.value || 0);
        fd.set('rate',  rateV  >= 0 ? `+${rateV}%`   : `${rateV}%`);
        fd.set('pitch', pitchV >= 0 ? `+${pitchV}Hz`  : `${pitchV}Hz`);
        fd.set('style', state.currentStyle);
        // Checkboxes don't submit when unchecked — send the real state explicitly.
        fd.set('trim_audio', $q('#merger-tab input[name="trim_audio"]')?.checked ? 'true' : 'false');

        const btn = $('merge-submit-btn');
        btn.disabled = true; btn.classList.add('loading');
        showProgress('merge-progress');

        const steps = [
            { pct: 25, label: '🎞️ Processing video clips…',  dur: 1800 },
            { pct: 50, label: '🔗 Merging & cropping…',       dur: 2200 },
            { pct: 70, label: '🎙️ Generating voiceover…',     dur: 1800 },
            { pct: 90, label: '🎵 Mixing audio tracks…',       dur: 1200 },
            { pct: 99, label: '📦 Finalising output…',         dur: 800  },
        ];
        const progressTimer = startProgress('merge-fill', 'merge-pct', 'merge-step', steps);

        try {
            const res  = await fetchWithTimeout('/api/merge', { method: 'POST', body: fd }, 1800000);
            const data = await res.json();

            if (progressTimer) clearInterval(progressTimer);
            $('merge-fill').style.width = '100%';
            $('merge-pct').textContent  = '100%';
            $('merge-step').textContent = '✅ Done!';

            if (data.success) {
                showToast(`✅ ${data.message}`, 'success', 5000);
                state.statsAudio++;
                animateCount($('stat-audio'), state.statsAudio);
                await loadGallery();
            } else {
                showToast(`❌ ${data.error}`, 'error', 6000);
            }
        } catch (err) {
            $('merge-pct').textContent = 'Error';
            $('merge-step').textContent = 'Processing stopped';
            showToast(err.message || 'Network error — check server', 'error');
        } finally {
            if (progressTimer) clearInterval(progressTimer);
            btn.disabled = false; btn.classList.remove('loading');
            setTimeout(() => hideProgress('merge-progress'), 2000);
        }
    });
}

// ─────────────────────────────────────────────────────────────────
// CLIP FORM
// ─────────────────────────────────────────────────────────────────
function initClipForm() {
    const form = $('clip-form');
    if (!form) return;

    const audioMode = $('audio-mode');
    const replacementAudio = $('replacement-audio');
    audioMode?.addEventListener('change', () => {
        const needsUpload = audioMode.value === 'upload';
        replacementAudio.disabled = !needsUpload;
        replacementAudio.required = needsUpload;
    });

    form.addEventListener('submit', async e => {
        e.preventDefault();
        const url = $('url')?.value.trim();
        if (!url || !/(youtube\.com|youtu\.be)/i.test(url)) {
            showToast('⚠️ Please enter a valid YouTube URL', 'error'); return;
        }

        const btn = $('clip-submit-btn');
        btn.disabled = true; btn.classList.add('loading');
        showProgress('clip-progress');

        const steps = [
            { pct: 20, label: '⬇️ Downloading video…',        dur: 3000 },
            { pct: 50, label: '✂️ Slicing into clips…',         dur: 2500 },
            { pct: 75, label: 'Applying creative adjustments…', dur: 2000 },
            { pct: 90, label: '💾 Saving clips to library…',   dur: 1200 },
            { pct: 92, label: '📦 Finalising server output…',  dur: 600  },
        ];
        const progressTimer = startProgress('clip-fill', 'clip-pct', 'clip-step', steps);

        try {
            const fd  = new FormData(form);
            // Checkboxes don't submit when unchecked — send the real state so
            // users can actually disable the mirror / zoom filters.
            fd.set('mirror', $q('#clipper-tab input[name="mirror"]')?.checked ? 'true' : 'false');
            fd.set('zoom',   $q('#clipper-tab input[name="zoom"]')?.checked ? 'true' : 'false');
            const res = await fetchWithTimeout('/api/clip', { method: 'POST', body: fd }, 900000);
            const data = await res.json();

            if (progressTimer) clearInterval(progressTimer);

            if (data.success) {
                $('clip-fill').style.width = '100%';
                $('clip-pct').textContent  = '100%';
                $('clip-step').textContent = '✅ Done!';
                showToast(`✅ ${data.message}`, 'success', 5000);
                state.statsClips += data.filenames?.length || 0;
                animateCount($('stat-clips'), state.statsClips);
                await loadGallery();
            } else {
                $('clip-pct').textContent  = 'Error';
                $('clip-step').textContent = '❌ Processing failed';
                showToast(`❌ ${data.error}`, 'error', 7000);
            }
        } catch (err) {
            $('clip-pct').textContent  = 'Error';
            $('clip-step').textContent = '❌ Connection failed';
            showToast(err.message || 'Network error — check server logs', 'error');
        } finally {
            if (progressTimer) clearInterval(progressTimer);
            btn.disabled = false; btn.classList.remove('loading');
            setTimeout(() => hideProgress('clip-progress'), 2000);
        }
    });
}

function initAIVideoForm() {
    const form = $('ai-video-form');
    if (!form) return;

    form.addEventListener('submit', async e => {
        e.preventDefault();
        
        const scriptText = $('ai_script_text').value.trim();
        if (!scriptText) {
            showToast('⚠️ Please enter a script', 'error');
            return;
        }

        const fd = new FormData(form);
        
        // Sync slider values to form data
        const rateV  = parseInt($('ai-rate-slider')?.value || 0);
        const pitchV = parseInt($('ai-pitch-slider')?.value || 0);
        fd.set('rate',  rateV  >= 0 ? `+${rateV}%`   : `${rateV}%`);
        fd.set('pitch', pitchV >= 0 ? `+${pitchV}Hz`  : `${pitchV}Hz`);
        fd.set('style', state.aiCurrentStyle || '');
        // Checkboxes don't submit when unchecked — send the real state explicitly.
        fd.set('trim_audio', $q('#ai-creator-tab input[name="trim_audio"]')?.checked ? 'true' : 'false');

        const btn = $('ai-submit-btn');
        btn.disabled = true;
        btn.classList.add('loading');
        showProgress('ai-progress');

        const steps = [
            { pct: 15, label: '📝 Parsing script & sentences…', dur: 1200 },
            { pct: 35, label: '🎙️ Generating narration speech…', dur: 3500 },
            { pct: 60, label: '🖼️ Downloading stock imagery…', dur: 4500 },
            { pct: 85, label: '🪄 Rendering dynamic slides…',  dur: 4000 },
            { pct: 98, label: '📦 Mixing & assembling video…', dur: 2000 },
        ];
        const progressTimer = startProgress('ai-fill', 'ai-pct', 'ai-step', steps);

        try {
            const res = await fetchWithTimeout('/api/generate-video', { method: 'POST', body: fd }, 1200000);
            const data = await res.json();

            if (progressTimer) clearInterval(progressTimer);
            $('ai-fill').style.width = '100%';
            $('ai-pct').textContent  = '100%';
            $('ai-step').textContent = '✅ Done!';

            if (data.success) {
                showToast(`✅ ${data.message} (${data.slides} slides)`, 'success', 5000);
                await loadGallery();
            } else {
                showToast(`❌ ${data.error}`, 'error', 7000);
            }
        } catch (err) {
            $('ai-pct').textContent = 'Error';
            $('ai-step').textContent = 'Generation stopped';
            showToast(err.message || 'Network error — check server logs', 'error');
        } finally {
            if (progressTimer) clearInterval(progressTimer);
            btn.disabled = false;
            btn.classList.remove('loading');
            setTimeout(() => hideProgress('ai-progress'), 2000);
        }
    });
}

// ─────────────────────────────────────────────────────────────────
// NVIDIA NIM ASSISTANT
// ─────────────────────────────────────────────────────────────────
async function readJsonResponse(response) {
    try { return await response.json(); }
    catch (_) { return { success: false, error: `Server error (HTTP ${response.status})` }; }
}

function setNvidiaConnection(connected) {
    const status = $('nvidia-status');
    if (status) {
        status.classList.toggle('connected', connected);
        status.innerHTML = `<span class="connection-dot"></span> ${connected ? 'Connected' : 'Not connected'}`;
    }
    if ($('nvidia-disconnect-btn')) $('nvidia-disconnect-btn').hidden = !connected;
    if ($('nvidia-verify-btn')) $('nvidia-verify-btn').hidden = !connected;
    if ($('nvidia-connect-btn')) $('nvidia-connect-btn').hidden = connected;
    if ($('nvidia-api-key')) {
        $('nvidia-api-key').disabled = connected;
        $('nvidia-api-key').placeholder = connected ? 'Saved securely with Windows' : 'nvapi-••••••••••••••••';
    }
}

async function loadNvidiaStatus() {
    try {
        const response = await fetchWithTimeout('/api/nvidia/status', {}, 10000);
        const data = await readJsonResponse(response);
        setNvidiaConnection(Boolean(data.configured));
    } catch (_) {
        setNvidiaConnection(false);
    }
}

function setButtonLoading(button, loading, label) {
    if (!button) return;
    button.disabled = loading;
    button.classList.toggle('loading', loading);
    const text = button.querySelector('.btn-text');
    if (text && label) text.textContent = label;
}

async function connectNvidia() {
    const input = $('nvidia-api-key');
    const button = $('nvidia-connect-btn');
    const key = input?.value.trim() || '';
    if (!key) { showToast('Enter your NVIDIA API key first.', 'error'); return; }
    setButtonLoading(button, true, 'Saving securely…');
    try {
        const response = await fetchWithTimeout('/api/nvidia/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: key }),
        }, 20000);
        const data = await readJsonResponse(response);
        if (!response.ok || !data.success) throw new Error(data.error || 'Could not connect NVIDIA.');
        input.value = '';
        setNvidiaConnection(true);
        showToast(data.message || 'NVIDIA AI key saved securely.', 'success');
    } catch (error) {
        showToast(error.message, 'error', 6000);
    } finally {
        setButtonLoading(button, false, 'Connect securely');
    }
}

async function verifyNvidia() {
    const button = $('nvidia-verify-btn');
    button.disabled = true;
    button.textContent = 'Testing…';
    try {
        const response = await fetchWithTimeout('/api/nvidia/verify', { method: 'POST' }, 60000);
        const data = await readJsonResponse(response);
        if (!response.ok || !data.success) throw new Error(data.error || 'NVIDIA key test failed.');
        showToast('NVIDIA key verified successfully.', 'success');
    } catch (error) {
        showToast(error.message, 'error', 7000);
    } finally {
        button.disabled = false;
        button.textContent = 'Test key';
    }
}

async function disconnectNvidia() {
    try {
        const response = await fetchWithTimeout('/api/nvidia/disconnect', { method: 'POST' }, 15000);
        const data = await readJsonResponse(response);
        if (!response.ok || !data.success) throw new Error(data.error || 'Could not disconnect NVIDIA.');
        setNvidiaConnection(false);
        showToast('Saved NVIDIA key removed.', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function transcribeWithNvidia() {
    const filename = $('nvidia-video-select')?.value || '';
    if (!filename) { showToast('Create or select an exported video first.', 'error'); return; }
    const button = $('nvidia-transcribe-btn');
    const status = $('nvidia-transcribe-status');
    button.disabled = true;
    status.hidden = false;
    try {
        const response = await fetchWithTimeout('/api/nvidia/transcribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename, language: $('nvidia-asr-language')?.value || 'en-US' }),
        }, 360000);
        const data = await readJsonResponse(response);
        if (!response.ok || !data.success) throw new Error(data.error || 'Transcription failed.');
        $('nvidia-transcript').value = data.transcript;
        showToast('Transcript generated with NVIDIA Parakeet.', 'success');
    } catch (error) {
        showToast(error.message, 'error', 7000);
    } finally {
        button.disabled = false;
        status.hidden = true;
    }
}

function renderNvidiaMetadata(metadata) {
    state.nvidiaMetadata = metadata;
    $('nvidia-result-title').textContent = metadata.title || '';
    $('nvidia-result-description').textContent = metadata.description || '';
    $('nvidia-result-hook').textContent = metadata.hook || '';
    $('nvidia-result-comment').textContent = metadata.pinned_comment || '';
    const hashtags = $('nvidia-result-hashtags');
    hashtags.innerHTML = '';
    (metadata.hashtags || []).forEach(tag => {
        const span = document.createElement('span');
        span.textContent = tag.startsWith('#') ? tag : `#${tag}`;
        hashtags.appendChild(span);
    });
    $('nvidia-results').hidden = false;
    $('nvidia-results').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function generateNvidiaMetadata() {
    const transcript = $('nvidia-transcript')?.value.trim() || '';
    if (!transcript) { showToast('Generate a transcript or enter the video topic first.', 'error'); return; }
    const button = $('nvidia-generate-btn');
    setButtonLoading(button, true, 'NVIDIA is writing…');
    try {
        const response = await fetchWithTimeout('/api/nvidia/generate-metadata', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                transcript,
                language: $('nvidia-output-language')?.value || 'English',
                tone: $('nvidia-tone')?.value || 'High-energy',
            }),
        }, 180000);
        const data = await readJsonResponse(response);
        if (!response.ok || !data.success) throw new Error(data.error || 'Metadata generation failed.');
        renderNvidiaMetadata(data.metadata);
        showToast('Your Shorts package is ready.', 'success');
    } catch (error) {
        showToast(error.message, 'error', 7000);
    } finally {
        setButtonLoading(button, false, 'Generate with NVIDIA AI');
    }
}

async function copyText(value) {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    showToast('Copied to clipboard.', 'success', 1800);
}

function initNvidiaAssistant() {
    $('nvidia-connect-btn')?.addEventListener('click', connectNvidia);
    $('nvidia-verify-btn')?.addEventListener('click', verifyNvidia);
    $('nvidia-disconnect-btn')?.addEventListener('click', disconnectNvidia);
    $('nvidia-transcribe-btn')?.addEventListener('click', transcribeWithNvidia);
    $('nvidia-generate-btn')?.addEventListener('click', generateNvidiaMetadata);
    $('nvidia-key-toggle')?.addEventListener('click', event => {
        const input = $('nvidia-api-key');
        const show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        event.currentTarget.textContent = show ? 'Hide' : 'Show';
        event.currentTarget.setAttribute('aria-label', show ? 'Hide API key' : 'Show API key');
    });
    document.querySelectorAll('.copy-field-btn').forEach(button => {
        button.addEventListener('click', () => copyText($(button.dataset.copy)?.textContent.trim() || ''));
    });
    $('nvidia-copy-all')?.addEventListener('click', () => {
        const item = state.nvidiaMetadata;
        if (!item) return;
        const tags = (item.hashtags || []).map(tag => tag.startsWith('#') ? tag : `#${tag}`).join(' ');
        copyText(`${item.title}\n\n${item.description}\n\n${tags}\n\nHook: ${item.hook}\n\nPinned comment: ${item.pinned_comment}`);
    });
    loadNvidiaStatus();
    syncNvidiaVideoOptions();
}

// ─────────────────────────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {

    // Add age to state
    state.currentAge   = 'adult';
    state.aiCurrentAge = 'adult';

    // 1. Initialize synchronous UI components immediately so they are clickable
    initTabs();
    initAudioToggle();
    initDropzone();
    initSliders('tts');
    initSliders('ai');
    initMergeForm();
    initClipForm();
    initAIVideoForm();
    initNvidiaAssistant();

    // Video modal
    $('modal-close')?.addEventListener('click', closeVideoModal);
    $('modal-close-btn')?.addEventListener('click', closeVideoModal);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeVideoModal(); });

    // Ratio card visual selection
    document.querySelectorAll('.ratio-card input[type=radio]').forEach(radio => {
        radio.addEventListener('change', () => {
            document.querySelectorAll('.ratio-card').forEach(c => c.classList.remove('selected'));
            radio.closest('.ratio-card').classList.add('selected');
        });
        if (radio.checked) radio.closest('.ratio-card').classList.add('selected');
    });

    // Populate AI language selector from TTS language selector
    const aiLang = $('ai-language');
    if (aiLang && $('tts-language')) {
        aiLang.innerHTML = $('tts-language').innerHTML;
    }

    // 2. Load async data without blocking UI click handlers
    (async () => {
        // Voice metadata and existing exports are independent. Loading both in
        // parallel keeps the library from looking empty on slower voice calls.
        await Promise.all([
            loadVoices().then(() => {
                buildAgeGrid('tts');
                buildAgeGrid('ai');
            }).catch(err => console.error('Error loading voices:', err)),
            loadGallery().catch(err => console.error('Error loading gallery:', err)),
        ]);

        // Voice interactions (TTS Panel)
        $('tts-language')?.addEventListener('change', e => {
            state.currentLang  = e.target.value;
            state.currentStyle = '';
            state.currentAge   = 'adult';
            $('tts-style').value = '';
            updateVoiceDropdown(e.target.value, 'tts');
            buildAgeGrid('tts');
        });

        $('tts-voice')?.addEventListener('change', () => {
            state.currentStyle = '';
            $('tts-style').value = '';
            updateMoodGrid('tts');
        });

        $('preview-voice-btn')?.addEventListener('click', () => previewVoice('tts'));

        // Voice interactions (AI Panel)
        $('ai-language')?.addEventListener('change', e => {
            state.aiCurrentLang  = e.target.value;
            state.aiCurrentStyle = '';
            state.aiCurrentAge   = 'adult';
            $('ai-tts-style').value = '';
            updateVoiceDropdown(e.target.value, 'ai');
            buildAgeGrid('ai');
        });

        $('ai-voice')?.addEventListener('change', () => {
            state.aiCurrentStyle = '';
            $('ai-tts-style').value = '';
            updateMoodGrid('ai');
        });

        $('ai-preview-voice-btn')?.addEventListener('click', () => previewVoice('ai'));

        // Library
        $('refresh-gallery')?.addEventListener('click', loadGallery);
        $('clear-library-btn')?.addEventListener('click', clearLibrary);
        $('library-search')?.addEventListener('input', loadGallery);

        // Auto-refresh library every 30s
        setInterval(loadGallery, 30000);
    })();
});
