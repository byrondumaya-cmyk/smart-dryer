'use client';

// src/components/ScanControl.js — Start/Stop + interval slider
import { useState, useEffect } from 'react';
import { sendCommand, updateConfig } from '@/lib/firestore';
import { toast } from './Toast';

export default function ScanControl({ status, config }) {
  const [interval, setInterval_]  = useState(300);
  const [busy, setBusy]           = useState(false);

  const isRunning = status?.running === true;

  useEffect(() => {
    if (config?.scan_interval) setInterval_(config.scan_interval);
  }, [config?.scan_interval]);

  async function toggleScan() {
    setBusy(true);
    try {
      const cmd = isRunning ? 'scan_stop' : 'scan_start';
      await sendCommand(cmd);
      toast(`Command sent: ${cmd.replace('_', ' ').toUpperCase()}`, 'ok');
    } catch {
      toast('Failed to send command', 'err');
    } finally {
      setBusy(false);
    }
  }

  async function saveInterval(val) {
    const seconds = parseInt(val);
    await updateConfig({ scan_interval: seconds });
    toast(`Scan interval set to ${fmtInterval(seconds)}`, 'ok');
  }

  function fmtInterval(s) {
    const m = Math.floor(s / 60);
    const r = s % 60;
    return r ? `${m}m ${r}s` : `${m} min`;
  }

  function sliderPct(val) {
    return ((val - 60) / (3600 - 60)) * 100;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Big start/stop button */}
      <button
        id="scan-toggle-btn"
        onClick={toggleScan}
        disabled={busy}
        className={`btn btn-full ${isRunning ? 'btn-danger' : 'btn-primary'}`}
        style={{ padding: '16px', fontSize: '15px', letterSpacing: '4px' }}
      >
        {busy ? '· · ·' : isRunning ? '■ STOP SCAN' : '▶ START SCAN'}
      </button>

      {/* Last cycle */}
      {status?.last_cycle_at && (
        <div style={styles.lastCycle}>
          <span style={styles.label}>LAST CYCLE</span>
          <span style={styles.mono}>
            {(() => {
              try {
                const d = status.last_cycle_at?.toDate
                  ? status.last_cycle_at.toDate()
                  : new Date(status.last_cycle_at);
                return d.toLocaleTimeString('en-US', { hour12: false });
              } catch { return '—'; }
            })()}
          </span>
        </div>
      )}

      {/* All-dry notification status */}
      {status?.all_dry_notified && (
        <div style={styles.allDryBadge}>
          ✅ All slots DRY — SMS sent!
        </div>
      )}

      {/* Interval slider */}
      <div>
        <div style={styles.sliderRow}>
          <span style={styles.label}>SCAN INTERVAL</span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: '14px', color: 'var(--accent)' }}>
            {fmtInterval(interval)}
          </span>
        </div>
        <div style={styles.sliderBounds}>
          <span>1 MIN</span>
          <span>60 MIN</span>
        </div>
        <input
          id="scan-interval-slider"
          type="range"
          min="60" max="3600" step="60"
          value={interval}
          onChange={e => setInterval_(Number(e.target.value))}
          onMouseUp={e => saveInterval(e.target.value)}
          onTouchEnd={e => saveInterval(e.target.value)}
          style={{ '--fill': `${sliderPct(interval)}%` }}
        />
      </div>
    </div>
  );
}

const styles = {
  lastCycle: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    background: '#0d1015',
    border: '1px solid var(--border)',
    borderRadius: '4px',
    padding: '10px 14px',
  },
  label: {
    fontFamily: 'var(--sans)', fontSize: '9px',
    fontWeight: 700, letterSpacing: '3px',
    color: 'var(--text-dim)', textTransform: 'uppercase',
  },
  mono: { fontFamily: 'var(--mono)', fontSize: '13px', color: 'var(--accent)' },
  allDryBadge: {
    background: 'rgba(0,230,118,0.08)',
    border: '1px solid rgba(0,230,118,0.3)',
    borderRadius: '4px',
    padding: '10px 14px',
    fontFamily: 'var(--mono)',
    fontSize: '11px', color: 'var(--dry)',
    letterSpacing: '1px', textAlign: 'center',
  },
  sliderRow: {
    display: 'flex', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: '8px',
  },
  sliderBounds: {
    display: 'flex', justifyContent: 'space-between',
    fontFamily: 'var(--mono)', fontSize: '9px',
    color: 'var(--text-dim)', letterSpacing: '1px',
    marginBottom: '8px',
  },
};
