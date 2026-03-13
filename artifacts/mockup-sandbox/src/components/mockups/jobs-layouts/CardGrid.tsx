import './_group.css';
import { Search, SlidersHorizontal, User, Calendar, ChevronLeft, ChevronRight } from 'lucide-react';

const statusColors: Record<string, { color: string; bg: string; border: string }> = {
  New: { color: '#3b82f6', bg: '#eff6ff', border: '#bfdbfe' },
  Active: { color: '#22c55e', bg: '#f0fdf4', border: '#bbf7d0' },
  Suspended: { color: '#ef4444', bg: '#fef2f2', border: '#fecaca' },
  'Awaiting info': { color: '#f59e0b', bg: '#fffbeb', border: '#fde68a' },
  Completed: { color: '#14b8a6', bg: '#f0fdfa', border: '#99f6e4' },
  Invoiced: { color: '#a855f7', bg: '#faf5ff', border: '#e9d5ff' },
};

const jobs = [
  { id: 1, ref: '2512045 (232917)', customer: 'DEOL & Jagjeet Singh GILL', client: 'No client', reg: '', type: 'Process Serve', booking: 'New Visit', agent: 'Grant Cook', schedule: '13/01/2026 09:00', overdue: true, status: 'Awaiting info', priority: 'Normal' },
  { id: 2, ref: '2601071 (1105322)', customer: 'SAPAVADIYA FAMILY TRUST', client: 'No client', reg: '2DI92K', type: 'Repo/Collect', booking: 'New Visit', agent: 'DanielC', schedule: '30/01/2026 09:00', overdue: true, status: 'Suspended', priority: 'Normal' },
  { id: 3, ref: '2501088 (130704-1)', customer: 'Western Triumph Services', client: 'No client', reg: '1WY2RV', type: 'Repo/Collect', booking: 'New Visit', agent: 'Grant Cook', schedule: '30/01/2026 09:00', overdue: true, status: 'Active', priority: 'Normal' },
  { id: 4, ref: '2601001 (331545)', customer: 'BIGAUS ENTERPRISES', client: 'No client', reg: '', type: 'Repo/Collect', booking: 'New Visit', agent: 'DanielC', schedule: '30/01/2026 09:00', overdue: true, status: 'Suspended', priority: 'Normal' },
  { id: 5, ref: '2601065 (328216)', customer: 'PLOZZA', client: 'No client', reg: '', type: 'Repo/Collect', booking: 'New Visit', agent: 'DanielC', schedule: '30/01/2026 09:00', overdue: true, status: 'Awaiting info', priority: 'Normal' },
  { id: 6, ref: '2603043', customer: 'Light Forest Pty Ltd', client: 'IAG', reg: 'ABC123', type: 'New Visit', booking: 'New Visit', agent: '', schedule: '', overdue: false, status: 'New', priority: 'Normal' },
  { id: 7, ref: '2603042', customer: 'Phillips', client: 'Suncorp', reg: '', type: 'Repo/Collect', booking: 'New Visit', agent: '', schedule: '', overdue: false, status: 'New', priority: 'High' },
  { id: 8, ref: '2602192 (620645)', customer: 'Kay K Pty Ltd', client: 'No client', reg: 'XYZ789', type: 'Repo/Collect', booking: 'New Visit', agent: 'Grant Cook', schedule: '14/03/2026 09:00', overdue: false, status: 'Active', priority: 'Normal' },
];

