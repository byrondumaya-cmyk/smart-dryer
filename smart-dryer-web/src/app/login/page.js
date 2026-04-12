'use client';

// src/app/login/page.js — Firebase Email/Password Login
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';

export default function LoginPage() {
  const { signIn } = useAuth();
  const router = useRouter();

  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await signIn(email, password);
      router.replace('/dashboard');
    } catch (err) {
      setError(parseFirebaseError(err.code));
    } finally {
      setLoading(false);
    }
  }

  function parseFirebaseError(code) {
    const map = {
      'auth/user-not-found':      'No account found with this email.',
      'auth/wrong-password':      'Incorrect password.',
      'auth/invalid-email':       'Invalid email address.',
      'auth/too-many-requests':   'Too many attempts. Try again later.',
      'auth/invalid-credential':  'Invalid email or password.',
    };
    return map[code] || 'Login failed. Please try again.';
  }

  return (
    <div style={styles.page}>
      {/* Animated bg grid */}
      <div style={styles.grid} />

      <div style={styles.card}>
        {/* Logo */}
        <div style={styles.logo}>
          <div style={styles.logoIcon}>
            <svg viewBox="0 0 24 24" fill="none" stroke="#00e5ff" strokeWidth="2" width="24" height="24">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 7v5l3 3" />
              <path d="M7 12c0-2.76 2.24-5 5-5" />
            </svg>
          </div>
          <div>
            <h1 style={styles.title}>SMART<span style={{ color: 'var(--accent)' }}> DRYER</span></h1>
            <p style={styles.subtitle}>CONTROL SYSTEM</p>
          </div>
        </div>

        <p style={styles.label}>SIGN IN TO CONTINUE</p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <div className="input-group">
            <label>Email Address</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="admin@example.com"
              required
              autoComplete="email"
            />
          </div>

          <div className="input-group">
            <label>Password</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div style={styles.errorBox}>
              <span style={{ color: 'var(--danger)', fontSize: '12px', fontFamily: 'var(--mono)' }}>
                ⚠ {error}
              </span>
            </div>
          )}

          <button
            id="login-submit"
            type="submit"
            className="btn btn-primary btn-full"
            disabled={loading}
            style={{ marginTop: '8px', fontSize: '13px', letterSpacing: '4px' }}
          >
            {loading ? 'AUTHENTICATING...' : '→ SIGN IN'}
          </button>
        </form>

        <p style={styles.footer}>
          Smart Drying Rack System · Raspberry Pi Control
        </p>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'var(--bg)',
    position: 'relative',
    overflow: 'hidden',
    padding: '20px',
  },
  grid: {
    position: 'absolute',
    inset: 0,
    backgroundImage: `
      linear-gradient(rgba(0,229,255,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,229,255,0.03) 1px, transparent 1px)
    `,
    backgroundSize: '40px 40px',
    pointerEvents: 'none',
  },
  card: {
    position: 'relative',
    background: 'var(--panel)',
    border: '1px solid var(--border2)',
    borderRadius: '8px',
    padding: '40px',
    width: '100%',
    maxWidth: '420px',
    boxShadow: '0 0 60px rgba(0,229,255,0.08), 0 20px 60px rgba(0,0,0,0.6)',
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    marginBottom: '32px',
  },
  logoIcon: {
    width: '48px', height: '48px',
    border: '2px solid var(--accent)',
    borderRadius: '6px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0 0 20px rgba(0,229,255,0.2)',
    flexShrink: 0,
  },
  title: {
    fontSize: '24px',
    fontWeight: 900,
    letterSpacing: '4px',
    color: '#fff',
    fontFamily: 'var(--sans)',
  },
  subtitle: {
    fontSize: '9px',
    letterSpacing: '5px',
    color: 'var(--text-dim)',
    fontFamily: 'var(--mono)',
    marginTop: '3px',
  },
  label: {
    fontSize: '10px',
    letterSpacing: '4px',
    color: 'var(--text-dim)',
    fontFamily: 'var(--mono)',
    marginBottom: '24px',
    paddingBottom: '16px',
    borderBottom: '1px solid var(--border)',
  },
  form: { display: 'flex', flexDirection: 'column', gap: '4px' },
  errorBox: {
    background: 'rgba(255,23,68,0.05)',
    border: '1px solid rgba(255,23,68,0.3)',
    borderRadius: '4px',
    padding: '10px 12px',
    marginTop: '4px',
  },
  footer: {
    marginTop: '28px',
    fontSize: '9px',
    letterSpacing: '2px',
    color: 'var(--text-dim)',
    fontFamily: 'var(--mono)',
    textAlign: 'center',
  },
};
