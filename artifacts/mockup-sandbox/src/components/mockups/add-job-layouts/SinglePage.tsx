import { useState } from "react";
import { ChevronDown, ChevronRight, Upload, Plus, Search, Calendar, Clock, User, FileText, Car, Building2, DollarSign, MapPin, Hash, ClipboardList } from "lucide-react";

function Section({ title, icon: Icon, defaultOpen = true, children, badge }: {
  title: string; icon: any; defaultOpen?: boolean; children: React.ReactNode; badge?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 10, background: "#fff", overflow: "hidden" }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 8, padding: "10px 14px",
          background: open ? "#f8fafc" : "#fff", border: "none", cursor: "pointer",
          borderBottom: open ? "1px solid #e5e7eb" : "none", transition: "all .15s"
        }}
      >
        {open ? <ChevronDown size={16} color="#6b7280" /> : <ChevronRight size={16} color="#6b7280" />}
        <Icon size={16} color="#2563eb" />
        <span style={{ fontWeight: 600, fontSize: ".85rem", color: "#1e293b" }}>{title}</span>
        {badge && <span style={{ marginLeft: "auto", fontSize: ".7rem", background: "#dbeafe", color: "#2563eb", padding: "1px 8px", borderRadius: 99, fontWeight: 600 }}>{badge}</span>}
      </button>
      {open && <div style={{ padding: "12px 14px" }}>{children}</div>}
    </div>
  );
}

function Field({ label, placeholder, width, value, type, children }: {
  label: string; placeholder?: string; width?: string; value?: string; type?: string; children?: React.ReactNode;
}) {
  return (
    <div style={{ flex: width || "1", minWidth: 0 }}>
      <label style={{ display: "block", fontSize: ".72rem", fontWeight: 600, color: "#6b7280", marginBottom: 3, letterSpacing: ".03em" }}>{label}</label>
      {children || (
        <input
          type={type || "text"}
          value={value}
          placeholder={placeholder}
          readOnly
          style={{
            width: "100%", padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 7,
            fontSize: ".82rem", color: "#1e293b", background: value ? "#eff6ff" : "#fff", outline: "none"
          }}
        />
      )}
    </div>
  );
}

function SelectField({ label, value, options }: { label: string; value: string; options: string[] }) {
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <label style={{ display: "block", fontSize: ".72rem", fontWeight: 600, color: "#6b7280", marginBottom: 3, letterSpacing: ".03em" }}>{label}</label>
      <select
        defaultValue={value}
        style={{
          width: "100%", padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 7,
          fontSize: ".82rem", color: "#1e293b", background: "#fff", outline: "none", cursor: "pointer"
        }}
      >
        {options.map(o => <option key={o}>{o}</option>)}
      </select>
    </div>
  );
}

