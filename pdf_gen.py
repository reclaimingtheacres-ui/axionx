import io
import os
import base64
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader, simpleSplit

PAGE_W, PAGE_H = A4
ML = 40
MR = 40
MT = 36
CW = PAGE_W - ML - MR

DARK       = HexColor('#111827')
MUTED      = HexColor('#6b7280')
LINE       = HexColor('#9ca3af')
_WISE_AMBER = HexColor('#f59e0b')

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'static', 'images', 'swpi_logo_sm.png')


def _v(d, *keys, default=''):
    for k in keys:
        v = d.get(k)
        if v:
            return str(v)
    return default


def _trunc(val, max_ch=40):
    s = str(val or '')
    return s[:max_ch] + ('\u2026' if len(s) > max_ch else '')


def _sig_box(c, x, y, w, h, label, sig_b64=None, date_str=''):
    c.setStrokeColor(LINE)
    c.setLineWidth(0.75)
    c.rect(x, y - h, w, h, fill=0, stroke=1)
    if sig_b64:
        try:
            raw_b64 = sig_b64.split(',')[-1]
            raw = base64.b64decode(raw_b64)
            img = ImageReader(io.BytesIO(raw))
            c.drawImage(img, x + 4, y - h + 22, width=w - 8, height=h - 30,
                        preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    c.setStrokeColor(MUTED)
    c.setLineWidth(0.5)
    c.line(x + 6, y - h + 20, x + w - 6, y - h + 20)
    c.setFont('Helvetica', 7.5)
    c.setFillColor(MUTED)
    c.drawString(x + 6, y - h + 10, str(label)[:50])
    if date_str:
        c.drawRightString(x + w - 6, y - h + 10, f'Dated: {date_str}')


def _cb(c, x, y, label, checked=False, w=8, h=8):
    c.setStrokeColor(DARK)
    c.setLineWidth(0.75)
    c.rect(x, y - h + 1, w, h, fill=0, stroke=1)
    if checked:
        c.setFont('Helvetica-Bold', 7)
        c.setFillColor(DARK)
        c.drawString(x + 1.5, y - h + 2.5, 'X')
    c.setFont('Helvetica', 7.5)
    c.setFillColor(DARK)
    c.drawString(x + w + 3, y - h + 2, label)
    return x + w + 3 + c.stringWidth(label, 'Helvetica', 7.5) + 10


def _condition_checked(val, option):
    if not val:
        return False
    v = val.strip().lower()
    o = option.strip().lower()
    return o in v or v in o


def _hr(c, y, strong=False):
    c.setStrokeColor(DARK if strong else LINE)
    c.setLineWidth(0.75 if strong else 0.3)
    c.line(ML, y, PAGE_W - MR, y)


def _swpi_letterhead(c):
    y = PAGE_H - MT
    logo_h, logo_w = 55, 88
    try:
        c.drawImage(LOGO_PATH, ML, y - logo_h, width=logo_w, height=logo_h,
                    preserveAspectRatio=True, mask='auto')
    except Exception:
        c.setFont('Helvetica-Bold', 16)
        c.setFillColor(DARK)
        c.drawString(ML, y - 32, 'SWPI')
    c.setFont('Helvetica', 8)
    c.setFillColor(DARK)
    c.drawRightString(PAGE_W - MR, y - 8,  'PO Box 651, SUNSHINE. VIC, 3020')
    c.drawRightString(PAGE_W - MR, y - 20, 'Ph: +61 429 996 260')
    return y - logo_h - 4


def _vir_condition_row(c, y, label, val, options):
    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(DARK)
    c.drawString(ML, y - 9, label + ':')
    x = ML + 84
    for opt in options:
        x = _cb(c, x, y, opt, _condition_checked(val, opt))
    _hr(c, y - 14)
    return y - 14


# =============================================================================
# 1. SWPI VIR — Surrendered / Repossession Receipt
# =============================================================================

def generate_vir_pdf(data, agent_sig=None, customer_sig=None):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Surrendered / Repossession Receipt')

    y = _swpi_letterhead(c)
    y -= 4

    client_ref = _v(data, 'client_reference')
    registration = _v(data, 'registration')
    ref_display = client_ref or ''
    if registration and registration not in ref_display:
        ref_display = f'{ref_display} / {registration}' if ref_display else registration
    if ref_display:
        c.setFont('Helvetica', 8)
        c.setFillColor(DARK)
        c.drawCentredString(PAGE_W / 2, y, f'Client Ref: {ref_display}')
    y -= 14

    title = 'SURRENDERED / REPOSSESSION RECEIPT'
    c.setFont('Helvetica-Bold', 11)
    c.setFillColor(DARK)
    c.drawCentredString(PAGE_W / 2, y, title)
    tw = c.stringWidth(title, 'Helvetica-Bold', 11)
    _hr(c, y - 1, strong=True)

    swpi_ref = _v(data, 'swpi_ref')
    if swpi_ref:
        c.setFont('Helvetica-Bold', 8)
        c.drawRightString(PAGE_W - MR, y, f'SWPi Ref: {swpi_ref}')
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(DARK)
    c.drawString(ML, y, 'Finance Company:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 90, y, _trunc(_v(data, 'finance_company'), 28))
    c.setFont('Helvetica-Bold', 8)
    c.drawString(PAGE_W - MR - 130, y, 'Date:')
    c.setFont('Helvetica', 8)
    c.drawString(PAGE_W - MR - 100, y, _v(data, 'repo_date'))
    y -= 12

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'Customer Name:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 84, y, _trunc(_v(data, 'customer_name'), 28))
    c.setFont('Helvetica-Bold', 8)
    c.drawString(PAGE_W - MR - 130, y, 'Account No:')
    c.setFont('Helvetica', 8)
    c.drawString(PAGE_W - MR - 68, y, _trunc(_v(data, 'account_number'), 16))
    y -= 12

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'Surrendered / Repossessed from:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 168, y, _trunc(_v(data, 'repo_address'), 42))
    y -= 8
    _hr(c, y, strong=True)
    y -= 2

    col_heads  = ['YEAR', 'MAKE', 'MODEL', 'COLOUR', 'REG', 'EXPIRY']
    col_vals   = [_v(data, 'year'), _v(data, 'make'), _v(data, 'model'),
                  _v(data, 'colour'), _v(data, 'registration'), _v(data, 'rego_expiry')]
    col_widths = [38, 56, 72, 80, 55, 42]
    x = ML
    c.setFont('Helvetica-Bold', 7.5)
    c.setFillColor(DARK)
    for h, w in zip(col_heads, col_widths):
        c.drawString(x + 2, y - 10, h)
        x += w
    y -= 12
    _hr(c, y)
    y -= 2
    x = ML
    c.setFont('Helvetica', 8)
    for v, w in zip(col_vals, col_widths):
        c.drawString(x + 2, y - 10, _trunc(v, int(w / 5.2)))
        x += w
    y -= 12
    _hr(c, y, strong=True)
    y -= 4

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'VIN/CHASSIS:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 72, y, _v(data, 'vin'))
    y -= 12

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'ENGINE:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 50, y, _v(data, 'engine_number'))
    y -= 12

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'KILOMETERS:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 66, y, _v(data, 'speedometer'))
    y -= 8
    _hr(c, y)
    y -= 4

    keys_val  = _v(data, 'keys_obtained')
    how_many  = _v(data, 'how_many_keys')
    keys_disp = keys_val + (f'  qty({how_many})' if how_many else '')

    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML, y, 'PERSON PRESENT')
    c.setFont('Helvetica', 7.5)
    c.drawString(ML + 95, y, _v(data, 'person_present'))
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML + 165, y, 'KEYS OBTAINED?')
    c.setFont('Helvetica', 7.5)
    c.drawString(ML + 250, y, keys_disp)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML + 330, y, 'VOL SURRENDER?')
    c.setFont('Helvetica', 7.5)
    c.drawString(ML + 420, y, _v(data, 'vol_surrender'))
    y -= 12

    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML, y, 'FORM 13?')
    c.setFont('Helvetica', 7.5)
    c.drawString(ML + 56, y, _v(data, 'form_13'))
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML + 165, y, 'SECURITY DRIVABLE?')
    c.setFont('Helvetica', 7.5)
    c.drawString(ML + 268, y, _v(data, 'security_drivable'))
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML + 330, y, 'POLICE NOTIFIED?')
    c.setFont('Helvetica', 7.5)
    c.drawString(ML + 424, y, _v(data, 'police_notified'))
    y -= 12

    station = _v(data, 'station_officer')
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML + 330, y, 'STATION/OFFICER:')
    c.setFont('Helvetica', 7.5)
    c.drawString(ML + 424, y, station)
    y -= 12

    effects = _v(data, 'personal_effects_removed')
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML, y, 'PERSONAL EFFECTS REMOVED?')
    c.setFont('Helvetica', 7.5)
    c.drawString(ML + 162, y, effects)
    y -= 12

    effects_list = _v(data, 'personal_effects_list')
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML, y, 'LIST:')
    c.setFont('Helvetica', 7.5)
    c.drawString(ML + 34, y, _trunc(effects_list, 70))
    y -= 8
    _hr(c, y)
    y -= 4

    for lbl, field, offset in [
        ('TYRES:', 'tyres', 42), ('BODY:', 'body', 38),
        ('DUCO:', 'duco', 38),  ('INTERIOR:', 'interior', 54),
    ]:
        xp = ML + (0 if lbl == 'TYRES:' else
                   116 if lbl == 'BODY:' else
                   228 if lbl == 'DUCO:' else 330)
        c.setFont('Helvetica-Bold', 7.5)
        c.drawString(xp, y, lbl)
        c.setFont('Helvetica', 7.5)
        c.drawString(xp + offset, y, _v(data, field))
    y -= 12

    for lbl, field, xp, offset in [
        ('ENGINE:', 'engine_condition', ML, 50),
        ('TRANSMISSION:', 'transmission', ML + 228, 80),
    ]:
        c.setFont('Helvetica-Bold', 7.5)
        c.drawString(xp, y, lbl)
        c.setFont('Helvetica', 7.5)
        c.drawString(xp + offset, y, _v(data, field))
    y -= 12

    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML, y, 'FUEL level:')
    c.setFont('Helvetica', 7.5)
    c.drawString(ML + 60, y, _v(data, 'fuel_level'))
    y -= 12

    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML, y, 'DAMAGE:')
    dmg = _v(data, 'damage_list') if _v(data, 'any_damage').upper() == 'YES' else ''
    c.setFont('Helvetica', 7.5)
    c.drawString(ML + 50, y, _trunc(dmg, 72))
    y -= 12
    _hr(c, y)
    y -= 6

    agent_name = _v(data, 'agent_name', default='the agent')
    legal1 = (
        f"I, {agent_name}, mercantile agent, acting on behalf of the above financier, hereby certify "
        "that a true copy of this notice was furnished to the above named by;"
    )
    legal2 = (
        "I ACKNOWLEDGE RECEIPT OF THIS ORIGINAL NOTICE AND THAT THE ABOVE AGENT OR FINANCE "
        "COMPANY ARE NOT RESPONSIBLE FOR ANY LOSS OF ANY PERSONAL EFFECTS LEFT IN THE MOTOR VEHICLE."
    )
    c.setFont('Helvetica-Oblique', 7.5)
    c.setFillColor(DARK)
    for line in simpleSplit(legal1, 'Helvetica-Oblique', 7.5, CW):
        c.drawString(ML, y, line)
        y -= 10
    y -= 3
    c.setFont('Helvetica-BoldOblique', 7.5)
    for line in simpleSplit(legal2, 'Helvetica-BoldOblique', 7.5, CW):
        c.drawString(ML, y, line)
        y -= 10
    y -= 8

    sig_w = (CW - 14) / 2
    sig_h = 76
    date_str = _v(data, 'repo_date')
    _sig_box(c, ML, y, sig_w, sig_h, 'Customer Signature', customer_sig, date_str)
    _sig_box(c, ML + sig_w + 14, y, sig_w, sig_h,
             f'Agent / Mercantile Agent: {agent_name}', agent_sig, date_str)

    c.save()
    buf.seek(0)
    return buf.read()


