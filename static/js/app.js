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
};

// ─────────────────────────────────────────────────────────────────
// UTILITIES
// ─────────────────────────────────────────────────────────────────
function $(id)   { return document.getElementById(id); }
function $q(sel) { return document.querySelector(sel); }

function showToast(msg, type = 'success', duration = 3500) {
    const t = $('toast');
    t.textContent = msg;
    t.className = `toast ${type} show`;
    setTimeout(() => t.classList.remove('show'), duration);
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
        const res  = await fetch('/api/outputs');
        const data = await res.json();

        const filtered = searchVal
            ? data.filter(f => f.filename.toLowerCase().includes(searchVal))
            : data;

        if (!filtered.length) {
            container.innerHTML = `
                <div class="empty-library">
                    <div class="library-empty-art">${searchVal ? '🔍' : '🎞️'}</div>
                    <span>${searchVal ? 'No files match your search.' : 'No files exported yet.<br>Run a merge or clip operation to begin.'}</span>
                </div>`;
            animateCount($('stat-files'), 0);
            return;
        }

        state.statsFiles = data.length;
        animateCount($('stat-files'), data.length);

        container.innerHTML = filtered.map(file => {
            const isClip  = file.filename.includes('clip_');
            const icon    = isClip ? '✂️' : '🎬';
            return `
            <div class="video-card" data-fn="${file.filename}">
                <div class="video-card-info">
                    <span class="video-card-title">${icon} ${file.filename}</span>
                    <span class="video-card-meta">${file.duration} &nbsp;|&nbsp; ${file.size}</span>
                </div>
                <div class="video-card-actions">
                    <button class="action-btn play-action" data-fn="${file.filename}">▶ Play</button>
                    <button class="action-btn download-action" data-fn="${file.filename}">↓ Save</button>
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
    const confirmed = confirm('🗑️ Delete ALL exported files from disk?\n\nThis cannot be undone.');
    if (!confirmed) return;

    const btn = $('clear-library-btn');
    btn.textContent = '⏳ Clearing…';
    btn.disabled = true;

    try {
        const res  = await fetch('/api/clear-library', { method: 'POST' });
        const data = await res.json();
        showToast(`✅ Cleared ${data.deleted} file${data.deleted !== 1 ? 's' : ''} from library`, 'success');
        animateCount($('stat-files'), 0);
        await loadGallery();
    } catch (e) {
        showToast('❌ Failed to clear library', 'error');
    } finally {
        btn.textContent = '🗑 Clear All';
        btn.disabled = false;
    }
}

// ─────────────────────────────────────────────────────────────────
// VIDEO MODAL
// ─────────────────────────────────────────────────────────────────
function openVideoModal(filename) {
    $('modal-title').textContent = `▶ ${filename}`;
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
        const res  = await fetch('/api/voices');
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

        const res = await fetch('/api/preview-voice', { method: 'POST', body: fd });
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
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            $(btn.dataset.tab)?.classList.add('active');
        });
    });
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
    if (!fill) return null;

    let idx = 0;
    let cur = 0;

    const iv = setInterval(() => {
        if (idx >= steps.length) { clearInterval(iv); onDone?.(); return; }
        const { pct: target, label, dur } = steps[idx];
        step.textContent = label;

        const speed = (target - cur) / (dur / 120);
        const inner = setInterval(() => {
            cur = Math.min(cur + speed, target);
            fill.style.width = `${cur}%`;
            pct.textContent  = `${Math.round(cur)}%`;
            if (cur >= target) { clearInterval(inner); idx++; }
        }, 120);
    }, 0);

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
        startProgress('merge-fill', 'merge-pct', 'merge-step', steps);

        try {
            const res  = await fetch('/api/merge', { method: 'POST', body: fd });
            const data = await res.json();

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
            showToast('❌ Network error — check server', 'error');
        } finally {
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

    form.addEventListener('submit', async e => {
        e.preventDefault();
        const url = $('url')?.value.trim();
        if (!url || !url.includes('youtube')) {
            showToast('⚠️ Please enter a valid YouTube URL', 'error'); return;
        }

        const btn = $('clip-submit-btn');
        btn.disabled = true; btn.classList.add('loading');
        showProgress('clip-progress');

        const steps = [
            { pct: 20, label: '⬇️ Downloading video…',        dur: 3000 },
            { pct: 50, label: '✂️ Slicing into clips…',         dur: 2500 },
            { pct: 75, label: '🎨 Applying safety filters…',   dur: 2000 },
            { pct: 90, label: '💾 Saving clips to library…',   dur: 1200 },
            { pct: 99, label: '📦 Cleaning up temp files…',    dur: 600  },
        ];
        startProgress('clip-fill', 'clip-pct', 'clip-step', steps);

        try {
            const fd  = new FormData(form);
            const res = await fetch('/api/clip', { method: 'POST', body: fd });
            const data = await res.json();

            $('clip-fill').style.width = '100%';
            $('clip-pct').textContent  = '100%';
            $('clip-step').textContent = '✅ Done!';

            if (data.success) {
                showToast(`✅ ${data.message}`, 'success', 5000);
                state.statsClips += data.filenames?.length || 0;
                animateCount($('stat-clips'), state.statsClips);
                await loadGallery();
            } else {
                showToast(`❌ ${data.error}`, 'error', 7000);
            }
        } catch (err) {
            showToast('❌ Network error — check server logs', 'error');
        } finally {
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
        startProgress('ai-fill', 'ai-pct', 'ai-step', steps);

        try {
            const res = await fetch('/api/generate-video', { method: 'POST', body: fd });
            const data = await res.json();

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
            showToast('❌ Network error — check server logs', 'error');
        } finally {
            btn.disabled = false;
            btn.classList.remove('loading');
            setTimeout(() => hideProgress('ai-progress'), 2000);
        }
    });
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
        try {
            await loadVoices();
            buildAgeGrid('tts');
            buildAgeGrid('ai');
        } catch (err) {
            console.error("Error loading voices:", err);
        }

        try {
            await loadGallery();
        } catch (err) {
            console.error("Error loading gallery:", err);
        }

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
