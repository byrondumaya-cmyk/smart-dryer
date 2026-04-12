'use client';

// src/components/ScanHistory.js — Timeline of past scan cycles from Firestore
export default function ScanHistory({ history }) {
  const slots = [1, 2, 3, 4, 5];

  function formatTs(ts) {
    if (!ts) return '—';
    try {
      const d = ts?.toDate ? ts.toDate() : new Date(ts);
      return d.toLocaleString('en-US', {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
        hour12: false,
      });
    } catch { return '—'; }
  }

  if (!history?.length) {
    return (
      <div style={styles.empty}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: '11px', color: 'var(--text-dim)', letterSpacing: '2px' }}>
          NO SCAN HISTORY YET — START A SCAN TO BEGIN
        </span>
      </div>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>TIMESTAMP</th>
            {slots.map(s => (
              <th key={s} style={styles.th}>S{s}</th>
            ))}
            <th style={styles.th}>RESULT</th>
          </tr>
        </thead>
        <tbody>
          {history.map((entry, i) => {
            const slotData = entry.slots || {};
            const allDry = entry.all_dry;

            return (
              <tr key={entry.id || i} style={{
                ...styles.row,
                background: allDry ? 'rgba(0,230,118,0.04)' : 'transparent',
              }}>
                <td style={styles.td}>
                  <span style={styles.mono}>{formatTs(entry.timestamp)}</span>
                </td>
                {slots.map(s => {
                  const d = slotData[String(s)] || {};
                  const isDry = d.label === 'DRY';
                  const isWet = d.label === 'WET';
                  return (
                    <td key={s} style={styles.tdSlot}>
                      <span style={{
                        ...styles.badge,
                        background: isDry ? 'rgba(0,230,118,0.15)'
                                  : isWet ? 'rgba(41,121,255,0.15)'
                                  : 'transparent',
                        color: isDry ? 'var(--dry)'
                             : isWet ? 'var(--wet)'
                             : 'var(--text-dim)',
                        border: isDry ? '1px solid rgba(0,230,118,0.3)'
                              : isWet ? '1px solid rgba(41,121,255,0.3)'
                              : '1px solid var(--border)',
                      }}>
                        {d.label || '—'}
                      </span>
                    </td>
                  );
                })}
                <td style={styles.tdSlot}>
                  <span style={{
                    ...styles.badge,
                    color: allDry ? 'var(--dry)' : 'var(--warn)',
                    background: allDry ? 'rgba(0,230,118,0.1)' : 'rgba(255,171,0,0.08)',
                    border: allDry ? '1px solid rgba(0,230,118,0.3)' : '1px solid rgba(255,171,0,0.3)',
                  }}>
                    {allDry ? '✓ ALL DRY' : 'IN PROG'}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const styles = {
  empty: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    padding: '40px 20px',
    border: '1px dashed var(--border2)',
    borderRadius: '4px',
  },
  table: {
    width: '100%', borderCollapse: 'collapse',
    fontFamily: 'var(--mono)', fontSize: '11px',
  },
  th: {
    padding: '8px 10px',
    textAlign: 'left',
    fontFamily: 'var(--sans)',
    fontSize: '9px', fontWeight: 700,
    letterSpacing: '2px', textTransform: 'uppercase',
    color: 'var(--text-dim)',
    borderBottom: '1px solid var(--border)',
    whiteSpace: 'nowrap',
  },
  row: {
    borderBottom: '1px solid var(--border)',
    transition: 'background 0.2s',
  },
  td: {
    padding: '8px 10px',
    whiteSpace: 'nowrap',
  },
  tdSlot: {
    padding: '6px 10px',
    textAlign: 'center',
  },
  mono: {
    fontFamily: 'var(--mono)', fontSize: '11px',
    color: 'var(--text-mid)', letterSpacing: '0.5px',
  },
  badge: {
    display: 'inline-block',
    padding: '2px 6px', borderRadius: '2px',
    fontSize: '9px', letterSpacing: '1px',
    fontFamily: 'var(--mono)', fontWeight: 700,
  },
};
