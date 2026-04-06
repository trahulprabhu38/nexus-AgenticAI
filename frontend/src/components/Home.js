import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Float, MeshDistortMaterial } from '@react-three/drei';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import * as THREE from 'three';

/* ── Animated sphere cluster for the 3D hero ─────────────────────── */
function GlowSphere({ position, color, speed, distort }) {
  const ref = useRef();
  useFrame((state) => {
    ref.current.rotation.x = state.clock.elapsedTime * speed * 0.3;
    ref.current.rotation.y = state.clock.elapsedTime * speed * 0.2;
  });
  return (
    <Float speed={1.5} rotationIntensity={0.4} floatIntensity={1.2}>
      <mesh ref={ref} position={position}>
        <icosahedronGeometry args={[1, 16]} />
        <MeshDistortMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.3}
          roughness={0.2}
          metalness={0.8}
          distort={distort}
          speed={2}
          transparent
          opacity={0.85}
        />
      </mesh>
    </Float>
  );
}

function ParticleField() {
  const count = 600;
  const positions = useMemo(() => {
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count * 3; i++) {
      pos[i] = (Math.random() - 0.5) * 20;
    }
    return pos;
  }, []);

  const ref = useRef();
  useFrame((state) => {
    ref.current.rotation.y = state.clock.elapsedTime * 0.02;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial size={0.02} color="#6366f1" transparent opacity={0.6} sizeAttenuation />
    </points>
  );
}

function Scene() {
  return (
    <>
      <ambientLight intensity={0.15} />
      <pointLight position={[5, 5, 5]} intensity={0.8} color="#6366f1" />
      <pointLight position={[-5, -3, 3]} intensity={0.4} color="#14b8a6" />
      <GlowSphere position={[0, 0, 0]} color="#6366f1" speed={0.4} distort={0.4} />
      <GlowSphere position={[2.5, -1, -1]} color="#14b8a6" speed={0.3} distort={0.3} />
      <GlowSphere position={[-2, 1.5, -2]} color="#8b5cf6" speed={0.5} distort={0.5} />
      <ParticleField />
      <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={0.5} />
    </>
  );
}

/* ── Animations ──────────────────────────────────────────────────── */
const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.15, duration: 0.7, ease: [0.22, 1, 0.36, 1] },
  }),
};

const agents = [
  'Intent Classification',
  'Table Selection',
  'Column Pruning',
  'SQL Generation',
  'SQL Validation',
  'Audit & Safety',
];

function Home() {
  const navigate = useNavigate();
  const user = typeof window !== 'undefined' ? JSON.parse(localStorage.getItem('user') || 'null') : null;
  const isAdmin = Boolean(user && user.role === 'admin');

  return (
    <div style={{ position: 'relative', minHeight: '100vh', overflow: 'hidden', background: '#0a0f1a' }}>
      {/* 3D Background */}
      <div style={{ position: 'absolute', inset: 0, zIndex: 0 }}>
        <Canvas camera={{ position: [0, 0, 6], fov: 55 }}>
          <Scene />
        </Canvas>
      </div>

      {/* Gradient overlay */}
      <div style={{
        position: 'absolute', inset: 0, zIndex: 1,
        background: 'linear-gradient(180deg, rgba(10,15,26,0.3) 0%, rgba(10,15,26,0.85) 70%, rgba(10,15,26,1) 100%)',
      }} />

      {/* Content */}
      <div style={{ position: 'relative', zIndex: 2, minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        {/* Nav */}
        <motion.nav
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '20px 40px',
          }}
        >
          <div style={{ fontSize: '1.2rem', fontWeight: 700, letterSpacing: '-0.5px' }}>
            <span style={{ color: '#6366f1' }}>AIML</span>
            <span style={{ color: '#f1f5f9' }}> NEXUS</span>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              className="glass-button secondary"
              onClick={() => navigate(isAdmin ? '/dashboard' : '/login')}
              style={{ padding: '8px 20px', fontSize: '0.85rem' }}
            >
              {isAdmin ? 'Dashboard' : 'Admin'}
            </button>
            <button
              className="glass-button"
              onClick={() => navigate('/login')}
              style={{ padding: '8px 20px', fontSize: '0.85rem' }}
            >
              Get Started
            </button>
          </div>
        </motion.nav>

        {/* Hero */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          justifyContent: 'center', alignItems: 'center',
          padding: '0 40px', textAlign: 'center', maxWidth: '900px', margin: '0 auto',
        }}>
          <motion.div custom={0} variants={fadeUp} initial="hidden" animate="visible"
            style={{ marginBottom: '16px' }}
          >
            <span style={{
              display: 'inline-block',
              padding: '6px 16px', borderRadius: '100px',
              background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)',
              color: '#818cf8', fontSize: '0.8rem', fontWeight: 600, letterSpacing: '1px',
              textTransform: 'uppercase',
            }}>
              Multi-Agent RAG Platform
            </span>
          </motion.div>

          <motion.h1 custom={1} variants={fadeUp} initial="hidden" animate="visible"
            style={{
              fontSize: 'clamp(2.5rem, 5vw, 4rem)', fontWeight: 800,
              lineHeight: 1.1, letterSpacing: '-1.5px', marginBottom: '20px',
            }}
          >
            Intelligent Academic
            <br />
            <span style={{
              background: 'linear-gradient(135deg, #6366f1, #14b8a6)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>
              Data Assistant
            </span>
          </motion.h1>

          <motion.p custom={2} variants={fadeUp} initial="hidden" animate="visible"
            style={{
              fontSize: '1.15rem', color: '#94a3b8', lineHeight: 1.7,
              maxWidth: '600px', marginBottom: '36px',
            }}
          >
            Query academic databases with natural language. Six specialized AI agents
            collaborate to classify, retrieve, validate, and synthesize answers in real time.
          </motion.p>

          <motion.div custom={3} variants={fadeUp} initial="hidden" animate="visible"
            style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', justifyContent: 'center' }}
          >
            <button className="glass-button" onClick={() => navigate('/login')}
              style={{ padding: '14px 36px', fontSize: '1.05rem', borderRadius: '14px' }}
            >
              Launch Nexus
            </button>
            <button className="glass-button secondary" onClick={() => navigate(isAdmin ? '/dashboard' : '/login')}
              style={{ padding: '14px 28px', fontSize: '1.05rem', borderRadius: '14px' }}
            >
              View Dashboard
            </button>
          </motion.div>
        </div>

        {/* Agent pipeline strip */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8, duration: 0.7 }}
          style={{
            padding: '30px 40px 40px', display: 'flex',
            justifyContent: 'center', gap: '12px', flexWrap: 'wrap',
          }}
        >
          {agents.map((name, i) => (
            <motion.div
              key={name}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 1 + i * 0.1, duration: 0.4 }}
              style={{
                padding: '10px 18px', borderRadius: '10px',
                background: 'rgba(99,102,241,0.06)',
                border: '1px solid rgba(99,102,241,0.15)',
                color: '#94a3b8', fontSize: '0.82rem', fontWeight: 500,
                display: 'flex', alignItems: 'center', gap: '6px',
              }}
            >
              <span style={{ color: '#14b8a6', fontSize: '0.7rem' }}>{i + 1}</span>
              {name}
              {i < agents.length - 1 && (
                <span style={{ color: '#4b5563', marginLeft: '4px' }}>&rarr;</span>
              )}
            </motion.div>
          ))}
        </motion.div>
      </div>
    </div>
  );
}

export default Home;
