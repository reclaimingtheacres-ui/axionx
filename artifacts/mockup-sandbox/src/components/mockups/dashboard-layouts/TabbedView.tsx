import './_group.css';
import { useState } from 'react';
import { Search, Plus, AlertTriangle, ChevronLeft, ChevronRight } from 'lucide-react';

const tiles = [
  { label: 'All Jobs', count: 2097, color: '#111827', key: 'all' },
  { label: 'New', count: 41, color: '#16a34a', key: 'New' },
  { label: 'Active', count: 154, color: '#d97706', key: 'Active' },
  { label: 'Phone Work', count: 0, color: '#2563eb', key: 'Phone' },
  { label: 'Suspended', count: 75, color: '#dc2626', key: 'Suspended' },
  { label: 'Awaiting', count: 119, color: '#f59e0b', key: 'Awaiting' },
  { label: 'Completed', count: 60, color: '#0d9488', key: 'Completed' },
  { label: 'Invoiced', count: 1169, color: '#6b7280', key: 'Invoiced' },
];

const allJobs: Record<string, { ref: string; customer: string; agent: string; schedule: string; status: string }[]> = {
  New: [
    { ref: '2603043', customer: 'Light Forest Pty Ltd', agent: '—', schedule: '—', status: 'New' },
    { ref: '2603042', customer: 'Phillips', agent: '—', schedule: '—', status: 'New' },
    { ref: '2603041', customer: 'Punugoti', agent: '—', schedule: '—', status: 'New' },
    { ref: '2602185', customer: 'Moureddine Family Trust', agent: '—', schedule: '—', status: 'New' },
    { ref: '2603040', customer: 'Stone', agent: '—', schedule: '—', status: 'New' },
    { ref: '2602192', customer: 'Kay K Pty Ltd', agent: 'Grant Cook', schedule: '—', status: 'New' },
    { ref: '2602175', customer: 'Siddiqui', agent: 'Grant Cook', schedule: '—', status: 'New' },
    { ref: '2602174', customer: 'Abdallah', agent: 'Grant Cook', schedule: '—', status: 'New' },
    { ref: '2603015', customer: 'Adamson', agent: '—', schedule: '—', status: 'New' },
    { ref: '2603039', customer: 'Goriss-Dazeley', agent: '—', schedule: '—', status: 'New' },
    { ref: '2603038', customer: 'Randhawa Enterprise', agent: '—', schedule: '—', status: 'New' },
    { ref: '2603037', customer: 'Rizk Group Vic', agent: '—', schedule: '—', status: 'New' },
    { ref: '2603036', customer: 'Warehouse Management', agent: '—', schedule: '—', status: 'New' },
    { ref: '2603027', customer: 'Wellington', agent: '—', schedule: '—', status: 'New' },
    { ref: '2603035', customer: 'Pearson', agent: '—', schedule: '—', status: 'New' },
  ],
  Active: [
    { ref: '2601980', customer: 'Randhawa Enterprise Pty Ltd', agent: 'Grant Cook', schedule: 'Today 14:00', status: 'Active' },
    { ref: '2601445', customer: 'Melbourne Auto Glass', agent: 'Grant Cook', schedule: 'Tomorrow 09:00', status: 'Active' },
    { ref: '2600812', customer: 'Thompson & Co', agent: 'Grant Cook', schedule: '15/03/26 10:30', status: 'Active' },
    { ref: '2600750', customer: 'J & M Motors', agent: '—', schedule: '16/03/26 08:00', status: 'Active' },
    { ref: '2600698', customer: 'ACE Panel Works', agent: 'Grant Cook', schedule: '—', status: 'Active' },
    { ref: '2600655', customer: 'Capital Smash Repairs', agent: '—', schedule: '—', status: 'Active' },
    { ref: '2600601', customer: 'Bright Star Motors', agent: 'Grant Cook', schedule: '17/03/26 11:00', status: 'Active' },
    { ref: '2600590', customer: 'Westside Panel', agent: '—', schedule: '—', status: 'Active' },
    { ref: '2600577', customer: 'Deluxe Autobody', agent: 'Grant Cook', schedule: '18/03/26 09:30', status: 'Active' },
    { ref: '2600550', customer: 'City Crash Repairs', agent: '—', schedule: '—', status: 'Active' },
    { ref: '2600520', customer: 'Eastern Suburbs Auto', agent: 'Grant Cook', schedule: '—', status: 'Active' },
    { ref: '2600488', customer: 'Northern Panel Works', agent: '—', schedule: '19/03/26 14:00', status: 'Active' },
  ],
  Suspended: [
    { ref: '2601100', customer: 'Coastal Repairs', agent: '—', schedule: '—', status: 'Suspended' },
    { ref: '2600990', customer: 'Bayside Motors', agent: 'Grant Cook', schedule: '—', status: 'Suspended' },
    { ref: '2600880', customer: 'Hilltop Auto', agent: '—', schedule: '—', status: 'Suspended' },
  ],
  Awaiting: [
    { ref: '2601200', customer: 'Greenfield Smash', agent: 'Grant Cook', schedule: '—', status: 'Awaiting' },
    { ref: '2601150', customer: 'Premier Auto Body', agent: '—', schedule: '—', status: 'Awaiting' },
  ],
  Completed: [
    { ref: '2600400', customer: 'Metro Panel Works', agent: 'Grant Cook', schedule: '—', status: 'Completed' },
  ],
  Invoiced: [
    { ref: '2600300', customer: 'Southern Cross Auto', agent: 'Grant Cook', schedule: '—', status: 'Invoiced' },
  ],
  Phone: [],
};