# =============================================================================
# 2. SWPI Transport Instructions / Tow Receipt
# =============================================================================

def generate_transport_pdf(data, agent_sig=None, tow_sig=None):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Transport Instructions / Tow Receipt')

    y = _swpi_letterhead(c)
    y -= 6

    title = 'TRANSPORT INSTRUCTIONS / TOW RECEIPT'
    c.setFont('Helvetica-Bold', 11)
    c.setFillColor(DARK)
    c.drawCentredString(PAGE_W / 2, y, title)
    _hr(c, y - 1, strong=True)
    y -= 14

    swpi_ref = _v(data, 'swpi_ref')
    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'SWPI REFERENCE:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 96, y, swpi_ref)
    y -= 12

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'FINANCE COMPANY:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 100, y, _trunc(_v(data, 'finance_company'), 28))
    c.setFont('Helvetica-Bold', 8)
    c.drawString(PAGE_W - MR - 130, y, 'DATE:')
    c.setFont('Helvetica', 8)
    c.drawString(PAGE_W - MR - 100, y, _v(data, 'repo_date'))
    y -= 12

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'CUSTOMER NAME:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 88, y, _trunc(_v(data, 'customer_name'), 38))
    y -= 12

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'REPOSSESSION ADDRESS:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 126, y, _trunc(_v(data, 'repo_address'), 42))
    y -= 10
    _hr(c, y)
    y -= 4

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'SECURITY DETAILS')
    y -= 12

    make_model = ' '.join(filter(None, [_v(data, 'make'), _v(data, 'model')])) or ''
    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'MAKE / MODEL:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 78, y, _trunc(make_model, 30))
    c.setFont('Helvetica-Bold', 8)
    c.drawString(PAGE_W - MR - 130, y, 'REGO:')
    c.setFont('Helvetica', 8)
    c.drawString(PAGE_W - MR - 98, y, _v(data, 'registration'))
    y -= 12

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'VIN:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 28, y, _v(data, 'vin'))
    y -= 10
    _hr(c, y)
    y -= 4

    tow_name = _v(data, 'tow_company_name')
    tow_phone = _v(data, 'tow_phone')
    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'TOW CONTRACTOR:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 96, y, _trunc(tow_name + (' ' + tow_phone if tow_phone else ''), 36))
    c.setFont('Helvetica-Bold', 8)
    c.drawString(PAGE_W - MR - 130, y, 'PHONE:')
    c.setFont('Helvetica', 8)
    c.drawString(PAGE_W - MR - 90, y, tow_phone)
    y -= 12

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'TOW COSTS:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 62, y, _v(data, 'tow_costs') or 'TBA')
    y -= 12
    _hr(c, y)
    y -= 6

    delivery_label = 'PLEASE DELIVER THE ABOVE ASSET TO THE FOLLOWING AUCTION FACILITY'
    c.setFont('Helvetica-Bold', 8.5)
    c.setFillColor(DARK)
    c.drawCentredString(PAGE_W / 2, y, delivery_label)
    y -= 6
    _hr(c, y)
    y -= 10

    deliver_to = _v(data, 'deliver_to', 'delivery_address')
    delivery_addr = _v(data, 'delivery_address')
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(PAGE_W / 2, y, _trunc(deliver_to, 60))
    if delivery_addr and delivery_addr != deliver_to:
        y -= 12
        c.setFont('Helvetica', 9)
        c.drawCentredString(PAGE_W / 2, y, _trunc(delivery_addr, 70))
    y -= 14
    _hr(c, y)
    y -= 8

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'SEND YOUR INVOICE DIRECT TO:')
    y -= 12
    client_name  = _v(data, 'client_name')
    client_email = _v(data, 'client_email')
    invoice_line = client_name + (f'  \u2014  {client_email}' if client_email else '')
    c.setFont('Helvetica', 8.5)
    c.drawString(ML, y, _trunc(invoice_line, 65))
    y -= 16
    _hr(c, y)
    y -= 8

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'REFERENCE / JOB NUMBER:')
    y -= 12
    ref = ' / '.join(filter(None, [_v(data, 'client_reference'),
                                   _v(data, 'registration')])) or _v(data, 'swpi_ref')
    c.setFont('Helvetica', 9)
    c.drawString(ML, y, ref)
    y -= 20

    agent_name = _v(data, 'agent_name', default='Agent')
    sig_w = (CW - 14) / 2
    sig_h = 80
    date_str = _v(data, 'repo_date')
    _sig_box(c, ML, y, sig_w, sig_h, f'AGENT SIGNATURE: {agent_name}', agent_sig, date_str)
    _sig_box(c, ML + sig_w + 14, y, sig_w, sig_h, 'TOW SIGNATURE:', tow_sig, date_str)

    c.save()
    buf.seek(0)
    return buf.read()


