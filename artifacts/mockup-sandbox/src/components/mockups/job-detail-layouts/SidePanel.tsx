import React, { useState } from 'react';

const tabs = ['Job', 'Notes & Docs', 'Schedule', 'Forms', 'Settings'];

export default function SidePanel() {
  const [activeTab, setActiveTab] = useState('Job');

  return (
    <div style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', background: '#fff', minHeight: '100vh', color: '#111827' }}>
      {/* Top bar: job ref + status */}
      <div style={{ padding: '10px 20px', borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 20, background: '#fff' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
          <span style={{ fontWeight: 700, fontSize: '1rem', color: '#2563eb' }}>2601071</span>
          <span style={{ fontWeight: 600, fontSize: '.92rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>THE TRUSTEE FOR THE SAPAVADIYA FAMILY TRUST</span>
          <select style={{ background: '#22c55e15', color: '#22c55e', border: '1.5px solid #22c55e40', borderRadius: 99, padding: '3px 10px', fontSize: '.76rem', fontWeight: 600, appearance: 'none' as const }}>
            <option>Active</option>
          </select>
        </div>
        <button style={{ padding: '4px 10px', fontSize: '.76rem', background: '#2563eb', color: '#fff', border: 0, borderRadius: 8, cursor: 'pointer', fontWeight: 500, flexShrink: 0 }}>+ New Job</button>
      </div>

      {/* Action buttons + warning badge */}
      <div style={{ padding: '6px 20px', borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {['Add to Job ▾', 'Create Doc ▾', 'Copy ▾', 'Message ▾', 'Add Booking'].map(b => (
            <button key={b} style={{ padding: '4px 10px', fontSize: '.72rem', background: '#2563eb', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer', fontWeight: 500 }}>{b}</button>
          ))}
        </div>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: 6, padding: '3px 10px', fontSize: '.72rem', color: '#92400e', flexShrink: 0 }}>
          <span>⚠ 6 unfinished updates</span>
          <button style={{ padding: '1px 7px', fontSize: '.66rem', background: '#f59e0b', color: '#fff', border: 0, borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}>View</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', minHeight: 'calc(100vh - 86px)' }}>
        {/* Main content */}
        <div style={{ borderRight: '1px solid #e5e7eb' }}>
          {/* Tabs */}
          <div style={{ display: 'flex', gap: 0, borderBottom: '2px solid #e5e7eb', padding: '0 20px' }}>
            {tabs.map(t => (
              <button key={t} onClick={() => setActiveTab(t)} style={{ padding: '8px 16px', fontSize: '.82rem', fontWeight: activeTab === t ? 600 : 400, color: activeTab === t ? '#2563eb' : '#6b7280', borderBottom: `2px solid ${activeTab === t ? '#2563eb' : 'transparent'}`, background: 'none', border: 'none', cursor: 'pointer', marginBottom: -2 }}>
                {t}
                {t === 'Notes & Docs' && <span style={{ background: '#ef4444', color: '#fff', borderRadius: 99, padding: '0 5px', fontSize: '.62rem', marginLeft: 4, fontWeight: 600 }}>14</span>}
                {t === 'Schedule' && <span style={{ background: '#e5e7eb', color: '#6b7280', borderRadius: 99, padding: '0 5px', fontSize: '.62rem', marginLeft: 4 }}>1</span>}
              </button>
            ))}
          </div>

          {/* Content area */}
          <div style={{ padding: '14px 20px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Customer */}
            <div style={{ padding: '12px 14px', background: '#f9fafb', borderRadius: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: '.7rem', fontWeight: 700, color: '#6b7280', letterSpacing: '.04em' }}>CUSTOMER(S)</span>
                <div style={{ display: 'flex', gap: 4 }}>
                  <button style={{ fontSize: '.66rem', padding: '2px 7px', border: '1px solid #e5e7eb', borderRadius: 4, background: '#fff', color: '#374151', cursor: 'pointer' }}>Open in Maps</button>
                  <button style={{ fontSize: '.66rem', padding: '2px 7px', border: '1px solid #e5e7eb', borderRadius: 4, background: '#fff', color: '#374151', cursor: 'pointer' }}>Edit</button>
                </div>
              </div>
              <span style={{ fontSize: '.64rem', padding: '1px 6px', background: 'rgba(37,99,235,.12)', color: '#2563eb', borderRadius: 4, fontWeight: 600 }}>Debtor</span>
              <div style={{ fontWeight: 600, fontSize: '.86rem', marginTop: 4 }}>THE TRUSTEE FOR THE SAPAVADIYA FAMILY TRUST & RUDRAKSH HOLDING PTY LTD</div>
              <div style={{ fontSize: '.82rem' }}>Jay PATEL</div>
              <div style={{ fontSize: '.8rem', color: '#2563eb', marginTop: 2 }}>0420201910</div>
            </div>

            {/* Client */}
            <div style={{ padding: '12px 14px', background: 'rgba(37,99,235,.04)', borderRadius: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: '.7rem', fontWeight: 700, color: '#2563eb', letterSpacing: '.04em' }}>CLIENT</span>
                <button style={{ fontSize: '.68rem', padding: '3px 10px', background: '#2563eb', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer' }}>+ Add Client</button>
              </div>
              <div style={{ fontSize: '.82rem', color: '#ef4444', fontWeight: 600 }}>Not linked — use Add Client to assign</div>
            </div>

            {/* Lender */}
            <div style={{ padding: '12px 14px', background: '#f9fafb', borderRadius: 10 }}>
              <div style={{ fontSize: '.7rem', fontWeight: 700, color: '#6b7280', letterSpacing: '.04em', marginBottom: 8 }}>LENDER DETAILS</div>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 6, marginBottom: 6 }}>
                {[['LENDER', 'VWFS'], ['ACCOUNT NO.', '1105322'], ['CONTRACT', 'Unregulated']].map(([l, v]) => (
                  <div key={l}>
                    <div style={{ fontSize: '.6rem', color: '#9ca3af' }}>{l}</div>
                    <div style={{ fontSize: '.82rem', fontWeight: 600 }}>{v}</div>
                  </div>
                ))}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
                {[['ARREARS', '$0.00'], ['COSTS', '$1,259.50'], ['NEXT PMT', '$0.00'], ['DUE DATE', '30/01/2026']].map(([l, v]) => (
                  <div key={l}>
                    <div style={{ fontSize: '.6rem', color: '#9ca3af' }}>{l}</div>
                    <div style={{ fontSize: '.82rem', fontWeight: 600 }}>{v}</div>
                  </div>
                ))}
              </div>
              <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: 6, marginTop: 8, display: 'flex', gap: 20 }}>
                <div>
                  <div style={{ fontSize: '.58rem', color: '#9ca3af' }}>GROSS DUE</div>
                  <div style={{ fontWeight: 700, fontSize: '.92rem' }}>$1,259.50</div>
                </div>
                <div>
                  <div style={{ fontSize: '.58rem', color: '#9ca3af' }}>TOTAL DUE NOW</div>
                  <div style={{ fontWeight: 700, fontSize: '1rem', color: '#2563eb' }}>$1,259.50</div>
                </div>
              </div>
            </div>

            {/* Security */}
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 10, overflow: 'hidden' }}>
              <div style={{ padding: '8px 14px', fontWeight: 650, fontSize: '.85rem', background: '#fafafa', borderBottom: '1px solid #e5e7eb' }}>Security/s</div>
              <div style={{ padding: '10px 14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ padding: '2px 6px', background: '#e5e7eb', borderRadius: 4, fontSize: '.68rem', fontWeight: 600 }}>vehicle</span>
                    <span style={{ fontWeight: 600, fontFamily: 'monospace', fontSize: '.86rem' }}>2DI9ZK</span>
                    <span style={{ fontSize: '.8rem', color: '#6b7280' }}>— 2018 LAND ROVER RANGE ROVER VE</span>
                  </div>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button style={{ padding: '3px 8px', fontSize: '.7rem', background: '#16a34a', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer' }}>VicRoads</button>
                    <button style={{ padding: '3px 8px', fontSize: '.7rem', background: '#dc2626', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer' }}>Repo Lock</button>
                  </div>
                </div>
                <div style={{ fontSize: '.76rem', color: '#6b7280', marginTop: 2 }}>VIN: SALYA2AK9JA725936</div>
              </div>
            </div>
          </div>
        </div>

        {/* Right sidebar */}
        <div style={{ padding: '14px', background: '#f9fafb', fontSize: '.82rem' }}>
          {/* Quick info */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: '.68rem', fontWeight: 700, color: '#9ca3af', letterSpacing: '.04em', marginBottom: 8 }}>JOB INFO</div>
            {[
              ['Job Type', 'Repo/Collect'],
              ['Visit Type', 'New Visit'],
              ['Priority', 'Normal'],
              ['Internal Ref', '2601071'],
              ['Client Ref', '1105322'],
            ].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #e5e7eb' }}>
                <span style={{ color: '#6b7280', fontSize: '.78rem' }}>{k}</span>
                <span style={{ fontWeight: 500, fontSize: '.78rem' }}>{v}</span>
              </div>
            ))}
          </div>

          {/* Agent */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: '.68rem', fontWeight: 700, color: '#9ca3af', letterSpacing: '.04em', marginBottom: 8 }}>ASSIGNED</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb' }}>
              <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 700, fontSize: '.72rem' }}>DC</div>
              <div>
                <div style={{ fontWeight: 600, fontSize: '.82rem' }}>DanielC</div>
                <div style={{ fontSize: '.7rem', color: '#6b7280' }}>Field Agent</div>
              </div>
            </div>
          </div>

          {/* Next schedule */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: '.68rem', fontWeight: 700, color: '#9ca3af', letterSpacing: '.04em', marginBottom: 8 }}>NEXT SCHEDULE</div>
            <div style={{ padding: '8px 10px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8 }}>
              <div style={{ fontWeight: 600, fontSize: '.84rem', color: '#ef4444' }}>OVERDUE</div>
              <div style={{ fontSize: '.82rem', color: '#991b1b' }}>30/01/2026 09:00</div>
              <div style={{ fontSize: '.72rem', color: '#6b7280', marginTop: 2 }}>New Visit · DanielC</div>
            </div>
          </div>

          {/* Payments */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div style={{ fontSize: '.68rem', fontWeight: 700, color: '#9ca3af', letterSpacing: '.04em' }}>PAYMENTS</div>
              <button style={{ fontSize: '.66rem', padding: '2px 8px', background: '#2563eb', color: '#fff', border: 0, borderRadius: 4, cursor: 'pointer' }}>+ Add</button>
            </div>
            <div style={{ padding: '14px 10px', border: '1.5px dashed #e5e7eb', borderRadius: 8, textAlign: 'center', color: '#9ca3af', fontSize: '.78rem' }}>
              No payments yet
            </div>
          </div>

          {/* Financial summary */}
          <div style={{ padding: '10px', background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ color: '#6b7280', fontSize: '.76rem' }}>Gross Due</span>
              <span style={{ fontWeight: 600, fontSize: '.82rem' }}>$1,259.50</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ color: '#6b7280', fontSize: '.76rem' }}>Payments</span>
              <span style={{ fontWeight: 600, fontSize: '.82rem', color: '#16a34a' }}>$0.00</span>
            </div>
            <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: 6, marginTop: 4, display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontWeight: 700, fontSize: '.82rem' }}>Net Due</span>
              <span style={{ fontWeight: 700, fontSize: '.95rem', color: '#2563eb' }}>$1,259.50</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
