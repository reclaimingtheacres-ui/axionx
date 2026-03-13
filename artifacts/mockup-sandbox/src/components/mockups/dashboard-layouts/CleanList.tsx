import './_group.css';
import { Search, Plus, ChevronRight, AlertTriangle } from 'lucide-react';

const tiles = [
  { label: 'All Jobs', count: 2097, color: '#111827', bg: '#f9fafb' },
  { label: 'New', count: 41, color: '#16a34a', bg: '#f0fdf4' },
  { label: 'Active', count: 154, color: '#d97706', bg: '#fffbeb' },
  { label: 'Phone Work', count: 0, color: '#2563eb', bg: '#eff6ff' },
  { label: 'Suspended', count: 75, color: '#dc2626', bg: '#fef2f2' },
  { label: 'Awaiting', count: 119, color: '#f59e0b', bg: '#fffbeb' },
  { label: 'Completed', count: 60, color: '#0d9488', bg: '#f0fdfa' },
  { label: 'Invoiced', count: 1169, color: '#6b7280', bg: '#f9fafb' },
];

const newJobs = [
  { ref: '2603043', customer: 'Light Forest Pty Ltd', agent: '—', schedule: '—' },
  { ref: '2603042', customer: 'Phillips', agent: '—', schedule: '—' },
  { ref: '2603041', customer: 'Punugoti', agent: '—', schedule: '—' },
  { ref: '2602185', customer: 'The Trustee For Moureddine Family Trust', agent: '—', schedule: '—' },
  { ref: '2603040', customer: 'Stone', agent: '—', schedule: '—' },
];

const activeJobs = [
  { ref: '2602192', customer: 'Kay K Pty Ltd', agent: 'Grant Cook', schedule: 'Tomorrow 09:00' },
  { ref: '2602175', customer: 'Siddiqui', agent: 'Grant Cook', schedule: '15/03/26 10:30' },
  { ref: '2602174', customer: 'Abdallah', agent: 'Grant Cook', schedule: '—' },
  { ref: '2603015', customer: 'Adamson', agent: '—', schedule: '—' },
  { ref: '2603039', customer: 'Goriss-Dazeley', agent: '—', schedule: '16/03/26 08:00' },
];

const suspendedJobs = [
  { ref: '2601980', customer: 'Randhawa Enterprise Pty Ltd', agent: 'Grant Cook', schedule: '—' },
  { ref: '2601445', customer: 'Melbourne Auto Glass', agent: '—', schedule: '—' },
  { ref: '2600812', customer: 'Thompson & Co', agent: 'Grant Cook', schedule: '—' },
];

type StatusSection = {
  label: string;
  color: string;
  total: number;
  jobs: { ref: string; customer: string; agent: string; schedule: string }[];
};

const sections: StatusSection[] = [
  { label: 'New', color: '#16a34a', total: 41, jobs: newJobs },
  { label: 'Active', color: '#d97706', total: 154, jobs: activeJobs },
  { label: 'Suspended', color: '#dc2626', total: 75, jobs: suspendedJobs },
];

function JobTable({ section }: { section: StatusSection }) {
  return (
    <div style={{
      background: 'var(--card)',
      border: '1px solid var(--line)',
      borderRadius: 16,
      marginBottom: 16,
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid var(--line)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%',
            background: section.color, display: 'inline-block',
          }} />
          <span style={{ color: section.color, fontSize: '.85rem', fontWeight: 600 }}>
            {section.label}
          </span>
          <span style={{
            background: section.color + '18',
            color: section.color,
            border: `1px solid ${section.color}44`,
            fontSize: '.72rem',
            fontWeight: 600,
            borderRadius: 99,
            padding: '2px 8px',
          }}>
            {section.total}
          </span>
        </div>
        <a href="#" style={{
          fontSize: '.8rem',
          color: 'var(--accent)',
          textDecoration: 'none',
          fontWeight: 500,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
        }}>
          View all <ChevronRight size={14} />
        </a>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.84rem' }}>
        <thead>
          <tr style={{ color: 'var(--muted)' }}>
            <th style={{ fontWeight: 500, padding: '8px 16px', borderBottom: '1px solid var(--line)', textAlign: 'left' }}>Job Ref</th>
            <th style={{ fontWeight: 500, padding: '8px 16px', borderBottom: '1px solid var(--line)', textAlign: 'left' }}>Customer</th>
            <th style={{ fontWeight: 500, padding: '8px 16px', borderBottom: '1px solid var(--line)', textAlign: 'left' }}>Agent</th>
            <th style={{ fontWeight: 500, padding: '8px 16px', borderBottom: '1px solid var(--line)', textAlign: 'left' }}>Next Schedule</th>
          </tr>
        </thead>
        <tbody>
          {section.jobs.map((j) => (
            <tr key={j.ref} style={{ cursor: 'pointer', borderBottom: '1px solid var(--line)' }}
              onMouseOver={(e) => (e.currentTarget.style.background = '#f8fafc')}
              onMouseOut={(e) => (e.currentTarget.style.background = 'transparent')}>
              <td style={{ padding: '10px 16px', color: 'var(--accent)', fontWeight: 600 }}>{j.ref}</td>
              <td style={{ padding: '10px 16px', fontWeight: 500 }}>{j.customer}</td>
              <td style={{ padding: '10px 16px', color: 'var(--muted)' }}>{j.agent}</td>
              <td style={{ padding: '10px 16px', color: j.schedule.startsWith('Tomorrow') ? '#60a5fa' : 'var(--muted)' }}>
                {j.schedule}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CleanList() {
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
          <span>You have <b>6</b> unfinished attendance updates requiring completion.</span>
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
        marginBottom: 24,
      }}>
        {tiles.map((t) => (
          <div key={t.label} style={{
            background: t.bg,
            border: '1px solid rgba(0,0,0,.06)',
            borderRadius: 12,
            padding: '10px 12px',
            cursor: 'pointer',
            transition: 'transform .12s',
          }}>
            <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--muted)', marginBottom: 3 }}>{t.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: t.color }}>{t.count}</div>
          </div>
        ))}
      </div>

      {sections.map((s) => (
        <JobTable key={s.label} section={s} />
      ))}
    </div>
  );
}
