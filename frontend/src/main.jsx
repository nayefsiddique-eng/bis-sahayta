import React,{useEffect,useMemo,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Search,Plus,Sun,Moon,Settings,History,Compass,Paperclip,Mic,Send,Menu,X,ChevronRight,ArrowLeft,Bookmark,MessageSquare,SlidersHorizontal,Trash2,CheckCircle2,ExternalLink,Volume2,Copy} from 'lucide-react';
import './styles.css';
import bisLogo from "./assets/bis.png";

const starterChats=[
  {id:1,title:'BIS certification for packaged water',time:'Today'},
  {id:2,title:'Understanding IS 302 requirements',time:'Yesterday'},
  {id:3,title:'Documents needed for licensing',time:'Sep 25'}
];

const prompts=[
  'Understand a Standard',
  'BIS Certification Scheme',
  'Find Requirements',
  'Check Documents',
  'Testing & Lab Compliance'
];

function App(){
  const [page,setPage]=useState('home');
  const [dark,setDark]=useState(localStorage.getItem('bis-theme')==='dark');
  const [mobile,setMobile]=useState(false);
  const [query,setQuery]=useState('');
  const [messages,setMessages]=useState([]);
  const [chats,setChats]=useState(starterChats);
  const [activeId,setActiveId]=useState(null);
  const [mode,setMode]=useState('Simple');
  const [settings,setSettings]=useState({large:false,citations:true});
  const [guideReport,setGuideReport]=useState(null);

  useEffect(()=>{
    document.documentElement.classList.toggle('dark',dark);
    localStorage.setItem('bis-theme',dark?'dark':'light')
  },[dark]);

  const send=async(text=query)=>{
    text=text.trim();
    if(!text)return;

    const id=Date.now();

    setMessages(m=>[
      ...m,
      {role:'user',text},
      {role:'assistant',text:'',loading:true}
    ]);

    setQuery('');
    setPage('chat');
    setActiveId(id);

    try{
      const response=await fetch('/api/chat',{
        method:'POST',
        headers:{
          'Content-Type':'application/json',
          'X-API-Key':'demo-key-123'
        },
        body:JSON.stringify({
          query:text,
          lang:'en',
          top_k:5
        })
      });

      const data=await response.json();

      if(!response.ok){
        throw new Error(
          data?.detail ||
          data?.message ||
          `Request failed (${response.status})`
        );
      }

      const sources=Array.isArray(data.sources)
        ? data.sources
        : [];

      setMessages(m=>m.map((msg,i)=>
        i===m.length-1
          ? {
              role:'assistant',
              text:data.answer||'No answer was returned by the BIS backend.',
              sources,
              confidence:data.confidence,
              detectedIntent:data.detected_intent,
              scanContext:data.scan_context
            }
          : msg
      ));

    }catch(error){

      setMessages(m=>m.map((msg,i)=>
        i===m.length-1
          ? {
              role:'assistant',
              text:`I couldn't connect to the BIS backend. Make sure Nayef's backend is running on port 8000.\n\n${error.message}`,
              error:true
            }
          : msg
      ));

    }
  };

  const newChat=()=>{
    setMessages([]);
    setActiveId(null);
    setPage('home');
    setQuery('');
  };

  const nav=(p)=>{
    setPage(p);
    setMobile(false);
  };

  return (
    <div className={settings.large?'app large-text':'app'}>

      <header className="topbar">

        <button
          className="icon-btn mobile-only"
          onClick={()=>setMobile(!mobile)}
        >
          {mobile?<X/>:<Menu/>}
        </button>

        <button
          className="brand"
          onClick={()=>nav('home')}
        >

          <img
            src={bisLogo}
            alt="BIS"
            className="bis-logo"
          />

          <div>
            <b>BIS Sahayta</b>
            <span>AI assistant for BIS information</span>
          </div>

        </button>

        <div className="top-actions">

          <button
            className="icon-btn"
            onClick={()=>setDark(!dark)}
            title="Toggle theme"
          >
            {dark?<Sun/>:<Moon/>}
          </button>

          <button
            className="new-btn"
            onClick={newChat}
          >
            <Plus size={18}/>
            New Chat
          </button>

        </div>

      </header>

      <div className="layout">

        <aside className={'sidebar '+(mobile?'open':'')}>

          <button
            className="new-chat"
            onClick={newChat}
          >
            <Plus/>
            New Chat
          </button>

          <nav>

            <Nav
              active={page==='home'||page==='chat'}
              icon={<MessageSquare/>}
              label="Ask Sahayta"
              onClick={()=>nav(messages.length?'chat':'home')}
            />

            <Nav
              active={page==='guide'}
              icon={<Compass/>}
              label="Guide Me"
              onClick={()=>nav('guide')}
            />

            <Nav
              active={page==='history'}
              icon={<History/>}
              label="History"
              onClick={()=>nav('history')}
            />

          </nav>

          <div className="side-label">
            RECENT
          </div>

          {chats.map(c=>
            <button
              className="chat-link"
              key={c.id}
              onClick={()=>{
                setActiveId(c.id);
                setMessages([
                  {
                    role:'user',
                    text:c.title
                  },
                  {
                    role:'assistant',
                    text:'This saved conversation is a frontend demo. Your future backend can load the real session here.'
                  }
                ]);
                nav('chat');
              }}
            >
              <MessageSquare size={16}/>
              <span>{c.title}</span>
            </button>
          )}

          <div className="sidebar-bottom">

            <button
              className="side-link"
              onClick={()=>nav('settings')}
            >
              <Settings/>
              Settings
            </button>

            <button
              className="side-link"
              onClick={()=>nav('home')}
            >
              <Bookmark/>
              Saved standards
            </button>

          </div>

        </aside>

        {mobile&&
          <div
            className="backdrop"
            onClick={()=>setMobile(false)}
          />
        }

        <main className="main">

          {page==='home'&&
            <Home
              query={query}
              setQuery={setQuery}
              send={send}
              nav={nav}
              dark={dark}
            />
          }

          {page==='chat'&&
            <Chat
              messages={messages}
              query={query}
              setQuery={setQuery}
              send={send}
              mode={mode}
              setMode={setMode}
            />
          }

          {page==='guide'&&
            <Guide
              onReport={setGuideReport}
              onContinue={(report)=>{
                setGuideReport(report);

                setMessages([
                  {
                    role:'assistant',
                    text:report.chatContext,
                    guideReport:true
                  }
                ]);

                setQuery('');
                setPage('chat');
              }}
            />
          }

          {page==='history'&&
            <HistoryPage
              chats={chats}
              setChats={setChats}
            />
          }

          {page==='settings'&&
            <SettingsPage
              dark={dark}
              setDark={setDark}
              settings={settings}
              setSettings={setSettings}
            />
          }

        </main>

      </div>

    </div>
  );
}

