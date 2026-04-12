'use client';

// src/components/SlotGrid.js — 5-slot status cards with snapshot modal
import { useState } from 'react';

const SLOT_LABELS = { 1: 'Slot 1', 2: 'Slot 2', 3: 'Slot 3', 4: 'Slot 4', 5: 'Slot 5' };

export default function SlotGrid({ slots, currentSlot }) {
  const [modal, setModal] = useState(null); // { slot, url, label }

  function getSlotClass(slot, data) {
    if (currentSlot === slot) return 'scanning';
    if (!data?.label) return '';
    return data.label === 'DRY' ? 'dry' : 'wet';
  }

  function formatTime(ts) {
    if (!ts) return '—';
    try {
      const d = ts?.toDate ? ts.toDate() : new Date(ts);
      return d.toLocaleTimeString('en-US', { hour12: false });
    } catch { return '—'; }
  }

  return (
    <>
      <div style={styles.grid}>
        {[1, 2, 3, 4, 5].map((slot) => {
          const data = slots?.[String(slot)] || {};
          const cls  = getSlotClass(slot, data);
          const isScanning = currentSlot === slot;

          return (
            <div
              key={slot}
              id={`slot-card-${slot}`}
              className={`slot-card ${cls}`}
              onClick={() => data.snapshot_url && setModal({ slot, url: data.snapshot_url, label: data.label })}
              style={{ cursor: data.snapshot_url ? 'pointer' : 'default' }}
            >
              {/* Slot number */}
              <span style={styles.slotNum}>SLOT {slot}</span>

              {/* Icon */}
              <span style={styles.icon}>
                {isScanning ? '⟳' : data.label === 'DRY' ? '☀' : data.label === 'WET' ? '💧' : '◌'}
              </span>

              {/* Label */}
              <span style={{
                ...styles.label,
                color: isScanning        ? 'var(--accent)'
                      : data.label==='DRY' ? 'var(--dry)'
                      : data.label==='WET' ? 'var(--wet)'
                      : 'var(--text-dim)',
              }}>
                {isScanning ? 'SCANNING' : data.label || '—'}
              </span>

              {/* Confidence */}
              <span style={styles.conf}>
                {!isScanning && data.confidence != null
                  ? `${(data.confidence * 100).toFixed(1)}%`
                  : ''}
              </span>

              {/* Last scanned */}
              <span style={styles.time}>{formatTime(data.last_scanned)}</span>

              {/* Snapshot indicator */}
              {data.snapshot_url && !isScanning && (
                <span style={styles.snapBadge}>📷 VIEW</span>
              )}

              {/* Simulated flag */}
              {data.simulated && (
                <span style={styles.simBadge}>SIM</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Snapshot modal */}
      {modal && (
        <div style={styles.overlay} onClick={() => setModal(null)}>
          <div style={styles.modalCard} onClick={e => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <span style={styles.modalTitle}>
                SLOT {modal.slot} — LAST SCAN SNAPSHOT
              </span>
              <button
                style={styles.modalClose}
                onClick={() => setModal(null)}
              >✕</button>
            </div>
            <div style={styles.modalBody}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={modal.url}
                alt={`Slot ${modal.slot} snapshot`}
                style={styles.snapImage}
              />
              <div style={styles.snapLabel}>
                <span style={{
                  color: modal.label === 'DRY' ? 'var(--dry)' : 'var(--wet)',
                  fontFamily: 'var(--mono)',
                  letterSpacing: '3px',
                  fontSize: '14px',
                  fontWeight: 700,
                }}>
                  ● {modal.label || 'UNKNOWN'}
                </span>
                <span style={{ color: 'var(--text-dim)', fontSize: '11px', fontFamily: 'var(--mono)' }}>
                  Captured during last scan cycle
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

const styles = {
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(5, 1fr)',
    gap: '12px',
  },
  slotNum: {
    fontFamily: 'var(--mono)',
    fontSize: '10px',
    color: 'var(--text-dim)',
    letterSpacing: '2px',
  },
  icon: { fontSize: '32px', lineHeight: 1 },
  label: {
    fontFamily: 'var(--sans)',
    fontSize: '13px', fontWeight: 900,
    letterSpacing: '3px', textTransform: 'uppercase',
  },
  conf: {
    fontFamily: 'var(--mono)',
    fontSize: '10px', color: 'var(--text-dim)',
  },
  time: {
    fontFamily: 'var(--mono)',
    fontSize: '9px', color: 'var(--text-dim)',
    letterSpacing: '1px',
  },
  snapBadge: {
    fontSize: '9px',
    fontFamily: 'var(--mono)',
    color: 'var(--accent)',
    letterSpacing: '1px',
    backgroundColor: 'rgba(0,229,255,0.08)',
    padding: '2px 6px',
    borderRadius: '2px',
    border: '1px solid rgba(0,229,255,0.2)',
  },
  simBadge: {
    position: 'absolute',
    top: '6px', right: '6px',
    fontSize: '8px', letterSpacing: '1px',
    fontFamily: 'var(--mono)',
    color: 'var(--warn)',
    background: 'rgba(255,171,0,0.1)',
    border: '1px solid rgba(255,171,0,0.3)',
    padding: '1px 4px', borderRadius: '2px',
  },
  overlay: {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,0.8)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 500,
    backdropFilter: 'blur(4px)',
  },
  modalCard: {
    background: 'var(--panel)',
    border: '1px solid var(--border2)',
    borderRadius: '8px',
    width: '90%', maxWidth: '520px',
    overflow: 'hidden',
    boxShadow: '0 20px 60px rgba(0,0,0,0.7)',
  },
  modalHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '16px 20px',
    borderBottom: '1px solid var(--border)',
  },
  modalTitle: {
    fontFamily: 'var(--mono)', fontSize: '11px',
    letterSpacing: '3px', color: 'var(--accent)',
  },
  modalClose: {
    background: 'none', border: 'none',
    color: 'var(--text-dim)', cursor: 'pointer',
    fontSize: '16px', padding: '0 4px',
  },
  modalBody: { padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' },
  snapImage: {
    width: '100%', borderRadius: '4px',
    border: '1px solid var(--border)',
    background: '#000',
  },
  snapLabel: {
    display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center',
  },
};
