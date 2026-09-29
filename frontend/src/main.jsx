import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Search, Plus, Sun, Moon, Settings, History, Compass, Paperclip, Mic, Send, Menu, X,
  ChevronRight, ArrowLeft, Bookmark, MessageSquare, Trash2, CheckCircle2, Volume2, Copy
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

async function apiFetch(url, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
    ...(options.headers || {}),
  };
  const response = await fetch(url, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorMsg = typeof data?.detail === 'string'
      ? data.detail
      : data?.detail?.message || data?.message || `Request failed (${response.status})`;
    throw new Error(errorMsg);
  }
  return data;
}

function App() {
  const [page, setPage] = useState('home');
  const [dark, setDark] = useState(localStorage.getItem('bis-theme') === 'dark');
  const [mobile, setMobile] = useState(false);
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [mode, setMode] = useState('Simple');
  const [settings, setSettings] = useState({ large: false, citations: true });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('bis-theme', dark ? 'dark' : 'light');
  }, [dark]);

  const fetchSessions = async () => {
    try {
      const data = await apiFetch('/api/sessions');
      setSessions(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  const loadSession = async (sid) => {
    try {
      const msgs = await apiFetch(`/api/sessions/${sid}/messages`);
      setActiveSessionId(sid);
      setMessages(
        msgs.map(m => ({
          role: m.role,
          text: m.content,
          sources: m.metadata?.sources || [],
          confidence: m.metadata?.confidence,
        }))
      );
      setPage('chat');
    } catch (err) {
      console.error('Failed to load session messages:', err);
    }
  };

  const deleteSession = async (sid) => {
    try {
      await apiFetch(`/api/sessions/${sid}`, { method: 'DELETE' });
      if (activeSessionId === sid) {
        newChat();
      }
      fetchSessions();
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  const send = async (text = query) => {
    text = text.trim();
    if (!text) return;

    setMessages(m => [
      ...m,
      { role: 'user', text },
      { role: 'assistant', text: '', loading: true }
    ]);

    setQuery('');
    setPage('chat');

    try {
      const styleMap = { Simple: 'simple', Short: 'short', Technical: 'technical' };
      const bodyPayload = {
        query: text,
        session_id: activeSessionId || undefined,
        lang: 'en',
        use_rag: true,
        n_results: 5,
        style: styleMap[mode] || 'simple',
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
              confidence: data.confidence,
              intent: data.intent,
            }
          : msg
      ));
    } catch (error) {
      setMessages(m => m.map((msg, i) =>
        i === m.length - 1
          ? {
              role: 'assistant',
              text: `Unable to complete request. ${error.message}`,
              error: true,
            }
          : msg
      ));
    }
  };

  const newChat = () => {
    setMessages([]);
    setActiveSessionId(null);
    setPage('home');
    setQuery('');
  };

  const nav = (p) => {
    setPage(p);
    setMobile(false);
  };

  return (
    <div className={settings.large ? 'app large-text' : 'app'}>
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

          {sessions.slice(0, 5).map(c => (
            <button
              className={'chat-link ' + (activeSessionId === c.id ? 'active' : '')}
              key={c.id}
              onClick={() => loadSession(c.id)}
            >
              <MessageSquare size={16} />
              <span>{c.preview || 'Chat session'}</span>
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
            <Home query={query} setQuery={setQuery} send={send} nav={nav} />
          )}

          {page === 'chat' && (
            <Chat
              messages={messages}
              query={query}
              setQuery={setQuery}
              send={send}
              mode={mode}
              setMode={setMode}
              retry={() => {
                const lastUser = [...messages].reverse().find(m => m.role === 'user');
                if (lastUser) send(lastUser.text);
              }}
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
              settings={settings}
              setSettings={setSettings}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function Nav({ active, icon, label, onClick }) {
  return (
    <button className={'nav-item ' + (active ? 'active' : '')} onClick={onClick}>
      {icon}
      <span>{label}</span>
    </button>
  );
}

function Home({ query, setQuery, send, nav }) {
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

        <Composer query={query} setQuery={setQuery} send={send} />

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

function Composer({ query, setQuery, send }) {
  return (
    <div className="composer">
      <textarea
        value={query}
        onChange={e => setQuery(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        placeholder="Ask anything about BIS…"
        rows="1"
      />
      <div className="composer-row">
        <div>
          <button className="mini"><Paperclip size={17} />Attach</button>
          <button className="mini"><Mic size={17} />Voice</button>
        </div>
        <button className="send" onClick={() => send()}>
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}

function Chat({ messages, query, setQuery, send, mode, setMode, retry }) {
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
            >
              {x}
            </button>
          ))}
        </div>
      </div>

      <div className="messages">
        {messages.length === 0 ? (
          <div className="empty">
            <MessageSquare size={34} />
            <h3>Start a BIS conversation</h3>
            <p>Ask a question and your RAG-backed answer will appear here.</p>
          </div>
        ) : (
          messages.map((m, i) => (
            <div className={'message ' + m.role} key={i}>
              <div className="avatar">{m.role === 'user' ? 'You' : 'BIS'}</div>
              <div className="bubble">
                {m.loading ? (
                  <div className="typing">
                    <span /><span /><span />Searching BIS knowledge…
                  </div>
                ) : (
                  <div className="message-text">{m.text}</div>
                )}

                {m.error && (
                  <div style={{ marginTop: '8px' }}>
                    <button className="mini" onClick={retry}>Retry Question</button>
                  </div>
                )}

                {m.role === 'assistant' && !m.loading && !m.error && (
                  <div className="answer-tools">
                    <button onClick={() => navigator.clipboard?.writeText(m.text || '')}>
                      <Copy size={14} />Copy
                    </button>
                    <button onClick={() => {
                      if ('speechSynthesis' in window) {
                        window.speechSynthesis.cancel();
                        window.speechSynthesis.speak(new SpeechSynthesisUtterance(m.text || ''));
                      }
                    }}>
                      <Volume2 size={14} />Listen
                    </button>
                  </div>
                )}

                {m.role === 'assistant' && !m.loading && m.sources?.length > 0 && (
                  <div className="sources-list">
                    <div className="sources-title">
                      <CheckCircle2 size={14} />BIS sources
                    </div>
                    {m.sources.map((s, j) => (
                      <div className="source" key={j}>
                        <b>{s.title || s.document_id || 'BIS Standard'}</b>
                        <span>Clause / Page {s.clause || '—'} · {s.snippet || ''}</span>
                      </div>
                    ))}
                  </div>
                )}

                {m.role === 'assistant' && !m.loading && typeof m.relevance === 'number' && (
                  <div className="confidence">
                    Relevance: {Math.round(m.relevance * 100)}%
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="chat-composer">
        <Composer query={query} setQuery={setQuery} send={send} />
      </div>
    </section>
  );
}

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

    const generated = {
      goal, product, need, next,
      summary: `You are looking for help with ${goal.toLowerCase()} for ${product.toLowerCase()}, mainly around ${need.toLowerCase()}.`,
      steps: [
        `Clarify the exact BIS requirement for ${product.toLowerCase()}.`,
        `Identify the applicable Indian Standard, scheme, testing or compliance route.`,
        `Prepare documents relevant to your need: ${need.toLowerCase()}.`,
        `Use BIS Sahayta chat for the specific requirement or process.`
      ],
      important: [
        `Your answers are a starting point, not a final compliance decision.`,
        `Exact requirements depend on the product and applicable standard.`
      ],
      chatContext: `Please guide me on ${goal} for ${product} focusing on ${need}.`
    };
    setReport(generated);
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
                <b>{c.preview}</b>
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

function SettingsPage({ dark, setDark, settings, setSettings }) {
  const [backendStatus, setBackendStatus] = useState('Checking...');

  useEffect(() => {
    apiFetch('/api/health')
      .then(d => setBackendStatus(d.status === 'ok' ? 'Backend connected' : 'Degraded'))
      .catch(() => setBackendStatus('Disconnected'));
  }, []);

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

        <Setting title="Backend connection" desc="Status from GET /health">
          <span className={`status ${backendStatus === 'Backend connected' ? 'connected' : 'error'}`}>
            <span />
            {backendStatus}
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

createRoot(document.getElementById('root')).render(<App />);