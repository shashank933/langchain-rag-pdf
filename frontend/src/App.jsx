import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import ReactMarkdown from 'react-markdown';
import { useAuth } from './AuthContext';
import LoginPage from './LoginPage';
import {
  createSession,
  uploadPdf,
  askQuestion,
  clearSession,
} from './api';

function LoadingDots() {
  return (
    <div className="loading-dots">
      <span></span>
      <span></span>
      <span></span>
    </div>
  );
}

function SourceCard({ source, index }) {
  return (
    <div className="source-card">
      <div className="source-card-header">
        SOURCE {index + 1}
        {source.page != null && <> &middot; PAGE {source.page}</>}
        {source.source && <> &middot; {source.source}</>}
      </div>
      <div className="source-card-content">{source.content}</div>
    </div>
  );
}

function ChatMessage({ message }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);

  return (
    <div className={`message ${message.role}`}>
      <div className="message-avatar">
        {message.role === 'user' ? '👤' : '🤖'}
      </div>
      <div>
        <div className="message-bubble">
          {message.role === 'assistant' ? (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          ) : (
            <p>{message.content}</p>
          )}
        </div>
        {message.role === 'assistant' &&
          message.sources &&
          message.sources.length > 0 && (
            <details
              className="sources-toggle"
              open={sourcesOpen}
              onToggle={(e) => setSourcesOpen(e.target.open)}
            >
              <summary>
                VIEW SOURCES ({message.sources.length})
              </summary>
              <div className="sources-list">
                {message.sources.map((source, i) => (
                  <SourceCard key={i} source={source} index={i} />
                ))}
              </div>
            </details>
          )}
      </div>
    </div>
  );
}

