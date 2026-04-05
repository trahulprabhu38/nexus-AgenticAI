import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import SpeechRecognition, { useSpeechRecognition } from 'react-speech-recognition';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getApiBase } from '../config';
import './Chatbot.css';

const API_BASE = getApiBase();
const PERSONAS = ['default', 'student', 'faculty', 'parent', 'recruiter'];

function Chatbot() {
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem('nexusMessages');
    return saved ? JSON.parse(saved) : [{ text: 'Hello! I am your AIML Nexus assistant. How can I help you today? You can ask about your results, timetable, attendance, or fees.', sender: 'bot' }];
  });
  const [input, setInput] = useState('');
  const [chatHistory, setChatHistory] = useState(() => {
    const saved = localStorage.getItem('nexusChatHistory');
    return saved ? JSON.parse(saved) : [];
  });
  const [currentChatId, setCurrentChatId] = useState(() => {
    return localStorage.getItem('nexusCurrentChatId') || null;
  });
  const [sessionId, setSessionId] = useState(null);
  const [isListening, setIsListening] = useState(false);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [feedbackStatus, setFeedbackStatus] = useState('');
  const [agents, setAgents] = useState([]);
  const [persona, setPersona] = useState('default');
  const navigate = useNavigate();
  const messagesEndRef = useRef(null);

  const {
    transcript,
    listening,
    resetTranscript,
    browserSupportsSpeechRecognition
  } = useSpeechRecognition();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  useEffect(() => {
    localStorage.setItem('nexusMessages', JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    localStorage.setItem('nexusChatHistory', JSON.stringify(chatHistory));
  }, [chatHistory]);

  useEffect(() => {
    localStorage.setItem('nexusCurrentChatId', currentChatId || '');
  }, [currentChatId]);

  useEffect(() => {
    if (transcript) {
      setInput(transcript);
    }
  }, [transcript]);

  useEffect(() => {
    createSession();
    fetchAgents();
  }, []);

  const createSession = async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/session`, { method: 'POST' });
      const data = await res.json();
      setSessionId(data.session_id);
    } catch (err) {
      console.warn('Backend not available:', err.message);
    }
  };

  const fetchAgents = async () => {
    try {
      const res = await fetch(`${API_BASE}/agents/`);
      const data = await res.json();
      setAgents(data);
    } catch (err) {
      console.warn('Could not fetch agents:', err.message);
    }
  };

  const sendToBackend = async (text) => {
    if (!sessionId) return null;
    try {
      const res = await fetch(
        `${API_BASE}/chat/send?session_id=${sessionId}&text=${encodeURIComponent(text)}&persona=${encodeURIComponent(persona)}`,
        { method: 'POST' }
      );
      return await res.json();
    } catch (err) {
      console.warn('Backend send failed:', err.message);
      return null;
    }
  };

  const handleVoiceInput = () => {
    if (!browserSupportsSpeechRecognition) {
      alert('Browser does not support speech recognition.');
      return;
    }
    if (listening) {
      SpeechRecognition.stopListening();
      setIsListening(false);
      if (input.trim()) handleSend();
    } else {
      resetTranscript();
      SpeechRecognition.startListening({ continuous: true });
      setIsListening(true);
    }
  };

  const handleSubmitFeedback = async () => {
    if (!feedback.trim()) {
      setFeedbackStatus('Please enter your feedback before submitting.');
      return;
    }
    try {
      const userObj = JSON.parse(localStorage.getItem('user') || '{}');
      const email = userObj.email || 'guest@nexus.ai';
      const res = await fetch(`${API_BASE}/audit/feedback?session_id=${encodeURIComponent(sessionId || 'unknown')}&feedback=${encodeURIComponent(feedback)}&email=${encodeURIComponent(email)}`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.status === 'ok') {
        setFeedbackStatus('Thank you for your feedback!');
        setFeedback('');
      } else {
        setFeedbackStatus('Could not submit feedback.');
      }
    } catch (err) {
      console.warn('Feedback submit failed:', err.message);
      setFeedbackStatus('Failed to submit feedback.');
    }
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = { text: input, sender: 'user' };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    const currentInput = input;
    setInput('');

    if (isListening) {
      SpeechRecognition.stopListening();
      setIsListening(false);
      resetTranscript();
    }

    // History Logic
    if (!currentChatId) {
      const chatId = Date.now().toString();
      setCurrentChatId(chatId);
      const newChat = {
        id: chatId,
        title: currentInput.slice(0, 30) + (currentInput.length > 30 ? '...' : ''),
        messages: newMessages,
        timestamp: new Date()
      };
      setChatHistory(prev => [newChat, ...prev]);
    }

    setLoading(true);
    
    // Detect if this is a modification request (add, insert, update, save, edit)
    const isModification = /\b(add|insert|update|save|edit|delete)\b/i.test(currentInput);
    const userObj = JSON.parse(localStorage.getItem('user') || '{}');
    const userEmail = userObj.email || 'guest@nexus.ai';

    let backendResponse;
    if (isModification) {
      try {
        const res = await fetch(`${API_BASE}/chat/modify?text=${encodeURIComponent(currentInput)}&email=${encodeURIComponent(userEmail)}`, { method: 'POST' });
        const data = await res.json();
        backendResponse = { 
          response: `${data.message}${data.sql ? `\n\n**Executed SQL:** \`${data.sql}\`` : ""}`,
          intent: "modification"
        };
      } catch (err) {
        backendResponse = { response: "Failed to process modification. Backend might be offline." };
      }
    } else {
      backendResponse = await sendToBackend(currentInput);
    }

    let botMessage;
    if (backendResponse && backendResponse.response) {
      botMessage = {
        text: backendResponse.response,
        sender: 'bot',
        agent: backendResponse.sender || (isModification ? 'db_modifier' : 'agent'),
        intent: backendResponse.intent,
        confidence: backendResponse.confidence,
        entropy_reduction: backendResponse.entropy_reduction,
        reasoning: backendResponse.reasoning,
        metadata: backendResponse,
      };
    } else {
      botMessage = { text: "Error connecting to service. Please try again.", sender: 'bot', agent: 'system' };
    }

    const finalMessages = [...newMessages, botMessage];
    setMessages(finalMessages);
    
    // Correctly update history:
    setChatHistory(prev => {
      const updated = prev.map(chat =>
        chat.id === (currentChatId || Date.now().toString()) ? { ...chat, messages: finalMessages } : chat
      );
      // If it was a new chat that didn't get into history yet (race condition), add it
      if (!updated.find(c => c.id === currentChatId)) {
         return [{ id: currentChatId, title: currentInput.slice(0,30), messages: finalMessages, timestamp: new Date() }, ...updated];
      }
      return updated;
    });

    setLoading(false);
  };

  const startNewChat = () => {
    setCurrentChatId(null);
    setMessages([
      { text: 'Hello! I am your AIML Nexus assistant. How can I help you today?', sender: 'bot' }
    ]);
    createSession();
  };

  const toggleAgent = async (agentName, currentEnabled) => {
    try {
      const action = currentEnabled ? 'disable' : 'enable';
      await fetch(`${API_BASE}/agents/${action}/${agentName}`, { method: 'POST' });
      fetchAgents();
    } catch (err) {
      console.warn('Could not toggle agent:', err.message);
    }
  };

  return (
    <div className="chatbot-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div style={{ padding: '24px', borderBottom: '1px solid var(--border-color)' }}>
          <button className="new-chat-btn" onClick={startNewChat}>+ New Conversation</button>
          <h3 style={{ margin: '20px 0 10px', fontSize: '0.9rem', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '1px' }}>History</h3>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {chatHistory.map(chat => (
            <div
              key={chat.id}
              className={`chat-history-item ${currentChatId === chat.id ? 'active' : ''}`}
              onClick={() => {
                setCurrentChatId(chat.id);
                setMessages(chat.messages);
              }}
            >
              <div style={{ fontWeight: '600', fontSize: '0.95rem', marginBottom: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{chat.title}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{new Date(chat.timestamp).toLocaleDateString()}</div>
            </div>
          ))}
        </div>

        {/* Agent Panel */}
        <div style={{ padding: '20px', background: 'rgba(0,0,0,0.2)', borderTop: '1px solid var(--border-color)' }}>
          <h4 style={{ margin: '0 0 12px', fontSize: '0.8rem', color: 'var(--accent-color)', textTransform: 'uppercase' }}>Active Agents</h4>
          {agents.map(a => (
            <div key={a.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', fontSize: '0.85rem' }}>
              <span style={{ opacity: a.enabled ? 1 : 0.5 }}>{a.enabled ? '● ONLINE' : '○ OFFLINE'} - {a.name}</span>
              <button
                onClick={() => toggleAgent(a.name, a.enabled)}
                style={{
                  background: 'none', border: '1px solid var(--border-color)', color: 'white', borderRadius: '4px', fontSize: '10px', padding: '2px 6px', cursor: 'pointer'
                }}
              >
                {a.enabled ? 'DISABLE' : 'ENABLE'}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat */}
      <div className="main-chat">
        <header className="chat-header">
          <h2>AIML NEXUS</h2>
          <div className="header-actions">
            <select 
              className="persona-select"
              value={persona} 
              onChange={(e) => setPersona(e.target.value)}
            >
              {PERSONAS.map(p => <option key={p} value={p}>{p.toUpperCase()}</option>)}
            </select>
            <button className="glass-button secondary" onClick={() => navigate(isAdmin ? '/dashboard' : '/login')} style={{ padding: '6px 16px', fontSize: '0.85rem' }}>
              Admin Dashboard
            </button>
            <button className="glass-button danger" onClick={() => {
              localStorage.removeItem('user');
              navigate('/');
            }} style={{ padding: '6px 16px', fontSize: '0.85rem' }}>Logout</button>
          </div>
        </header>

        <div className="messages-list">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message-wrapper ${msg.sender === 'user' ? 'user' : 'bot'}`}>
              {msg.sender === 'bot' && (
                <div className="message-meta">
                  <span className="agent-badge">via {msg.agent}</span>
                  {msg.intent && <span>{msg.intent} ({Math.round(msg.confidence * 100)}%)</span>}
                </div>
              )}
              {msg.reasoning && msg.sender === 'bot' && (
                <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginBottom: '4px', maxWidth: '80%' }}>
                  💡 {msg.reasoning}
                </div>
              )}
              <div className="message-bubble">
                <div className="message-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.text}
                  </ReactMarkdown>
                </div>
                {msg.sender === 'bot' && msg.metadata?.duration && (
                  <div style={{ 
                    fontSize: '0.65rem', 
                    opacity: 0.6, 
                    textAlign: 'right', 
                    marginTop: '4px',
                    fontFamily: 'monospace' 
                  }}>
                    Took: {msg.metadata.duration}s
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="message-wrapper bot">
              <div className="message-bubble" style={{ fontStyle: 'italic', color: 'var(--accent-color)' }}>
                Nexus is analyzing...
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
            placeholder="Search academic results, schedules..."
          />
          <button className={`voice-btn ${listening ? 'listening' : ''}`} onClick={handleVoiceInput}>
            {listening ? '●' : '🎤'}
          </button>
          <button className="send-btn" onClick={handleSend} disabled={loading}>
            {loading ? '...' : 'SEND'}
          </button>
        </div>

        <div className="feedback-container">
          <textarea
            className="feedback-input"
            rows={3}
            value={feedback}
            placeholder="Share your feedback on this session or agent performance..."
            onChange={(e) => setFeedback(e.target.value)}
          />
          <div className="feedback-actions">
            <button className="feedback-btn" onClick={handleSubmitFeedback}>Submit Feedback</button>
            {feedbackStatus && <span className="feedback-status">{feedbackStatus}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Chatbot;
