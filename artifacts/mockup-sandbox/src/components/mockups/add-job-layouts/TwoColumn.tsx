import { useState } from "react";
import { Search, Upload, Plus, Calendar, Clock, User, Car, DollarSign, FileText, MapPin, Sparkles, ChevronDown, ChevronRight, Info, AlertTriangle, CheckCircle2, ShieldAlert } from "lucide-react";

function Field({ label, placeholder, value, type, flex, children }: {
  label: string; placeholder?: string; value?: string; type?: string; flex?: string; children?: React.ReactNode;
}) {
  return (
    <div style={{ flex: flex || "1", minWidth: 0 }}>
      <label style={{ display: "block", fontSize: ".7rem", fontWeight: 600, color: "#64748b", marginBottom: 2, letterSpacing: ".03em" }}>{label}</label>
      {children || (
        <input type={type || "text"} value={value} placeholder={placeholder} readOnly style={{
          width: "100%", padding: "5px 8px", border: "1px solid #e2e8f0", borderRadius: 6,
          fontSize: ".8rem", color: "#1e293b", background: value ? "#f0f7ff" : "#fff", outline: "none"
        }} />
      )}
    </div>
  );
}

function Sel({ label, value, options, flex }: { label: string; value: string; options: string[]; flex?: string }) {
  return (
    <div style={{ flex: flex || "1", minWidth: 0 }}>
      <label style={{ display: "block", fontSize: ".7rem", fontWeight: 600, color: "#64748b", marginBottom: 2, letterSpacing: ".03em" }}>{label}</label>
      <select defaultValue={value} style={{
        width: "100%", padding: "5px 8px", border: "1px solid #e2e8f0", borderRadius: 6,
        fontSize: ".8rem", color: "#1e293b", background: "#fff", outline: "none", cursor: "pointer"
      }}>
        {options.map(o => <option key={o}>{o}</option>)}
      </select>
    </div>
  );
}