export function TabbedView() {
  const [activeTab, setActiveTab] = useState('New');
  const [page, setPage] = useState(1);
  const perPage = 10;

  const jobs = allJobs[activeTab] || [];
  const totalPages = Math.max(1, Math.ceil(jobs.length / perPage));
  const displayed = jobs.slice((page - 1) * perPage, page * perPage);
  const tabTile = tiles.find(t => t.key === activeTab);

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', padding: '24px 32px' }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'var(--card)', border: '1px solid var(--line)',
        borderRadius: 16, padding: '12px 16px', marginBottom: 16,
      }}>
        <span style={{ fontSize: '1.1rem', fontWeight: 650 }}>Home</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button style={{
            background: 'linear-gradient(90deg, #60a5fa, #3b82f6)',
            border: 'none', color: '#fff', borderRadius: 12,
            padding: '8px 16px', fontWeight: 600, fontSize: '.85rem',
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
          }}>
            <Plus size={16} /> New Job
          </button>
          <span style={{ fontSize: '.85rem', color: 'var(--muted)' }}>
            Signed in as <b style={{ color: 'var(--text)' }}>Grant Cook</b>
          </span>
        </div>
      </div>

      <div style={{
        background: '#fffbeb', border: '1px solid #fde68a',
        borderRadius: 14, padding: '10px 16px', marginBottom: 16,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        fontSize: '.85rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle size={16} color="#d97706" />
          <span>You have <b>6</b> unfinished attendance updates.</span>
        </div>
        <a href="#" style={{
          background: '#dc2626', color: '#fff', borderRadius: 10,
          padding: '5px 14px', fontSize: '.78rem', fontWeight: 600,
          textDecoration: 'none',
        }}>View Drafts</a>
      </div>

      <div style={{ position: 'relative', marginBottom: 20 }}>
        <input
          type="text"
          placeholder="Search jobs, customer, rego, VIN..."
          style={{
            width: '100%', boxSizing: 'border-box', padding: '12px 16px 12px 40px',
            border: '1px solid var(--line)', borderRadius: 14,
            fontSize: '.95rem', background: 'var(--card)', color: 'var(--text)',
            outline: 'none',
          }}
        />
        <Search size={18} style={{ position: 'absolute', left: 14, top: 13, color: 'var(--muted)' }} />
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
        gap: 10,
        marginBottom: 20,
      }}>
        {tiles.map((t) => (
          <div
            key={t.key}
            onClick={() => { setActiveTab(t.key === 'all' ? 'New' : t.key); setPage(1); }}
            style={{
              background: activeTab === t.key ? t.color + '12' : '#f9fafb',
              border: activeTab === t.key ? `2px solid ${t.color}55` : '1px solid rgba(0,0,0,.06)',
              borderRadius: 12,
              padding: '10px 12px',
              cursor: 'pointer',
              transition: 'all .15s',
            }}
          >
            <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--muted)', marginBottom: 3 }}>{t.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: t.color }}>{t.count}</div>
          </div>
        ))}
      </div>

      <div style={{
        background: 'var(--card)', border: '1px solid var(--line)',
        borderRadius: 16, overflow: 'hidden',
      }}>
        <div style={{
          display: 'flex', gap: 0, borderBottom: '1px solid var(--line)',
          overflowX: 'auto',
        }}>
          {['New', 'Active', 'Suspended', 'Awaiting', 'Completed', 'Invoiced'].map((tab) => {
            const t = tiles.find(x => x.key === tab);
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                onClick={() => { setActiveTab(tab); setPage(1); }}
                style={{
                  border: 'none',
                  borderBottom: isActive ? `2px solid ${t?.color}` : '2px solid transparent',
                  background: 'transparent',
                  padding: '12px 20px',
                  fontSize: '.83rem',
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? t?.color : 'var(--muted)',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  transition: 'all .15s',
                }}
              >
                {tab}
                <span style={{
                  marginLeft: 6, fontSize: '.72rem',
                  background: isActive ? t?.color + '18' : '#f3f4f6',
                  color: isActive ? t?.color : 'var(--muted)',
                  borderRadius: 99, padding: '1px 7px',
                }}>
                  {t?.count ?? 0}
                </span>
              </button>
            );
          })}
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.84rem' }}>
          <thead>
            <tr style={{ color: 'var(--muted)' }}>
              <th style={{ fontWeight: 500, padding: '10px 16px', borderBottom: '1px solid var(--line)', textAlign: 'left' }}>Job Ref</th>
              <th style={{ fontWeight: 500, padding: '10px 16px', borderBottom: '1px solid var(--line)', textAlign: 'left' }}>Customer</th>
              <th style={{ fontWeight: 500, padding: '10px 16px', borderBottom: '1px solid var(--line)', textAlign: 'left' }}>Agent</th>
              <th style={{ fontWeight: 500, padding: '10px 16px', borderBottom: '1px solid var(--line)', textAlign: 'left' }}>Next Schedule</th>
            </tr>
          </thead>
          <tbody>
            {displayed.length === 0 ? (
              <tr><td colSpan={4} style={{ padding: 32, textAlign: 'center', color: 'var(--muted)' }}>No jobs in this status.</td></tr>
            ) : displayed.map((j) => (
              <tr key={j.ref} style={{ cursor: 'pointer' }}
                onMouseOver={(e) => (e.currentTarget.style.background = '#f8fafc')}
                onMouseOut={(e) => (e.currentTarget.style.background = 'transparent')}>
                <td style={{ padding: '10px 16px', color: 'var(--accent)', fontWeight: 600, borderBottom: '1px solid var(--line)' }}>{j.ref}</td>
                <td style={{ padding: '10px 16px', fontWeight: 500, borderBottom: '1px solid var(--line)' }}>{j.customer}</td>
                <td style={{ padding: '10px 16px', color: 'var(--muted)', borderBottom: '1px solid var(--line)' }}>{j.agent}</td>
                <td style={{ padding: '10px 16px', borderBottom: '1px solid var(--line)',
                  color: j.schedule.startsWith('Today') ? '#ffd166' : j.schedule.startsWith('Tomorrow') ? '#60a5fa' : 'var(--muted)',
                  fontWeight: j.schedule.startsWith('Today') ? 600 : 400,
                }}>{j.schedule}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {totalPages > 1 && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 16px', borderTop: '1px solid var(--line)',
            fontSize: '.82rem', color: 'var(--muted)',
          }}>
            <span>Showing {(page - 1) * perPage + 1}–{Math.min(page * perPage, jobs.length)} of {jobs.length}</span>
            <div style={{ display: 'flex', gap: 4 }}>
              <button
                disabled={page <= 1}
                onClick={() => setPage(p => p - 1)}
                style={{
                  border: '1px solid var(--line)', borderRadius: 8, background: 'var(--card)',
                  padding: '6px 10px', cursor: page <= 1 ? 'default' : 'pointer',
                  opacity: page <= 1 ? 0.4 : 1,
                }}
              ><ChevronLeft size={14} /></button>
              {Array.from({ length: totalPages }, (_, i) => (
                <button
                  key={i}
                  onClick={() => setPage(i + 1)}
                  style={{
                    border: page === i + 1 ? '1px solid var(--accent)' : '1px solid var(--line)',
                    borderRadius: 8,
                    background: page === i + 1 ? 'var(--accent)' : 'var(--card)',
                    color: page === i + 1 ? '#fff' : 'var(--text)',
                    padding: '6px 12px', cursor: 'pointer',
                    fontWeight: page === i + 1 ? 600 : 400,
                    fontSize: '.82rem',
                  }}
                >{i + 1}</button>
              ))}
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(p => p + 1)}
                style={{
                  border: '1px solid var(--line)', borderRadius: 8, background: 'var(--card)',
                  padding: '6px 10px', cursor: page >= totalPages ? 'default' : 'pointer',
                  opacity: page >= totalPages ? 0.4 : 1,
                }}
              ><ChevronRight size={14} /></button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