export function SinglePage() {
  return (
    <div style={{ minHeight: "100vh", background: "#f1f5f9", fontFamily: "'Inter', system-ui, sans-serif" }}>
      <div style={{ maxWidth: 820, margin: "0 auto", padding: "20px 16px 40px" }}>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div>
            <h1 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>New Job</h1>
            <p style={{ fontSize: ".78rem", color: "#64748b", margin: "2px 0 0" }}>Fill in details below. Sections can be expanded as needed.</p>
          </div>
          <button style={{
            display: "flex", alignItems: "center", gap: 6, padding: "7px 14px", background: "#fff",
            border: "1px solid #d1d5db", borderRadius: 8, fontSize: ".8rem", color: "#374151", cursor: "pointer"
          }}>
            <Upload size={14} /> Upload to auto-fill
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>

          <Section title="Job Identification" icon={Hash} defaultOpen={true}>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <Field label="JOB NUMBER" value="2603002" width="140px" />
              <Field label="CONTRACT NUMBER" placeholder="e.g., AMO18972" />
              <Field label="CLIENT JOB NUMBER" placeholder="e.g., CJN-001" />
            </div>
            <div style={{ fontSize: ".72rem", color: "#9ca3af", marginTop: 4 }}>Auto-generated · Type contract # to search previous jobs and clone</div>
          </Section>

          <Section title="Client & Customer" icon={Building2} defaultOpen={true}>
            <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: "block", fontSize: ".72rem", fontWeight: 600, color: "#6b7280", marginBottom: 3 }}>CLIENT</label>
                <div style={{ display: "flex", gap: 6 }}>
                  <div style={{ flex: 1, position: "relative" }}>
                    <Search size={14} style={{ position: "absolute", left: 8, top: 8, color: "#9ca3af" }} />
                    <input placeholder="Search client..." readOnly style={{
                      width: "100%", padding: "6px 10px 6px 28px", border: "1px solid #d1d5db", borderRadius: 7,
                      fontSize: ".82rem", background: "#fff", outline: "none"
                    }} />
                  </div>
                  <button style={{ padding: "4px 10px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 7, fontSize: ".75rem", fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap" }}>+ New</button>
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: "block", fontSize: ".72rem", fontWeight: 600, color: "#6b7280", marginBottom: 3 }}>CUSTOMER</label>
                <div style={{ display: "flex", gap: 6 }}>
                  <div style={{ flex: 1, position: "relative" }}>
                    <Search size={14} style={{ position: "absolute", left: 8, top: 8, color: "#9ca3af" }} />
                    <input placeholder="Search customer..." readOnly style={{
                      width: "100%", padding: "6px 10px 6px 28px", border: "1px solid #d1d5db", borderRadius: 7,
                      fontSize: ".82rem", background: "#fff", outline: "none"
                    }} />
                  </div>
                  <button style={{ padding: "4px 10px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 7, fontSize: ".75rem", fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap" }}>+ New</button>
                </div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <Field label="CUSTOMER ADDRESS" placeholder="Street, Suburb, State, Postcode" />
            </div>
            <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
              <Field label="JOB ADDRESS" placeholder="Street, Suburb, State, Postcode" />
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6, fontSize: ".78rem", color: "#6b7280", cursor: "pointer" }}>
              <input type="checkbox" defaultChecked style={{ accentColor: "#2563eb" }} /> Same as customer address
            </label>
          </Section>

          <Section title="Job Classification" icon={ClipboardList} defaultOpen={true}>
            <div style={{ display: "flex", gap: 10 }}>
              <SelectField label="JOB TYPE" value="Collect Only" options={["Collect Only", "Investigate", "Field Call", "Locate & Collect", "Skip Trace"]} />
              <SelectField label="VISIT TYPE" value="New Visit" options={["New Visit", "Revisit", "Final Visit"]} />
              <SelectField label="STATUS" value="New" options={["New", "Active", "Suspended"]} />
              <SelectField label="PRIORITY" value="Normal" options={["Normal", "Urgent", "Low"]} />
            </div>
          </Section>

          <Section title="Lender & Financial" icon={DollarSign} defaultOpen={false} badge="Optional">
            <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
              <Field label="LENDER" placeholder="e.g. Nissan Finance" />
              <Field label="ACCOUNT NUMBER" placeholder="e.g. 1234567" />
              <SelectField label="REGULATION" value="Select..." options={["Select...", "Regulated", "Unregulated"]} />
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <Field label="ARREARS" value="$0.00" width="120px" />
              <Field label="COSTS" value="$0.00" width="120px" />
              <Field label="MMP" value="$0.00" width="120px" />
              <Field label="DUE DATE" placeholder="dd/mm/yyyy" type="date" />
            </div>
          </Section>

          <Section title="Security / Asset" icon={Car} defaultOpen={false} badge="Optional">
            <div style={{ padding: "10px 12px", background: "#f8fafc", borderRadius: 8, border: "1px solid #e5e7eb" }}>
              <div style={{ display: "flex", gap: 10, marginBottom: 8 }}>
                <SelectField label="TYPE" value="Vehicle" options={["Vehicle", "Equipment", "Property", "Other"]} />
                <Field label="DESCRIPTION" placeholder="e.g. 2019 Ford Ranger XL" />
              </div>
              <div style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
                <Field label="YEAR" placeholder="2019" width="70px" />
                <Field label="MAKE" placeholder="Ford" width="100px" />
                <Field label="MODEL" placeholder="Ranger" width="100px" />
                <Field label="COLOUR" placeholder="White" width="90px" />
              </div>
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                <Field label="REGO" placeholder="ABC123" />
                <Field label="VIN" placeholder="VIN number" />
                <Field label="ENGINE" placeholder="Engine #" />
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <Field label="ASSET ADDRESS" placeholder="Property/site address" />
                <Field label="SERIAL" placeholder="Serial (equipment)" width="180px" />
              </div>
            </div>
            <button style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 8, padding: "4px 12px", background: "none", border: "1px dashed #d1d5db", borderRadius: 7, fontSize: ".78rem", color: "#2563eb", cursor: "pointer", fontWeight: 600 }}>
              <Plus size={14} /> Add Another Security
            </button>
          </Section>

          <Section title="Instructions & Delivery" icon={FileText} defaultOpen={false} badge="Optional">
            <div style={{ marginBottom: 10 }}>
              <Field label="DELIVER TO" placeholder="Type auction yard name..." />
            </div>
            <div>
              <label style={{ display: "block", fontSize: ".72rem", fontWeight: 600, color: "#6b7280", marginBottom: 3 }}>DESCRIPTION & INSTRUCTIONS</label>
              <textarea
                placeholder="Job description, field agent instructions, access codes, contact times, background information..."
                readOnly
                style={{
                  width: "100%", minHeight: 80, padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 7,
                  fontSize: ".82rem", resize: "vertical", fontFamily: "inherit", outline: "none"
                }}
              />
              <div style={{ fontSize: ".7rem", color: "#9ca3af", marginTop: 2 }}>Visible to assigned agents on their job view</div>
            </div>
          </Section>

          <Section title="Schedule" icon={Calendar} defaultOpen={false} badge="Optional">
            <p style={{ fontSize: ".78rem", color: "#64748b", margin: "0 0 10px" }}>Optionally create an initial booking when the job is saved.</p>
            <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: "block", fontSize: ".72rem", fontWeight: 600, color: "#6b7280", marginBottom: 3 }}>BOOKING TYPE</label>
                <div style={{ position: "relative" }}>
                  <Search size={14} style={{ position: "absolute", left: 8, top: 8, color: "#9ca3af" }} />
                  <input placeholder="Type to search or enter new..." readOnly style={{
                    width: "100%", padding: "6px 10px 6px 28px", border: "1px solid #d1d5db", borderRadius: 7,
                    fontSize: ".82rem", background: "#fff", outline: "none"
                  }} />
                </div>
              </div>
              <Field label="DATE" value="14/03/2026" type="date" width="150px" />
              <Field label="TIME" value="09:00" type="time" width="120px" />
            </div>
            <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
              <SelectField label="ASSIGNED TO" value="— Unassigned —" options={["— Unassigned —", "Grant Cook", "John Smith"]} />
              <div style={{ flex: 2 }} />
            </div>
            <div>
              <label style={{ display: "block", fontSize: ".72rem", fontWeight: 600, color: "#6b7280", marginBottom: 3 }}>SCHEDULE NOTES</label>
              <textarea
                placeholder="Notes for this appointment..."
                readOnly
                style={{
                  width: "100%", minHeight: 50, padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 7,
                  fontSize: ".82rem", resize: "vertical", fontFamily: "inherit", outline: "none"
                }}
              />
            </div>
          </Section>

        </div>

        <div style={{
          position: "sticky", bottom: 0, background: "#f1f5f9", padding: "14px 0 4px",
          display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 10,
          borderTop: "1px solid #e5e7eb", marginTop: 12
        }}>
          <button style={{ padding: "8px 20px", background: "#fff", border: "1px solid #d1d5db", borderRadius: 8, fontSize: ".85rem", color: "#374151", cursor: "pointer", fontWeight: 500 }}>Cancel</button>
          <button style={{ padding: "8px 28px", background: "#1e293b", color: "#fff", border: "none", borderRadius: 8, fontSize: ".85rem", fontWeight: 600, cursor: "pointer" }}>Add Job</button>
          <button style={{ padding: "8px 28px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, fontSize: ".85rem", fontWeight: 600, cursor: "pointer" }}>Save Job</button>
        </div>

      </div>
    </div>
  );
}
