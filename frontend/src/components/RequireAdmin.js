import React from 'react';
import { Navigate } from 'react-router-dom';

export function getCurrentUser() {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    return JSON.parse(window.localStorage.getItem('user') || 'null');
  } catch (error) {
    return null;
  }
}

export function isAdminUser() {
  const user = getCurrentUser();
  return Boolean(user && user.role === 'admin');
}

export default function RequireAdmin({ children }) {
  const user = getCurrentUser();
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (user.role !== 'admin') {
    return <Navigate to="/chatbot" replace />;
  }
  return children;
}