function JobCard({ job }: { job: typeof jobs[0] }) {
  const sc = statusColors[job.status] || { color: '#6b7280', bg: '#f3f4f6', border: '#e5e7eb' };
  return (
    <div style={{
      background: 'var(--card)',
      border: `1px solid ${sc.border}`,
      borderRadius: 14,
      padding: 0,
      cursor: 'pointer',
      transition: 'transform .12s, box-shadow .12s',
      overflow: 'hidden',
      borderTop: `3px solid ${sc.color}`,
    }}
      onMouseOver={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,.08)'; }}
      onMouseOut={(e) => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = 'none'; }}
    >
      <div style={{ padding: '14px 16px 10px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
          <div>
            <div style={{ color: 'var(--accent)', fontWeight: 700, fontSize: '.9rem', marginBottom: 2 }}>{job.ref}</div>
            <div style={{ fontWeight: 600, fontSize: '.88rem', lineHeight: 1.3 }}>{job.customer}</div>
          </div>
          <span style={{
            fontSize: '.7rem', fontWeight: 600,
            background: sc.bg, color: sc.color,
            border: `1px solid ${sc.border}`,
            borderRadius: 99, padding: '3px 10px',
            whiteSpace: 'nowrap',
          }}>{job.status}</span>
        </div>

        <div style={{ fontSize: '.78rem', color: 'var(--muted)', marginBottom: 10 }}>
          {job.client}{job.reg && ` · Reg: ${job.reg}`}
        </div>

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
          <span style={{
            fontSize: '.72rem', fontWeight: 500,
            background: '#f3f4f6', color: 'var(--text)',
            borderRadius: 6, padding: '2px 8px',
          }}>{job.type}</span>
          {job.booking && (
            <span style={{
              fontSize: '.72rem', fontWeight: 600,
              background: '#22c55e', color: '#fff',
              borderRadius: 6, padding: '2px 8px',
            }}>{job.booking}</span>
          )}
        </div>
      </div>

      <div style={{
        padding: '10px 16px',
        background: '#fafbfc',
        borderTop: '1px solid var(--line)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: '.78rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: job.agent ? 'var(--text)' : '#dc2626' }}>
          <User size={13} />
          <span style={{ fontWeight: 500 }}>{job.agent || 'Unassigned'}</span>
        </div>
        {job.schedule ? (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 5,
            color: job.overdue ? '#ef4444' : 'var(--muted)',
            fontWeight: job.overdue ? 600 : 400,
          }}>
            <Calendar size={13} />
            {job.overdue && <span style={{ fontSize: '.65rem', background: '#fef2f2', color: '#ef4444', border: '1px solid #fecaca', borderRadius: 3, padding: '0 4px' }}>LATE</span>}
            {job.schedule}
          </div>
        ) : (
          <span style={{ color: 'var(--line)' }}>No schedule</span>
        )}
      </div>
    </div>
  );
}

export function CardGrid() {
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
        borderRadius: 14, padding: '14px 18px', marginBottom: 16,
      }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
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
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, fontSize: '.78rem', color: 'var(--muted)' }}>
          <span>Showing 1–8 of 2,097 jobs</span>
          <span>Page 1 of 263</span>
        </div>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(2, 1fr)',
        gap: 14,
        marginBottom: 20,
      }}>
        {jobs.map((j) => <JobCard key={j.id} job={j} />)}
      </div>

      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        gap: 4, padding: '8px 0',
      }}>
        <button style={{
          border: '1px solid var(--line)', borderRadius: 8, background: 'var(--card)',
          padding: '8px 12px', cursor: 'pointer', opacity: 0.4,
        }}><ChevronLeft size={14} /></button>
        {[1, 2, 3, '...', 263].map((p, i) => (
          <button key={i} style={{
            border: p === 1 ? '1px solid var(--accent)' : '1px solid var(--line)',
            borderRadius: 8,
            background: p === 1 ? 'var(--accent)' : 'var(--card)',
            color: p === 1 ? '#fff' : typeof p === 'string' ? 'var(--muted)' : 'var(--text)',
            padding: '8px 13px', cursor: typeof p === 'string' ? 'default' : 'pointer',
            fontWeight: p === 1 ? 600 : 400, fontSize: '.84rem',
          }}>{p}</button>
        ))}
        <button style={{
          border: '1px solid var(--line)', borderRadius: 8, background: 'var(--card)',
          padding: '8px 12px', cursor: 'pointer',
        }}><ChevronRight size={14} /></button>
      </div>
    </div>
  );
}
