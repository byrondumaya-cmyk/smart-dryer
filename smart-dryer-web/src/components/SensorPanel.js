'use client';

// src/components/SensorPanel.js — Per-slot DHT sensor readings
export default function SensorPanel({ sensors }) {
  const slots = [1, 2, 3, 4, 5];

  function avg(key) {
    const vals = slots
      .map(s => sensors?.[String(s)]?.[key])
      .filter(v => v != null && !isNaN(v));
    if (!vals.length) return null;
    return (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1);
  }

  function tempColor(t) {
    if (t == null) return 'var(--accent)';
    if (t > 38) return 'var(--danger)';
    if (t > 32) return 'var(--warn)';
    return 'var(--dry)';
  }

  function humiColor(h) {
    if (h == null) return 'var(--accent)';
    if (h > 75) return 'var(--wet)';
    if (h < 40) return 'var(--warn)';
    return 'var(--accent)';
  }

  const avgTemp = avg('temperature');
  const avgHumi = avg('humidity');

  return (
    <div>
      {/* Averages */}
      <div style={styles.avgRow}>
        <div style={styles.avgBox}>
          <span style={{ ...styles.avgVal, color: tempColor(Number(avgTemp)) }}>
            {avgTemp ?? '—'}<span style={styles.unit}>°C</span>
          </span>
          <span className="data-lbl">AVG TEMP</span>
        </div>
        <div style={styles.avgBox}>
          <span style={{ ...styles.avgVal, color: humiColor(Number(avgHumi)) }}>
            {avgHumi ?? '—'}<span style={styles.unit}>%</span>
          </span>
          <span className="data-lbl">AVG HUMIDITY</span>
        </div>
      </div>

      {/* Per-slot table */}
      <div style={styles.tableHead}>
        {['SLOT', 'SENSOR', 'TEMP', 'HUMIDITY', 'STATUS'].map(h => (
          <span key={h} style={styles.th}>{h}</span>
        ))}
      </div>

      {slots.map(slot => {
        const d = sensors?.[String(slot)] || {};
        const model = slot <= 2 || slot === 5 ? 'DHT22' : 'DHT11';
        const hasError = !!d.error;

        return (
          <div key={slot} style={styles.tableRow} id={`sensor-row-${slot}`}>
            <span style={styles.slotNum}>S{slot}</span>
            <span style={styles.model}>{model}</span>
            <span style={{ ...styles.val, color: tempColor(d.temperature) }}>
              {d.temperature != null ? `${d.temperature}°C` : '—'}
            </span>
            <span style={{ ...styles.val, color: humiColor(d.humidity) }}>
              {d.humidity != null ? `${d.humidity}%` : '—'}
            </span>
            <span style={{
              ...styles.status,
              color: hasError ? 'var(--danger)' : d.temperature != null ? 'var(--dry)' : 'var(--text-dim)',
            }}>
              {hasError ? '⚠ ERR' : d.temperature != null ? '✓ OK' : '· · ·'}
            </span>
          </div>
        );
      })}
    </div>
  );
}

const styles = {
  avgRow: {
    display: 'grid', gridTemplateColumns: '1fr 1fr',
    gap: '10px', marginBottom: '20px',
  },
  avgBox: {
    background: '#0d1015',
    border: '1px solid var(--border)',
    borderRadius: '4px',
    padding: '14px 16px',
    textAlign: 'center',
    display: 'flex', flexDirection: 'column', gap: '4px',
  },
  avgVal: {
    fontFamily: 'var(--mono)',
    fontSize: '28px', lineHeight: 1,
    fontWeight: 400,
  },
  unit: { fontSize: '14px', color: 'var(--text-dim)' },
  tableHead: {
    display: 'grid',
    gridTemplateColumns: '40px 60px 1fr 1fr 60px',
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
  tableRow: {
    display: 'grid',
    gridTemplateColumns: '40px 60px 1fr 1fr 60px',
    gap: '8px',
    alignItems: 'center',
    padding: '8px 0',
    borderBottom: '1px solid var(--border)',
  },
  slotNum: {
    fontFamily: 'var(--mono)',
    fontSize: '12px', color: 'var(--accent)',
  },
  model: {
    fontFamily: 'var(--mono)',
    fontSize: '10px', color: 'var(--text-dim)',
    letterSpacing: '1px',
  },
  val: {
    fontFamily: 'var(--mono)',
    fontSize: '13px', fontWeight: 700,
  },
  status: {
    fontFamily: 'var(--mono)',
    fontSize: '10px', letterSpacing: '1px',
  },
};
