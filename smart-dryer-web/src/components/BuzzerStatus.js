'use client';

// src/components/BuzzerStatus.js — Last buzzer event + UV relay status
export default function BuzzerStatus({ status }) {
  const patterns = {
    drying_complete: { icon: '🔔', label: 'DRYING COMPLETE', color: 'var(--dry)', glow: 'var(--glow-dry)' },
    error:           { icon: '⚠', label: 'ERROR ALERT',      color: 'var(--danger)', glow: 'var(--glow-danger)' },
    alert:           { icon: '📢', label: 'SYSTEM ALERT',     color: 'var(--accent)', glow: 'var(--glow)' },
  };

  const event  = status?.buzzer_last;
  const p      = patterns[event] || null;
  const uvOn   = status?.uv_on === true;

  function formatTime(ts) {
    if (!ts) return '—';
    try {
      const d = ts?.toDate ? ts.toDate() : new Date(ts);
      return d.toLocaleTimeString('en-US', { hour12: false });
    } catch { return '—'; }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

      {/* Last buzzer event */}
      <div style={{
        ...styles.eventBox,
        borderColor: p ? p.color : 'var(--border)',
        boxShadow: p ? p.glow : 'none',
      }}>
        <span style={styles.eventIcon}>{p ? p.icon : '🔕'}</span>
        <div style={styles.eventInfo}>
          <span style={{ ...styles.eventLabel, color: p ? p.color : 'var(--text-dim)' }}>
            {p ? p.label : 'NO EVENTS YET'}
          </span>
          <span style={styles.eventTime}>
            {formatTime(status?.buzzer_last_at)}
          </span>
        </div>
      </div>

      {/* Pattern legend */}
      <div style={styles.legend}>
        {Object.entries(patterns).map(([key, val]) => (
          <div key={key} style={styles.legendRow}>
            <span style={styles.legendIcon}>{val.icon}</span>
            <span style={{ ...styles.legendLabel, color: val.color }}>{val.label}</span>
            <span style={styles.legendDesc}>
              {key === 'drying_complete' ? '3-tone ascending chime' :
               key === 'error'           ? '3 rapid low beeps' :
                                           'Single short beep'}
            </span>
          </div>
        ))}
      </div>

      {/* UV Relay live status */}
      <div style={{ ...styles.uvBox, borderColor: uvOn ? '#a259ff' : 'var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{
            width: '10px', height: '10px',
            borderRadius: '50%',
            background: uvOn ? '#a259ff' : 'var(--text-dim)',
            boxShadow: uvOn ? '0 0 10px #a259ff' : 'none',
            display: 'inline-block',
            transition: 'all 0.3s',
          }} />
          <span style={{ fontFamily: 'var(--mono)', fontSize: '11px', letterSpacing: '2px' }}>
            UV STERILIZATION: <strong style={{ color: uvOn ? '#a259ff' : 'var(--text-dim)' }}>
              {uvOn ? 'ACTIVE' : 'OFF'}
            </strong>
          </span>
        </div>
        <span style={styles.uvNote}>
          {uvOn ? 'Active during idle interval between scans' : 'Disabled during active scan cycle'}
        </span>
      </div>
    </div>
  );
}

const styles = {
  eventBox: {
    background: '#0d1015',
    border: '1px solid var(--border)',
    borderRadius: '4px',
    padding: '14px 16px',
    display: 'flex', alignItems: 'center', gap: '14px',
    transition: 'all 0.3s ease',
  },
  eventIcon: { fontSize: '28px', lineHeight: 1, flexShrink: 0 },
  eventInfo: { display: 'flex', flexDirection: 'column', gap: '4px' },
  eventLabel: {
    fontFamily: 'var(--sans)',
    fontSize: '13px', fontWeight: 900,
    letterSpacing: '3px', textTransform: 'uppercase',
  },
  eventTime: {
    fontFamily: 'var(--mono)',
    fontSize: '11px', color: 'var(--text-dim)',
    letterSpacing: '1px',
  },
  legend: {
    display: 'flex', flexDirection: 'column', gap: '6px',
  },
  legendRow: {
    display: 'grid',
    gridTemplateColumns: '24px 160px 1fr',
    alignItems: 'center',
    gap: '8px',
    padding: '6px 10px',
    background: '#0d1015',
    borderRadius: '3px',
    border: '1px solid var(--border)',
  },
  legendIcon: { fontSize: '14px', textAlign: 'center' },
  legendLabel: {
    fontFamily: 'var(--mono)',
    fontSize: '10px', letterSpacing: '1px',
    fontWeight: 700,
  },
  legendDesc: {
    fontFamily: 'var(--mono)',
    fontSize: '10px', color: 'var(--text-dim)',
    letterSpacing: '0.5px',
  },
  uvBox: {
    border: '1px solid var(--border)',
    borderRadius: '4px',
    padding: '14px 16px',
    display: 'flex', flexDirection: 'column', gap: '6px',
    transition: 'border-color 0.3s',
  },
  uvNote: {
    fontFamily: 'var(--mono)',
    fontSize: '9px', color: 'var(--text-dim)',
    letterSpacing: '0.5px', lineHeight: 1.5,
  },
};
