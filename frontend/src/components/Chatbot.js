import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import SpeechRecognition, { useSpeechRecognition } from 'react-speech-recognition';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getApiBase } from '../config';
import { isAdminUser } from './RequireAdmin';
import './Chatbot.css';

const API_BASE = getApiBase();
const PERSONAS = ['default', 'student', 'faculty', 'parent', 'recruiter'];

function Chatbot() {
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem('nexusMessages');
    return saved ? JSON.parse(saved) : [{ text: 'Hello! I am your AIML Nexus assistant. Ask me about results, timetables, placements, or anything academic.', sender: 'bot' }];
  });
  const [input, setInput] = useState('');
  const [chatHistory, setChatHistory] = useState(() => {
    const saved = localStorage.getItem('nexusChatHistory');
    return saved ? JSON.parse(saved) : [];
  });
  const [currentChatId, setCurrentChatId] = useState(() => localStorage.getItem('nexusCurrentChatId') || null);
  const [sessionId, setSessionId] = useState(null);
  const [isListening, setIsListening] = useState(false);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [feedbackStatus, setFeedbackStatus] = useState('');
  const [agents, setAgents] = useState([]);
  const [persona, setPersona] = useState('default');
  const [showAgents, setShowAgents] = useState(false);
  const isAdmin = isAdminUser();
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);

  const { transcript, listening, resetTranscript, browserSupportsSpeechRecognition } = useSpeechRecognition();

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  useEffect(() => { localStorage.setItem('nexusMessages', JSON.stringify(messages)); }, [messages]);
  useEffect(() => { localStorage.setItem('nexusChatHistory', JSON.stringify(chatHistory)); }, [chatHistory]);
  useEffect(() => { localStorage.setItem('nexusCurrentChatId', currentChatId || ''); }, [currentChatId]);
  useEffect(() => { if (transcript) setInput(transcript); }, [transcript]);
  useEffect(() => { createSession(); fetchAgents(); }, []);

  const createSession = async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/session`, { method: 'POST' });
      const data = await res.json();
      setSessionId(data.session_id);
    } catch (err) { console.warn('Backend unavailable:', err.message); }
  };

  const fetchAgents = async () => {
    try {
      const res = await fetch(`${API_BASE}/agents/`);
      setAgents(await res.json());
    } catch (err) { console.warn('Could not fetch agents:', err.message); }
  };

  const sendToBackend = async (text) => {
    if (!sessionId) return null;
    try {
      const res = await fetch(
        `${API_BASE}/chat/send?session_id=${sessionId}&text=${encodeURIComponent(text)}&persona=${encodeURIComponent(persona)}`,
        { method: 'POST' }
      );
      return await res.json();
    } catch (err) { return null; }
  };

  const handleVoiceInput = () => {
    if (!browserSupportsSpeechRecognition) { alert('Speech recognition not supported.'); return; }
    if (listening) {
      SpeechRecognition.stopListening(); setIsListening(false);
      if (input.trim()) handleSend();
    } else {
      resetTranscript();
      SpeechRecognition.startListening({ continuous: true });
      setIsListening(true);
    }
  };

  const handleSubmitFeedback = async () => {
    if (!feedback.trim()) { setFeedbackStatus('Enter feedback first.'); return; }
    try {
      const userObj = JSON.parse(localStorage.getItem('user') || '{}');
      const email = userObj.email || 'guest@nexus.ai';
      const res = await fetch(`${API_BASE}/audit/feedback?session_id=${encodeURIComponent(sessionId || 'unknown')}&feedback=${encodeURIComponent(feedback)}&email=${encodeURIComponent(email)}`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'ok') { setFeedbackStatus('Thanks for your feedback!'); setFeedback(''); }
      else setFeedbackStatus('Could not submit feedback.');
    } catch { setFeedbackStatus('Submission failed.'); }
  };

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMessage = { text: input, sender: 'user' };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    const currentInput = input;
    setInput('');
    if (isListening) { SpeechRecognition.stopListening(); setIsListening(false); resetTranscript(); }

    if (!currentChatId) {
      const chatId = Date.now().toString();
      setCurrentChatId(chatId);
      setChatHistory(prev => [{ id: chatId, title: currentInput.slice(0, 35) + (currentInput.length > 35 ? '...' : ''), messages: newMessages, timestamp: new Date() }, ...prev]);
    }

    setLoading(true);

    const isModification = /\b(add|insert|update|save|edit|delete)\b/i.test(currentInput);
    const userObj = JSON.parse(localStorage.getItem('user') || '{}');
    const userEmail = userObj.email || 'guest@nexus.ai';

    let backendResponse;
    if (isModification) {
      try {
        const res = await fetch(`${API_BASE}/chat/modify?text=${encodeURIComponent(currentInput)}&email=${encodeURIComponent(userEmail)}`, { method: 'POST' });
        const data = await res.json();
        backendResponse = { response: `${data.message}${data.sql ? `\n\n**SQL:** \`${data.sql}\`` : ''}`, intent: 'modification' };
      } catch { backendResponse = { response: 'Modification failed. Backend may be offline.' }; }
    } else {
      backendResponse = await sendToBackend(currentInput);
    }

    const botMessage = backendResponse?.response
      ? {
          text: backendResponse.response,
          sender: 'bot',
          agent: backendResponse.sender || 'agent',
          intent: backendResponse.intent,
          confidence: backendResponse.confidence,
          duration: backendResponse.duration,
        }
      : { text: 'Could not connect to the service. Please try again.', sender: 'bot', agent: 'system' };

    const finalMessages = [...newMessages, botMessage];
    setMessages(finalMessages);

    setChatHistory(prev => {
      const updated = prev.map(chat => chat.id === currentChatId ? { ...chat, messages: finalMessages } : chat);
      if (!updated.find(c => c.id === currentChatId)) {
        return [{ id: currentChatId, title: currentInput.slice(0, 35), messages: finalMessages, timestamp: new Date() }, ...updated];
      }
      return updated;
    });

    setLoading(false);
  };

  const startNewChat = () => {
    setCurrentChatId(null);
    setMessages([{ text: 'Hello! How can I help you today?', sender: 'bot' }]);
    createSession();
  };

  const toggleAgent = async (agentName, currentEnabled) => {
    try {
      await fetch(`${API_BASE}/agents/${currentEnabled ? 'disable' : 'enable'}/${agentName}`, { method: 'POST' });
      fetchAgents();
    } catch {}
  };

  return (
    <div className="chatbot-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div style={{ padding: '18px 16px', borderBottom: '1px solid var(--border)' }}>
          <button className="new-chat-btn" onClick={startNewChat}>+ New Chat</button>
          <div style={{ marginTop: '16px', fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>
            History
          </div>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {chatHistory.map(chat => (
            <div
              key={chat.id}
              className={`chat-history-item ${currentChatId === chat.id ? 'active' : ''}`}
              onClick={() => { setCurrentChatId(chat.id); setMessages(chat.messages); }}
            >
              <div style={{ fontWeight: 500, fontSize: '0.88rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{chat.title}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>{new Date(chat.timestamp).toLocaleDateString()}</div>
            </div>
          ))}
        </div>

        {/* Agent status panel (collapsible) */}
        <div style={{ borderTop: '1px solid var(--border)' }}>
          <button
            onClick={() => setShowAgents(!showAgents)}
            style={{
              width: '100%', background: 'none', border: 'none', cursor: 'pointer',
              padding: '12px 16px', display: 'flex', justifyContent: 'space-between',
              alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.72rem',
              fontWeight: 600, textTransform: 'uppercase', letterSpacing: '1px',
            }}
          >
            Agents ({agents.filter(a => a.enabled).length}/{agents.length})
            <span style={{ fontSize: '0.9rem' }}>{showAgents ? '\u25B4' : '\u25BE'}</span>
          </button>
          {showAgents && (
            <div style={{ padding: '0 16px 12px' }}>
              {agents.map(a => (
                <div key={a.name} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '5px 0', fontSize: '0.78rem',
                }}>
                  <span style={{ color: a.enabled ? 'var(--success)' : 'var(--text-muted)' }}>
                    {a.enabled ? '\u25CF' : '\u25CB'} {a.name.replace(/_/g, ' ')}
                  </span>
                  <button
                    onClick={() => toggleAgent(a.name, a.enabled)}
                    style={{
                      background: 'none', border: '1px solid var(--border)',
                      color: 'var(--text-muted)', borderRadius: '4px',
                      fontSize: '0.65rem', padding: '2px 6px', cursor: 'pointer',
                    }}
                  >{a.enabled ? 'OFF' : 'ON'}</button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main Chat */}
      <div className="main-chat">
        <header className="chat-header">
          <h2><span>AIML</span> NEXUS</h2>
          <div className="header-actions">
            <select className="persona-select" value={persona} onChange={(e) => setPersona(e.target.value)}>
              {PERSONAS.map(p => <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>)}
            </select>
            <button className="glass-button secondary" onClick={() => navigate(isAdmin ? '/dashboard' : '/login')} style={{ padding: '6px 14px', fontSize: '0.8rem' }}>
              Dashboard
            </button>
            <button className="glass-button danger" onClick={() => { localStorage.removeItem('user'); navigate('/'); }} style={{ padding: '6px 14px', fontSize: '0.8rem' }}>
              Logout
            </button>
          </div>
        </header>

        <div className="messages-list">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message-wrapper ${msg.sender === 'user' ? 'user' : 'bot'}`}>
              {msg.sender === 'bot' && msg.agent && (
                <div className="message-meta">
                  <span className="agent-badge">{msg.agent}</span>
                  {msg.intent && <span>{msg.intent}</span>}
                  {msg.duration && <span>{msg.duration}s</span>}
                </div>
              )}
              <div className="message-bubble">
                <div className="message-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
                </div>
              </div>
            </div>
          ))}
          {loading && (
            <div className="message-wrapper bot">
              <div className="message-bubble" style={{ color: 'var(--accent)', fontStyle: 'italic' }}>
                <span className="loading-dots">Thinking</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-container">
          <input
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask about results, placements, schedules..."
          />
          <button className={`voice-btn ${listening ? 'listening' : ''}`} onClick={handleVoiceInput}>
            {listening ? '\u25CF' : '\uD83C\uDFA4'}
          </button>
          <button className="send-btn" onClick={handleSend} disabled={loading}>
            {loading ? '...' : 'Send'}
          </button>
        </div>

        <div className="feedback-container">
          <textarea className="feedback-input" rows={2} value={feedback} placeholder="Share feedback on this session..." onChange={(e) => setFeedback(e.target.value)} />
          <div className="feedback-actions">
            <button className="feedback-btn" onClick={handleSubmitFeedback}>Submit</button>
            {feedbackStatus && <span className="feedback-status">{feedbackStatus}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Chatbot;