# =============================================================================
# 3. Wise Group — Vehicle Inspection Report
# =============================================================================

def generate_wise_vir_pdf(data, agent_sig=None, customer_sig=None):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Wise Group \u2014 Vehicle Inspection Report')

    y = PAGE_H - MT
    case_number = _v(data, 'wise_case_number', 'swpi_ref')
    title = f'VEHICLE INSPECTION REPORT{f"  {case_number}" if case_number else ""}'
    c.setFont('Helvetica-Bold', 12)
    c.setFillColor(DARK)
    c.drawCentredString(PAGE_W / 2, y, title)
    y -= 6
    _hr(c, y, strong=True)
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'Name of Debtor:')
    c.setFont('Helvetica', 9)
    c.drawString(ML + 88, y, _v(data, 'customer_name'))
    y -= 12
    _hr(c, y)
    y -= 8

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'VEHICLE DESCRIPTION')
    y -= 4
    _hr(c, y, strong=True)
    y -= 10

    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML, y, 'YEAR:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 32, y, _v(data, 'year'))
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML + 100, y, 'MAKE:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 130, y, _v(data, 'make'))
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML + 230, y, 'MODEL:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 264, y, _v(data, 'model'))
    y -= 11
    _hr(c, y)
    y -= 10

    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML, y, 'BODY TYPE:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 60, y, _v(data, 'body_type'))
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML + 130, y, 'COLOUR:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 172, y, _v(data, 'colour'))
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML + 258, y, 'REGO:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 288, y, _v(data, 'registration'))
    y -= 11
    _hr(c, y)
    y -= 10

    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(ML, y, 'VIN/CHASSIS:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 70, y, _v(data, 'vin'))
    y -= 11
    _hr(c, y)
    y -= 10

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'VEHICLE CONDITION')
    y -= 4
    _hr(c, y, strong=True)
    y -= 8

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'EXTERIOR')
    y -= 4
    _hr(c, y)
    y -= 2

    body_val = _v(data, 'body')
    paint_val = _v(data, 'duco')
    for lbl, val, opts in [
        ('BODY',    body_val,  ['POOR', 'GOOD', 'EXCELLENT', 'DAMAGED']),
        ('PAINT',   paint_val, ['POOR', 'GOOD', 'EXCELLENT', 'DAMAGED']),
        ('BUMPERS', body_val,  ['POOR', 'GOOD', 'EXCELLENT', 'DAMAGED']),
        ('WINDOWS', _v(data, 'glass'), ['BROKEN', 'CRACKED', 'GOOD']),
        ('TYRES',   _v(data, 'tyres'), ['BALD', 'FAIR', 'GOOD', 'EXCELLENT']),
    ]:
        y = _vir_condition_row(c, y, lbl, val, opts)
    y -= 6

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'MECHANICAL')
    y -= 4
    _hr(c, y)
    y -= 10

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'DOES VEHICLE DRIVE:')
    xb = ML + 120
    xb = _cb(c, xb, y, 'YES', _condition_checked(_v(data, 'security_drivable'), 'yes'))
    xb = _cb(c, xb, y, 'NO', _condition_checked(_v(data, 'security_drivable'), 'no'))
    xb += 16
    c.setFont('Helvetica-Bold', 8)
    c.drawString(xb, y, 'ENGINE INTACT:')
    xb2 = xb + 84
    eng = _v(data, 'engine_condition').lower()
    eng_ok = eng and eng not in ('damaged', 'poor', 'missing', 'no', 'n/a')
    xb2 = _cb(c, xb2, y, 'YES', eng_ok and bool(eng))
    _cb(c, xb2, y, 'NO', not eng_ok and bool(eng))
    _hr(c, y - 14)
    y -= 18

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'INTERIOR')
    y -= 4
    _hr(c, y)
    y -= 2

    interior_val = _v(data, 'interior')
    for lbl, val, opts in [
        ('TRIM',   interior_val, ['POOR', 'GOOD', 'EXCELLENT']),
        ('CARPET', interior_val, ['POOR', 'GOOD', 'EXCELLENT']),
        ('DASH',   interior_val, ['POOR', 'GOOD', 'EXCELLENT']),
    ]:
        y = _vir_condition_row(c, y, lbl, val, opts)
    y -= 6

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'OTHER')
    y -= 4
    _hr(c, y)
    y -= 10

    km = _v(data, 'speedometer')
    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, "KM'S ON CLOCK:")
    c.setFont('Helvetica', 8)
    line_end = ML + 88
    c.drawString(line_end, y, km or '___________________')
    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML + int(CW * 0.45), y, 'KEYS SECURED:')
    xb = ML + int(CW * 0.45) + 78
    keys_yes = _condition_checked(_v(data, 'keys_obtained'), 'yes')
    xb = _cb(c, xb, y, 'YES', keys_yes)
    _cb(c, xb, y, 'NO', not keys_yes)
    _hr(c, y - 14)
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'PLATES ATTACHED:')
    xb = ML + 100
    xb = _cb(c, xb, y, 'YES', True)
    _cb(c, xb, y, 'NO', False)
    _hr(c, y - 14)
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'ACCESSORIES:')
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(ML + 80, y - 1, PAGE_W - MR, y - 1)
    _hr(c, y - 14)
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'DETAILS OF ANY DAMAGE:')
    y -= 2
    dmg_val = _v(data, 'damage_list') if _v(data, 'any_damage').upper() == 'YES' else ''
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.rect(ML, y - 30, CW, 30, fill=0, stroke=1)
    if dmg_val:
        c.setFont('Helvetica', 8)
        c.setFillColor(DARK)
        for i, ln in enumerate(simpleSplit(dmg_val[:200], 'Helvetica', 8, CW - 8)[:2]):
            c.drawString(ML + 4, y - 14 - i * 11, ln)
    y -= 38

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'TOWED BY:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 56, y, _v(data, 'tow_company_name'))
    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML + int(CW * 0.47), y, 'TOWING COST: $')
    c.setFont('Helvetica', 8)
    c.drawString(ML + int(CW * 0.47) + 84, y, _v(data, 'tow_costs'))
    _hr(c, y - 14)
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'DELIVERED TO:')
    xb = ML + 82
    delivery = _v(data, 'deliver_to', 'delivery_address').upper()
    for yard in ['GAMERS', 'PICKLES', 'HELD AT TOWING YARD', 'OTHER']:
        xb = _cb(c, xb, y, yard, any(w in delivery for w in yard.split()))
    _hr(c, y - 14)
    y -= 20

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'DOES THE DEBTOR WISH TO REDEEM THE SECURITY:')
    xb = ML + 272
    redeem_yes = _condition_checked(_v(data, 'vol_surrender'), 'yes')
    xb = _cb(c, xb, y, 'YES', redeem_yes)
    _cb(c, xb, y, 'NO', not redeem_yes)
    _hr(c, y - 14)
    y -= 24

    agent_name = _v(data, 'agent_name')
    sig_w = (CW - 14) / 2
    sig_h = 72
    date_str = _v(data, 'repo_date')
    _sig_box(c, ML, y, sig_w, sig_h, f'Agent: {agent_name}', agent_sig, date_str)
    _sig_box(c, ML + sig_w + 14, y, sig_w, sig_h, 'Customer Signature', customer_sig, date_str)

    c.save()
    buf.seek(0)
    return buf.read()


