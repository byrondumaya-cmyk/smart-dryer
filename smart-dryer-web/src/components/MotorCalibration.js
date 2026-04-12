'use client';

// src/components/MotorCalibration.js — Slot timing from home (ms)
import { useState, useEffect } from 'react';
import { sendCommand } from '@/lib/firestore';
import { toast } from './Toast';

const DEFAULT_STEPS = { 1: 0, 2: 800, 3: 1600, 4: 2400, 5: 3200 };

export default function MotorCalibration({ config }) {
  const [slots, setSlots] = useState(DEFAULT_STEPS);

  useEffect(() => {
    if (config?.slot_steps) {
      const parsed = {};
      Object.entries(config.slot_steps).forEach(([k, v]) => {
        parsed[parseInt(k)] = parseInt(v);
      });
      setSlots(s => ({ ...s, ...parsed }));
    }
  }, [config?.slot_steps]);

  function nudge(slot, delta) {
    setSlots(s => ({ ...s, [slot]: Math.max(0, (s[slot] || 0) + delta) }));
  }

  async function saveSlot(slot) {
    try {
      await sendCommand('update_config', {
        slot_steps: { [slot]: slots[slot] },
      });
      toast(`Slot ${slot} → ${slots[slot]}ms saved`, 'ok');
    } catch {
      toast('Failed to save calibration', 'err');
    }
  }

  return (
    <div>
      {/* Header row */}
      <div style={styles.headerRow}>
        {['SLOT', 'TIME FROM HOME (ms)', '', '', ''].map((h, i) => (
          <span key={i} style={styles.th}>{h}</span>
        ))}
      </div>

      {[1, 2, 3, 4, 5].map(slot => (
        <div key={slot} style={styles.row} id={`calib-row-${slot}`}>
          <span style={styles.slotLbl}>S{slot}</span>

          <input
            id={`calib-input-${slot}`}
            type="number"
            value={slots[slot] ?? 0}
            min="0" max="9999" step="10"
            onChange={e => setSlots(s => ({
              ...s, [slot]: Math.max(0, parseInt(e.target.value) || 0),
            }))}
            style={styles.input}
          />

          <button
            id={`calib-minus-${slot}`}
            onClick={() => nudge(slot, -50)}
            className="btn btn-sm"
            style={{ fontSize: '12px', padding: '7px 10px' }}
          >
            −50
          </button>
          <button
            id={`calib-plus-${slot}`}
            onClick={() => nudge(slot, 50)}
            className="btn btn-sm"
            style={{ fontSize: '12px', padding: '7px 10px' }}
          >
            +50
          </button>
          <button
            id={`calib-set-${slot}`}
            onClick={() => saveSlot(slot)}
            className="btn btn-sm accent"
            style={{ fontSize: '11px' }}
          >
            SET
          </button>
        </div>
      ))}

      {/* Help note */}
      <div style={styles.note}>
        <span style={styles.noteText}>
          ℹ Values in milliseconds from home position (slot 1 = 0ms). RPI applies on next move.
        </span>
      </div>
    </div>
  );
}

const styles = {
  headerRow: {
    display: 'grid',
    gridTemplateColumns: '40px 1fr 60px 60px 60px',
    gap: '8px',
    paddingBottom: '8px',
    borderBottom: '1px solid var(--border)',
    marginBottom: '4px',
  },
  th: {
    fontFamily: 'var(--sans)',
    fontSize: '9px', fontWeight: 700,
    letterSpacing: '2px', color: 'var(--text-dim)',
    textTransform: 'uppercase',
  },
  row: {
    display: 'grid',
    gridTemplateColumns: '40px 1fr 60px 60px 60px',
    gap: '8px',
    alignItems: 'center',
    padding: '8px 0',
    borderBottom: '1px solid var(--border)',
  },
  slotLbl: {
    fontFamily: 'var(--mono)',
    fontSize: '13px', color: 'var(--accent)',
  },
  input: {
    background: '#0d1015',
    border: '1px solid var(--border2)',
    borderRadius: '3px',
    padding: '7px 10px',
    color: 'var(--text)',
    fontFamily: 'var(--mono)',
    fontSize: '13px',
    outline: 'none',
    width: '100%',
  },
  note: {
    marginTop: '14px',
    background: 'rgba(0,229,255,0.03)',
    borderRadius: '4px',
    padding: '10px 12px',
    border: '1px solid var(--border)',
  },
  noteText: {
    fontFamily: 'var(--mono)',
    fontSize: '10px', color: 'var(--text-dim)',
    lineHeight: 1.6, letterSpacing: '0.5px',
  },
};
