import './_group.css';
import { Search, ChevronLeft, ChevronRight, ChevronDown, SlidersHorizontal } from 'lucide-react';

const statusColors: Record<string, { color: string; bg: string }> = {
  New: { color: '#3b82f6', bg: '#eff6ff' },
  Active: { color: '#22c55e', bg: '#f0fdf4' },
  Suspended: { color: '#f59e0b', bg: '#fffbeb' },
  'Awaiting info': { color: '#f59e0b', bg: '#fffbeb' },
  Completed: { color: '#14b8a6', bg: '#f0fdfa' },
  Invoiced: { color: '#a855f7', bg: '#faf5ff' },
};

const jobs = [
  { id: 1, ref: '2512045 (232917)', customer: 'DEOL & Jagjeet Singh GILL', client: 'No client', reg: '', type: 'Process Serve', booking: 'New Visit', agent: 'Grant Cook', schedule: '13/01/2026 09:00', overdue: true, status: 'Awaiting info' },
  { id: 2, ref: '2601071 (1105322)', customer: 'SAPAVADIYA FAMILY TRUST & RUDRAKSH', client: 'No client', reg: '2DI92K', type: 'Repo/Collect', booking: 'New Visit', agent: 'DanielC', schedule: '30/01/2026 09:00', overdue: true, status: 'Suspended' },
  { id: 3, ref: '2501088 (130704-1)', customer: 'Western Triumph Services Pty Ltd', client: 'No client', reg: '1WY2RV', type: 'Repo/Collect', booking: 'New Visit', agent: 'Grant Cook', schedule: '30/01/2026 09:00', overdue: true, status: 'Active' },
  { id: 4, ref: '2601001 (331545)', customer: 'BIGAUS ENTERPRISES PTY LTD', client: 'No client', reg: '', type: 'Repo/Collect', booking: 'New Visit', agent: 'DanielC', schedule: '30/01/2026 09:00', overdue: true, status: 'Suspended' },
  { id: 5, ref: '2601065 (328216)', customer: 'PLOZZA', client: 'No client', reg: '', type: 'Repo/Collect', booking: 'New Visit', agent: 'DanielC', schedule: '30/01/2026 09:00', overdue: true, status: 'Awaiting info' },
  { id: 6, ref: '2603043', customer: 'Light Forest Pty Ltd', client: 'IAG', reg: 'ABC123', type: 'New Visit', booking: 'New Visit', agent: '—', schedule: '—', overdue: false, status: 'New' },
  { id: 7, ref: '2603042', customer: 'Phillips', client: 'Suncorp', reg: '', type: 'Repo/Collect', booking: 'New Visit', agent: '—', schedule: '—', overdue: false, status: 'New' },
  { id: 8, ref: '2602192 (620645)', customer: 'Kay K Pty Ltd', client: 'No client', reg: 'XYZ789', type: 'Repo/Collect', booking: 'New Visit', agent: 'Grant Cook', schedule: '14/03/2026 09:00', overdue: false, status: 'Active' },
  { id: 9, ref: '2602175 (KIA148296)', customer: 'SIDDIQUI', client: 'No client', reg: '', type: 'Repo/Collect', booking: 'New Visit', agent: 'Grant Cook', schedule: '15/03/2026 10:30', overdue: false, status: 'Active' },
  { id: 10, ref: '2603039', customer: 'GORISS-DAZELEY', client: 'No client', reg: '', type: 'New Visit', booking: '', agent: '—', schedule: '—', overdue: false, status: 'New' },
];

function StatusBadge({ status }: { status: string }) {
  const cfg = statusColors[status] || { color: '#6b7280', bg: '#f3f4f6' };
  return (
    <span style={{
      fontSize: '.72rem', fontWeight: 600,
      background: cfg.bg, color: cfg.color,
      border: `1px solid ${cfg.color}40`,
      borderRadius: 99, padding: '2px 10px',
      whiteSpace: 'nowrap',
    }}>{status}</span>
  );
}