function Card({ title, icon: Icon, children, muted }: { title: string; icon: any; children: React.ReactNode; muted?: boolean }) {
  return (
    <div style={{ background: "#fff", borderRadius: 10, border: "1px solid #e5e7eb", overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 12px", borderBottom: "1px solid #f1f5f9", background: "#fafbfc" }}>
        <Icon size={14} color={muted ? "#94a3b8" : "#2563eb"} />
        <span style={{ fontWeight: 600, fontSize: ".8rem", color: muted ? "#94a3b8" : "#1e293b" }}>{title}</span>
        {muted && <span style={{ marginLeft: "auto", fontSize: ".65rem", color: "#94a3b8", fontWeight: 500 }}>optional</span>}
      </div>
      <div style={{ padding: "10px 12px" }}>{children}</div>
    </div>
  );
}

function SecurityAssetBlock() {
  const [showParsed, setShowParsed] = useState(false);
  const hasDescription = true;

  return (
    <div style={{ background: "#f8fafc", borderRadius: 7, padding: "8px 10px", border: "1px solid #f1f5f9" }}>
      <div style={{ display: "flex", gap: 6, marginBottom: 6 }}>
        <Sel label="TYPE" value="Vehicle" options={["Vehicle", "Equipment", "Property", "Other"]} flex="100px" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <label style={{ display: "block", fontSize: ".7rem", fontWeight: 600, color: "#64748b", marginBottom: 2, letterSpacing: ".03em" }}>DESCRIPTION</label>
          <input
            value="2019 Ford Ranger XL REG: ABC123 VIN: 6FPPXXMJ2PKL12345 White"
            readOnly
            style={{
              width: "100%", padding: "5px 8px", border: "1px solid #e2e8f0", borderRadius: 6,
              fontSize: ".8rem", color: "#1e293b", background: "#fff", outline: "none"
            }}
          />
        </div>
      </div>

      {hasDescription && (
        <div style={{ marginBottom: 6 }}>
          <button
            onClick={() => setShowParsed(!showParsed)}
            style={{
              display: "flex", alignItems: "center", gap: 4, background: "none", border: "none",
              padding: "2px 0", fontSize: ".72rem", color: "#2563eb", cursor: "pointer", fontWeight: 500
            }}
          >
            <Sparkles size={11} />
            Auto-parsed details
            {showParsed ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </button>
          {showParsed && (
            <div style={{
              marginTop: 4, padding: "6px 8px", background: "#eff6ff", borderRadius: 6,
              border: "1px solid #dbeafe"
            }}>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 6 }}>
                {[
                  ["Year", "2019"],
                  ["Make", "Ford"],
                  ["Model", "Ranger XL"],
                  ["Colour", "White"],
                  ["Engine", "—"],
                ].map(([k, v]) => (
                  <div key={k} style={{ minWidth: 0 }}>
                    <div style={{ fontSize: ".62rem", color: "#64748b", fontWeight: 600, letterSpacing: ".04em" }}>{k}</div>
                    <div style={{ fontSize: ".76rem", color: "#1e293b", fontWeight: 600 }}>{v}</div>
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <Sparkles size={10} color="#94a3b8" />
                <span style={{ fontSize: ".65rem", color: "#94a3b8" }}>Parsed from description — used for forms</span>
              </div>

              <div style={{ marginTop: 6, paddingTop: 6, borderTop: "1px dashed #bfdbfe" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 4 }}>
                  <Clock size={10} color="#94a3b8" />
                  <span style={{ fontSize: ".65rem", color: "#94a3b8", fontWeight: 500 }}>Populated after job creation from Vehicle Registration notes</span>
                </div>
                <div style={{ display: "flex", gap: 12 }}>
                  <div>
                    <div style={{ fontSize: ".62rem", color: "#64748b", fontWeight: 600, letterSpacing: ".04em" }}>Rego Expiry</div>
                    <div style={{ fontSize: ".76rem", color: "#94a3b8", fontStyle: "italic" }}>pending</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <div style={{ display: "flex", gap: 6, marginBottom: 6 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <label style={{ display: "block", fontSize: ".7rem", fontWeight: 600, color: "#64748b", marginBottom: 2, letterSpacing: ".03em" }}>REGO</label>
          <div style={{ position: "relative" }}>
            <input value="ABC123" readOnly style={{
              width: "100%", padding: "5px 8px", border: "1px solid #e2e8f0", borderRadius: 6,
              fontSize: ".8rem", color: "#1e293b", background: "#f0f7ff", outline: "none"
            }} />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 3, marginTop: 2 }}>
            <AlertTriangle size={10} color="#ef4444" />
            <span style={{ fontSize: ".62rem", color: "#ef4444", fontWeight: 500 }}>Rego mismatch — VicRoads shows XYZ789</span>
          </div>
        </div>
        <Field label="VIN" placeholder="VIN number" value="6FPPXXMJ2PKL12345" />
        <Field label="COLOUR" placeholder="White" value="White" />
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 2 }}>
            <label style={{ fontSize: ".7rem", fontWeight: 600, color: "#64748b", letterSpacing: ".03em" }}>ASSET ADDRESS</label>
            <span style={{ fontSize: ".64rem", color: "#94a3b8", fontStyle: "italic" }}>from customer address</span>
          </div>
          <input value="42 Bourke St, Melbourne VIC 3000" readOnly style={{
            width: "100%", padding: "5px 8px", border: "1px solid #e2e8f0", borderRadius: 6,
            fontSize: ".8rem", color: "#1e293b", background: "#f0f7ff", outline: "none", cursor: "text"
          }} />
        </div>
        <Field label="SERIAL" placeholder="Equipment serial" flex="140px" />
      </div>
      <div style={{ marginTop: 4 }}>
        <label style={{ display: "block", fontSize: ".7rem", fontWeight: 600, color: "#64748b", marginBottom: 2 }}>NOTES</label>
        <input placeholder="Additional security notes..." readOnly style={{
          width: "100%", padding: "5px 8px", border: "1px solid #e2e8f0", borderRadius: 6,
          fontSize: ".8rem", outline: "none"
        }} />
      </div>
    </div>
  );
}

export function TwoColumn() {
  return (
    <div style={{ minHeight: "100vh", background: "#f1f5f9", fontFamily: "'Inter', system-ui, sans-serif" }}>
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "20px 16px 40px" }}>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div>
            <h1 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#0f172a", margin: 0 }}>New Job</h1>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 12px", background: "#fff", border: "1px solid #d1d5db", borderRadius: 7, fontSize: ".78rem", color: "#374151", cursor: "pointer" }}>
              <Upload size={13} /> Upload & Auto-fill
            </button>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 12, alignItems: "start" }}>

          {/* LEFT COLUMN — Core fields */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>

            <Card title="Job Identification" icon={FileText}>
              <div style={{ display: "flex", gap: 8 }}>
                <Field label="JOB #" value="2603002" flex="120px" />
                <Field label="CONTRACT NUMBER" placeholder="e.g., AMO18972 — type to clone" />
                <Field label="CLIENT JOB #" placeholder="e.g., CJN-001" />
              </div>
            </Card>

            <Card title="Client & Customer" icon={User}>
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                <div style={{ flex: 1 }}>
                  <label style={{ display: "block", fontSize: ".7rem", fontWeight: 600, color: "#64748b", marginBottom: 2 }}>CLIENT</label>
                  <div style={{ display: "flex", gap: 4 }}>
                    <div style={{ flex: 1, position: "relative" }}>
                      <Search size={13} style={{ position: "absolute", left: 7, top: 7, color: "#9ca3af" }} />
                      <input placeholder="Search..." readOnly style={{ width: "100%", padding: "5px 8px 5px 26px", border: "1px solid #e2e8f0", borderRadius: 6, fontSize: ".8rem", outline: "none" }} />
                    </div>
                    <button style={{ padding: "3px 8px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, fontSize: ".72rem", fontWeight: 600, cursor: "pointer" }}>+</button>
                  </div>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ display: "block", fontSize: ".7rem", fontWeight: 600, color: "#64748b", marginBottom: 2 }}>CUSTOMER</label>
                  <div style={{ display: "flex", gap: 4 }}>
                    <div style={{ flex: 1, position: "relative" }}>
                      <Search size={13} style={{ position: "absolute", left: 7, top: 7, color: "#9ca3af" }} />
                      <input placeholder="Search..." readOnly style={{ width: "100%", padding: "5px 8px 5px 26px", border: "1px solid #e2e8f0", borderRadius: 6, fontSize: ".8rem", outline: "none" }} />
                    </div>
                    <button style={{ padding: "3px 8px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, fontSize: ".72rem", fontWeight: 600, cursor: "pointer" }}>+</button>
                  </div>
                </div>
              </div>
              <Field label="CUSTOMER ADDRESS" placeholder="Street, Suburb, State, Postcode" />
              <div style={{ marginTop: 8 }}>
                <Field label="JOB ADDRESS" placeholder="Street, Suburb, State, Postcode" />
              </div>
              <label style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 5, fontSize: ".74rem", color: "#64748b", cursor: "pointer" }}>
                <input type="checkbox" defaultChecked style={{ accentColor: "#2563eb" }} /> Same as customer address
              </label>
            </Card>

            <div style={{ display: "flex", gap: 8 }}>
              <Sel label="JOB TYPE" value="Collect Only" options={["Collect Only", "Investigate", "Field Call", "Locate & Collect", "Skip Trace"]} />
              <Sel label="VISIT TYPE" value="New Visit" options={["New Visit", "Revisit", "Final Visit"]} />
              <Sel label="STATUS" value="New" options={["New", "Active", "Suspended"]} />
              <Sel label="PRIORITY" value="Normal" options={["Normal", "Urgent", "Low"]} />
            </div>

            <Card title="Security / Asset" icon={Car} muted>
              <SecurityAssetBlock />
              <button style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 6, background: "none", border: "1px dashed #cbd5e1", borderRadius: 6, padding: "3px 10px", fontSize: ".74rem", color: "#2563eb", fontWeight: 600, cursor: "pointer" }}>
                <Plus size={12} /> Add Another
              </button>
            </Card>

          </div>

          {/* RIGHT COLUMN — Details, schedule, financial */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10, position: "sticky", top: 20 }}>

            <Card title="Lender & Financial" icon={DollarSign} muted>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <Field label="LENDER" placeholder="e.g. Nissan Finance" />
                <div style={{ display: "flex", gap: 6 }}>
                  <Field label="ACCOUNT #" placeholder="1234567" />
                  <Sel label="REGULATION" value="Select..." options={["Select...", "Regulated", "Unregulated"]} />
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <Field label="ARREARS" value="$0.00" />
                  <Field label="COSTS" value="$0.00" />
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <Field label="MMP" value="$0.00" />
                  <Field label="DUE DATE" placeholder="dd/mm/yyyy" type="date" />
                </div>
              </div>
            </Card>

            <Card title="Instructions" icon={FileText} muted>
              <Field label="DELIVER TO" placeholder="Auction yard name..." />
              <div style={{ marginTop: 6 }}>
                <label style={{ display: "block", fontSize: ".7rem", fontWeight: 600, color: "#64748b", marginBottom: 2 }}>DESCRIPTION & INSTRUCTIONS</label>
                <textarea placeholder="Agent instructions, access codes, contact times..." readOnly style={{
                  width: "100%", minHeight: 70, padding: "6px 8px", border: "1px solid #e2e8f0", borderRadius: 6,
                  fontSize: ".8rem", resize: "vertical", fontFamily: "inherit", outline: "none"
                }} />
                <div style={{ fontSize: ".68rem", color: "#94a3b8", marginTop: 1 }}>Visible to assigned agents</div>
              </div>
            </Card>

            <Card title="Initial Schedule" icon={Calendar} muted>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ position: "relative" }}>
                  <label style={{ display: "block", fontSize: ".7rem", fontWeight: 600, color: "#64748b", marginBottom: 2 }}>BOOKING TYPE</label>
                  <div style={{ position: "relative" }}>
                    <Search size={13} style={{ position: "absolute", left: 7, top: 7, color: "#9ca3af" }} />
                    <input placeholder="Type to search or enter new..." readOnly style={{
                      width: "100%", padding: "5px 8px 5px 26px", border: "1px solid #e2e8f0", borderRadius: 6,
                      fontSize: ".8rem", outline: "none"
                    }} />
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <Field label="DATE" value="14/03/2026" type="date" />
                  <Field label="TIME" value="09:00" type="time" />
                </div>
                <Sel label="ASSIGNED TO" value="— Unassigned —" options={["— Unassigned —", "Grant Cook", "John Smith"]} />
                <div>
                  <label style={{ display: "block", fontSize: ".7rem", fontWeight: 600, color: "#64748b", marginBottom: 2 }}>NOTES</label>
                  <textarea placeholder="Appointment notes..." readOnly style={{
                    width: "100%", minHeight: 40, padding: "5px 8px", border: "1px solid #e2e8f0", borderRadius: 6,
                    fontSize: ".8rem", resize: "vertical", fontFamily: "inherit", outline: "none"
                  }} />
                </div>
              </div>
            </Card>

          </div>

        </div>

        <div style={{
          position: "sticky", bottom: 0, background: "#f1f5f9", padding: "12px 0 4px",
          display: "flex", justifyContent: "flex-end", gap: 8, borderTop: "1px solid #e2e8f0", marginTop: 10
        }}>
          <button style={{ padding: "7px 18px", background: "#fff", border: "1px solid #d1d5db", borderRadius: 7, fontSize: ".82rem", color: "#374151", cursor: "pointer" }}>Cancel</button>
          <button style={{ padding: "7px 24px", background: "#1e293b", color: "#fff", border: "none", borderRadius: 7, fontSize: ".82rem", fontWeight: 600, cursor: "pointer" }}>Add Job</button>
          <button style={{ padding: "7px 24px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 7, fontSize: ".82rem", fontWeight: 600, cursor: "pointer" }}>Save Job</button>
        </div>

      </div>
    </div>
  );
}