function Nav({active,icon,label,onClick}){

  return (
    <button
      className={'nav-item '+(active?'active':'')}
      onClick={onClick}
    >
      {icon}
      <span>{label}</span>
    </button>
  );

}

function Home({query,setQuery,send,nav}){

  return (
    <section className="home page">

      <div className="hero">

        <div className="trust">
          <CheckCircle2 size={16}/>
          BIS information assistant
        </div>

        <h1>
          How can <span>BIS Sahayta</span>
          <br/>
          help you today?
        </h1>

        <p>
          Ask about Indian Standards, certification, testing,
          licensing, documents and compliance — in simple language.
        </p>

        <Composer
          query={query}
          setQuery={setQuery}
          send={send}
        />

        <div className="prompt-grid">

          {prompts.map(p=>
            <button
              key={p}
              onClick={()=>setQuery(p+' — ')}
            >
              {p}
              <ChevronRight size={16}/>
            </button>
          )}

        </div>

        <button
          className="guide-card"
          onClick={()=>nav('guide')}
        >

          <div className="guide-icon">
            <Compass/>
          </div>

          <div>
            <b>Not sure where to start?</b>
            <span>
              Let Sahayta guide you step-by-step.
            </span>
          </div>

          <ChevronRight/>

        </button>

      </div>

    </section>
  );

}

