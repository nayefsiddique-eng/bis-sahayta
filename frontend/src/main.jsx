import React, { useEffect, useRef, useState, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Search, Plus, Sun, Moon, Settings, History, Compass, Paperclip, Mic, MicOff,
  Send, Menu, X, ChevronRight, ArrowLeft, Bookmark, MessageSquare, Trash2,
  CheckCircle2, Volume2, VolumeX, Copy, FileText, AlertCircle, Loader2, Camera
} from 'lucide-react';
import './styles.css';
import bisLogo from "./assets/bis.png";

const API_KEY = import.meta.env.VITE_API_KEY || 'demo-key-123';

const prompts = [
  'Understand a Standard',
  'BIS Certification Scheme',
  'Find Requirements',
  'Check Documents',
  'Testing & Lab Compliance'
];

// ─────────────────────────────────────────────────────────────────────────────
// API helpers
// ─────────────────────────────────────────────────────────────────────────────

async function apiFetch(url, options = {}) {
  const isFormData = options.body instanceof FormData;
  const headers = {
    'X-API-Key': API_KEY,
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers || {}),
  };
  const response = await fetch(url, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorMsg = typeof data?.detail === 'string'
      ? data.detail
      : data?.detail?.message || data?.message || `Request failed (${response.status})`;
    const err = new Error(errorMsg);
    err.status = response.status;
    err.retryAfter = Number(response.headers.get('Retry-After')) ||
      (data?.detail && (data.detail.retry_after_seconds || data.detail.retry_after)) || null;
    throw err;
  }
  return data;
}

// ─────────────────────────────────────────────────────────────────────────────
// Markdown renderer (safe, no external dep)
// ─────────────────────────────────────────────────────────────────────────────

