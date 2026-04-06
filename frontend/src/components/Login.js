import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { motion } from 'framer-motion';
import { getApiBase } from '../config';

const API_BASE = getApiBase();

function Login() {
  const [isRegister, setIsRegister] = useState(false);
  const [hostEmail, setHostEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const navigate = useNavigate();
  const { register, handleSubmit, formState: { errors } } = useForm();

  useEffect(() => {
    // If already logged in, redirect
    const user = JSON.parse(localStorage.getItem('user') || 'null');
    if (user) navigate(user.role === 'admin' ? '/dashboard' : '/chatbot');

    const loadHostEmail = async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/host-email`);
        const data = await res.json();
        if (data.host_email) { setHostEmail(data.host_email); return; }
      } catch {}
      if (process.env.REACT_APP_HOST_EMAIL) setHostEmail(process.env.REACT_APP_HOST_EMAIL);
    };
    loadHostEmail();
  }, [navigate]);

  const onSubmit = async (data) => {
    setErrorMsg('');
    setLoading(true);

    try {
      if (isRegister) {
        const res = await fetch(`${API_BASE}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: data.name, email: data.email, password: data.password, student_id: data.id || '' }),
        });
        const result = await res.json();
        if (result.status === 'ok') {
          setErrorMsg('');
          setIsRegister(false);
          alert('Registration successful! Please sign in.');
        } else {
          setErrorMsg(result.message || 'Registration failed');
        }
      } else {
        const res = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: data.email, password: data.password }),
        });
        const result = await res.json();
        if (result.status === 'ok') {
          localStorage.setItem('user', JSON.stringify(result.user));
          navigate(result.user.role === 'admin' ? '/dashboard' : '/chatbot');
        } else {
          setErrorMsg(result.message || 'Invalid credentials');
        }
      }
    } catch {
      setErrorMsg('Could not connect to the server. Please try again.');
    }

    setLoading(false);
  };

  const validatePassword = (value) => {
    const regex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{6,}$/;
    return regex.test(value) || 'Min 6 chars with uppercase, lowercase, number, and symbol';
  };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center',
      background: 'var(--bg-primary)',
    }}>
      {/* Subtle gradient blob */}
      <div style={{
        position: 'absolute', top: '-20%', left: '-10%',
        width: '500px', height: '500px', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(99,102,241,0.08), transparent 70%)',
        filter: 'blur(60px)', pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute', bottom: '-15%', right: '-5%',
        width: '400px', height: '400px', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(20,184,166,0.06), transparent 70%)',
        filter: 'blur(60px)', pointerEvents: 'none',
      }} />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        style={{
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          borderRadius: '20px', padding: '40px', width: '420px', maxWidth: '90vw',
          boxShadow: '0 8px 40px rgba(0,0,0,0.4)', position: 'relative',
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '8px' }}>
          <span style={{ fontSize: '1.1rem', fontWeight: 700, letterSpacing: '-0.3px' }}>
            <span style={{ color: 'var(--accent)' }}>AIML</span>
            <span style={{ color: 'var(--text-primary)' }}> NEXUS</span>
          </span>
        </div>

        <h2 style={{
          textAlign: 'center', marginBottom: '28px', fontWeight: 700,
          fontSize: '1.5rem', letterSpacing: '-0.5px', color: 'var(--text-primary)',
        }}>
          {isRegister ? 'Create Account' : 'Welcome back'}
        </h2>

        {errorMsg && (
          <div style={{
            background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)',
            borderRadius: '10px', padding: '10px 14px', marginBottom: '14px',
            color: '#f87171', fontSize: '0.85rem', textAlign: 'center',
          }}>
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {isRegister && (
            <>
              <div>
                <input {...register('name', { required: 'Name is required' })} placeholder="Full Name" className="glass-input" />
                {errors.name && <p style={{ color: '#f87171', fontSize: '0.78rem', marginTop: '4px' }}>{errors.name.message}</p>}
              </div>
              <div>
                <input {...register('id', { required: 'ID is required' })} placeholder="Student ID / USN" className="glass-input" />
                {errors.id && <p style={{ color: '#f87171', fontSize: '0.78rem', marginTop: '4px' }}>{errors.id.message}</p>}
              </div>
            </>
          )}
          <div>
            <input {...register('email', { required: 'Email is required' })} placeholder="Email" type="email" className="glass-input" />
            {errors.email && <p style={{ color: '#f87171', fontSize: '0.78rem', marginTop: '4px' }}>{errors.email.message}</p>}
          </div>
          <div>
            <input {...register('password', { required: 'Password is required', validate: isRegister ? validatePassword : undefined })} placeholder="Password" type="password" className="glass-input" />
            {errors.password && <p style={{ color: '#f87171', fontSize: '0.78rem', marginTop: '4px' }}>{errors.password.message}</p>}
          </div>

          <button type="submit" className="glass-button" disabled={loading} style={{ marginTop: '6px', width: '100%', padding: '13px', fontSize: '0.95rem', opacity: loading ? 0.6 : 1 }}>
            {loading ? 'Please wait...' : isRegister ? 'Sign Up' : 'Sign In'}
          </button>
        </form>

        {hostEmail && !isRegister && (
          <div style={{ marginTop: '14px', textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Admin: {hostEmail} / Admin@123
          </div>
        )}

        <div style={{ marginTop: '20px', textAlign: 'center' }}>
          <button
            onClick={() => { setIsRegister(!isRegister); setErrorMsg(''); }}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--accent)', fontSize: '0.88rem', fontWeight: 500,
            }}
          >
            {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Sign up"}
          </button>
        </div>

        <div style={{ marginTop: '18px', textAlign: 'center' }}>
          <button
            onClick={() => navigate('/')}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--text-muted)', fontSize: '0.82rem',
            }}
          >
            &larr; Back to home
          </button>
        </div>
      </motion.div>
    </div>
  );
}

export default Login;