# =============================================================================
# 4. Form 13 — Consent to Enter Premises (NCCP Schedule 1)
# =============================================================================

def generate_form_13_pdf(data, occupant_sig=None, agent_sig=None):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Form 13 Consent to Enter Premises')

    y = PAGE_H - MT

    c.setFont('Helvetica-Bold', 12)
    c.setFillColor(DARK)
    c.drawCentredString(PAGE_W / 2, y, 'Form 13 Consent to enter premises')
    y -= 16

    c.setFont('Helvetica', 7.5)
    c.setFillColor(MUTED)
    c.drawRightString(PAGE_W - MR, y, 'subsection 99 (2) of the Code')
    y -= 10
    c.drawRightString(PAGE_W - MR, y, 'regulation 87 of the Regulations')
    y -= 14

    c.setFont('Helvetica', 8)
    c.setFillColor(DARK)
    c.drawRightString(PAGE_W - MR, y, '...............')
    c.drawRightString(PAGE_W - MR - 15, y, 'Date')
    y -= 16

    credit_provider = _v(data, 'finance_company', 'client_name')
    c.setFont('Helvetica', 8)
    c.drawString(ML, y, 'TO: . . . . . . . . ')
    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML + 68, y, credit_provider)
    c.setFont('Helvetica', 8)
    c.drawString(ML + 68 + c.stringWidth(credit_provider, 'Helvetica-Bold', 8) + 4, y, '. . . . . . . . . .')
    y -= 10
    c.setFont('Helvetica-Oblique', 7.5)
    c.setFillColor(MUTED)
    c.drawString(ML + 68, y, '(name of credit provider)')
    y -= 10
    c.setFont('Helvetica-Oblique', 7.5)
    c.drawString(ML + 68, y, '(Australian credit licence number)')
    y -= 18

    occupier_name = _v(data, 'customer_name')
    occupier_addr = _v(data, 'repo_address')
    c.setFont('Helvetica', 8)
    c.setFillColor(DARK)
    c.drawString(ML, y, 'FROM: . . . . . . . . . . ')
    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML + 100, y, occupier_name)
    c.setFont('Helvetica', 8)
    end_x = ML + 100 + c.stringWidth(occupier_name, 'Helvetica-Bold', 8) + 4
    if end_x < PAGE_W - MR - 40:
        c.drawString(end_x, y, '. . . . . . . . . . . . . . . . . .')
    y -= 10
    c.setFont('Helvetica-Oblique', 7.5)
    c.setFillColor(MUTED)
    c.drawString(ML + 100, y, '(name of occupier)')
    y -= 12

    c.setFont('Helvetica', 8)
    c.setFillColor(DARK)
    c.drawString(ML + 100, y, _trunc(occupier_addr, 55))
    y -= 10
    c.setFont('Helvetica-Oblique', 7.5)
    c.setFillColor(MUTED)
    c.drawString(ML + 100, y, "(address of occupier's premises)")
    y -= 10
    c.setFont('Helvetica', 8)
    c.setFillColor(DARK)
    c.drawString(ML + 100, y, '.........................................')
    y -= 10
    c.setFont('Helvetica-Oblique', 7.5)
    c.setFillColor(MUTED)
    c.drawString(ML + 100, y, "('the premises')")
    y -= 18

    consent_text = (
        "I consent to the credit provider entering the premises for the purpose of taking "
        "possession of the mortgaged goods described below."
    )
    c.setFont('Helvetica', 8.5)
    c.setFillColor(DARK)
    for line in simpleSplit(consent_text, 'Helvetica', 8.5, CW):
        c.drawString(ML, y, line)
        y -= 12
    y -= 6

    make_model = ' '.join(filter(None, [_v(data, 'year'), _v(data, 'make'),
                                        _v(data, 'model')])) or _v(data, 'description')
    vin = _v(data, 'vin')
    goods_desc = make_model
    if vin:
        goods_desc += f', VIN/CHASSIS: {vin}'

    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(ML, y, 'The mortgaged goods are:')
    y -= 12
    c.setFont('Helvetica', 8.5)
    c.drawString(ML, y, _trunc(goods_desc, 80))
    y -= 20

    _hr(c, y, strong=True)
    y -= 14

    c.setFont('Helvetica-Bold', 10)
    c.drawCentredString(PAGE_W / 2, y, 'IMPORTANT')
    y -= 12

    important = (
        'YOU HAVE THE RIGHT TO REFUSE CONSENT. IF YOU DO THE CREDIT PROVIDER MAY GO TO '
        'COURT FOR PERMISSION TO ENTER THE PREMISES.'
    )
    c.setFont('Helvetica-Bold', 8.5)
    for line in simpleSplit(important, 'Helvetica-Bold', 8.5, CW):
        c.drawCentredString(PAGE_W / 2, y, line)
        y -= 12
    y -= 6
    _hr(c, y, strong=True)
    y -= 20

    c.setFont('Helvetica', 8)
    c.setFillColor(MUTED)
    c.drawCentredString(PAGE_W / 2, y, '..................................................')
    y -= 10
    c.drawCentredString(PAGE_W / 2, y, '(signature of occupier giving consent)')
    y -= 18

    agent_name  = _v(data, 'agent_name')
    date_str    = _v(data, 'repo_date')
    sig_w = (CW - 14) / 2
    sig_h = 80

    _sig_box(c, ML, y, sig_w, sig_h, 'Signature of Occupier giving consent', occupant_sig, date_str)
    _sig_box(c, ML + sig_w + 14, y, sig_w, sig_h,
             f'Agent: {agent_name}, {_v(data, "repo_address")}', agent_sig, date_str)
    y -= (sig_h + 16)

    c.setFont('Helvetica', 7.5)
    c.setFillColor(MUTED)
    c.drawCentredString(PAGE_W / 2, y,
        'Schedule 1 to the National Consumer Credit Protection Regulations 2010')

    c.save()
    buf.seek(0)
    return buf.read()


