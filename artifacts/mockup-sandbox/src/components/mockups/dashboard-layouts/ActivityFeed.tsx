import './_group.css';
import { Search, Plus, AlertTriangle, Clock, ArrowUpRight, ChevronRight } from 'lucide-react';

const statusConfig: Record<string, { color: string; bg: string }> = {
  New: { color: '#16a34a', bg: '#f0fdf4' },
  Active: { color: '#d97706', bg: '#fffbeb' },
  Suspended: { color: '#dc2626', bg: '#fef2f2' },
  Awaiting: { color: '#f59e0b', bg: '#fffbeb' },
  Completed: { color: '#0d9488', bg: '#f0fdfa' },
};

const summaryItems = [
  { label: 'Total Active', value: 195, color: '#d97706', sub: '+12 this week' },
  { label: 'Needs Attention', value: 75, color: '#dc2626', sub: 'Suspended' },
  { label: 'Awaiting Response', value: 119, color: '#f59e0b', sub: 'From clients' },
  { label: 'Completed Today', value: 3, color: '#0d9488', sub: 'Ready to invoice' },
];

const recentActivity = [
  { ref: '2603043', customer: 'Light Forest Pty Ltd', status: 'New', agent: '—', time: '2 min ago', action: 'Job created' },
  { ref: '2603042', customer: 'Phillips', status: 'New', agent: '—', time: '8 min ago', action: 'Job created' },
  { ref: '2601980', customer: 'Randhawa Enterprise', status: 'Active', agent: 'Grant Cook', time: '15 min ago', action: 'Schedule updated' },
  { ref: '2603041', customer: 'Punugoti', status: 'New', agent: '—', time: '22 min ago', action: 'Job created' },
  { ref: '2601445', customer: 'Melbourne Auto Glass', status: 'Active', agent: 'Grant Cook', time: '35 min ago', action: 'Note added' },
  { ref: '2602185', customer: 'Moureddine Family Trust', status: 'New', agent: '—', time: '1 hr ago', action: 'Job created' },
  { ref: '2600812', customer: 'Thompson & Co', status: 'Suspended', agent: 'Grant Cook', time: '1 hr ago', action: 'Status changed' },
  { ref: '2601200', customer: 'Greenfield Smash', status: 'Awaiting', agent: 'Grant Cook', time: '2 hrs ago', action: 'Awaiting client info' },
  { ref: '2600750', customer: 'J & M Motors', status: 'Active', agent: '—', time: '2 hrs ago', action: 'Field note submitted' },
  { ref: '2600400', customer: 'Metro Panel Works', status: 'Completed', agent: 'Grant Cook', time: '3 hrs ago', action: 'Job completed' },
];

const upcomingSchedules = [
  { ref: '2601980', customer: 'Randhawa Enterprise', time: 'Today 14:00', agent: 'Grant Cook' },
  { ref: '2601445', customer: 'Melbourne Auto Glass', time: 'Tomorrow 09:00', agent: 'Grant Cook' },
  { ref: '2600812', customer: 'Thompson & Co', time: '15/03 10:30', agent: 'Grant Cook' },
  { ref: '2600750', customer: 'J & M Motors', time: '16/03 08:00', agent: '—' },
];

function StatusBadge({ status }: { status: string }) {
  const cfg = statusConfig[status] || { color: '#6b7280', bg: '#f3f4f6' };
  return (
    <span style={{
      fontSize: '.7rem', fontWeight: 600,
      background: cfg.bg, color: cfg.color,
      border: `1px solid ${cfg.color}33`,
      borderRadius: 6, padding: '2px 8px',
      whiteSpace: 'nowrap',
    }}>{status}</span>
  );
}

