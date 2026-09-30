/**
 * Advanced Multilingual Speech Synthesis (TTS) Service for BIS Sahayta
 * Features:
 *  - Automatic Unicode-based script/language detection (HI, TE, UR, BN, TA, KN, ML, MR, GU, EN)
 *  - Browser Voice Loading & Asynchronous Voice Matching Priority
 *  - Speech Markdown & Citation Pre-cleaning (strips *, #, ``, tables, URLs, [1] citations)
 *  - Long Response Chunking (paragraphs, sentences, headings, lists)
 *  - Speech Parameters Tuning (rate, pitch, volume)
 *  - Single Active Playback Queue with Play, Pause, Resume, Stop controls
 */

// Language to Locale priorities (12 Indian languages + English)
const LOCALE_PRIORITIES = {
  hi: ['hi-IN', 'hi'],
  te: ['te-IN', 'te'],
  ur: ['ur-IN', 'ur-PK', 'ur'],
  bn: ['bn-IN', 'bn-BD', 'bn'],
  ta: ['ta-IN', 'ta-LK', 'ta'],
  kn: ['kn-IN', 'kn'],
  ml: ['ml-IN', 'ml'],
  mr: ['mr-IN', 'mr', 'hi-IN'],
  gu: ['gu-IN', 'gu'],
  or: ['or-IN', 'or'],
  pa: ['pa-IN', 'pa-PK', 'pa'],
  as: ['as-IN', 'as', 'bn-IN'],
  en: ['en-IN', 'en-US', 'en-GB', 'en'],
};

// Rate tuning per language
const RATE_SETTINGS = {
  hi: 0.95,
  te: 0.92,
  ur: 0.92,
  bn: 0.92,
  ta: 0.92,
  kn: 0.92,
  ml: 0.92,
  mr: 0.92,
  gu: 0.92,
  or: 0.92,
  pa: 0.92,
  as: 0.92,
  en: 0.98,
};

/**
 * 1. Language Detection via Script Unicode Ranges (12 Indian Languages)
 */
export function detectLanguage(text) {
  if (!text || typeof text !== 'string') return 'en';

  let hiCount = 0;
  let teCount = 0;
  let urCount = 0;
  let bnCount = 0;
  let taCount = 0;
  let knCount = 0;
  let mlCount = 0;
  let guCount = 0;
  let orCount = 0;
  let paCount = 0;

  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    // Devanagari (Hindi / Marathi) - 0x0900 to 0x097F
    if (code >= 0x0900 && code <= 0x097f) hiCount++;
    // Gurmukhi / Punjabi - 0x0A00 to 0x0A7F
    else if (code >= 0x0a00 && code <= 0x0a7f) paCount++;
    // Gujarati - 0x0A80 to 0x0AFF
    else if (code >= 0x0a80 && code <= 0x0aff) guCount++;
    // Bengali / Assamese - 0x0980 to 0x09FF
    else if (code >= 0x0980 && code <= 0x09ff) bnCount++;
    // Odia - 0x0B00 to 0x0B7F
    else if (code >= 0x0b00 && code <= 0x0b7f) orCount++;
    // Tamil - 0x0B80 to 0x0BFF
    else if (code >= 0x0b80 && code <= 0x0bff) taCount++;
    // Telugu - 0x0C00 to 0x0C7F
    else if (code >= 0x0c00 && code <= 0x0c7f) teCount++;
    // Kannada - 0x0C80 to 0x0CFF
    else if (code >= 0x0c80 && code <= 0x0cff) knCount++;
    // Malayalam - 0x0D00 to 0x0D7F
    else if (code >= 0x0d00 && code <= 0x0d7f) mlCount++;
    // Arabic/Urdu - 0x0600 to 0x06FF
    else if (code >= 0x0600 && code <= 0x06ff) urCount++;
  }

  const counts = [
    { lang: 'hi', count: hiCount },
    { lang: 'te', count: teCount },
    { lang: 'ur', count: urCount },
    { lang: 'bn', count: bnCount },
    { lang: 'ta', count: taCount },
    { lang: 'kn', count: knCount },
    { lang: 'ml', count: mlCount },
    { lang: 'gu', count: guCount },
    { lang: 'or', count: orCount },
    { lang: 'pa', count: paCount },
  ];

  counts.sort((a, b) => b.count - a.count);
  if (counts[0].count > 5) {
    return counts[0].lang;
  }
  return 'en';
}

/**
 * 2. Markdown & Citation Text Sanitizer for Natural Recitation
 */