# =============================================================================
# 5. Voluntary Surrender — Section 78(1) NCC
# =============================================================================

def generate_voluntary_surrender_pdf(data, customer_sig=None, agent_sig=None):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Voluntary Surrender \u2014 Section 78(1)')

    y = PAGE_H - MT

    c.setFont('Helvetica-Bold', 12)
    c.setFillColor(DARK)
    c.drawCentredString(PAGE_W / 2, y, 'SECTION 78(1) NOTICE')
    y -= 14

    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(PAGE_W / 2, y, 'VOLUNTARY SURRENDER OF MORTGAGE TO GOODS')
    y -= 6
    _hr(c, y, strong=True)
    y -= 16

    creditor = _v(data, 'finance_company', 'client_name')
    c.setFont('Helvetica', 9)
    c.drawString(ML, y, 'To: ')
    c.setFont('Helvetica-Bold', 9)
    c.drawString(ML + 24, y, creditor)
    y -= 14

    mortgagor = _v(data, 'customer_name')
    c.setFont('Helvetica', 9)
    c.drawString(ML, y, 'Mortgagor/s: ')
    c.setFont('Helvetica-Bold', 9)
    c.drawString(ML + 76, y, mortgagor)
    y -= 14

    address = _v(data, 'repo_address')
    c.setFont('Helvetica', 9)
    c.drawString(ML, y, 'Address of Mortgagor/s: ')
    c.setFont('Helvetica', 9)
    c.drawString(ML + 140, y, _trunc(address, 48))
    y -= 14

    account = _v(data, 'account_number')
    c.setFont('Helvetica', 9)
    c.drawString(ML, y, 'Agreement/Account No. ')
    c.setFont('Helvetica-Bold', 9)
    c.drawString(ML + 130, y, account)
    y -= 14

    make_model = ' '.join(filter(None, [_v(data, 'year'), _v(data, 'make'),
                                        _v(data, 'model')])) or _v(data, 'description')
    vin = _v(data, 'vin')
    goods_desc = make_model
    if vin:
        goods_desc += f', VIN/CHASSIS: {vin}'
    c.setFont('Helvetica', 9)
    c.drawString(ML, y, 'Description of Goods: ')
    c.setFont('Helvetica', 9)
    c.drawString(ML + 128, y, _trunc(goods_desc, 50))
    y -= 14

    c.setFont('Helvetica', 9)
    c.drawString(ML, y, 'Place of Delivery:')
    delivery = _v(data, 'deliver_to', 'delivery_address')
    c.setFont('Helvetica', 9)
    c.drawString(ML + 106, y, _trunc(delivery, 48))
    y -= 18

    c.setFont('Helvetica', 8.5)
    c.drawString(ML, y, 'I/We the person/s named above as Mortgagor/s:')
    y -= 14

    terms = [
        f'1.  Require ({creditor}) to sell the Mortgaged goods:',
        '        a.  As soon as reasonably practicable; and',
        '        b.  For the best price that (Creditor) can reasonable obtain.',
        '',
        '2.  I/We acknowledge that the Mortgaged goods have already been delivered to the place '
        'of delivery as set out above',
        '    or will be delivered to the place of delivery within (7) seven days from the date '
        'of this Notice during ordinary business',
        '    hours.',
    ]
    for term in terms:
        if not term:
            y -= 6
            continue
        for ln in simpleSplit(term, 'Helvetica', 8.5, CW):
            c.drawString(ML, y, ln)
            y -= 12
    y -= 10

    c.setFont('Helvetica-Bold', 9)
    c.drawString(ML, y, 'Declaration:')
    y -= 16

    c.setFont('Helvetica', 8.5)
    c.drawString(ML, y, 'Mortgagor/s signature:')
    y -= 16
    _hr(c, y)
    y -= 8

    sig_w = CW
    sig_h = 80
    date_str = _v(data, 'repo_date')
    _sig_box(c, ML, y, sig_w, sig_h, f'Mortgagor/s: {mortgagor}', customer_sig, date_str)
    y -= (sig_h + 14)

    c.setFont('Helvetica', 8.5)
    c.drawString(ML, y, 'Print Name: _____________________________________')
    c.drawString(ML + CW * 0.6, y, 'Date:')
    y -= 20

    if agent_sig:
        _sig_box(c, ML, y, (CW - 14) / 2, 70,
                 f'Witness (Agent): {_v(data, "agent_name")}', agent_sig, date_str)

    c.save()
    buf.seek(0)
    return buf.read()