export function CompactTable() {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', padding: '20px 28px' }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'var(--card)', border: '1px solid var(--line)',
        borderRadius: 16, padding: '12px 16px', marginBottom: 16,
      }}>
        <span style={{ fontSize: '1.1rem', fontWeight: 650 }}>Jobs</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button style={{
            background: 'linear-gradient(90deg, #60a5fa, #3b82f6)',
            border: 'none', color: '#fff', borderRadius: 10,
            padding: '7px 14px', fontWeight: 600, fontSize: '.82rem',
            cursor: 'pointer',
          }}>+ New Job</button>
          <span style={{ fontSize: '.82rem', color: 'var(--muted)' }}>
            Signed in as <b style={{ color: 'var(--text)' }}>Grant Cook</b>
          </span>
        </div>
      </div>

      <div style={{
        background: 'var(--card)', border: '1px solid var(--line)',
        borderRadius: 16, overflow: 'hidden',
      }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--line)' }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 280px', position: 'relative' }}>
              <input placeholder="Search job no., client, customer, rego, VIN..."
                style={{
                  width: '100%', boxSizing: 'border-box', padding: '8px 12px 8px 34px',
                  border: '1px solid var(--line)', borderRadius: 10,
                  fontSize: '.84rem', background: '#fff', outline: 'none',
                }} />
              <Search size={15} style={{ position: 'absolute', left: 10, top: 10, color: 'var(--muted)' }} />
            </div>
            <select style={{
              padding: '8px 28px 8px 10px', border: '1px solid var(--line)',
              borderRadius: 10, fontSize: '.84rem', background: '#fff', outline: 'none',
              appearance: 'none', minWidth: 130,
            }}>
              <option>All statuses</option>
              <option>New</option>
              <option>Active</option>
              <option>Suspended</option>
            </select>
            <select style={{
              padding: '8px 28px 8px 10px', border: '1px solid var(--line)',
              borderRadius: 10, fontSize: '.84rem', background: '#fff', outline: 'none',
              appearance: 'none', minWidth: 160,
            }}>
              <option>Sort: Oldest Scheduled</option>
              <option>Sort: Job # high–low</option>
            </select>
            <button style={{
              padding: '8px 14px', border: '1px solid var(--line)',
              borderRadius: 10, fontSize: '.84rem', background: '#fff',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5,
              color: 'var(--muted)',
            }}>
              <SlidersHorizontal size={14} /> Filters
            </button>
            <button style={{
              padding: '8px 16px', border: 'none',
              borderRadius: 10, fontSize: '.84rem', background: 'var(--accent)',
              color: '#fff', fontWeight: 600, cursor: 'pointer',
            }}>Filter</button>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '.78rem', color: 'var(--muted)' }}>
            <span>Showing 1–10 of 2,097 jobs</span>
            <span>Page 1 of 84</span>
          </div>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.82rem' }}>
          <thead>
            <tr style={{ background: '#f9fafb' }}>
              <th style={{ fontWeight: 600, padding: '10px 16px', textAlign: 'left', color: 'var(--muted)', fontSize: '.75rem', textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '1px solid var(--line)' }}>Job Ref</th>
              <th style={{ fontWeight: 600, padding: '10px 16px', textAlign: 'left', color: 'var(--muted)', fontSize: '.75rem', textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '1px solid var(--line)' }}>Customer</th>
              <th style={{ fontWeight: 600, padding: '10px 16px', textAlign: 'left', color: 'var(--muted)', fontSize: '.75rem', textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '1px solid var(--line)' }}>Reg</th>
              <th style={{ fontWeight: 600, padding: '10px 16px', textAlign: 'left', color: 'var(--muted)', fontSize: '.75rem', textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '1px solid var(--line)' }}>Agent</th>
              <th style={{ fontWeight: 600, padding: '10px 16px', textAlign: 'left', color: 'var(--muted)', fontSize: '.75rem', textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '1px solid var(--line)' }}>Booking</th>
              <th style={{ fontWeight: 600, padding: '10px 16px', textAlign: 'left', color: 'var(--muted)', fontSize: '.75rem', textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '1px solid var(--line)' }}>Next Schedule</th>
              <th style={{ fontWeight: 600, padding: '10px 16px', textAlign: 'left', color: 'var(--muted)', fontSize: '.75rem', textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '1px solid var(--line)' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j, i) => (
              <tr key={j.id}
                style={{ cursor: 'pointer', borderBottom: '1px solid var(--line)' }}
                onMouseOver={(e) => (e.currentTarget.style.background = '#f8fafc')}
                onMouseOut={(e) => (e.currentTarget.style.background = 'transparent')}>
                <td style={{ padding: '10px 16px', color: 'var(--accent)', fontWeight: 600, whiteSpace: 'nowrap' }}>{j.ref}</td>
                <td style={{ padding: '10px 16px', fontWeight: 500, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{j.customer}</td>
                <td style={{ padding: '10px 16px', color: j.reg ? 'var(--text)' : 'var(--line)', fontFamily: 'monospace', fontSize: '.8rem' }}>{j.reg || '—'}</td>
                <td style={{ padding: '10px 16px', color: j.agent === '—' ? '#dc2626' : 'var(--muted)', fontStyle: j.agent === '—' ? 'italic' : 'normal', fontSize: '.8rem' }}>
                  {j.agent === '—' ? 'Unassigned' : j.agent}
                </td>
                <td style={{ padding: '10px 16px' }}>
                  {j.booking ? (
                    <span style={{
                      fontSize: '.72rem', fontWeight: 600,
                      background: '#22c55e', color: '#fff',
                      borderRadius: 99, padding: '2px 10px',
                      whiteSpace: 'nowrap',
                    }}>{j.booking}</span>
                  ) : (
                    <span style={{ color: 'var(--line)' }}>—</span>
                  )}
                </td>
                <td style={{ padding: '10px 16px', whiteSpace: 'nowrap' }}>
                  {j.schedule === '—' ? (
                    <span style={{ color: 'var(--line)' }}>—</span>
                  ) : (
                    <span style={{
                      fontSize: '.78rem',
                      color: j.overdue ? '#ef4444' : 'var(--muted)',
                      fontWeight: j.overdue ? 600 : 400,
                    }}>
                      {j.overdue && <span style={{ fontSize: '.68rem', background: '#fef2f2', color: '#ef4444', border: '1px solid #fecaca', borderRadius: 4, padding: '1px 5px', marginRight: 4 }}>OVERDUE</span>}
                      {j.schedule}
                    </span>
                  )}
                </td>
                <td style={{ padding: '10px 16px' }}><StatusBadge status={j.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 18px', borderTop: '1px solid var(--line)',
          fontSize: '.82rem', color: 'var(--muted)',
        }}>
          <span>Showing 1–10 of 2,097</span>
          <div style={{ display: 'flex', gap: 4 }}>
            <button style={{
              border: '1px solid var(--line)', borderRadius: 8, background: 'var(--card)',
              padding: '6px 10px', cursor: 'pointer', opacity: 0.4,
            }}><ChevronLeft size={14} /></button>
            {[1, 2, 3, '...', 84].map((p, i) => (
              <button key={i} style={{
                border: p === 1 ? '1px solid var(--accent)' : '1px solid var(--line)',
                borderRadius: 8,
                background: p === 1 ? 'var(--accent)' : 'var(--card)',
                color: p === 1 ? '#fff' : typeof p === 'string' ? 'var(--muted)' : 'var(--text)',
                padding: '6px 11px', cursor: typeof p === 'string' ? 'default' : 'pointer',
                fontWeight: p === 1 ? 600 : 400, fontSize: '.82rem',
              }}>{p}</button>
            ))}
            <button style={{
              border: '1px solid var(--line)', borderRadius: 8, background: 'var(--card)',
              padding: '6px 10px', cursor: 'pointer',
            }}><ChevronRight size={14} /></button>
          </div>
        </div>
      </div>
    </div>
  );
}
