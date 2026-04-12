'use client';

// src/components/Toast.js — Global toast notification system
import { useState, useEffect, useCallback } from 'react';

let _setToast = null;

export function toast(message, type = '') {
  if (_setToast) _setToast({ message, type, id: Date.now() });
}

export default function Toast() {
  const [current, setCurrent] = useState(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => { _setToast = setCurrent; return () => { _setToast = null; }; }, []);

  useEffect(() => {
    if (!current) return;
    setVisible(true);
    const t = setTimeout(() => setVisible(false), 2800);
    return () => clearTimeout(t);
  }, [current]);

  if (!current) return null;

  const borderColor = current.type === 'ok'  ? 'var(--dry)'
                    : current.type === 'err' ? 'var(--danger)'
                    : current.type === 'warn'? 'var(--warn)'
                    : 'var(--accent)';

  return (
    <div style={{
      ...styles.toast,
      opacity:   visible ? 1 : 0,
      transform: visible ? 'translateY(0)' : 'translateY(8px)',
      borderLeftColor: borderColor,
    }}>
      {current.message}
    </div>
  );
}

const styles = {
  toast: {
    position: 'fixed',
    bottom: '24px', right: '24px',
    padding: '12px 20px',
    borderRadius: '3px',
    fontFamily: 'var(--mono)',
    fontSize: '12px',
    letterSpacing: '1px',
    borderLeft: '3px solid var(--accent)',
    background: 'var(--panel)',
    color: 'var(--text)',
    boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
    transition: 'all 0.3s ease',
    pointerEvents: 'none',
    zIndex: 1000,
    maxWidth: '320px',
  },
};