export function cleanTextForSpeech(text) {
  if (!text) return '';

  return (
    text
      // Remove fenced code blocks completely from speech
      .replace(/```[\s\S]*?```/g, ' Code snippet omitted. ')
      // Remove raw inline code
      .replace(/`([^`]+)`/g, '$1')
      // Remove URLs
      .replace(/https?:\/\/\S+/g, '')
      // Remove inline citations like [1], [2], [1, 2]
      .replace(/\[\d+(?:\s*,\s*\d+)*\]/g, '')
      // Convert Markdown headers to clean titles
      .replace(/^#{1,6}\s+(.+)$/gm, '$1.')
      // Convert list markers
      .replace(/^[\s-*+.]+(\d+\.)?\s+/gm, '')
      // Remove Markdown bold/italic syntax
      .replace(/(\*\*|__|\*|_)(.*?)\1/g, '$2')
      // Clean table lines (pipes to spaces)
      .replace(/\|/g, ' ')
      .replace(/[-:]{3,}/g, '')
      // Clean double spaces & carriage returns
      .replace(/\r\n|\r/g, '\n')
      .replace(/\n{2,}/g, '. ')
      .replace(/\s+/g, ' ')
      .trim()
  );
}

/**
 * 3. Text Chunking into Natural Paragraph/Sentence Boundaries
 */
export function chunkTextForSpeech(text, maxLength = 200) {
  const cleaned = cleanTextForSpeech(text);
  if (!cleaned) return [];

  // Split by sentence terminators (. ! ? \n)
  const rawSentences = cleaned.split(/(?<=[.!?\n])\s+/);
  const chunks = [];
  let currentChunk = '';

  for (const s of rawSentences) {
    const trimmed = s.trim();
    if (!trimmed) continue;

    if ((currentChunk + ' ' + trimmed).length <= maxLength) {
      currentChunk = currentChunk ? currentChunk + ' ' + trimmed : trimmed;
    } else {
      if (currentChunk) chunks.push(currentChunk);
      if (trimmed.length > maxLength) {
        // Sub-chunk long sentence by commas/clauses
        const clauses = trimmed.split(/(?<=[,;])\s+/);
        let clauseChunk = '';
        for (const c of clauses) {
          if ((clauseChunk + ' ' + c).length <= maxLength) {
            clauseChunk = clauseChunk ? clauseChunk + ' ' + c : c;
          } else {
            if (clauseChunk) chunks.push(clauseChunk);
            clauseChunk = c;
          }
        }
        if (clauseChunk) currentChunk = clauseChunk;
        else currentChunk = '';
      } else {
        currentChunk = trimmed;
      }
    }
  }

  if (currentChunk) chunks.push(currentChunk);
  return chunks;
}

/**
 * 4. Frontend TTS Service Class
 */
class TTSService {
  constructor() {
    this.voices = [];
    this.currentUtterance = null;
    this.queue = [];
    this.speakingState = 'idle'; // idle | loading | speaking | paused | error
    this.onStateChange = null;
    this.activeMessageId = null;

    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      this.loadVoices();
      window.speechSynthesis.onvoiceschanged = () => this.loadVoices();
    }
  }

  loadVoices() {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    this.voices = window.speechSynthesis.getVoices() || [];
  }

  getAvailableVoices() {
    if (!this.voices.length && typeof window !== 'undefined' && 'speechSynthesis' in window) {
      this.loadVoices();
    }
    return this.voices;
  }

  selectVoice(langKey) {
    const voices = this.getAvailableVoices();
    if (!voices.length) return null;

    const targetLocales = LOCALE_PRIORITIES[langKey] || LOCALE_PRIORITIES.en;

    // 1. Match exact locale in priority order (e.g., hi-IN)
    for (const locale of targetLocales) {
      const match = voices.find(v => v.lang && v.lang.toLowerCase() === locale.toLowerCase());
      if (match) return match;
    }

    // 2. Match language prefix (e.g. 'hi')
    for (const locale of targetLocales) {
      const prefix = locale.split('-')[0].toLowerCase();
      const match = voices.find(v => v.lang && v.lang.toLowerCase().startsWith(prefix));
      if (match) return match;
    }

    // 3. Indian English or Regional voice fallback
    const indianFallback = voices.find(v => v.lang && v.lang.toLowerCase().includes('in'));
    if (indianFallback) return indianFallback;

    // 4. Default voice
    return voices.find(v => v.default) || voices[0] || null;
  }

  setState(state) {
    this.speakingState = state;
    if (typeof this.onStateChange === 'function') {
      this.onStateChange(state);
    }
  }

  speak(rawText, messageId = null, onEndCallback = null) {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;

    this.stop(); // Stop any existing playback

    const langKey = detectLanguage(rawText);
    const chunks = chunkTextForSpeech(rawText);
    if (!chunks.length) return;

    this.activeMessageId = messageId;
    this.queue = [...chunks];
    this.setState('speaking');

    const voice = this.selectVoice(langKey);
    const rate = RATE_SETTINGS[langKey] || 0.95;

    const speakNextChunk = () => {
      if (this.queue.length === 0) {
        this.setState('idle');
        this.activeMessageId = null;
        if (typeof onEndCallback === 'function') onEndCallback();
        return;
      }

      const chunk = this.queue.shift();
      const utter = new SpeechSynthesisUtterance(chunk);
      if (voice) utter.voice = voice;
      utter.lang = voice?.lang || (LOCALE_PRIORITIES[langKey] ? LOCALE_PRIORITIES[langKey][0] : 'en-IN');
      utter.rate = rate;
      utter.pitch = 1.0;
      utter.volume = 1.0;

      utter.onend = () => {
        if (this.speakingState === 'speaking') {
          speakNextChunk();
        }
      };

      utter.onerror = (e) => {
        console.warn('TTS utterance error:', e);
        if (this.queue.length > 0 && this.speakingState === 'speaking') {
          speakNextChunk();
        } else {
          this.setState('error');
          this.activeMessageId = null;
        }
      };

      this.currentUtterance = utter;
      window.speechSynthesis.speak(utter);
    };

    speakNextChunk();
  }

  pause() {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window && this.speakingState === 'speaking') {
      window.speechSynthesis.pause();
      this.setState('paused');
    }
  }

  resume() {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window && this.speakingState === 'paused') {
      window.speechSynthesis.resume();
      this.setState('speaking');
    }
  }

  stop() {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      this.queue = [];
      this.currentUtterance = null;
      this.activeMessageId = null;
      this.setState('idle');
    }
  }

  isSpeaking(messageId = null) {
    if (messageId !== null) {
      return (this.speakingState === 'speaking' || this.speakingState === 'paused') && this.activeMessageId === messageId;
    }
    return this.speakingState === 'speaking' || this.speakingState === 'paused';
  }
}

export const ttsService = new TTSService();
