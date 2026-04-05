import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { getApiBase } from '../config';

const API_BASE = getApiBase();

function Login() {
  const [isRegister, setIsRegister] = useState(false);
  const [hostEmail, setHostEmail] = useState('');
  const [hostPassword, setHostPassword] = useState('Admin@123');
  const navigate = useNavigate();
  const { register, handleSubmit, formState: { errors } } = useForm();

  useEffect(() => {
    const loadHostEmail = async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/host-email`);
        const data = await res.json();
        if (data.host_email) {
          setHostEmail(data.host_email);
          return;
        }
      } catch (err) {
        console.warn('Could not load host email:', err.message);
      }
      if (process.env.REACT_APP_HOST_EMAIL) {
        setHostEmail(process.env.REACT_APP_HOST_EMAIL);
      }
    };
    loadHostEmail();
  }, []);

  const onSubmit = (data) => {
    if (typeof window === 'undefined') return;

    if (isRegister) {
      const storedUser = {
        ...data,
        role: 'user',
      };
      localStorage.setItem('user', JSON.stringify(storedUser));
      alert('Registration successful! Please login.');
      setIsRegister(false);
      return;
    }

    let storedUser = null;
    try {
      storedUser = JSON.parse(localStorage.getItem('user') || 'null');
    } catch (error) {
      storedUser = null;
    }

    if (storedUser && storedUser.email === data.email && storedUser.password === data.password) {
      localStorage.setItem('user', JSON.stringify(storedUser));
      navigate('/chatbot');
      return;
    }

    if (hostEmail && data.email === hostEmail && data.password === hostPassword) {
      const adminUser = {
        email: hostEmail,
        password: hostPassword,
        role: 'admin',
        name: 'Host Admin',
      };
      localStorage.setItem('user', JSON.stringify(adminUser));
      navigate('/dashboard');
      return;
    }

    alert('Invalid credentials');
  };

  const validatePassword = (value) => {
    const regex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{6,}$/;
    return regex.test(value) || "Password must be at least 6 characters with uppercase, lowercase, number, and symbol";
  };

  return (
    <div className="glass-container" style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div className="glass-card" style={{ padding: '40px', width: '400px' }}>
        <h2 style={{ textAlign: 'center', marginBottom: '30px', fontWeight: 700, letterSpacing: '-0.5px' }}>
          {isRegister ? 'Create Account' : 'Welcome Back'}
        </h2>
        <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {isRegister && (
            <>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <input
                  {...register('name', { required: 'Name is required' })}
                  placeholder="Full Name"
                  className="glass-input"
                />
                {errors.name && <p style={{ color: '#f87171', fontSize: '0.8rem' }}>{errors.name.message}</p>}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <input
                  {...register('id', { required: 'ID is required' })}
                  placeholder="Student ID"
                  className="glass-input"
                />
                {errors.id && <p style={{ color: '#f87171', fontSize: '0.8rem' }}>{errors.id.message}</p>}
              </div>
            </>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <input
              {...register('email', { required: 'Email is required' })}
              placeholder="Email Address"
              type="email"
              className="glass-input"
            />
            {errors.email && <p style={{ color: '#f87171', fontSize: '0.8rem' }}>{errors.email.message}</p>}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <input
              {...register('password', {
                required: 'Password is required',
                validate: validatePassword
              })}
              placeholder="Password"
              type="password"
              className="glass-input"
            />
            {errors.password && <p style={{ color: '#f87171', fontSize: '0.8rem' }}>{errors.password.message}</p>}
          </div>
          
          <button type="submit" className="glass-button" style={{ marginTop: '10px' }}>
            {isRegister ? 'Sign Up' : 'Sign In'}
          </button>
        </form>

        <div style={{ marginTop: '24px', textAlign: 'center' }}>
          <button
            onClick={() => setIsRegister(!isRegister)}
            className="glass-button secondary"
            style={{ width: '100%', fontSize: '0.9rem' }}
          >
            {isRegister ? 'Already have an account? Login' : 'New user? Create an account'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default Login;
