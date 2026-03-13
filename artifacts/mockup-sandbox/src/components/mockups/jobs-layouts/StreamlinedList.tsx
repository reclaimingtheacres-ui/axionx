import './_group.css';
import { Search, SlidersHorizontal, ChevronLeft, ChevronRight } from 'lucide-react';

const statusColors: Record<string, { color: string; bg: string }> = {
  New: { color: '#3b82f6', bg: '#eff6ff' },
  Active: { color: '#22c55e', bg: '#f0fdf4' },
  Suspended: { color: '#ef4444', bg: '#fef2f2' },
  'Awaiting info': { color: '#f59e0b', bg: '#fffbeb' },
  Completed: { color: '#14b8a6', bg: '#f0fdfa' },
  Invoiced: { color: '#a855f7', bg: '#faf5ff' },
};

const jobs = [
  { id: 1, ref: '2512045 (232917)', customer: 'DEOL & Jagjeet Singh GILL', client: 'No client', reg: '', type: 'Process Serve', booking: 'New Visit', agent: 'Grant Cook', schedule: '13/01/2026 09:00', overdue: true, status: 'Awaiting info' },
  { id: 2, ref: '2601071 (1105322)', customer: 'SAPAVADIYA FAMILY TRUST & RUDRAKSH HOLDING', client: 'No client', reg: '2DI92K', type: 'Repo/Collect', booking: 'New Visit', agent: 'DanielC', schedule: '30/01/2026 09:00', overdue: true, status: 'Suspended' },
  { id: 3, ref: '2501088 (130704-1)', customer: 'Western Triumph Services Pty Ltd', client: 'No client', reg: '1WY2RV', type: 'Repo/Collect', booking: 'New Visit', agent: 'Grant Cook', schedule: '30/01/2026 09:00', overdue: true, status: 'Active' },
  { id: 4, ref: '2601001 (331545)', customer: 'BIGAUS ENTERPRISES PTY LTD', client: 'No client', reg: '', type: 'Repo/Collect', booking: 'New Visit', agent: 'DanielC', schedule: '30/01/2026 09:00', overdue: true, status: 'Suspended' },
  { id: 5, ref: '2601065 (328216)', customer: 'PLOZZA', client: 'No client', reg: '', type: 'Repo/Collect', booking: 'New Visit', agent: 'DanielC', schedule: '30/01/2026 09:00', overdue: true, status: 'Awaiting info' },
  { id: 6, ref: '2603043', customer: 'Light Forest Pty Ltd', client: 'IAG', reg: 'ABC123', type: 'New Visit', booking: 'New Visit', agent: '', schedule: '', overdue: false, status: 'New' },
  { id: 7, ref: '2603042', customer: 'Phillips', client: 'Suncorp', reg: '', type: 'Repo/Collect', booking: 'New Visit', agent: '', schedule: '', overdue: false, status: 'New' },
  { id: 8, ref: '2602192 (620645)', customer: 'Kay K Pty Ltd', client: 'No client', reg: 'XYZ789', type: 'Repo/Collect', booking: 'New Visit', agent: 'Grant Cook', schedule: '14/03/2026 09:00', overdue: false, status: 'Active' },
  { id: 9, ref: '2602175 (KIA148296)', customer: 'SIDDIQUI', client: 'No client', reg: '', type: 'Repo/Collect', booking: 'New Visit', agent: 'Grant Cook', schedule: '15/03/2026 10:30', overdue: false, status: 'Active' },
  { id: 10, ref: '2603039', customer: 'GORISS-DAZELEY', client: 'No client', reg: '', type: 'New Visit', booking: '', agent: '', schedule: '', overdue: false, status: 'New' },
];

function JobRow({ job }: { job: typeof jobs[0] }) {
  const sc = statusColors[job.status] || { color: '#6b7280', bg: '#f3f4f6' };
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '14px 18px',
        borderBottom: '1px solid var(--line)',
        cursor: 'pointer',
        transition: 'background .1s',
      }}
      onMouseOver={(e) => (e.currentTarget.style.background = '#f8fafc')}
      onMouseOut={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <div style={{
        width: 4, height: 40, borderRadius: 2,
        background: sc.color, flexShrink: 0,
      }} />

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <span style={{ color: 'var(--accent)', fontWeight: 700, fontSize: '.88rem' }}>{job.ref}</span>
          <span style={{ fontWeight: 600, fontSize: '.88rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.customer}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: '.76rem', color: 'var(--muted)' }}>{job.client}</span>
          {job.reg && (
            <>
              <span style={{ fontSize: '.76rem', color: 'var(--line)' }}>·</span>
              <span style={{ fontSize: '.76rem', color: 'var(--text)', fontFamily: 'monospace', fontWeight: 500 }}>{job.reg}</span>
            </>
          )}
          <span style={{ fontSize: '.76rem', color: 'var(--line)' }}>·</span>
          <span style={{ fontSize: '.76rem', color: 'var(--muted)' }}>{job.type}</span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <div style={{ textAlign: 'right', minWidth: 100 }}>
          <div style={{
            fontSize: '.76rem', fontWeight: 500,
            color: job.agent ? 'var(--text)' : '#dc2626',
            marginBottom: 2,
          }}>
            {job.agent || 'Unassigned'}
          </div>
          {job.schedule ? (
            <div style={{
              fontSize: '.72rem',
              color: job.overdue ? '#ef4444' : 'var(--muted)',
              fontWeight: job.overdue ? 600 : 400,
            }}>
              {job.overdue && '⚠ '}
              {job.schedule}
            </div>
          ) : (
            <div style={{ fontSize: '.72rem', color: 'var(--line)' }}>No schedule</div>
          )}
        </div>

        {job.booking && (
          <span style={{
            fontSize: '.72rem', fontWeight: 600,
            background: '#22c55e', color: '#fff',
            borderRadius: 99, padding: '3px 10px',
            whiteSpace: 'nowrap', minWidth: 72, textAlign: 'center',
          }}>{job.booking}</span>
        )}

        <span style={{
          fontSize: '.72rem', fontWeight: 600,
          background: sc.bg, color: sc.color,
          border: `1px solid ${sc.color}40`,
          borderRadius: 99, padding: '3px 12px',
          whiteSpace: 'nowrap', minWidth: 80, textAlign: 'center',
        }}>{job.status}</span>
      </div>
    </div>
  );
}

export function StreamlinedList() {
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
            padding: '7px 14px', fontWeight: 600, fontSize: '.82rem', cursor: 'pointer',
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
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
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
              padding: '8px 12px', border: '1px solid var(--line)',
              borderRadius: 10, fontSize: '.84rem', background: '#fff', minWidth: 130,
            }}>
              <option>All statuses</option>
            </select>
            <select style={{
              padding: '8px 12px', border: '1px solid var(--line)',
              borderRadius: 10, fontSize: '.84rem', background: '#fff', minWidth: 160,
            }}>
              <option>Sort: Oldest Scheduled</option>
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
              padding: '8px 16px', border: 'none', borderRadius: 10,
              fontSize: '.84rem', background: 'var(--accent)', color: '#fff', fontWeight: 600, cursor: 'pointer',
            }}>Filter</button>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '.78rem', color: 'var(--muted)' }}>
            <span>Showing 1–10 of 2,097 jobs</span>
            <span>Page 1 of 84</span>
          </div>
        </div>

        <div>
          {jobs.map((j) => <JobRow key={j.id} job={j} />)}
        </div>

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
