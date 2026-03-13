import React, { useState } from 'react';

const statusColor: Record<string, string> = {
  Active: '#22c55e',
  New: '#3b82f6',
  Suspended: '#f59e0b',
  Completed: '#14b8a6',
  Invoiced: '#a855f7',
};

const tabs = ['Job', 'Notes & Docs', 'Schedule', 'Forms', 'Settings'];

export default function CondensedHeader() {
  const [activeTab, setActiveTab] = useState('Job');
  const sc = statusColor['Active'];

  return (
    <div style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', background: '#fff', minHeight: '100vh', color: '#111827' }}>
      {/* Compact Header */}
      <div style={{ padding: '10px 20px', borderBottom: '1px solid #e5e7eb', background: '#fff', position: 'sticky', top: 0, zIndex: 20 }}>
        {/* Row 1: Job ref + status + actions */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            <span style={{ fontWeight: 700, fontSize: '1rem', color: '#2563eb', whiteSpace: 'nowrap' }}>2601071</span>
            <span style={{ fontWeight: 600, fontSize: '.92rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>THE TRUSTEE FOR THE SAPAVADIYA FAMILY TRUST</span>
            <span style={{ fontSize: '.72rem', color: '#6b7280', whiteSpace: 'nowrap' }}>Client Ref: 1105322</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
            <select style={{ background: `${sc}15`, color: sc, border: `1.5px solid ${sc}40`, borderRadius: 99, padding: '3px 24px 3px 10px', fontSize: '.78rem', fontWeight: 600, appearance: 'none' as const, cursor: 'pointer' }}>
              <option>Active</option>
            </select>
            <button style={{ padding: '4px 10px', fontSize: '.78rem', background: '#2563eb', color: '#fff', border: 0, borderRadius: 8, cursor: 'pointer', fontWeight: 500 }}>+ New Job</button>
          </div>
        </div>

        {/* Row 2: Meta info inline */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, fontSize: '.76rem', color: '#6b7280', marginBottom: 8 }}>
          <span>Repo/Collect</span>
          <span style={{ color: '#d4d4d8' }}>·</span>
          <span>New Visit</span>
          <span style={{ color: '#d4d4d8' }}>·</span>
          <span>Priority: Normal</span>
          <span style={{ color: '#d4d4d8' }}>·</span>
          <span style={{ color: '#2563eb', fontWeight: 500 }}>DanielC</span>
          <span style={{ color: '#d4d4d8' }}>·</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <span style={{ color: '#ef4444', fontWeight: 600, fontSize: '.65rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 3, padding: '0 4px' }}>OVERDUE</span>
            30/01/2026 09:00
          </span>
        </div>

        {/* Row 3: Action buttons + tabs combined */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div style={{ display: 'flex', gap: 4 }}>
            {['Add to Job ▾', 'Create Doc ▾', 'Copy ▾', 'Message ▾', 'Add Booking'].map(b => (
              <button key={b} style={{ padding: '4px 10px', fontSize: '.74rem', background: '#f3f4f6', color: '#374151', border: '1px solid #e5e7eb', borderRadius: 6, cursor: 'pointer', fontWeight: 500 }}>{b}</button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 2 }}>
            {tabs.map(t => (
              <button key={t} onClick={() => setActiveTab(t)} style={{ padding: '6px 14px', fontSize: '.82rem', fontWeight: activeTab === t ? 600 : 400, color: activeTab === t ? '#2563eb' : '#6b7280', borderBottom: activeTab === t ? '2px solid #2563eb' : '2px solid transparent', background: 'none', border: 'none', borderTop: 'none', borderLeft: 'none', borderRight: 'none', cursor: 'pointer', borderBottomWidth: 2, borderBottomStyle: 'solid', borderBottomColor: activeTab === t ? '#2563eb' : 'transparent' }}>
                {t}
                {t === 'Notes & Docs' && <span style={{ background: '#ef4444', color: '#fff', borderRadius: 99, padding: '0 5px', fontSize: '.62rem', marginLeft: 4, fontWeight: 600 }}>14</span>}
                {t === 'Schedule' && <span style={{ background: '#e5e7eb', color: '#6b7280', borderRadius: 99, padding: '0 5px', fontSize: '.62rem', marginLeft: 4 }}>1</span>}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Warning banner */}
      <div style={{ margin: '12px 20px 0', padding: '8px 14px', background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: 8, fontSize: '.8rem', color: '#92400e', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>⚠ You have 6 unfinished attendance updates requiring completion.</span>
        <button style={{ padding: '3px 10px', fontSize: '.74rem', background: '#f59e0b', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer' }}>View Drafts</button>
      </div>

      {/* Content */}
      <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Customer + Client row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div style={{ padding: '14px 16px', background: '#f9fafb', borderRadius: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: '.72rem', fontWeight: 700, color: '#6b7280', letterSpacing: '.04em' }}>CUSTOMER(S)</span>
              <div style={{ display: 'flex', gap: 6 }}>
                <button style={{ fontSize: '.68rem', padding: '2px 8px', border: '1px solid #e5e7eb', borderRadius: 6, background: '#fff', color: '#374151', cursor: 'pointer' }}>Open in Maps</button>
              </div>
            </div>
            <span style={{ fontSize: '.66rem', padding: '1px 7px', background: 'rgba(37,99,235,.12)', color: '#2563eb', borderRadius: 4, fontWeight: 600 }}>Debtor</span>
            <div style={{ fontWeight: 600, fontSize: '.88rem', marginTop: 4 }}>THE TRUSTEE FOR THE SAPAVADIYA FAMILY TRUST & RUDRAKSH HOLDING PTY LTD</div>
            <div style={{ fontSize: '.84rem' }}>Jay PATEL</div>
            <div style={{ fontSize: '.82rem', color: '#2563eb', marginTop: 2 }}>0420201910</div>
            <button style={{ marginTop: 4, fontSize: '.68rem', padding: '2px 7px', border: '1px solid #e5e7eb', borderRadius: 4, background: '#fff', color: '#374151', cursor: 'pointer' }}>Edit</button>
          </div>

          <div style={{ padding: '14px 16px', background: 'rgba(37,99,235,.04)', borderRadius: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: '.72rem', fontWeight: 700, color: '#2563eb', letterSpacing: '.04em' }}>CLIENT</span>
              <button style={{ fontSize: '.68rem', padding: '3px 10px', background: '#2563eb', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer' }}>+ Add Client</button>
            </div>
            <div style={{ fontSize: '.84rem', color: '#ef4444', fontWeight: 600 }}>Not linked — use Add Client to assign</div>
          </div>
        </div>

        {/* Lender + Payments */}
        <div style={{ padding: '14px 16px', background: '#f9fafb', borderRadius: 10 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: 20 }}>
            <div>
              <div style={{ fontSize: '.72rem', fontWeight: 700, color: '#6b7280', letterSpacing: '.04em', marginBottom: 10 }}>LENDER DETAILS</div>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 8, marginBottom: 8 }}>
                {[['LENDER', 'VWFS'], ['ACCOUNT NO.', '1105322'], ['CONTRACT', 'Unregulated']].map(([l, v]) => (
                  <div key={l}>
                    <div style={{ fontSize: '.62rem', color: '#9ca3af', letterSpacing: '.03em' }}>{l}</div>
                    <div style={{ fontSize: '.84rem', fontWeight: 600 }}>{v}</div>
                  </div>
                ))}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 8 }}>
                {[['ARREARS', '$0.00'], ['COSTS', '$1,259.50'], ['NEXT PMT DUE', '$0.00'], ['PMT DUE DATE', '30/01/2026']].map(([l, v]) => (
                  <div key={l}>
                    <div style={{ fontSize: '.62rem', color: '#9ca3af', letterSpacing: '.03em' }}>{l}</div>
                    <div style={{ fontSize: '.84rem', fontWeight: 600 }}>{v}</div>
                  </div>
                ))}
              </div>
              <div style={{ borderTop: '1px solid #e5e7eb', paddingTop: 8, display: 'flex', gap: 24 }}>
                <div>
                  <div style={{ fontSize: '.6rem', color: '#9ca3af' }}>GROSS DUE</div>
                  <div style={{ fontWeight: 700, fontSize: '.95rem' }}>$1,259.50</div>
                </div>
                <div>
                  <div style={{ fontSize: '.6rem', color: '#9ca3af' }}>TOTAL DUE NOW</div>
                  <div style={{ fontWeight: 700, fontSize: '1.05rem', color: '#2563eb' }}>$1,259.50</div>
                </div>
              </div>
              <button style={{ marginTop: 8, fontSize: '.74rem', padding: '4px 12px', border: '1px solid #e5e7eb', borderRadius: 6, background: '#fff', color: '#374151', cursor: 'pointer' }}>Edit Lender Details</button>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <div style={{ fontSize: '.72rem', fontWeight: 700, color: '#6b7280', letterSpacing: '.04em' }}>PAYMENTS RECEIVED</div>
                <button style={{ fontSize: '.72rem', padding: '3px 10px', background: '#2563eb', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer' }}>+ Enter Pmt</button>
              </div>
              <div style={{ border: '1.5px dashed #e5e7eb', borderRadius: 8, padding: '20px 12px', textAlign: 'center', color: '#9ca3af', fontSize: '.8rem' }}>
                No payments recorded yet.<br />
                <span style={{ fontSize: '.72rem' }}>Tap <strong>+ Enter Pmt</strong> to add one.</span>
              </div>
            </div>
          </div>
        </div>

        {/* Security */}
        <div style={{ border: '1px solid #e5e7eb', borderRadius: 10, overflow: 'hidden' }}>
          <div style={{ padding: '10px 16px', fontWeight: 650, fontSize: '.88rem', borderBottom: '1px solid #e5e7eb', background: '#fafafa' }}>Security/s</div>
          <div style={{ padding: '12px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ padding: '2px 8px', background: '#e5e7eb', borderRadius: 4, fontSize: '.7rem', fontWeight: 600, color: '#374151' }}>vehicle</span>
                <span style={{ fontWeight: 600, fontSize: '.88rem', fontFamily: 'monospace' }}>2DI9ZK</span>
                <span style={{ fontSize: '.82rem', color: '#6b7280' }}>— 2018 LAND ROVER RANGE ROVER VE</span>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button style={{ padding: '4px 10px', fontSize: '.72rem', background: '#16a34a', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer' }}>VicRoads</button>
                <button style={{ padding: '4px 10px', fontSize: '.72rem', background: '#dc2626', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer' }}>Repo Lock</button>
              </div>
            </div>
            <div style={{ fontSize: '.78rem', color: '#6b7280' }}>VIN: SALYA2AK9JA725936</div>
          </div>
        </div>
      </div>
    </div>
  );
}