function Composer({query,setQuery,send}){

  return (
    <div className="composer">

      <textarea
        value={query}
        onChange={e=>setQuery(e.target.value)}
        onKeyDown={e=>{
          if(e.key==='Enter'&&!e.shiftKey){
            e.preventDefault();
            send();
          }
        }}
        placeholder="Ask anything about BIS…"
        rows="1"
      />

      <div className="composer-row">

        <div>

          <button className="mini">
            <Paperclip size={17}/>
            Attach
          </button>

          <button className="mini">
            <Mic size={17}/>
            Voice
          </button>

        </div>

        <button
          className="send"
          onClick={()=>send()}
        >
          <Send size={18}/>
        </button>

      </div>

    </div>
  );

}

function Chat({
  messages,
  query,
  setQuery,
  send,
  mode,
  setMode
}){

  return (
    <section className="chat page">

      <div className="chat-header">

        <div>
          <span className="eyebrow">
            BIS Sahayta
          </span>

          <h2>
            Conversation
          </h2>
        </div>

        <div className="mode">

          <span>
            Response:
          </span>

          {['Simple','Short','Technical'].map(x=>
            <button
              className={mode===x?'selected':''}
              onClick={()=>setMode(x)}
              key={x}
            >
              {x}
            </button>
          )}

        </div>

      </div>

      <div className="messages">

        {messages.length===0
          ?
          <div className="empty">

            <MessageSquare size={34}/>

            <h3>
              Start a BIS conversation
            </h3>

            <p>
              Ask a question and your RAG-backed answer can appear here.
            </p>

          </div>
          :
          messages.map((m,i)=>
            <div
              className={'message '+m.role}
              key={i}
            >

              <div className="avatar">
                {m.role==='user'?'You':'BIS'}
              </div>

              <div className="bubble">

                {m.loading
                  ?
                  <div className="typing">
                    <span/>
                    <span/>
                    <span/>
                    Searching BIS knowledge…
                  </div>
                  :
                  <div className="message-text">
                    {m.text}
                  </div>
                }

                {m.role==='assistant'&&!m.loading&&
                  <div className="answer-tools">

                    <button
                      onClick={()=>
                        navigator.clipboard?.writeText(m.text||'')
                      }
                    >
                      <Copy size={14}/>
                      Copy
                    </button>

                    <button
                      onClick={()=>{
                        if('speechSynthesis' in window){
                          window.speechSynthesis.cancel();

                          window.speechSynthesis.speak(
                            new SpeechSynthesisUtterance(
                              m.text||''
                            )
                          );
                        }
                      }}
                    >
                      <Volume2 size={14}/>
                      Listen
                    </button>

                  </div>
                }

                {m.role==='assistant'&&!m.loading&&m.sources?.length>0&&
                  <div className="sources-list">

                    <div className="sources-title">
                      <CheckCircle2 size={14}/>
                      BIS sources
                    </div>

                    {m.sources.map((s,j)=>
                      <div
                        className="source"
                        key={j}
                      >

                        <b>
                          {s.standard_number||'BIS Standard'}
                        </b>

                        <span>
                          {s.document||'Document'} · Page {s.page??'—'} · {s.section||'—'}
                        </span>

                      </div>
                    )}

                  </div>
                }

                {m.role==='assistant'&&!m.loading&&typeof m.confidence==='number'&&
                  <div className="confidence">
                    Confidence: {Math.round(m.confidence*100)}%
                  </div>
                }

              </div>

            </div>
          )
        }

      </div>

      <div className="chat-composer">

        <Composer
          query={query}
          setQuery={setQuery}
          send={send}
        />

      </div>

    </section>
  );

}