# =============================================================================
# 6. Auction Manager Letter
# =============================================================================

def generate_auction_letter_pdf(data):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Auction Manager Letter')

    y = PAGE_H - MT

    finance_company = _v(data, 'finance_company', 'client_name', default='the Finance Company')
    ref_number      = _v(data, 'account_number', 'client_reference', 'swpi_ref')
    make_model      = ' '.join(filter(None, [_v(data, 'year'), _v(data, 'make'),
                                             _v(data, 'model')])) or _v(data, 'description')
    registration    = _v(data, 'registration')
    engine_number   = _v(data, 'engine_number')
    vin             = _v(data, 'vin')

    c.setFont('Helvetica-Bold', 11)
    c.setFillColor(DARK)
    c.drawString(ML, y, 'TO THE AUCTION MANAGER')
    y -= 20

    body1 = (
        f'This unit has been repossessed on behalf of {finance_company}. '
        'Please assign this asset to their stock list'
    )
    c.setFont('Helvetica', 9.5)
    for ln in simpleSplit(body1, 'Helvetica', 9.5, CW):
        c.drawString(ML, y, ln)
        y -= 14
    y -= 8

    c.setFont('Helvetica', 9.5)
    c.drawString(ML, y, f'Please quote the following reference number: ')
    c.setFont('Helvetica-Bold', 9.5)
    c.drawString(ML + c.stringWidth('Please quote the following reference number: ',
                                    'Helvetica', 9.5), y, ref_number)
    y -= 18

    for label, value in [
        ('UNIT DETAILS:', make_model),
        ('REGO NO:', registration),
        ('ENGINE NUMBER:', engine_number),
        ('VIN number:', vin),
    ]:
        c.setFont('Helvetica-Bold', 9.5)
        lw = c.stringWidth(label, 'Helvetica-Bold', 9.5)
        c.drawString(ML, y, label)
        c.setFont('Helvetica', 9.5)
        c.drawString(ML + lw + 6, y, value)
        y -= 14
    y -= 12

    for para in [
        'Should you have any further queries, please contact this office.',
        '',
        'We thank you for your assistance.',
    ]:
        if not para:
            y -= 6
            continue
        c.setFont('Helvetica', 9.5)
        c.drawString(ML, y, para)
        y -= 14
    y -= 18

    c.setFont('Helvetica', 9.5)
    c.drawString(ML, y, 'Yours faithfully,')
    y -= 28

    agent_name = _v(data, 'agent_name')
    if agent_name:
        c.setFont('Helvetica-Bold', 9.5)
        c.drawString(ML, y, agent_name)
        y -= 14
    c.setFont('Helvetica-Bold', 9.5)
    c.drawString(ML, y, 'South West Process Serving & Investigative Agency')
    y -= 12
    c.setFont('Helvetica', 9)
    c.drawString(ML, y, '+61 429 996 260')
    y -= 10
    c.drawString(ML, y, 'PO Box 651, Sunshine VIC 3020')

    c.save()
    buf.seek(0)
    return buf.read()


