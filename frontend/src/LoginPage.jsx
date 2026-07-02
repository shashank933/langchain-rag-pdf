import React, { useState } from 'react';
import { useAuth } from './AuthContext';

export default function LoginPage() {
  const { login, loginError, setLoginError } = useAuth();
  const [username, setUsername] = useState(import.meta.env.VITE_DEFAULT_USERNAME || '');
  const [password, setPassword] = useState(import.meta.env.VITE_DEFAULT_PASSWORD || '');
  const [showPassword, setShowPassword] = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setLoginError('Please enter both username and password');
      return;
    }
    login(username.trim(), password);
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">
            <img
              src="/logo.svg"
              alt="SmartChat logo"
              style={{ width: 72, height: 72 }}
            />
          </div>
          <h1>SmartChat</h1>
          <p>Upload. Ask. Get answers.</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          {loginError && (
            <div className="nb-alert nb-alert-error">
              {loginError}
            </div>
          )}

          <div className="form-group">
            <label htmlFor="username">Username</label>
            <div className="input-wrapper">
              <span className="input-icon">👤</span>
              <input
                id="username"
                type="text"
                placeholder="Enter username"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value);
                  if (loginError) setLoginError('');
                }}
                autoFocus
                autoComplete="username"
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <div className="input-wrapper">
              <span className="input-icon">🔒</span>
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                placeholder="Enter password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (loginError) setLoginError('');
                }}
                autoComplete="current-password"
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>

          <button type="submit" className="nb-btn nb-btn-primary login-btn">
            SIGN IN
          </button>
        </form>

        <div className="login-footer">
          Powered by <code>LangChain</code> + <code>DeepSeek</code><br/>RAG-based document intelligence
        </div>
      </div>
    </div>
  );
}