function Guide({onReport,onContinue}){

  const [step,setStep]=useState(1);
  const [answers,setAnswers]=useState({});
  const [report,setReport]=useState(null);

  const qs=[
    'What are you trying to get help with?',
    'What product, service or activity is involved?',
    'What do you need right now?',
    'What would you like to do next?'
  ];

  const opts=[
    [
      'BIS certification',
      'Find a standard',
      'Testing / laboratory',
      'Consumer complaint'
    ],
    [
      'Food or water',
      'Electrical product',
      'Construction material',
      'Other product'
    ],
    [
      'Requirements',
      'Documents',
      'Fees / process',
      'Explain a standard'
    ],
    [
      'Show me the next steps',
      'I want to ask another question'
    ]
  ];

  const makeReport=()=>{

    const goal=answers[1]||'BIS information';
    const product=answers[2]||'Not specified';
    const need=answers[3]||'General guidance';
    const next=answers[4]||'Show me the next steps';

    const generated={
      goal,
      product,
      need,
      next,

      summary:
        `You are looking for help with ${goal.toLowerCase()} for ${product.toLowerCase()}, mainly around ${need.toLowerCase()}.`,

      steps:[
        `Clarify the exact BIS requirement for ${product.toLowerCase()}.`,
        `Identify the applicable Indian Standard, scheme, testing or compliance route.`,
        `Prepare the documents or information relevant to your selected need: ${need.toLowerCase()}.`,
        `Use BIS Sahayta chat for the specific requirement, standard number, process or document you want to verify.`
      ],

      important:[
        `Your answers are a starting point, not a final compliance decision.`,
        `Exact requirements can depend on the product, applicable standard and certification/testing route.`,
        `For a precise answer, continue to Chat and ask about the specific requirement you need.`
      ],

      chatContext:
        `Guide Me context:\nGoal: ${goal}\nProduct / activity: ${product}\nNeed: ${need}\nNext step: ${next}\n\nPlease use this context to help me with my BIS query.`
    };

    setReport(generated);
    onReport?.(generated);

  };

  if(report){

    return (
      <section className="guide page">

        <div className="guide-head">

          <span className="eyebrow">
            GUIDE ME · REPORT
          </span>

          <h2>
            Your BIS guidance report
          </h2>

          <p>
            Here is a structured starting point based on the answers you provided.
          </p>

        </div>

        <div className="report-card">

          <div className="report-top">

            <div className="report-icon">
              <CheckCircle2/>
            </div>

            <div>

              <b>
                Guidance summary
              </b>

              <p>
                {report.summary}
              </p>

            </div>

          </div>

          <div className="report-grid">

            <div className="report-section">
              <span>YOUR GOAL</span>
              <h3>{report.goal}</h3>
            </div>

            <div className="report-section">
              <span>PRODUCT / ACTIVITY</span>
              <h3>{report.product}</h3>
            </div>

            <div className="report-section">
              <span>WHAT YOU NEED</span>
              <h3>{report.need}</h3>
            </div>

            <div className="report-section">
              <span>NEXT STEP</span>
              <h3>{report.next}</h3>
            </div>

          </div>

          <div className="report-block">

            <h3>
              Recommended action path
            </h3>

            <ol>

              {report.steps.map((x,i)=>
                <li key={i}>
                  {x}
                </li>
              )}

            </ol>

          </div>

          <div className="report-block">

            <h3>
              Important points
            </h3>

            <ul>

              {report.important.map((x,i)=>
                <li key={i}>
                  {x}
                </li>
              )}

            </ul>

          </div>

          <div className="report-actions">

            <button
              onClick={()=>setReport(null)}
            >
              <ArrowLeft/>
              Edit answers
            </button>

            <button
              className="primary"
              onClick={()=>onContinue(report)}
            >
              Continue to Chat
              <ChevronRight/>
            </button>

          </div>

        </div>

      </section>
    );

  }

  return (
    <section className="guide page">

      <div className="guide-head">

        <span className="eyebrow">
          GUIDE ME
        </span>

        <h2>
          A simpler way to find your BIS path
        </h2>

        <p>
          Answer a few questions first. Sahayta will prepare a structured report before you enter Chat.
        </p>

      </div>

      <div className="progress">

        <div className="progress-line">

          <span
            style={{
              width:`${step*25}%`
            }}
          />

        </div>

        <div>
          Step {step} of 4
        </div>

      </div>

      <div className="wizard">

        <div className="wizard-icon">
          <Compass/>
        </div>

        <h3>
          {qs[step-1]}
        </h3>

        <div className="options">

          {opts[step-1].map(o=>
            <button
              key={o}
              className={answers[step]===o?'chosen':''}
              onClick={()=>
                setAnswers({
                  ...answers,
                  [step]:o
                })
              }
            >
              {o}
              <ChevronRight size={17}/>
            </button>
          )}

        </div>

        <div className="wizard-actions">

          <button
            disabled={step===1}
            onClick={()=>setStep(step-1)}
          >
            <ArrowLeft/>
            Back
          </button>

          {step<4
            ?
            <button
              className="primary"
              disabled={!answers[step]}
              onClick={()=>setStep(step+1)}
            >
              Continue
              <ChevronRight/>
            </button>
            :
            <button
              className="primary"
              disabled={!answers[step]}
              onClick={makeReport}
            >
              Generate Report
              <ChevronRight/>
            </button>
          }

        </div>

      </div>

    </section>
  );

}