function renderMarkdown(text) {
  if (!text) return '';
  // Escape HTML first to prevent XSS
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  const lines = escaped.split('\n');
  const output = [];
  let inCode = false;
  let codeLines = [];
  let codeLang = '';
  let inList = false;
  let listItems = [];
  let listType = null;

  const flushList = () => {
    if (!inList) return;
    const tag = listType === 'ol' ? 'ol' : 'ul';
    output.push(`<${tag}>${listItems.join('')}</${tag}>`);
    listItems = [];
    inList = false;
    listType = null;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Fenced code blocks
    if (line.startsWith('```')) {
      if (!inCode) {
        flushList();
        inCode = true;
        codeLang = line.slice(3).trim();
        codeLines = [];
        continue;
      } else {
        inCode = false;
        const code = codeLines.join('\n');
        output.push(`<pre><code class="lang-${codeLang}">${code}</code></pre>`);
        codeLines = [];
        continue;
      }
    }
    if (inCode) {
      codeLines.push(line);
      continue;
    }

    // Headings
    const h3 = line.match(/^### (.+)/);
    const h2 = line.match(/^## (.+)/);
    const h1 = line.match(/^# (.+)/);
    if (h3) { flushList(); output.push(`<h3>${inlineFormat(h3[1])}</h3>`); continue; }
    if (h2) { flushList(); output.push(`<h3>${inlineFormat(h2[1])}</h3>`); continue; }  // intentionally h3 for cleaner look
    if (h1) { flushList(); output.push(`<h3>${inlineFormat(h1[1])}</h3>`); continue; }

    // Ordered list
    const olMatch = line.match(/^(\d+)\. (.+)/);
    if (olMatch) {
      if (!inList || listType !== 'ol') { flushList(); inList = true; listType = 'ol'; }
      listItems.push(`<li>${inlineFormat(olMatch[2])}</li>`);
      continue;
    }

    // Unordered list
    const ulMatch = line.match(/^[-*+] (.+)/);
    if (ulMatch) {
      if (!inList || listType !== 'ul') { flushList(); inList = true; listType = 'ul'; }
      listItems.push(`<li>${inlineFormat(ulMatch[1])}</li>`);
      continue;
    }

    // Empty line
    if (line.trim() === '') {
      flushList();
      output.push('<br>');
      continue;
    }

    // Horizontal rule
    if (/^---+$/.test(line.trim())) {
      flushList();
      output.push('<hr>');
      continue;
    }

    // Normal paragraph line
    flushList();
    output.push(`<p>${inlineFormat(line)}</p>`);
  }

  flushList();
  if (inCode && codeLines.length) {
    output.push(`<pre><code>${codeLines.join('\n')}</code></pre>`);
  }

  // Clean up consecutive <br> elements
  return output.join('').replace(/(<br>){3,}/g, '<br><br>');
}

function inlineFormat(text) {
  return text
    // Bold+italic
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/_(.+?)_/g, '<em>$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Inline citations like [1], [2]
    .replace(/\[(\d+)\]/g, '<cite>[$1]</cite>');
}

function MarkdownContent({ text }) {
  const html = renderMarkdown(text || '');
  return (
    <div
      className="message-text markdown"
      // Safe: we escape HTML before processing markdown
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// App root
// ─────────────────────────────────────────────────────────────────────────────

function App() {
  const [page, setPage] = useState('home');
  const [dark, setDark] = useState(localStorage.getItem('bis-theme') === 'dark');
  const [mobile, setMobile] = useState(false);
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [mode, setMode] = useState('Simple');
  const [appSettings, setAppSettings] = useState({ large: false, citations: true });
  const [isLoading, setIsLoading] = useState(false);

  // Pending attachment state (shared across chat pages)
  const [pendingFile, setPendingFile] = useState(null); // { file, document_id, name, status }

  // Model selector state
  const [selectedModel, setSelectedModel] = useState(
    () => localStorage.getItem('bis-model') || 'auto'
  );
  const [availableModels, setAvailableModels] = useState([]);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('bis-theme', dark ? 'dark' : 'light');
  }, [dark]);

  // Fetch available models on mount (for selector UI)
  useEffect(() => {
    apiFetch('/api/models')
      .then(data => setAvailableModels(data.models || []))
      .catch(() => {}); // silently ignore — selector degrades gracefully
  }, []);

  // Persist model selection
  useEffect(() => {
    localStorage.setItem('bis-model', selectedModel);
  }, [selectedModel]);

  const fetchSessions = useCallback(async () => {
    try {
      const data = await apiFetch('/api/sessions');
      setSessions(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  }, []);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  const loadSession = useCallback(async (sid) => {
    try {
      const msgs = await apiFetch(`/api/sessions/${sid}/messages`);
      setActiveSessionId(sid);
      setMessages(
        msgs.map(m => ({
          role: m.role,
          text: m.content,
          sources: m.metadata?.sources || [],
          relevance:
            typeof m.metadata?.relevance === 'number'
              ? m.metadata.relevance
              : m.metadata?.confidence,
        }))
      );
      setPage('chat');
    } catch (err) {
      console.error('Failed to load session messages:', err);
      alert('Failed to load session. Please try again.');
    }
  }, []);

  const deleteSession = useCallback(async (sid) => {
    try {
      await apiFetch(`/api/sessions/${sid}`, { method: 'DELETE' });
      if (activeSessionId === sid) newChat();
      fetchSessions();
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  }, [activeSessionId, fetchSessions]);

  const send = useCallback(async (text = query, attachmentDocId = null) => {
    text = typeof text === 'string' ? text.trim() : '';
    if (!text || isLoading) return;

    const docId = attachmentDocId || (pendingFile?.document_id) || null;

    setMessages(m => [
      ...m,
      { role: 'user', text, attachmentName: pendingFile?.name || null },
      { role: 'assistant', text: '', loading: true }
    ]);

    setQuery('');
    setPage('chat');
    setIsLoading(true);
    if (docId) setPendingFile(null); // clear attachment after send

    try {
      const styleMap = { Simple: 'simple', Short: 'short', Technical: 'technical' };
      const bodyPayload = {
        query: text,
        session_id: activeSessionId || undefined,
        document_id: docId || undefined,
        lang: 'en',
        use_rag: true,
        n_results: 5,
        style: styleMap[mode] || 'simple',
        model: selectedModel || 'auto',
      };

      const data = await apiFetch('/api/chat', {
        method: 'POST',
        body: JSON.stringify(bodyPayload),
      });

      if (data.session_id) {
        setActiveSessionId(data.session_id);
        fetchSessions();
      }

      setMessages(m => m.map((msg, i) =>
        i === m.length - 1
          ? {
              role: 'assistant',
              text: data.answer || data.reply || 'No answer was returned by the BIS backend.',
              sources: data.sources || [],
              relevance: typeof data.relevance === 'number' ? data.relevance : data.confidence,
              intent: data.intent,
              responseLang: data.response_lang || 'en',
              modelUsed: data.model_used || null,
              fallbackUsed: data.fallback_used || false,
              fallbackReason: data.fallback_reason || null,
            }
          : msg
      ));
    } catch (error) {
      const friendlyMsg = error.status === 429
        ? `The AI service is rate limited. Please wait ${error.retryAfter || 30} seconds and press Retry.`
        : error.status === 404
        ? 'Session not found. Starting a new conversation.'
        : error.status >= 500
        ? 'The server encountered an error. Please try again shortly.'
        : error.status === 401
        ? 'Authentication error. Please refresh the page.'
        : `Unable to complete request: ${error.message}`;

      setMessages(m => m.map((msg, i) =>
        i === m.length - 1
          ? { role: 'assistant', text: friendlyMsg, error: true, retryAfter: error.retryAfter }
          : msg
      ));
    } finally {
      setIsLoading(false);
    }
  }, [query, isLoading, pendingFile, activeSessionId, mode, fetchSessions, selectedModel]);

  const newChat = useCallback(() => {
    setMessages([]);
    setActiveSessionId(null);
    setPage('home');
    setQuery('');
    setPendingFile(null);
  }, []);

  const nav = useCallback((p) => {
    setPage(p);
    setMobile(false);
  }, []);

  const retry = useCallback(() => {
    const lastUser = [...messages].reverse().find(m => m.role === 'user');
    if (lastUser) send(lastUser.text);
  }, [messages, send]);

  return (
    <div className={appSettings.large ? 'app large-text' : 'app'}>
      <header className="topbar">
        <button className="icon-btn mobile-only" onClick={() => setMobile(!mobile)}>
          {mobile ? <X /> : <Menu />}
        </button>

        <button className="brand" onClick={() => nav('home')}>
          <img src={bisLogo} alt="BIS" className="bis-logo" />
          <div>
            <b>BIS Sahayta</b>
            <span>AI assistant for BIS information</span>
          </div>
        </button>

        <div className="top-actions">
          <button className="icon-btn" onClick={() => setDark(!dark)} title="Toggle theme">
            {dark ? <Sun /> : <Moon />}
          </button>
          <button className="new-btn" onClick={newChat}>
            <Plus size={18} />
            New Chat
          </button>
        </div>
      </header>

      <div className="layout">
        <aside className={'sidebar ' + (mobile ? 'open' : '')}>
          <button className="new-chat" onClick={newChat}>
            <Plus />
            New Chat
          </button>

          <nav>
            <Nav
              active={page === 'home' || page === 'chat'}
              icon={<MessageSquare />}
              label="Ask Sahayta"
              onClick={() => nav(messages.length ? 'chat' : 'home')}
            />
            <Nav
              active={page === 'guide'}
              icon={<Compass />}
              label="Guide Me"
              onClick={() => nav('guide')}
            />
            <Nav
              active={page === 'history'}
              icon={<History />}
              label="History"
              onClick={() => nav('history')}
            />
          </nav>

          <div className="side-label">RECENT</div>

          {sessions.slice(0, 8).map(c => (
            <button
              className={'chat-link ' + (activeSessionId === c.id ? 'active' : '')}
              key={c.id}
              onClick={() => loadSession(c.id)}
            >
              <MessageSquare size={16} />
              <span>{(c.preview || 'Chat session').slice(0, 40)}</span>
            </button>
          ))}

          <div className="sidebar-bottom">
            <button className="side-link" onClick={() => nav('settings')}>
              <Settings />
              Settings
            </button>
          </div>
        </aside>

        {mobile && <div className="backdrop" onClick={() => setMobile(false)} />}

        <main className="main">
          {page === 'home' && (
            <Home
              query={query}
              setQuery={setQuery}
              send={send}
              nav={nav}
              pendingFile={pendingFile}
              setPendingFile={setPendingFile}
              isLoading={isLoading}
            />
          )}

          {page === 'chat' && (
            <Chat
              messages={messages}
              query={query}
              setQuery={setQuery}
              send={send}
              mode={mode}
              setMode={setMode}
              retry={retry}
              pendingFile={pendingFile}
              setPendingFile={setPendingFile}
              isLoading={isLoading}
              selectedModel={selectedModel}
              setSelectedModel={setSelectedModel}
              availableModels={availableModels}
            />
          )}

          {page === 'guide' && (
            <Guide
              onContinue={(report) => {
                newChat();
                send(report.chatContext);
              }}
            />
          )}

          {page === 'history' && (
            <HistoryPage
              sessions={sessions}
              loadSession={loadSession}
              deleteSession={deleteSession}
            />
          )}

          {page === 'settings' && (
            <SettingsPage
              dark={dark}
              setDark={setDark}
              settings={appSettings}
              setSettings={setAppSettings}
            />
          )}
        </main>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Nav item
// ─────────────────────────────────────────────────────────────────────────────

function Nav({ active, icon, label, onClick }) {
  return (
    <button className={'nav-item ' + (active ? 'active' : '')} onClick={onClick}>
      {icon}
      <span>{label}</span>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Voice (STT using Web Speech API)
// ─────────────────────────────────────────────────────────────────────────────

function VoiceButton({ onTranscript, disabled }) {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState(null);
  const recognitionRef = useRef(null);

  const isSupported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);

  const startListening = useCallback(() => {
    if (!isSupported) {
      setError('Voice input is not supported in this browser. Please use Chrome or Edge.');
      return;
    }
    if (listening) return;

    setError(null);
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-IN'; // Indian English

    recognition.onstart = () => setListening(true);

    recognition.onresult = (e) => {
      const transcript = Array.from(e.results)
        .map(r => r[0].transcript)
        .join(' ')
        .trim();
      if (transcript) {
        onTranscript(transcript);
      } else {
        setError('No speech detected. Please try again.');
      }
    };

    recognition.onerror = (e) => {
      setListening(false);
      if (e.error === 'not-allowed' || e.error === 'permission-denied') {
        setError('Microphone access denied. Please allow microphone access in your browser settings.');
      } else if (e.error === 'no-speech') {
        setError('No speech detected. Please speak clearly and try again.');
      } else if (e.error === 'network') {
        setError('Network error during voice recognition. Please check your connection.');
      } else {
        setError(`Voice input error: ${e.error}`);
      }
    };

    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch (err) {
      setListening(false);
      setError('Failed to start voice input. Please try again.');
    }
  }, [isSupported, listening, onTranscript]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    setListening(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    };
  }, []);

  return (
    <div className="voice-container">
      <button
        className={`mini voice-btn ${listening ? 'recording' : ''}`}
        onClick={listening ? stopListening : startListening}
        disabled={disabled || !isSupported}
        title={
          !isSupported
            ? 'Voice input not supported in this browser'
            : listening
            ? 'Click to stop recording'
            : 'Click to start voice input'
        }
      >
        {listening ? <MicOff size={17} /> : <Mic size={17} />}
        {listening ? 'Stop' : 'Voice'}
      </button>
      {error && (
        <div className="voice-error">
          <AlertCircle size={12} />
          {error}
          <button className="voice-error-close" onClick={() => setError(null)}>×</button>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// File Attachment
// ─────────────────────────────────────────────────────────────────────────────

const ALLOWED_TYPES = [
  'application/pdf',
  'image/jpeg',
  'image/png',
  'image/tiff',
  'image/webp',
];
const MAX_SIZE_MB = 20;

function AttachButton({ pendingFile, setPendingFile, disabled }) {
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const handleFileSelect = useCallback(async (file) => {
    if (!file) return;
    setError(null);

    // Client-side validation
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError(`Unsupported file type. Allowed: PDF, JPEG, PNG, TIFF, WebP`);
      return;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`File too large. Maximum size is ${MAX_SIZE_MB} MB.`);
      return;
    }
    if (file.size === 0) {
      setError('File is empty. Please select a valid file.');
      return;
    }

    setUploading(true);
    setPendingFile({ file, name: file.name, status: 'uploading', document_id: null });

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('lang', 'eng');

      const data = await apiFetch('/api/documents/upload', {
        method: 'POST',
        body: formData,
      });

      setPendingFile({
        file,
        name: file.name,
        status: 'ready',
        document_id: data.document_id,
        preview: data.extracted_text_preview || '',
      });
    } catch (err) {
      setPendingFile(null);
      if (err.status === 413) {
        setError('File too large for the server. Please use a smaller file.');
      } else if (err.status === 415) {
        setError('Unsupported file type. Please use PDF or an image.');
      } else {
        setError(`Upload failed: ${err.message}`);
      }
    } finally {
      setUploading(false);
    }
  }, [setPendingFile]);

  const handleInputChange = (e) => {
    const file = e.target.files?.[0];
    if (file) handleFileSelect(file);
    // Reset input so same file can be re-selected
    e.target.value = '';
  };

  const removeFile = useCallback(() => {
    setPendingFile(null);
    setError(null);
  }, [setPendingFile]);

  return (
    <div className="attach-container">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png,.tiff,.webp"
        style={{ display: 'none' }}
        onChange={handleInputChange}
      />

      {pendingFile ? (
        <div className="file-pill">
          {pendingFile.status === 'uploading' ? (
            <Loader2 size={13} className="spin" />
          ) : (
            <FileText size={13} />
          )}
          <span className="file-pill-name">{pendingFile.name}</span>
          {pendingFile.status === 'uploading' && <span className="file-pill-status">Uploading…</span>}
          {pendingFile.status === 'ready' && <CheckCircle2 size={11} color="#16a34a" />}
          <button className="file-pill-remove" onClick={removeFile} title="Remove file">×</button>
        </div>
      ) : (
        <button
          className="mini"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || uploading}
          title="Attach a PDF or image document"
        >
          {uploading ? <Loader2 size={17} className="spin" /> : <Paperclip size={17} />}
          Attach
        </button>
      )}

      {error && (
        <div className="attach-error">
          <AlertCircle size={12} />
          {error}
          <button className="voice-error-close" onClick={() => setError(null)}>×</button>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Live Camera Capture Modal & OCR
// ─────────────────────────────────────────────────────────────────────────────

function CameraButton({ setPendingFile, disabled }) {
  const [active, setActive] = useState(false);
  const [stream, setStream] = useState(null);
  const [capturedBlob, setCapturedBlob] = useState(null);
  const [capturedPreview, setCapturedPreview] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  const startCamera = async () => {
    setError(null);
    setCapturedBlob(null);
    setCapturedPreview(null);
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError('Camera access is not supported in this browser.');
      return;
    }
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
      });
      setStream(mediaStream);
      setActive(true);
    } catch (err) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setError('Camera permission denied. Please allow camera access in browser settings.');
      } else {
        setError(`Camera error: ${err.message || err.name}`);
      }
    }
  };

  useEffect(() => {
    if (active && stream && videoRef.current) {
      videoRef.current.srcObject = stream;
      videoRef.current.play().catch(console.error);
    }
  }, [active, stream]);

  const stopCamera = useCallback(() => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
    setActive(false);
  }, [stream]);

  const captureFrame = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      if (!blob) return;
      setCapturedBlob(blob);
      setCapturedPreview(canvas.toDataURL('image/jpeg'));
    }, 'image/jpeg', 0.9);
  };

  const confirmUpload = async () => {
    if (!capturedBlob) return;
    setProcessing(true);
    setError(null);
    try {
      const file = new File([capturedBlob], `camera-scan-${Date.now()}.jpg`, { type: 'image/jpeg' });
      setPendingFile({ file, name: file.name, status: 'uploading', document_id: null });

      const formData = new FormData();
      formData.append('file', file);
      formData.append('lang', 'eng');

      const data = await apiFetch('/api/documents/upload', {
        method: 'POST',
        body: formData,
      });

      setPendingFile({
        file,
        name: file.name,
        status: 'ready',
        document_id: data.document_id,
        preview: data.extracted_text_preview || '',
      });

      stopCamera();
    } catch (err) {
      setError(`OCR failed: ${err.message}`);
      setPendingFile(null);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="camera-container">
      <button
        className="mini camera-btn"
        onClick={startCamera}
        disabled={disabled}
        title="Capture document with live camera"
      >
        <Camera size={17} />
        Scan
      </button>

      {error && !active && (
        <div className="attach-error">
          <AlertCircle size={12} />
          {error}
          <button className="voice-error-close" onClick={() => setError(null)}>×</button>
        </div>
      )}

      {active && (
        <div className="camera-modal-backdrop">
          <div className="camera-modal">
            <div className="camera-modal-header">
              <h3>Camera Document Scan</h3>
              <button className="file-pill-remove" onClick={stopCamera}>×</button>
            </div>

            {error && <div className="attach-error"><AlertCircle size={12} />{error}</div>}

            <div className="camera-viewport">
              {!capturedPreview ? (
                <video ref={videoRef} playsInline autoPlay muted />
              ) : (
                <img src={capturedPreview} alt="Captured Document" />
              )}
              <canvas ref={canvasRef} style={{ display: 'none' }} />
            </div>

            <div className="camera-modal-actions">
              {!capturedPreview ? (
                <button className="mini" onClick={captureFrame}>
                  <Camera size={15} /> Capture Photo
                </button>
              ) : (
                <>
                  <button className="mini" onClick={() => setCapturedPreview(null)} disabled={processing}>
                    Retake
                  </button>
                  <button className="mini send" onClick={confirmUpload} disabled={processing}>
                    {processing ? <Loader2 size={15} className="spin" /> : <CheckCircle2 size={15} />}
                    {processing ? 'Processing OCR…' : 'Process OCR & Attach'}
                  </button>
                </>
              )}
              <button className="mini" onClick={stopCamera} disabled={processing}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Composer
// ─────────────────────────────────────────────────────────────────────────────

function Composer({ query, setQuery, send, pendingFile, setPendingFile, isLoading }) {
  const textareaRef = useRef(null);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
  }, [query]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && query.trim()) send();
    }
  };

  const handleVoiceTranscript = useCallback((transcript) => {
    setQuery(prev => prev ? prev + ' ' + transcript : transcript);
    textareaRef.current?.focus();
  }, [setQuery]);

  const canSend = query.trim().length > 0 && !isLoading;

  return (
    <div className="composer">
      <textarea
        ref={textareaRef}
        value={query}
        onChange={e => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask anything about BIS…"
        rows="1"
        disabled={isLoading}
      />
      <div className="composer-row">
        <div className="composer-tools">
          <AttachButton
            pendingFile={pendingFile}
            setPendingFile={setPendingFile}
            disabled={isLoading}
          />
          <CameraButton
            setPendingFile={setPendingFile}
            disabled={isLoading}
          />
          <VoiceButton
            onTranscript={handleVoiceTranscript}
            disabled={isLoading}
          />
        </div>
        <button
          className={`send ${!canSend ? 'send-disabled' : ''}`}
          onClick={() => !isLoading && send()}
          disabled={!canSend}
          title={isLoading ? 'Waiting for response…' : 'Send message'}
        >
          {isLoading ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
        </button>
      </div>
    </div>
  );
}

import { ttsService } from './services/ttsService';

// ─────────────────────────────────────────────────────────────────────────────
// TTS Listen button
// ─────────────────────────────────────────────────────────────────────────────

function ListenButton({ text, messageId, lang }) {
  const [ttsState, setTtsState] = useState('idle');
  const [voicesLoaded, setVoicesLoaded] = useState(false);
  const idRef = useRef(messageId || Math.random().toString());

  useEffect(() => {
    const handleStateChange = (state) => {
      if (ttsService.activeMessageId === idRef.current) {
        setTtsState(state);
      } else {
        setTtsState('idle');
      }
    };
    ttsService.onStateChange = handleStateChange;
    ttsService.onVoicesUpdated = () => setVoicesLoaded(prev => !prev);
    return () => {
      if (ttsService.activeMessageId === idRef.current) {
        ttsService.stop();
      }
    };
  }, []);

  const isSpeakingThis = ttsState === 'speaking' && ttsService.activeMessageId === idRef.current;
  const isPausedThis = ttsState === 'paused' && ttsService.activeMessageId === idRef.current;

  const handleListen = () => {
    if (!('speechSynthesis' in window)) return;

    if (isSpeakingThis) {
      ttsService.pause();
    } else if (isPausedThis) {
      ttsService.resume();
    } else {
      ttsService.speak(text, idRef.current, () => setTtsState('idle'), lang);
    }
  };

  const handleStop = (e) => {
    e.stopPropagation();
    ttsService.stop();
    setTtsState('idle');
  };

  const isSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;
  const targetLang = lang || detectLanguage(text);
  const hasVoice = isSupported && ttsService.hasMatchingVoice(targetLang);

  return (
    <div className="listen-btn-group" style={{ display: 'inline-flex', gap: '4px', alignItems: 'center' }}>
      <button
        onClick={handleListen}
        disabled={!isSupported || !hasVoice}
        style={{ opacity: !hasVoice ? 0.5 : 1, cursor: !hasVoice ? 'not-allowed' : 'pointer' }}
        title={
          !hasVoice
            ? `No native ${targetLang.toUpperCase()} voice installed on this device`
            : isSpeakingThis
            ? 'Pause speaking'
            : isPausedThis
            ? 'Resume speaking'
            : 'Listen to response'
        }
      >
        {isSpeakingThis ? <VolumeX size={14} /> : <Volume2 size={14} />}
        {isSpeakingThis ? 'Pause' : isPausedThis ? 'Resume' : 'Listen'}
      </button>
      {(isSpeakingThis || isPausedThis) && (
        <button
          onClick={handleStop}
          className="mini"
          style={{ padding: '2px 6px', fontSize: '11px' }}
          title="Stop audio playback"
        >
          Stop
        </button>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Home page
// ─────────────────────────────────────────────────────────────────────────────

function Home({ query, setQuery, send, nav, pendingFile, setPendingFile, isLoading }) {
  return (
    <section className="home page">
      <div className="hero">
        <div className="trust">
          <CheckCircle2 size={16} />
          BIS information assistant
        </div>

        <h1>
          How can <span>BIS Sahayta</span>
          <br />
          help you today?
        </h1>

        <p>
          Ask about Indian Standards, certification, testing, licensing, documents and compliance — in simple language.
        </p>

        <Composer
          query={query}
          setQuery={setQuery}
          send={send}
          pendingFile={pendingFile}
          setPendingFile={setPendingFile}
          isLoading={isLoading}
        />

        <div className="prompt-grid">
          {prompts.map(p => (
            <button
              key={p}
              onClick={() => {
                setQuery(p + ' ');
                const inputEl = document.querySelector('.composer textarea');
                if (inputEl) inputEl.focus();
              }}
            >
              {p}
              <ChevronRight size={16} />
            </button>
          ))}
        </div>

        <button className="guide-card" onClick={() => nav('guide')}>
          <div className="guide-icon"><Compass /></div>
          <div>
            <b>Not sure where to start?</b>
            <span>Let Sahayta guide you step-by-step.</span>
          </div>
          <ChevronRight />
        </button>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Chat page
// ─────────────────────────────────────────────────────────────────────────────

function Chat({ messages, query, setQuery, send, mode, setMode, retry, pendingFile, setPendingFile, isLoading,
               selectedModel, setSelectedModel, availableModels }) {
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const [userScrolled, setUserScrolled] = useState(false);

  // Model label helper
  const MODEL_LABELS = { auto: 'Auto', gemini: 'Gemini', gemma4: 'Gemma 4', qwen: 'Qwen' };

  const modelAvailMap = Object.fromEntries((availableModels || []).map(m => [m.key, m.available]));
  const isModelDisabled = (key) => {
    if (key === 'auto') return false; // auto is always available
    if (!availableModels.length) return false; // still loading
    return modelAvailMap[key] === false;
  };

  // Auto-scroll to bottom when new messages arrive, unless user scrolled up
  useEffect(() => {
    if (!userScrolled) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, userScrolled]);

  const handleScroll = () => {
    const container = messagesContainerRef.current;
    if (!container) return;
    const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
    setUserScrolled(!isAtBottom);
  };

  // Scroll to bottom when user sends (reset scroll lock)
  const handleSend = useCallback((text) => {
    setUserScrolled(false);
    send(text);
  }, [send]);

  const copyToClipboard = useCallback((text) => {
    navigator.clipboard?.writeText(text || '').catch(() => {
      // Fallback for browsers without clipboard API
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    });
  }, []);

  return (
    <section className="chat page">
      <div className="chat-header">
        <div>
          <span className="eyebrow">BIS Sahayta</span>
          <h2>Conversation</h2>
        </div>
        <div className="mode">
          <span>Response:</span>
          {['Simple', 'Short', 'Technical'].map(x => (
            <button
              className={mode === x ? 'selected' : ''}
              onClick={() => setMode(x)}
              key={x}
              disabled={isLoading}
            >
              {x}
            </button>
          ))}
        </div>
        {setSelectedModel && (
          <div className="model-selector" title="Select AI model">
            <select
              value={selectedModel || 'auto'}
              onChange={e => setSelectedModel(e.target.value)}
              disabled={isLoading}
              aria-label="AI model"
            >
              {['auto', 'gemini', 'gemma4', 'qwen'].map(key => (
                <option key={key} value={key} disabled={isModelDisabled(key)}>
                  {MODEL_LABELS[key]}{isModelDisabled(key) ? ' (unavailable)' : ''}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div
        className="messages"
        ref={messagesContainerRef}
        onScroll={handleScroll}
      >
        {messages.length === 0 ? (
          <div className="empty">
            <MessageSquare size={34} />
            <h3>Start a BIS conversation</h3>
            <p>Ask a question and your answer will appear here.</p>
          </div>
        ) : (
          messages.map((m, i) => (
            <MessageBubble
              key={i}
              message={m}
              onCopy={copyToClipboard}
              onRetry={retry}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {userScrolled && (
        <button
          className="scroll-to-bottom"
          onClick={() => {
            setUserScrolled(false);
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
          }}
        >
          ↓ Latest message
        </button>
      )}

      <div className="chat-composer">
        <Composer
          query={query}
          setQuery={setQuery}
          send={handleSend}
          pendingFile={pendingFile}
          setPendingFile={setPendingFile}
          isLoading={isLoading}
        />
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Message bubble
// ─────────────────────────────────────────────────────────────────────────────

function MessageBubble({ message: m, onCopy, onRetry }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    onCopy(m.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={'message ' + m.role}>
      <div className="avatar">{m.role === 'user' ? 'You' : 'BIS'}</div>
      <div className={`bubble ${m.error ? 'bubble-error' : ''}`}>
        {m.loading ? (
          <div className="typing">
            <span /><span /><span />Searching BIS knowledge…
          </div>
        ) : m.role === 'assistant' ? (
          <MarkdownContent text={m.text} />
        ) : (
          <div className="message-text">
            {m.text}
            {m.attachmentName && (
              <div className="msg-attachment">
                <FileText size={12} />
                <span>{m.attachmentName}</span>
              </div>
            )}
          </div>
        )}

        {m.error && (
          <div style={{ marginTop: '10px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button className="mini" onClick={onRetry}>
              Retry Question
            </button>
          </div>
        )}

        {m.role === 'assistant' && !m.loading && !m.error && (
          <div className="answer-tools">
            <button onClick={handleCopy}>
              <Copy size={14} />{copied ? 'Copied!' : 'Copy'}
            </button>
            <ListenButton
              text={m.text}
              messageId={m.id || m.timestamp || m.text?.slice(0, 20)}
              lang={m.responseLang || m.lang}
            />
          </div>
        )}

        {m.role === 'assistant' && !m.loading && (m.sources?.length > 0) && (
          <div className="sources-list">
            <div className="sources-title">
              <CheckCircle2 size={14} />BIS sources
            </div>
            {m.sources.map((s, j) => (
              <div className="source" key={j}>
                <b>{s.title || s.document_id || 'BIS Standard'}</b>
                <span>
                  {s.clause ? `Clause/Page ${s.clause}` : ''}
                  {s.snippet ? ` · ${s.snippet.slice(0, 120)}${s.snippet.length > 120 ? '…' : ''}` : ''}
                </span>
              </div>
            ))}
          </div>
        )}

        {m.role === 'assistant' && !m.loading && typeof m.relevance === 'number' && (
          <div className="confidence">
            Relevance: {Math.round(m.relevance * 100)}%
          </div>
        )}

        {m.role === 'assistant' && !m.loading && m.modelUsed && (
          <div className={`model-attribution ${m.fallbackUsed ? 'fallback' : ''}`}
               title={m.fallbackReason || `Answered by ${m.modelUsed}`}>
            {m.fallbackUsed
              ? `↩ Fallback: ${m.modelUsed}`
              : `⚡ ${m.modelUsed}`}
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Guide page
// ─────────────────────────────────────────────────────────────────────────────

function Guide({ onContinue }) {
  const [step, setStep] = useState(1);
  const [answers, setAnswers] = useState({});
  const [report, setReport] = useState(null);

  const qs = [
    'What are you trying to get help with?',
    'What product, service or activity is involved?',
    'What do you need right now?',
    'What would you like to do next?'
  ];

  const opts = [
    ['BIS certification', 'Find a standard', 'Testing / laboratory', 'Consumer complaint'],
    ['Food or water', 'Electrical product', 'Construction material', 'Other product'],
    ['Requirements', 'Documents', 'Fees / process', 'Explain a standard'],
    ['Show me the next steps', 'I want to ask another question']
  ];

  const makeReport = () => {
    const goal = answers[1] || 'BIS information';
    const product = answers[2] || 'Not specified';
    const need = answers[3] || 'General guidance';
    const next = answers[4] || 'Show me the next steps';

    setReport({
      goal, product, need, next,
      summary: `You are looking for help with ${goal.toLowerCase()} for ${product.toLowerCase()}, mainly around ${need.toLowerCase()}.`,
      chatContext: `Please guide me on ${goal} for ${product} focusing on ${need}.`
    });
  };

  if (report) {
    return (
      <section className="guide page">
        <div className="guide-head">
          <span className="eyebrow">GUIDE ME · REPORT</span>
          <h2>Your BIS guidance report</h2>
        </div>
        <div className="report-card">
          <div className="report-top">
            <div className="report-icon"><CheckCircle2 /></div>
            <div>
              <b>Guidance summary</b>
              <p>{report.summary}</p>
            </div>
          </div>
          <div className="report-actions">
            <button onClick={() => setReport(null)}><ArrowLeft />Edit answers</button>
            <button className="primary" onClick={() => onContinue(report)}>
              Continue to Chat <ChevronRight />
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="guide page">
      <div className="guide-head">
        <span className="eyebrow">GUIDE ME</span>
        <h2>A simpler way to find your BIS path</h2>
      </div>
      <div className="wizard">
        <h3>{qs[step - 1]}</h3>
        <div className="options">
          {opts[step - 1].map(o => (
            <button
              key={o}
              className={answers[step] === o ? 'chosen' : ''}
              onClick={() => setAnswers({ ...answers, [step]: o })}
            >
              {o} <ChevronRight size={17} />
            </button>
          ))}
        </div>
        <div className="wizard-actions">
          <button disabled={step === 1} onClick={() => setStep(step - 1)}><ArrowLeft />Back</button>
          {step < 4 ? (
            <button className="primary" disabled={!answers[step]} onClick={() => setStep(step + 1)}>
              Continue <ChevronRight />
            </button>
          ) : (
            <button className="primary" disabled={!answers[step]} onClick={makeReport}>
              Generate Report <ChevronRight />
            </button>
          )}
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// History page
// ─────────────────────────────────────────────────────────────────────────────

function HistoryPage({ sessions, loadSession, deleteSession }) {
  return (
    <section className="history-page page">
      <div className="section-head">
        <div>
          <span className="eyebrow">YOUR ACTIVITY</span>
          <h2>Search & chat history</h2>
        </div>
      </div>
      <div className="history-list">
        {sessions.length === 0 ? (
          <p style={{ color: 'var(--muted)' }}>No previous chat history found.</p>
        ) : (
          sessions.map(c => (
            <div className="history-card" key={c.id}>
              <div className="history-icon"><MessageSquare /></div>
              <div className="history-content" onClick={() => loadSession(c.id)} style={{ cursor: 'pointer' }}>
                <b>{(c.preview || 'Chat session').slice(0, 60)}</b>
                <span>{new Date(c.updated_at).toLocaleString()}</span>
              </div>
              <button className="icon-btn danger" onClick={() => deleteSession(c.id)}>
                <Trash2 size={17} />
              </button>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Settings page
// ─────────────────────────────────────────────────────────────────────────────

function SettingsPage({ dark, setDark, settings, setSettings }) {
  const [backendStatus, setBackendStatus] = useState('Checking...');
  const [backendDetails, setBackendDetails] = useState(null);

  useEffect(() => {
    apiFetch('/api/health')
      .then(d => {
        setBackendStatus(d.status === 'ok' ? 'Backend connected' : 'Degraded');
      })
      .catch(() => setBackendStatus('Disconnected'));

    apiFetch('/ready')
      .then(d => setBackendDetails(d.checks))
      .catch(() => {});
  }, []);

  const voiceSupported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);

  const ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;

  return (
    <section className="settings-page page">
      <div className="section-head">
        <div>
          <span className="eyebrow">PREFERENCES</span>
          <h2>Settings & accessibility</h2>
        </div>
      </div>
      <div className="settings-grid">
        <Setting title="Appearance" desc="Switch between light and dark mode.">
          <button className="toggle" onClick={() => setDark(!dark)}>
            <span className={dark ? 'on' : ''} />
            {dark ? 'Dark mode' : 'Light mode'}
          </button>
        </Setting>

        <Setting title="Text size" desc="Use larger text for better readability.">
          <button className="toggle" onClick={() => setSettings(s => ({ ...s, large: !s.large }))}>
            <span className={settings.large ? 'on' : ''} />
            {settings.large ? 'Large text' : 'Normal text'}
          </button>
        </Setting>

        <Setting title="Backend connection" desc="Status from GET /api/health">
          <span className={`status ${backendStatus === 'Backend connected' ? 'connected' : 'error'}`}>
            <span />
            {backendStatus}
          </span>
        </Setting>

        <Setting title="Voice input (STT)" desc="Speech-to-text using browser Web Speech API.">
          <span className={`status ${voiceSupported ? 'connected' : 'error'}`}>
            <span />
            {voiceSupported ? 'Supported' : 'Not supported (use Chrome/Edge)'}
          </span>
        </Setting>

        <Setting title="Text-to-speech (TTS)" desc="Listen to AI responses using browser speech synthesis.">
          <span className={`status ${ttsSupported ? 'connected' : 'error'}`}>
            <span />
            {ttsSupported ? 'Supported' : 'Not supported in this browser'}
          </span>
        </Setting>
      </div>
    </section>
  );
}

function Setting({ title, desc, children }) {
  return (
    <div className="setting">
      <div>
        <b>{title}</b>
        <p>{desc}</p>
      </div>
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Mount
// ─────────────────────────────────────────────────────────────────────────────

createRoot(document.getElementById('root')).render(<App />);