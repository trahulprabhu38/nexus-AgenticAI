import React from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Stars, Text } from '@react-three/drei';
import { useNavigate } from 'react-router-dom';



function Home() {
  const navigate = useNavigate();
  const user = typeof window !== 'undefined' ? JSON.parse(localStorage.getItem('user') || 'null') : null;
  const isAdmin = Boolean(user && user.role === 'admin');

  return (
    <div className="glass-container" style={{ position: 'relative', overflow: 'hidden' }}>
      <Canvas style={{ height: '100%', position: 'absolute', top: 0, left: 0 }}>
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} />
        <Stars radius={300} depth={60} count={20000} factor={7} saturation={0} fade />
        <OrbitControls enableZoom={false} enablePan={false} />
        <Text
          fontSize={0.8}
          color="white"
          anchorX="center"
          anchorY="middle"
          position={[0, 0, 0]}
          font="https://fonts.gstatic.com/s/outfit/v11/QGYsz_MVcBeNP4NJtEtq.woff2"
        >
          AIML NEXUS
        </Text>
      </Canvas>

      {/* Top Logos */}
      <div style={{ position: 'absolute', top: '24px', left: '24px', zIndex: 10 }}>
        <img src="/logo1.png" alt="DSCE Logo" style={{ width: '100px', filter: 'drop-shadow(0 4px 12px rgba(0,0,0,0.5))' }} />
      </div>
      <div style={{ position: 'absolute', top: '24px', right: '24px', zIndex: 10 }}>
        <img src="/logo2.png" alt="Tech Team" style={{ width: '140px', filter: 'drop-shadow(0 4px 12px rgba(0,0,0,0.5))' }} />
      </div>

      {/* Central Action */}
      <div style={{
        position: 'absolute',
        bottom: '15%',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 10,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '24px'
      }}>
        <p style={{ 
          color: 'var(--text-dim)', 
          fontSize: '1.2rem', 
          fontWeight: 300, 
          letterSpacing: '2px',
          textTransform: 'uppercase'
        }}>
          Revolutionizing Academic Insights
        </p>
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', justifyContent: 'center' }}>
          <button
            onClick={() => navigate('/login')}
            className="glass-button"
            style={{ 
              padding: '18px 48px', 
              fontSize: '1.4rem', 
              borderRadius: '40px',
              background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
              boxShadow: '0 8px 32px rgba(59, 130, 246, 0.4)'
            }}
          >
            EXPLORE NOW
          </button>
          <button
            onClick={() => navigate(isAdmin ? '/dashboard' : '/login')}
            className="glass-button"
            style={{ 
              padding: '18px 18px', 
              fontSize: '1rem', 
              borderRadius: '40px',
              background: 'rgba(255,255,255,0.12)',
              border: '1px solid rgba(255,255,255,0.18)'
            }}
          >
            {isAdmin ? 'ADMIN DASHBOARD' : 'ADMIN LOGIN'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default Home;