function HistoryPage({chats,setChats}){

  return (
    <section className="history-page page">

      <div className="section-head">

        <div>

          <span className="eyebrow">
            YOUR ACTIVITY
          </span>

          <h2>
            Search & chat history
          </h2>

        </div>

        <div className="searchbox">

          <Search/>

          <input
            placeholder="Search conversations…"
          />

        </div>

      </div>

      <div className="history-list">

        {chats.map(c=>
          <div
            className="history-card"
            key={c.id}
          >

            <div className="history-icon">
              <MessageSquare/>
            </div>

            <div className="history-content">

              <b>
                {c.title}
              </b>

              <span>
                {c.time} · Saved conversation
              </span>

            </div>

            <button className="icon-btn">
              <Bookmark size={18}/>
            </button>

            <button
              className="icon-btn danger"
              onClick={()=>
                setChats(
                  chats.filter(x=>x.id!==c.id)
                )
              }
            >
              <Trash2 size={17}/>
            </button>

          </div>
        )}

      </div>

    </section>
  );

}

function SettingsPage({
  dark,
  setDark,
  settings,
  setSettings
}){

  return (
    <section className="settings-page page">

      <div className="section-head">

        <div>

          <span className="eyebrow">
            PREFERENCES
          </span>

          <h2>
            Settings & accessibility
          </h2>

          <p>
            Make BIS Sahayta easier and more comfortable to use.
          </p>

        </div>

      </div>

      <div className="settings-grid">

        <Setting
          title="Appearance"
          desc="Switch between light and dark mode."
        >
          <button
            className="toggle"
            onClick={()=>setDark(!dark)}
          >
            <span className={dark?'on':''}/>
            {dark?'Dark mode':'Light mode'}
          </button>
        </Setting>

        <Setting
          title="Larger text"
          desc="Increase text size across the workspace."
        >
          <button
            className="toggle"
            onClick={()=>
              setSettings({
                ...settings,
                large:!settings.large
              })
            }
          >
            <span className={settings.large?'on':''}/>
            {settings.large?'Enabled':'Disabled'}
          </button>
        </Setting>

        <Setting
          title="Verified citations"
          desc="Show source badges on assistant answers."
        >
          <button
            className="toggle"
            onClick={()=>
              setSettings({
                ...settings,
                citations:!settings.citations
              })
            }
          >
            <span className={settings.citations?'on':''}/>
            {settings.citations?'Enabled':'Disabled'}
          </button>
        </Setting>

        <Setting
          title="Backend connection"
          desc="Connected to the local BIS RAG backend at POST /api/chat."
        >
          <span className="status connected">
            <span/>
            Backend connected
          </span>
        </Setting>

      </div>

    </section>
  );

}

function Setting({title,desc,children}){

  return (
    <div className="setting">

      <div>

        <b>
          {title}
        </b>

        <p>
          {desc}
        </p>

      </div>

      {children}

    </div>
  );

}

createRoot(
  document.getElementById('root')
).render(
  <App/>
);