'use client';

// src/app/dashboard/page.js — Protected main dashboard
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import {
  subscribeToStatus, subscribeToConfig,
  subscribeToSensors, subscribeToSlots,
  subscribeScanHistory,
} from '@/lib/firestore';

import Header       from '@/components/Header';
import SlotGrid     from '@/components/SlotGrid';
import SensorPanel  from '@/components/SensorPanel';
import ScanControl  from '@/components/ScanControl';
import SmsPanel     from '@/components/SmsPanel';
import MotorCalibration  from '@/components/MotorCalibration';
import BuzzerStatus from '@/components/BuzzerStatus';
import ScanHistory  from '@/components/ScanHistory';
import Toast        from '@/components/Toast';

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [status,  setStatus]  = useState(null);
  const [config,  setConfig]  = useState(null);
  const [sensors, setSensors] = useState(null);
  const [slots,   setSlots]   = useState(null);
  const [history, setHistory] = useState([]);

  // Auth guard
  useEffect(() => {
    if (!loading && !user) router.replace('/login');
  }, [user, loading, router]);

  // Firestore real-time subscriptions
  useEffect(() => {
    if (!user) return;
    const unsubs = [
      subscribeToStatus(setStatus),
      subscribeToConfig(setConfig),
      subscribeToSensors(setSensors),
      subscribeToSlots(setSlots),
      subscribeScanHistory(setHistory, 50),
    ];
    return () => unsubs.forEach(u => u());
  }, [user]);

  if (loading || !user) {
    return (
      <div style={styles.loading}>
        <span>AUTHENTICATING...</span>
      </div>
    );
  }

  const currentSlot = status?.current_slot ?? null;

  return (
    <>
      <Header status={status} />

      <main style={styles.main}>

        {/* ── Row 1: Slot grid (full width) ──────────────────────────── */}
        <section style={styles.fullRow}>
          <div className="panel">
            <div className="panel-title">Slot Status — YOLO ML Classification</div>
            <SlotGrid slots={slots} currentSlot={currentSlot} />
          </div>
        </section>

        {/* ── Row 2: Left main + Right sidebar ───────────────────────── */}
        <div style={styles.contentGrid}>

          {/* LEFT COLUMN */}
          <div style={styles.leftCol}>

            {/* Sensor readings */}
            <div className="panel">
              <div className="panel-title">Environment — DHT Sensor Array (5 Slots)</div>
              <SensorPanel sensors={sensors} />
            </div>

            {/* Motor calibration */}
            <div className="panel">
              <div className="panel-title">Motor Calibration — Slot Gap (L298N)</div>
              <MotorCalibration config={config} />
            </div>

            {/* Scan history */}
            <div className="panel">
              <div className="panel-title">Scan History</div>
              <ScanHistory history={history} />
            </div>

          </div>

          {/* RIGHT SIDEBAR */}
          <div style={styles.sidebar}>

            {/* Scan control */}
            <div className="panel">
              <div className="panel-title">Scan Control</div>
              <ScanControl status={status} config={config} />
            </div>

            {/* SMS Alert */}
            <div className="panel">
              <div className="panel-title">SMS Alert — Semaphore</div>
              <SmsPanel config={config} />
            </div>

            {/* Buzzer + UV */}
            <div className="panel">
              <div className="panel-title">Buzzer & UV Status</div>
              <BuzzerStatus status={status} />
            </div>

            {/* Connection status */}
            <div style={styles.connPanel}>
              <div style={styles.connRow}>
                <span style={styles.connDot} />
                <span style={styles.connLabel}>FIRESTORE LIVE</span>
              </div>
              <div style={styles.connRow}>
                <span style={{
                  ...styles.connDot,
                  background: status ? 'var(--dry)' : 'var(--text-dim)',
                  boxShadow: status ? 'var(--glow-dry)' : 'none',
                }} />
                <span style={styles.connLabel}>
                  RPI {status ? 'ONLINE' : 'OFFLINE / NO DATA'}
                </span>
              </div>
            </div>

          </div>
        </div>
      </main>

      <Toast />
    </>
  );
}

const styles = {
  loading: {
    minHeight: '100vh',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontFamily: 'var(--mono)', color: 'var(--accent)',
    letterSpacing: '3px', fontSize: '12px',
  },
  main: {
    display: 'flex', flexDirection: 'column', gap: '16px',
    padding: '20px 32px',
    maxWidth: '1400px',
    margin: '0 auto',
  },
  fullRow: { width: '100%' },
  contentGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 320px',
    gap: '16px',
    alignItems: 'start',
  },
  leftCol: { display: 'flex', flexDirection: 'column', gap: '16px' },
  sidebar: { display: 'flex', flexDirection: 'column', gap: '16px' },
  connPanel: {
    background: 'var(--panel)',
    border: '1px solid var(--border)',
    borderRadius: '4px',
    padding: '14px 16px',
    display: 'flex', flexDirection: 'column', gap: '8px',
  },
  connRow: { display: 'flex', alignItems: 'center', gap: '10px' },
  connDot: {
    width: '8px', height: '8px', borderRadius: '50%',
    background: 'var(--dry)',
    boxShadow: 'var(--glow-dry)',
    display: 'inline-block',
    animation: 'pulse-dot 2s ease-in-out infinite',
    flexShrink: 0,
  },
  connLabel: {
    fontFamily: 'var(--mono)',
    fontSize: '10px', color: 'var(--text-dim)',
    letterSpacing: '2px', textTransform: 'uppercase',
  },
};
