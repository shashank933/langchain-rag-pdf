import React, { createContext, useContext, useState, useCallback } from 'react';

const AuthContext = createContext(null);

const DEFAULT_USERNAME = import.meta.env.DEFAULT_USERNAME;
const DEFAULT_PASSWORD = import.meta.env.DEFAULT_PASSWORD;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loginError, setLoginError] = useState('');

  const login = useCallback((username, password) => {
    if (username === DEFAULT_USERNAME && password === DEFAULT_PASSWORD) {
      setUser({ username });
      setLoginError('');
      return true;
    } else {
      setLoginError('Invalid username or password');
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setLoginError('');
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, loginError, setLoginError }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
