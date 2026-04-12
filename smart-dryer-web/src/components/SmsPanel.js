'use client';

// src/components/SmsPanel.js — Recipient input + Test SMS (via Firestore command)
import { useState, useEffect } from 'react';
import { sendCommand, updateConfig } from '@/lib/firestore';
import { toast } from './Toast';

export default function SmsPanel({ config }) {
  const [number, setNumber] = useState('');
  const [busy, setBusy]     = useState(false);

  useEffect(() => {
    if (config?.sms_recipient) setNumber(config.sms_recipient);
  }, [config?.sms_recipient]);

  async function saveNumber() {
    const n = number.trim();
    if (!n) return toast('Enter a phone number first', 'err');
    try {
      await updateConfig({ sms_recipient: n });
      // Also send a command so RPI updates its in-memory state
      await sendCommand('update_sms_recipient', { number: n });
      toast('Number saved — RPI will sync shortly', 'ok');
    } catch {
      toast('Failed to save number', 'err');
    }
  }

  async function testSms() {
    const n = number.trim();
    if (!n) return toast('Enter a phone number first', 'err');
    setBusy(true);
    try {
      await sendCommand('sms_test', { number: n });
      toast('Test SMS command sent — RPI will dispatch via Semaphore', 'ok');
    } catch {
      toast('Failed to send command', 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Info note */}
      <div style={styles.note}>
        <span style={styles.noteText}>
          📡 SMS is sent by the Raspberry Pi via Semaphore. Your API key never leaves the device.
        </span>
      </div>

      {/* Phone number input */}
      <div className="input-group" style={{ marginBottom: 0 }}>
        <label>Recipient Number</label>
        <div className="input-row">
          <input
            id="sms-number-input"
            type="tel"
            value={number}
            onChange={e => setNumber(e.target.value)}
            placeholder="+639XXXXXXXXX"
          />
          <button
            id="sms-save-btn"
            onClick={saveNumber}
            className="btn btn-sm accent"
            style={{ whiteSpace: 'nowrap' }}
          >
            SAVE
          </button>
        </div>
      </div>

      {/* Test SMS button */}
      <button
        id="sms-test-btn"
        onClick={testSms}
        disabled={busy}
        className="btn btn-sm btn-full"
        style={{ padding: '10px', fontSize: '11px', letterSpacing: '3px' }}
      >
        {busy ? '· · ·' : '📨 SEND TEST SMS'}
      </button>

      {/* Trigger condition info */}
      <div style={styles.triggerInfo}>
        <span style={styles.triggerLabel}>AUTO-TRIGGER</span>
        <span style={styles.triggerVal}>When ALL 5 slots DRY</span>
      </div>
    </div>
  );
}

const styles = {
  note: {
    background: 'rgba(0,229,255,0.04)',
    border: '1px solid rgba(0,229,255,0.15)',
    borderRadius: '4px',
    padding: '10px 12px',
  },
  noteText: {
    fontFamily: 'var(--mono)',
    fontSize: '10px', color: 'var(--text-dim)',
    lineHeight: 1.6, letterSpacing: '0.5px',
  },
  triggerInfo: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    background: '#0d1015',
    border: '1px solid var(--border)',
    borderRadius: '4px',
    padding: '10px 14px',
  },
  triggerLabel: {
    fontFamily: 'var(--sans)', fontSize: '9px',
    fontWeight: 700, letterSpacing: '3px',
    color: 'var(--text-dim)', textTransform: 'uppercase',
  },
  triggerVal: {
    fontFamily: 'var(--mono)', fontSize: '11px',
    color: 'var(--dry)', letterSpacing: '1px',
  },
};
