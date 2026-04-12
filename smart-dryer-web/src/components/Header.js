'use client';

// src/components/Header.js
import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth-context';
import { useRouter } from 'next/navigation';

export default function Header({ status }) {
  const { signOut } = useAuth();
  const router = useRouter();
  const [clock, setClock] = useState('--:--:--');

  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString('en-US', { hour12: false }));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);

  async function handleSignOut() {
    await signOut();
    router.replace('/login');
  }

  const sysStatus = status?.system_status || 'idle';

  return (
    <header style={styles.header}>
      <div style={styles.logo}>
        <div style={styles.logoIcon}>
          <svg viewBox="0 0 24 24" fill="none" stroke="#00e5ff" strokeWidth="2" width="20" height="20">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 7v5l3 3" />
            <path d="M7 12c0-2.76 2.24-5 5-5" />
          </svg>
        </div>
        <h1 style={styles.title}>
          SMART <span style={{ color: 'var(--accent)' }}>DRYER</span>
        </h1>
        <span style={styles.version}>v2.0 · RPI</span>
      </div>

      <div style={styles.right}>
        <div style={styles.uvIndicator}>
          <span style={{
            ...styles.uvDot,
            background: status?.uv_on ? '#a259ff' : 'var(--text-dim)',
            boxShadow: status?.uv_on ? '0 0 8px #a259ff' : 'none',
          }} />
          <span style={styles.uvLabel}>UV {status?.uv_on ? 'ON' : 'OFF'}</span>
        </div>

        <div className={`sys-badge ${sysStatus}`}>
          ● {sysStatus.toUpperCase()}
        </div>

        <div style={styles.clock}>{clock}</div>

        <button
          id="header-signout"
          onClick={handleSignOut}
          className="btn btn-sm"
          style={{ fontSize: '10px', letterSpacing: '2px' }}
        >
          SIGN OUT
        </button>
      </div>
    </header>
  );
}

const styles = {
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '14px 32px',
    borderBottom: '1px solid var(--border)',
    background: 'var(--panel)',
    position: 'sticky',
    top: 0,
    zIndex: 100,
  },
  logo: { display: 'flex', alignItems: 'center', gap: '14px' },
  logoIcon: {
    width: '36px', height: '36px',
    border: '2px solid var(--accent)',
    borderRadius: '4px',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    boxShadow: 'var(--glow)',
  },
  title: {
    fontSize: '20px', fontWeight: 900, letterSpacing: '4px',
    fontFamily: 'var(--sans)', color: '#fff',
  },
  version: {
    fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--text-dim)',
    letterSpacing: '2px', marginLeft: '4px',
  },
  right: { display: 'flex', alignItems: 'center', gap: '20px' },
  uvIndicator: { display: 'flex', alignItems: 'center', gap: '6px' },
  uvDot: {
    width: '8px', height: '8px', borderRadius: '50%',
    display: 'inline-block', transition: 'all 0.3s ease',
  },
  uvLabel: {
    fontFamily: 'var(--mono)', fontSize: '10px',
    color: 'var(--text-dim)', letterSpacing: '2px',
  },
  clock: {
    fontFamily: 'var(--mono)', fontSize: '13px',
    color: 'var(--text-dim)', letterSpacing: '1px',
  },
};
