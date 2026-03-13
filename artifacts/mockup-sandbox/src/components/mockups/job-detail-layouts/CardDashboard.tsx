import React, { useState } from 'react';

const tabs = ['Job', 'Notes & Docs', 'Schedule', 'Forms', 'Settings'];

export default function CardDashboard() {
  const [activeTab, setActiveTab] = useState('Job');

  return (
    <div style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', background: '#f3f4f6', minHeight: '100vh', color: '#111827' }}>
      {/* Header */}
      <div style={{ padding: '12px 20px', background: '#fff', borderBottom: '1px solid #e5e7eb', position: 'sticky', top: 0, zIndex: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontWeight: 700, fontSize: '1rem', color: '#2563eb' }}>2601071</span>
            <span style={{ color: '#d4d4d8' }}>|</span>
            <span style={{ fontWeight: 600, fontSize: '.9rem' }}>THE TRUSTEE FOR THE SAPAVADIYA FAMILY TRUST</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <select style={{ background: '#22c55e15', color: '#22c55e', border: '1.5px solid #22c55e40', borderRadius: 99, padding: '3px 24px 3px 10px', fontSize: '.76rem', fontWeight: 600, appearance: 'none' as const }}>
              <option>Active</option>
            </select>
            <button style={{ padding: '4px 10px', fontSize: '.76rem', background: '#2563eb', color: '#fff', border: 0, borderRadius: 8, cursor: 'pointer' }}>+ New Job</button>
          </div>
        </div>

        {/* Meta + actions + tabs all in one row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div style={{ display: 'flex', gap: 2, borderBottom: '2px solid #e5e7eb', marginBottom: -1 }}>
            {tabs.map(t => (
              <button key={t} onClick={() => setActiveTab(t)} style={{ padding: '6px 14px', fontSize: '.8rem', fontWeight: activeTab === t ? 600 : 400, color: activeTab === t ? '#2563eb' : '#6b7280', borderBottom: `2px solid ${activeTab === t ? '#2563eb' : 'transparent'}`, background: 'none', border: 'none', cursor: 'pointer', marginBottom: -2 }}>
                {t}
                {t === 'Notes & Docs' && <span style={{ background: '#ef4444', color: '#fff', borderRadius: 99, padding: '0 5px', fontSize: '.6rem', marginLeft: 4, fontWeight: 600 }}>14</span>}
                {t === 'Schedule' && <span style={{ background: '#e5e7eb', color: '#6b7280', borderRadius: 99, padding: '0 5px', fontSize: '.6rem', marginLeft: 4 }}>1</span>}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 4, marginBottom: 4 }}>
            {['Add to Job ▾', 'Create Doc ▾', 'Copy ▾', 'Message ▾', 'Booking'].map(b => (
              <button key={b} style={{ padding: '4px 10px', fontSize: '.72rem', background: '#f9fafb', color: '#374151', border: '1px solid #e5e7eb', borderRadius: 6, cursor: 'pointer', fontWeight: 500 }}>{b}</button>
            ))}
          </div>
        </div>
      </div>

      {/* Warning */}
      <div style={{ margin: '12px 20px 0', padding: '8px 14px', background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: 8, fontSize: '.78rem', color: '#92400e', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>⚠ 6 unfinished attendance updates</span>
        <button style={{ padding: '2px 8px', fontSize: '.72rem', background: '#f59e0b', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer' }}>View Drafts</button>
      </div>

      {/* Summary strip */}
      <div style={{ margin: '12px 20px', display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
        {[
          { label: 'Job Type', value: 'Repo/Collect', sub: 'New Visit · Normal' },
          { label: 'Agent', value: 'DanielC', sub: 'Field Agent' },
          { label: 'Next Schedule', value: '30/01/2026', sub: 'OVERDUE', warn: true },
          { label: 'Client Ref', value: '1105322', sub: 'VWFS' },
          { label: 'Total Due', value: '$1,259.50', sub: 'Unregulated', accent: true },
        ].map(c => (
          <div key={c.label} style={{ padding: '10px 14px', background: '#fff', borderRadius: 10, border: `1px solid ${c.warn ? '#fecaca' : '#e5e7eb'}` }}>
            <div style={{ fontSize: '.64rem', color: '#9ca3af', fontWeight: 600, letterSpacing: '.03em', marginBottom: 4 }}>{c.label}</div>
            <div style={{ fontWeight: 700, fontSize: '.92rem', color: c.warn ? '#ef4444' : c.accent ? '#2563eb' : '#111827' }}>{c.value}</div>
            <div style={{ fontSize: '.7rem', color: c.warn ? '#ef4444' : '#6b7280', fontWeight: c.warn ? 600 : 400 }}>{c.sub}</div>
          </div>
        ))}
      </div>

      {/* Card grid */}
      <div style={{ padding: '0 20px 20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {/* Customer card */}
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', overflow: 'hidden' }}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 650, fontSize: '.84rem' }}>Customer(s)</span>
            <div style={{ display: 'flex', gap: 4 }}>
              <button style={{ fontSize: '.66rem', padding: '2px 7px', border: '1px solid #e5e7eb', borderRadius: 4, background: '#fff', color: '#374151', cursor: 'pointer' }}>Maps</button>
              <button style={{ fontSize: '.66rem', padding: '2px 7px', border: '1px solid #e5e7eb', borderRadius: 4, background: '#fff', color: '#374151', cursor: 'pointer' }}>Edit</button>
            </div>
          </div>
          <div style={{ padding: '12px 14px' }}>
            <span style={{ fontSize: '.64rem', padding: '1px 6px', background: 'rgba(37,99,235,.12)', color: '#2563eb', borderRadius: 4, fontWeight: 600 }}>Debtor</span>
            <div style={{ fontWeight: 600, fontSize: '.84rem', marginTop: 4 }}>THE TRUSTEE FOR THE SAPAVADIYA FAMILY TRUST & RUDRAKSH HOLDING PTY LTD</div>
            <div style={{ fontSize: '.82rem', marginTop: 2 }}>Jay PATEL</div>
            <div style={{ fontSize: '.8rem', color: '#2563eb', marginTop: 2 }}>0420201910</div>
          </div>
        </div>

        {/* Client card */}
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', overflow: 'hidden' }}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 650, fontSize: '.84rem', color: '#2563eb' }}>Client</span>
            <button style={{ fontSize: '.68rem', padding: '3px 10px', background: '#2563eb', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer' }}>+ Add Client</button>
          </div>
          <div style={{ padding: '12px 14px' }}>
            <div style={{ fontSize: '.82rem', color: '#ef4444', fontWeight: 600 }}>Not linked — use Add Client to assign</div>
          </div>
        </div>

        {/* Lender card */}
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', overflow: 'hidden' }}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontWeight: 650, fontSize: '.84rem' }}>Lender Details</span>
            <button style={{ fontSize: '.66rem', padding: '2px 7px', border: '1px solid #e5e7eb', borderRadius: 4, background: '#fff', color: '#374151', cursor: 'pointer' }}>Edit</button>
          </div>
          <div style={{ padding: '12px 14px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 6, marginBottom: 8 }}>
              {[['LENDER', 'VWFS'], ['ACCOUNT', '1105322'], ['CONTRACT', 'Unregulated']].map(([l, v]) => (
                <div key={l}>
                  <div style={{ fontSize: '.6rem', color: '#9ca3af' }}>{l}</div>
                  <div style={{ fontSize: '.82rem', fontWeight: 600 }}>{v}</div>
                </div>
              ))}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
              {[['ARREARS', '$0.00'], ['COSTS', '$1,259.50'], ['NEXT PMT', '$0.00'], ['DUE DATE', '30/01/26']].map(([l, v]) => (
                <div key={l}>
                  <div style={{ fontSize: '.6rem', color: '#9ca3af' }}>{l}</div>
                  <div style={{ fontSize: '.82rem', fontWeight: 600 }}>{v}</div>
                </div>
              ))}
            </div>
            <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: 8, marginTop: 8, display: 'flex', gap: 24, alignItems: 'baseline' }}>
              <div>
                <div style={{ fontSize: '.58rem', color: '#9ca3af' }}>GROSS DUE</div>
                <div style={{ fontWeight: 700, fontSize: '.9rem' }}>$1,259.50</div>
              </div>
              <div>
                <div style={{ fontSize: '.58rem', color: '#9ca3af' }}>TOTAL DUE NOW</div>
                <div style={{ fontWeight: 700, fontSize: '1rem', color: '#2563eb' }}>$1,259.50</div>
              </div>
            </div>
          </div>
        </div>

        {/* Payments card */}
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', overflow: 'hidden' }}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontWeight: 650, fontSize: '.84rem' }}>Payments Received</span>
            <button style={{ fontSize: '.68rem', padding: '3px 10px', background: '#2563eb', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer' }}>+ Enter Pmt</button>
          </div>
          <div style={{ padding: '16px 14px', textAlign: 'center' }}>
            <div style={{ border: '1.5px dashed #e5e7eb', borderRadius: 8, padding: '20px 12px', color: '#9ca3af', fontSize: '.8rem' }}>
              No payments recorded yet.<br />
              <span style={{ fontSize: '.72rem' }}>Tap <strong>+ Enter Pmt</strong> to add one.</span>
            </div>
          </div>
        </div>

        {/* Security card - full width */}
        <div style={{ gridColumn: '1 / -1', background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', overflow: 'hidden' }}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontWeight: 650, fontSize: '.84rem' }}>Security/s</span>
            <button style={{ fontSize: '.66rem', padding: '2px 7px', border: '1px solid #e5e7eb', borderRadius: 4, background: '#fff', color: '#374151', cursor: 'pointer' }}>+ Add Security</button>
          </div>
          <div style={{ padding: '10px 14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ padding: '2px 6px', background: '#e5e7eb', borderRadius: 4, fontSize: '.68rem', fontWeight: 600 }}>vehicle</span>
                <span style={{ fontWeight: 700, fontFamily: 'monospace', fontSize: '.88rem' }}>2DI9ZK</span>
                <span style={{ fontSize: '.82rem', color: '#6b7280' }}>— 2018 LAND ROVER RANGE ROVER VE</span>
              </div>
              <div style={{ display: 'flex', gap: 4 }}>
                <button style={{ padding: '3px 8px', fontSize: '.7rem', background: '#16a34a', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer' }}>VicRoads</button>
                <button style={{ padding: '3px 8px', fontSize: '.7rem', background: '#dc2626', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer' }}>Repo Lock</button>
                <button style={{ padding: '3px 8px', fontSize: '.7rem', border: '1px solid #e5e7eb', background: '#fff', color: '#374151', borderRadius: 6, cursor: 'pointer' }}>Edit</button>
              </div>
            </div>
            <div style={{ fontSize: '.76rem', color: '#6b7280', marginTop: 2 }}>VIN: SALYA2AK9JA725936</div>
          </div>
        </div>
      </div>
    </div>
  );
}