function Dashboard() {
  const { user, logout } = useAuth();
  const [sessionId, setSessionId] = useState(null);
  const [pdfLoaded, setPdfLoaded] = useState(false);
  const [pdfName, setPdfName] = useState('');
  const [chunkCount, setChunkCount] = useState(0);
  const [processing, setProcessing] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [answering, setAnswering] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    initSession();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function initSession() {
    try {
      const session = await createSession();
      setSessionId(session.session_id);
    } catch (err) {
      setError('Failed to connect to backend. Is it running?');
    }
  }

  async function handleReset() {
    if (!sessionId) return;
    try {
      await clearSession(sessionId);
    } catch {
      // ignore
    }
    setPdfLoaded(false);
    setPdfName('');
    setChunkCount(0);
    setMessages([]);
    setError(null);
    setSuccess(null);
    setProcessing(false);
    setUploadProgress(0);
    await initSession();
  }

  const onDrop = useCallback(
    async (acceptedFiles) => {
      const file = acceptedFiles[0];
      if (!file || !sessionId) return;

      setProcessing(true);
      setUploadProgress(0);
      setError(null);
      setSuccess(null);

      try {
        const result = await uploadPdf(sessionId, file, (progress) => {
          setUploadProgress(progress);
        });

        setPdfLoaded(true);
        setPdfName(result.pdf_name);
        setChunkCount(result.chunk_count);
        setMessages([]);
        setSuccess(result.message);
      } catch (err) {
        setError(err.message);
      } finally {
        setProcessing(false);
        setUploadProgress(0);
      }
    },
    [sessionId]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: processing,
  });

  async function handleAsk() {
    const question = inputValue.trim();
    if (!question || !sessionId || !pdfLoaded || answering) return;

    setAnswering(true);
    setError(null);

    const userMessage = { role: 'user', content: question };
    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');

    try {
      const result = await askQuestion(sessionId, question);
      const assistantMessage = {
        role: 'assistant',
        content: result.answer,
        sources: result.sources || [],
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(err.message);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${err.message}`, sources: [] },
      ]);
    } finally {
      setAnswering(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>PDF RAG</h1>
          <p>LangChain + DeepSeek</p>
        </div>

        <div className="sidebar-section">
          <div className="user-info">
            <span className="user-avatar">👤</span>
            <span className="user-name">{user?.username}</span>
            <button
              className="nb-btn nb-btn-outline logout-btn"
              onClick={logout}
            >
              LOGOUT
            </button>
          </div>
        </div>

        <div className="sidebar-section">
          <h3>Upload PDF</h3>
          <div
            {...getRootProps()}
            className={`dropzone ${isDragActive ? 'active' : ''}`}
          >
            <input {...getInputProps()} />
            <div className="dropzone-icon">
              {processing ? '⏳' : isDragActive ? '📂' : '📄'}
            </div>
            {processing ? (
              <div className="dropzone-text">
                Processing... {uploadProgress > 0 && `${uploadProgress}%`}
              </div>
            ) : (
              <>
                <div className="dropzone-text">
                  <strong>Click to upload</strong> or drag and drop
                </div>
                <div className="dropzone-hint">PDF files only</div>
              </>
            )}
          </div>
        </div>

        {pdfLoaded && (
          <div className="sidebar-section">
            <h3>Status</h3>
            <div className="status-card">
              <div className="status-item">
                <span
                  className={`status-dot ${pdfLoaded ? 'success' : 'waiting'}`}
                ></span>
                <span className="status-label">
                  {pdfLoaded ? 'PDF LOADED' : 'WAITING'}
                </span>
              </div>
              <div className="status-item">
                <span className="status-label">File:</span>
                <span className="status-value">{pdfName}</span>
              </div>
              <div className="status-item">
                <span className="status-label">Chunks:</span>
                <span className="status-value">{chunkCount}</span>
              </div>
            </div>
          </div>
        )}

        {pdfLoaded && (
          <div className="sidebar-section">
            <button className="nb-btn nb-btn-danger" onClick={handleReset}>
              RESET
            </button>
          </div>
        )}

        {!pdfLoaded && !processing && (
          <div className="sidebar-section">
            <button
              className="nb-btn nb-btn-primary"
              onClick={() => document.querySelector('input[type="file"]')?.click()}
            >
              PROCESS PDF
            </button>
          </div>
        )}

        {error && (
          <div className="nb-alert nb-alert-error">
            {error}
          </div>
        )}
        {success && (
          <div className="nb-alert nb-alert-success">
            {success}
          </div>
        )}

        <div className="sidebar-section" style={{ marginTop: 'auto' }}>
          <h3>How it works</h3>
          <div className="how-it-works">
            <ol>
              <li>Upload a PDF</li>
              <li>PDF is split into chunks</li>
              <li>Chunks are embedded</li>
              <li>Ask questions</li>
              <li>Get cited answers</li>
            </ol>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <div className="main-header">
          <h1>Chat with your PDF</h1>
          <p>
            Upload a PDF and ask questions — powered by LangChain + DeepSeek
          </p>
          {pdfLoaded && (
            <div className="pdf-badge">
              {pdfName} ({chunkCount} chunks)
            </div>
          )}
        </div>

        <div className="chat-area">
          {messages.length === 0 && (
            <div className="chat-empty">
              <div className="chat-empty-icon">💬</div>
              {pdfLoaded ? (
                <>
                  <h3>Ask a question</h3>
                  <p>Type your question below.</p>
                </>
              ) : (
                <>
                  <h3>No PDF loaded</h3>
                  <p>Upload a PDF using the sidebar.</p>
                </>
              )}
            </div>
          )}

          {messages.map((msg, i) => (
            <ChatMessage key={i} message={msg} />
          ))}

          {answering && (
            <div className="message assistant">
              <div className="message-avatar">🤖</div>
              <div className="message-bubble">
                <LoadingDots />
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        <div className="chat-input-area">
          <div className="chat-input-wrapper">
            <textarea
              ref={inputRef}
              className="chat-input"
              placeholder={
                pdfLoaded
                  ? 'Ask a question about your PDF...'
                  : 'Upload a PDF first...'
              }
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={!pdfLoaded || answering}
              rows={1}
            />
            <button
              className="send-btn"
              onClick={handleAsk}
              disabled={
                !pdfLoaded || answering || !inputValue.trim()
              }
              title="Send message"
            >
              {answering ? (
                <span className="spinner"></span>
              ) : (
                '→'
              )}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  const { user } = useAuth();

  if (!user) {
    return <LoginPage />;
  }

  return <Dashboard />;
}