export function ActivityFeed() {
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
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 12,
        marginBottom: 24,
      }}>
        {summaryItems.map((s) => (
          <div key={s.label} style={{
            background: 'var(--card)', border: '1px solid var(--line)',
            borderRadius: 14, padding: '16px 18px',
            borderLeft: `4px solid ${s.color}`,
          }}>
            <div style={{ fontSize: '.78rem', color: 'var(--muted)', marginBottom: 4 }}>{s.label}</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: s.color, marginBottom: 2 }}>{s.value}</div>
            <div style={{ fontSize: '.72rem', color: 'var(--muted)' }}>{s.sub}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16 }}>
        <div style={{
          background: 'var(--card)', border: '1px solid var(--line)',
          borderRadius: 16, overflow: 'hidden',
        }}>
          <div style={{
            padding: '14px 18px', borderBottom: '1px solid var(--line)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Clock size={16} color="var(--muted)" />
              <span style={{ fontWeight: 600, fontSize: '.9rem' }}>Recent Activity</span>
            </div>
            <a href="#" style={{
              fontSize: '.8rem', color: 'var(--accent)', textDecoration: 'none',
              fontWeight: 500, display: 'flex', alignItems: 'center', gap: 2,
            }}>
              View all jobs <ChevronRight size={14} />
            </a>
          </div>
          <div>
            {recentActivity.map((item, i) => (
              <div
                key={item.ref + i}
                style={{
                  padding: '12px 18px',
                  borderBottom: i < recentActivity.length - 1 ? '1px solid var(--line)' : 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  cursor: 'pointer',
                  transition: 'background .1s',
                }}
                onMouseOver={(e) => (e.currentTarget.style.background = '#f8fafc')}
                onMouseOut={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, minWidth: 0 }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: 10,
                    background: (statusConfig[item.status]?.bg || '#f3f4f6'),
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0,
                  }}>
                    <ArrowUpRight size={16} color={statusConfig[item.status]?.color || '#6b7280'} />
                  </div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                      <span style={{ color: 'var(--accent)', fontWeight: 600, fontSize: '.84rem' }}>{item.ref}</span>
                      <span style={{ fontWeight: 500, fontSize: '.84rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {item.customer}
                      </span>
                      {item.agent !== '—' && (
                        <span style={{ fontSize: '.75rem', color: 'var(--muted)', marginLeft: 'auto', whiteSpace: 'nowrap' }}>
                          {item.agent}
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: '.75rem', color: 'var(--muted)' }}>{item.action}</span>
                      <StatusBadge status={item.status} />
                      {item.agent === '—' && (
                        <span style={{ fontSize: '.72rem', color: '#dc2626', fontStyle: 'italic', marginLeft: 4 }}>Unassigned</span>
                      )}
                    </div>
                  </div>
                </div>
                <div style={{ fontSize: '.75rem', color: 'var(--muted)', whiteSpace: 'nowrap', marginLeft: 12 }}>
                  {item.time}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{
          background: 'var(--card)', border: '1px solid var(--line)',
          borderRadius: 16, overflow: 'hidden', alignSelf: 'start',
        }}>
          <div style={{
            padding: '14px 18px', borderBottom: '1px solid var(--line)',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <Clock size={16} color="var(--accent)" />
            <span style={{ fontWeight: 600, fontSize: '.9rem' }}>Upcoming Schedules</span>
          </div>
          {upcomingSchedules.map((s, i) => (
            <div key={s.ref} style={{
              padding: '12px 18px',
              borderBottom: i < upcomingSchedules.length - 1 ? '1px solid var(--line)' : 'none',
              cursor: 'pointer',
            }}
              onMouseOver={(e) => (e.currentTarget.style.background = '#f8fafc')}
              onMouseOut={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ color: 'var(--accent)', fontWeight: 600, fontSize: '.84rem' }}>{s.ref}</span>
                <span style={{
                  fontSize: '.78rem', fontWeight: 500,
                  color: s.time.startsWith('Today') ? '#d97706' : s.time.startsWith('Tomorrow') ? '#60a5fa' : 'var(--muted)',
                }}>{s.time}</span>
              </div>
              <div style={{ fontSize: '.8rem', color: 'var(--muted)' }}>
                {s.customer} · {s.agent}
              </div>
            </div>
          ))}
          <div style={{
            padding: '10px 18px', borderTop: '1px solid var(--line)',
            textAlign: 'center',
          }}>
            <a href="#" style={{
              fontSize: '.8rem', color: 'var(--accent)', textDecoration: 'none',
              fontWeight: 500,
            }}>View full schedule →</a>
          </div>
        </div>
      </div>
    </div>
  );
}