# =============================================================================
# 7. Towing Contractor Letter
# =============================================================================

def generate_tow_letter_pdf(data):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Towing Contractor Letter')

    y = PAGE_H - MT

    client_name  = _v(data, 'client_name', 'finance_company', default='our office')
    client_email = _v(data, 'client_email')
    ref_number   = _v(data, 'swpi_ref', 'client_reference', 'account_number')
    make_model   = ' '.join(filter(None, [_v(data, 'year'), _v(data, 'make'),
                                          _v(data, 'model')])) or _v(data, 'description')
    registration = _v(data, 'registration')
    engine_number = _v(data, 'engine_number')
    vin           = _v(data, 'vin')
    deliver_to    = _v(data, 'deliver_to', default='')
    delivery_addr = _v(data, 'delivery_address', default='')

    c.setFont('Helvetica-Bold', 11)
    c.setFillColor(DARK)
    c.drawString(ML, y, 'TO THE TOWING CONTRACTOR')
    y -= 20

    c.setFont('Helvetica', 9.5)
    c.drawString(ML, y, 'Please arrange for your account to be sent as follows;')
    y -= 18

    for label, value in [
        ('Addressed to:', client_name),
        ('Email:', client_email or 'wmgrecoveries@wisegroup.com.au'),
        ('Tel:', '(02) 9210 0040'),
    ]:
        c.setFont('Helvetica-Bold', 9.5)
        lw = c.stringWidth(label, 'Helvetica-Bold', 9.5)
        c.drawString(ML, y, label)
        c.setFont('Helvetica', 9.5)
        c.drawString(ML + lw + 6, y, value)
        y -= 14
    y -= 8

    c.setFont('Helvetica', 9.5)
    c.drawString(ML, y, 'Please quote the following reference number and matter name;')
    y -= 14

    c.setFont('Helvetica-Bold', 9.5)
    c.drawString(ML, y, 'Reference Number: ')
    c.setFont('Helvetica', 9.5)
    c.drawString(ML + c.stringWidth('Reference Number: ', 'Helvetica-Bold', 9.5), y, ref_number)
    y -= 18

    for label, value in [
        ('UNIT DETAILS:', make_model),
        ('REGO NO:', registration),
        ('ENGINE NUMBER:', engine_number),
        ('VIN/CHASSIS:', vin),
    ]:
        c.setFont('Helvetica-Bold', 9.5)
        lw = c.stringWidth(label, 'Helvetica-Bold', 9.5)
        c.drawString(ML, y, label)
        c.setFont('Helvetica', 9.5)
        c.drawString(ML + lw + 6, y, value)
        y -= 14
    y -= 10

    c.setFont('Helvetica-Bold', 9.5)
    c.drawString(ML, y, 'PLEASE ARRANGE FOR THE UNIT TO BE DELIVERED TO:')
    y -= 14

    c.setFont('Helvetica-Bold', 9)
    c.drawString(ML, y, 'Name of Auction Yard: ')
    c.setFont('Helvetica', 9)
    c.drawString(ML + c.stringWidth('Name of Auction Yard: ', 'Helvetica-Bold', 9), y,
                 _trunc(deliver_to, 40) or '___________________________________')
    y -= 12

    c.setFont('Helvetica-Bold', 9)
    c.drawString(ML, y, 'Address: ')
    c.setFont('Helvetica', 9)
    c.drawString(ML + c.stringWidth('Address: ', 'Helvetica-Bold', 9), y,
                 _trunc(delivery_addr, 55) or '___________________________________')
    y -= 18

    nb = (
        'NB: If the vehicle is to be stored, the storage facility must have sufficient '
        'insurance to cover any damage sustained to the vehicle whilst in their possession.'
    )
    c.setFont('Helvetica', 8.5)
    for ln in simpleSplit(nb, 'Helvetica', 8.5, CW):
        c.drawString(ML, y, ln)
        y -= 12
    y -= 8

    c.drawString(ML, y, 'Should you have any further queries, please contact this office.')

    c.save()
    buf.seek(0)
    return buf.read()


# =============================================================================
# 8. Complete Repo Pack — merge all applicable docs into one PDF
# =============================================================================

def generate_repo_pack_pdf(pdfs: list[bytes]) -> bytes:
    """Merge a list of PDF byte strings into a single PDF using pypdf."""
    try:
        from pypdf import PdfWriter, PdfReader
        writer = PdfWriter()
        for pdf_bytes in pdfs:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        out.seek(0)
        return out.read()
    except Exception:
        # Fallback: just return the first PDF if merge fails
        return pdfs[0] if pdfs else b''
