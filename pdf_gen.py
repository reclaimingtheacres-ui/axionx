import io
import os
import base64
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader, simpleSplit

PAGE_W, PAGE_H = A4
ML = 36
MR = 36
MT = 38
CW = PAGE_W - ML - MR

BLUE     = HexColor('#2563eb')
BLUE_LT  = HexColor('#dbeafe')
DARK     = HexColor('#111827')
MUTED    = HexColor('#6b7280')
LINE     = HexColor('#d1d5db')
ROW_ALT  = HexColor('#f9fafb')
ROW_H    = 18
LABEL_F  = ('Helvetica', 7.5)
VALUE_F  = ('Helvetica-Bold', 8.5)
_LW      = {1: 140, 2: 95, 3: 62, 4: 42}

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'static', 'images', 'swpi_logo.jpg')


def _v(d, *keys, default=''):
    for k in keys:
        v = d.get(k)
        if v:
            return str(v)
    return default


def _trunc(val, max_ch=32):
    s = str(val or '')
    return s[:max_ch] + ('…' if len(s) > max_ch else '')


def _section_hdr(c, y, title):
    c.setFillColor(BLUE)
    c.rect(ML, y - 16, CW, 16, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(ML + 6, y - 11.5, title.upper())
    return y - 16


def _row(c, y, pairs, alt=False):
    n = len(pairs)
    col = CW / n
    lw  = _LW.get(n, 95)
    if alt:
        c.setFillColor(ROW_ALT)
        c.rect(ML, y - ROW_H, CW, ROW_H, fill=1, stroke=0)
    for i, (lbl, val) in enumerate(pairs):
        x = ML + i * col
        max_ch = max(8, int((col - lw - 10) / 5.0))
        c.setFont(*LABEL_F)
        c.setFillColor(MUTED)
        c.drawString(x + 4, y - 12, str(lbl))
        c.setFont(*VALUE_F)
        c.setFillColor(DARK)
        c.drawString(x + lw, y - 12, _trunc(val, max_ch))
    c.setStrokeColor(LINE)
    c.setLineWidth(0.3)
    c.line(ML, y - ROW_H, PAGE_W - MR, y - ROW_H)
    return y - ROW_H


def _frow(c, y, lbl, val, alt=False):
    return _row(c, y, [(lbl, val)], alt)


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
    c.drawString(x + 6, y - h + 10, str(label)[:45])
    if date_str:
        c.drawRightString(x + w - 6, y - h + 10, f'Dated: {date_str}')


def _page_header(c, doc_title):
    y = PAGE_H - MT
    logo_h, logo_w = 50, 80
    try:
        c.drawImage(LOGO_PATH, ML, y - logo_h, width=logo_w, height=logo_h,
                    preserveAspectRatio=True, mask='auto')
    except Exception:
        c.setFont('Helvetica-Bold', 10)
        c.setFillColor(BLUE)
        c.drawString(ML, y - 20, 'SWPI')
    tx = ML + logo_w + 14
    c.setFont('Helvetica-Bold', 11)
    c.setFillColor(DARK)
    c.drawString(tx, y - 13, 'South West Process Serving & Investigative Agency')
    c.setFont('Helvetica', 9)
    c.setFillColor(MUTED)
    c.drawString(tx, y - 25, 'PO Box 651, Sunshine, VIC 3020')
    c.drawString(tx, y - 36, 'Phone: +61 429 996 260')
    sep_y = y - logo_h - 8
    c.setStrokeColor(LINE)
    c.setLineWidth(0.75)
    c.line(ML, sep_y, PAGE_W - MR, sep_y)
    tb_y = sep_y - 2
    c.setFillColor(BLUE)
    c.rect(ML, tb_y - 20, CW, 20, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 10)
    c.drawCentredString(PAGE_W / 2, tb_y - 14, doc_title.upper())
    return tb_y - 20 - 5


def generate_vir_pdf(data, agent_sig=None, customer_sig=None):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Vehicle Condition Report / Repossession Receipt')
    c.setAuthor('South West Process Serving & Investigative Agency')

    y = _page_header(c, 'Vehicle Condition Report / Repossession Receipt')
    y -= 2

    y = _section_hdr(c, y, 'Job Details')
    y = _row(c, y, [('Client', _v(data, 'client_name')),
                    ('Client Reference', _v(data, 'client_reference'))])
    y = _row(c, y, [('SWPI Reference', _v(data, 'swpi_ref')),
                    ('Finance Company', _v(data, 'finance_company'))], alt=True)
    y = _row(c, y, [('Date', _v(data, 'repo_date')),
                    ('Account Number', _v(data, 'account_number'))])
    y = _frow(c, y, 'Customer Name', _v(data, 'customer_name'), alt=True)
    y = _frow(c, y, 'Surrendered / Repossessed From Address',
              _v(data, 'repo_address'))
    y -= 3

    y = _section_hdr(c, y, 'Asset Details')
    y = _row(c, y, [('Year', _v(data, 'year')), ('Make', _v(data, 'make')),
                    ('Model', _v(data, 'model')), ('Colour', _v(data, 'colour'))],
             alt=True)
    y = _row(c, y, [('Registration', _v(data, 'registration')),
                    ('Rego Expiry', _v(data, 'rego_expiry'))])
    y = _row(c, y, [('VIN / Chassis', _v(data, 'vin')),
                    ('Engine Number', _v(data, 'engine_number'))], alt=True)
    y = _row(c, y, [('Odometer (km)', _v(data, 'speedometer')),
                    ('Description', _v(data, 'description'))])
    y -= 3

    y = _section_hdr(c, y, 'Recovery Details')
    keys_val = _v(data, 'keys_obtained')
    if keys_val == 'Yes' and _v(data, 'how_many_keys'):
        keys_val += f" ({_v(data, 'how_many_keys')} key(s))"
    y = _row(c, y, [('Person Present', _v(data, 'person_present')),
                    ('Keys Obtained', keys_val)], alt=True)
    y = _row(c, y, [('Voluntary Surrender', _v(data, 'vol_surrender')),
                    ('Lien Paid', _v(data, 'lien_paid'))])
    form13 = _v(data, 'form_13')
    if form13 == 'Yes' and _v(data, 'form_13_signed_by'):
        form13 += f", Signed By: {_v(data, 'form_13_signed_by')}"
    y = _row(c, y, [('Form 13', form13),
                    ('Security Drivable', _v(data, 'security_drivable'))], alt=True)
    police = _v(data, 'police_notified')
    if police == 'Yes' and _v(data, 'station_officer'):
        police += f" — {_v(data, 'station_officer')}"
    y = _frow(c, y, 'Police Notified', police)
    effects = _v(data, 'personal_effects_removed')
    if effects == 'Yes' and _v(data, 'removed_by_who'):
        effects += f", Removed By: {_v(data, 'removed_by_who')}"
    y = _frow(c, y, 'Personal Effects Removed', effects, alt=True)
    if _v(data, 'personal_effects_list'):
        y = _frow(c, y, 'List of Effects', _v(data, 'personal_effects_list'))
    y -= 3

    y = _section_hdr(c, y, 'Condition Report')
    y = _row(c, y, [('Tyres', _v(data, 'tyres')), ('Body', _v(data, 'body')),
                    ('Duco', _v(data, 'duco'))], alt=True)
    y = _row(c, y, [('Interior', _v(data, 'interior')),
                    ('Engine', _v(data, 'engine_condition')),
                    ('Transmission', _v(data, 'transmission'))])
    damage = _v(data, 'any_damage')
    if damage == 'Yes' and _v(data, 'damage_list'):
        damage += f": {_trunc(_v(data, 'damage_list'), 50)}"
    y = _row(c, y, [('Fuel Level', _v(data, 'fuel_level')), ('Damage', damage)],
             alt=True)
    y -= 6

    agent_name = _v(data, 'agent_name', default='the above agent')
    legal1 = (
        f"I, {agent_name}, mercantile agent, acting on behalf of the above financier, "
        "hereby certify that a true copy of this notice was furnished to the above named."
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
    sig_h = 75
    date_str = _v(data, 'repo_date')
    _sig_box(c, ML, y, sig_w, sig_h, 'Customer Signature', customer_sig, date_str)
    _sig_box(c, ML + sig_w + 14, y, sig_w, sig_h,
             f'Agent / Mercantile Agent: {agent_name}', agent_sig, date_str)

    c.save()
    buf.seek(0)
    return buf.read()


def generate_transport_pdf(data, agent_sig=None, tow_sig=None):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Transport Instructions / Tow Receipt')
    c.setAuthor('South West Process Serving & Investigative Agency')

    y = _page_header(c, 'Transport Instructions / Tow Receipt')
    y -= 2

    y = _section_hdr(c, y, 'Job Details')
    y = _row(c, y, [('SWPI Reference', _v(data, 'swpi_ref')),
                    ('Finance Company', _v(data, 'finance_company'))])
    y = _row(c, y, [('Date', _v(data, 'repo_date')),
                    ('Customer Name', _v(data, 'customer_name'))], alt=True)
    y = _frow(c, y, 'Repossession Address', _v(data, 'repo_address'))
    y -= 3

    y = _section_hdr(c, y, 'Security Details')
    make_model = ' '.join(filter(None, [_v(data, 'make'), _v(data, 'model')])) or '—'
    y = _row(c, y, [('Make / Model', make_model),
                    ('Registration', _v(data, 'registration'))], alt=True)
    y = _frow(c, y, 'VIN / Chassis', _v(data, 'vin'))
    y -= 3

    y = _section_hdr(c, y, 'Tow Contractor Details')
    y = _row(c, y, [('Tow Company', _v(data, 'tow_company_name')),
                    ('Phone', _v(data, 'tow_phone'))], alt=True)
    y = _frow(c, y, 'Tow Costs', _v(data, 'tow_costs') or 'TBA')
    y -= 3

    y = _section_hdr(c, y, 'Delivery Instructions')
    c.setFillColor(BLUE_LT)
    c.rect(ML, y - ROW_H, CW, ROW_H, fill=1, stroke=0)
    c.setFont('Helvetica-Bold', 8.5)
    c.setFillColor(BLUE)
    c.drawString(ML + 6, y - 12, 'Please deliver the above asset to the following facility:')
    c.setStrokeColor(LINE)
    c.setLineWidth(0.3)
    c.line(ML, y - ROW_H, PAGE_W - MR, y - ROW_H)
    y -= ROW_H

    y = _frow(c, y, 'Deliver To', _v(data, 'deliver_to'), alt=True)
    y = _frow(c, y, 'Delivery Address', _v(data, 'delivery_address'))
    invoice_val = _v(data, 'client_name')
    if _v(data, 'client_email'):
        invoice_val += f"  —  {_v(data, 'client_email')}"
    y = _frow(c, y, 'Send Invoice Direct To', invoice_val, alt=True)
    ref = ' / '.join(filter(None, [_v(data, 'client_reference'),
                                   _v(data, 'registration')])) or _v(data, 'swpi_ref')
    y = _frow(c, y, 'Reference / Job Number', ref)
    y -= 8

    agent_name = _v(data, 'agent_name', default='Agent')
    sig_w = (CW - 14) / 2
    sig_h = 82
    date_str = _v(data, 'repo_date')
    _sig_box(c, ML, y, sig_w, sig_h,
             f'Agent Signature: {agent_name}', agent_sig, date_str)
    _sig_box(c, ML + sig_w + 14, y, sig_w, sig_h,
             'Tow Operator Signature', tow_sig, date_str)

    c.save()
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
# Wise Vehicle Inspection Report
# ─────────────────────────────────────────────────────────────────────────────

_WISE_AMBER = HexColor('#f59e0b')
_WISE_DARK  = HexColor('#1e293b')

def _wise_header(c, case_number=''):
    y = PAGE_H - MT
    logo_h, logo_w = 50, 80
    try:
        c.drawImage(LOGO_PATH, ML, y - logo_h, width=logo_w, height=logo_h,
                    preserveAspectRatio=True, mask='auto')
    except Exception:
        pass
    tx = ML + logo_w + 14
    c.setFont('Helvetica-Bold', 11)
    c.setFillColor(_WISE_DARK)
    c.drawString(tx, y - 13, 'South West Process Serving & Investigative Agency')
    c.setFont('Helvetica', 9)
    c.setFillColor(MUTED)
    c.drawString(tx, y - 26, 'Wisely Accredited Agent  |  PO Box 651, Sunshine VIC 3020')
    c.drawString(tx, y - 38, 'Phone: +61 429 996 260')

    sep_y = y - logo_h - 8
    c.setStrokeColor(LINE)
    c.setLineWidth(0.75)
    c.line(ML, sep_y, PAGE_W - MR, sep_y)

    tb_y = sep_y - 2
    c.setFillColor(_WISE_AMBER)
    c.rect(ML, tb_y - 20, CW, 20, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 10)
    title = 'VEHICLE INSPECTION REPORT'
    if case_number:
        title += f'  —  WISE CASE {case_number}'
    c.drawCentredString(PAGE_W / 2, tb_y - 14, title)
    return tb_y - 20 - 5


def _cb(c, x, y, label, checked=False, w=8, h=8):
    """Draw a checkbox with label."""
    c.setStrokeColor(DARK)
    c.setLineWidth(0.75)
    c.rect(x, y - h + 1, w, h, fill=0, stroke=1)
    if checked:
        c.setFont('Helvetica-Bold', 8)
        c.setFillColor(DARK)
        c.drawString(x + 1.5, y - h + 2.5, 'X')
    c.setFont('Helvetica', 8)
    c.setFillColor(DARK)
    c.drawString(x + w + 4, y - h + 2, label)
    return x + w + 4 + len(label) * 5.2 + 10


def _condition_checked(val, option):
    """Map a condition text value to whether a checkbox should be checked."""
    if not val:
        return False
    v = val.strip().lower()
    o = option.strip().lower()
    return o in v or v in o


def _vir_condition_row(c, y, label, val, options):
    """Draw a condition label + checkbox row."""
    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(DARK)
    c.drawString(ML + 4, y - 9, label + ':')
    x = ML + 90
    for opt in options:
        x = _cb(c, x, y, opt, _condition_checked(val, opt))
    c.setStrokeColor(LINE)
    c.setLineWidth(0.25)
    c.line(ML, y - 14, PAGE_W - MR, y - 14)
    return y - 14


def generate_wise_vir_pdf(data, agent_sig=None, customer_sig=None):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Wise Group — Vehicle Inspection Report')

    case_number = _v(data, 'wise_case_number', 'swpi_ref')
    y = _wise_header(c, case_number)
    y -= 4

    # Debtor
    c.setFont('Helvetica-Bold', 9)
    c.setFillColor(DARK)
    c.drawString(ML, y, 'Name of Debtor:')
    c.setFont('Helvetica', 9)
    c.drawString(ML + 90, y, _v(data, 'customer_name', default=''))
    y -= 16

    # Vehicle description header
    c.setFillColor(_WISE_AMBER)
    c.rect(ML, y - 14, CW, 14, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(ML + 6, y - 10, 'VEHICLE DESCRIPTION')
    y -= 14

    # Year / Make / Model
    c.setFillColor(ROW_ALT)
    c.rect(ML, y - 14, CW, 14, fill=1, stroke=0)
    col3 = CW / 3
    for i, (lbl, field) in enumerate([('YEAR', 'year'), ('MAKE', 'make'), ('MODEL', 'model')]):
        x = ML + i * col3
        c.setFont('Helvetica-Bold', 7.5)
        c.setFillColor(MUTED)
        c.drawString(x + 4, y - 9, lbl + ':')
        c.setFont('Helvetica', 8.5)
        c.setFillColor(DARK)
        c.drawString(x + 38, y - 9, _trunc(_v(data, field), 18))
    c.setStrokeColor(LINE); c.setLineWidth(0.3)
    c.line(ML, y - 14, PAGE_W - MR, y - 14)
    y -= 14

    col4 = CW / 4
    for i, (lbl, field) in enumerate([('BODY TYPE', 'body_type'), ('COLOUR', 'colour'),
                                       ('REGO', 'registration'), ('ENGINE #', 'engine_number')]):
        x = ML + i * col4
        c.setFont('Helvetica-Bold', 7.5)
        c.setFillColor(MUTED)
        c.drawString(x + 4, y - 9, lbl + ':')
        c.setFont('Helvetica', 8.5)
        c.setFillColor(DARK)
        c.drawString(x + int(col4 * 0.5), y - 9, _trunc(_v(data, field), 10))
    c.setStrokeColor(LINE); c.setLineWidth(0.3)
    c.line(ML, y - 14, PAGE_W - MR, y - 14)
    y -= 14

    c.setFillColor(ROW_ALT)
    c.rect(ML, y - 14, CW, 14, fill=1, stroke=0)
    c.setFont('Helvetica-Bold', 7.5); c.setFillColor(MUTED)
    c.drawString(ML + 4, y - 9, 'VIN/CHASSIS:')
    c.setFont('Helvetica', 8.5); c.setFillColor(DARK)
    c.drawString(ML + 72, y - 9, _v(data, 'vin'))
    c.setStrokeColor(LINE); c.setLineWidth(0.3)
    c.line(ML, y - 14, PAGE_W - MR, y - 14)
    y -= 18

    # Condition — Exterior
    c.setFillColor(_WISE_AMBER); c.rect(ML, y - 14, CW, 14, fill=1, stroke=0)
    c.setFillColor(white); c.setFont('Helvetica-Bold', 8.5)
    c.drawString(ML + 6, y - 10, 'VEHICLE CONDITION  —  EXTERIOR')
    y -= 14

    for lbl, field, opts in [
        ('BODY',    'body',  ['POOR', 'GOOD', 'EXCELLENT', 'DAMAGED']),
        ('PAINT',   'duco',  ['POOR', 'GOOD', 'EXCELLENT', 'DAMAGED']),
        ('BUMPERS', 'body',  ['POOR', 'GOOD', 'EXCELLENT', 'DAMAGED']),
        ('WINDOWS', 'glass', ['BROKEN', 'CRACKED', 'GOOD']),
        ('TYRES',   'tyres', ['BALD', 'FAIR', 'GOOD', 'EXCELLENT']),
    ]:
        y = _vir_condition_row(c, y, lbl, _v(data, field), opts)
    y -= 4

    # Mechanical
    c.setFillColor(_WISE_AMBER); c.rect(ML, y - 14, CW, 14, fill=1, stroke=0)
    c.setFillColor(white); c.setFont('Helvetica-Bold', 8.5)
    c.drawString(ML + 6, y - 10, 'MECHANICAL')
    y -= 14

    c.setFont('Helvetica-Bold', 8); c.setFillColor(DARK)
    c.drawString(ML + 4, y - 9, 'DOES VEHICLE DRIVE:')
    xb = ML + 120
    xb = _cb(c, xb, y, 'YES', _v(data, 'security_drivable').upper() == 'YES')
    xb = _cb(c, xb, y, 'NO',  _v(data, 'security_drivable').upper() == 'NO')
    xb += 20
    c.drawString(xb, y - 9, 'ENGINE INTACT:')
    xb2 = xb + 82
    eng_ok = _v(data, 'engine_condition').lower() not in ('damaged', 'poor', 'missing', 'no')
    xb2 = _cb(c, xb2, y, 'YES', eng_ok and bool(_v(data, 'engine_condition')))
    _cb(c, xb2, y, 'NO', not eng_ok and bool(_v(data, 'engine_condition')))
    c.setStrokeColor(LINE); c.setLineWidth(0.25)
    c.line(ML, y - 14, PAGE_W - MR, y - 14)
    y -= 18

    # Interior
    c.setFillColor(_WISE_AMBER); c.rect(ML, y - 14, CW, 14, fill=1, stroke=0)
    c.setFillColor(white); c.setFont('Helvetica-Bold', 8.5)
    c.drawString(ML + 6, y - 10, 'INTERIOR')
    y -= 14

    for lbl, field, opts in [
        ('TRIM',   'interior', ['POOR', 'GOOD', 'EXCELLENT']),
        ('CARPET', 'interior', ['POOR', 'GOOD', 'EXCELLENT']),
        ('DASH',   'interior', ['POOR', 'GOOD', 'EXCELLENT']),
    ]:
        y = _vir_condition_row(c, y, lbl, _v(data, field), opts)
    y -= 4

    # Other
    c.setFillColor(_WISE_AMBER); c.rect(ML, y - 14, CW, 14, fill=1, stroke=0)
    c.setFillColor(white); c.setFont('Helvetica-Bold', 8.5)
    c.drawString(ML + 6, y - 10, 'OTHER')
    y -= 14

    km = _v(data, 'speedometer')
    c.setFont('Helvetica-Bold', 8); c.setFillColor(DARK)
    c.drawString(ML + 4, y - 9, "KM'S ON CLOCK:")
    c.setFont('Helvetica', 8)
    c.drawString(ML + 88, y - 9, km or '___________________')
    xb = ML + int(CW * 0.45)
    keys_yes = _v(data, 'keys_obtained').upper() == 'YES'
    c.setFont('Helvetica-Bold', 8)
    c.drawString(xb, y - 9, 'KEYS SECURED:')
    xb2 = xb + 76
    xb2 = _cb(c, xb2, y, 'YES', keys_yes)
    _cb(c, xb2, y, 'NO', not keys_yes)
    c.setStrokeColor(LINE); c.setLineWidth(0.25)
    c.line(ML, y - 14, PAGE_W - MR, y - 14)
    y -= 14

    c.setFont('Helvetica-Bold', 8); c.setFillColor(DARK)
    c.drawString(ML + 4, y - 9, 'PLATES ATTACHED:')
    xb = ML + 96
    xb = _cb(c, xb, y, 'YES', True)
    _cb(c, xb, y, 'NO', False)
    c.setStrokeColor(LINE); c.setLineWidth(0.25)
    c.line(ML, y - 14, PAGE_W - MR, y - 14)
    y -= 14

    c.setFont('Helvetica-Bold', 8); c.setFillColor(DARK)
    c.drawString(ML + 4, y - 9, 'ACCESSORIES:')
    c.setStrokeColor(MUTED); c.setLineWidth(0.5)
    c.line(ML + 80, y - 10, PAGE_W - MR, y - 10)
    c.setStrokeColor(LINE); c.setLineWidth(0.25)
    c.line(ML, y - 14, PAGE_W - MR, y - 14)
    y -= 18

    # Damage box
    c.setFont('Helvetica-Bold', 8); c.setFillColor(DARK)
    c.drawString(ML + 4, y - 8, 'DETAILS OF ANY DAMAGE:')
    dmg_val = _v(data, 'damage_list') if _v(data, 'any_damage').upper() == 'YES' else ''
    c.setFillColor(ROW_ALT)
    c.rect(ML, y - 42, CW, 32, fill=1, stroke=0)
    c.setStrokeColor(LINE); c.setLineWidth(0.5)
    c.rect(ML, y - 42, CW, 32, fill=0, stroke=1)
    if dmg_val:
        c.setFont('Helvetica', 8); c.setFillColor(DARK)
        for i, ln in enumerate(simpleSplit(dmg_val[:200], 'Helvetica', 8, CW - 8)[:3]):
            c.drawString(ML + 4, y - 18 - i * 11, ln)
    y -= 46

    # Tow / delivery
    c.setFont('Helvetica-Bold', 8); c.setFillColor(DARK)
    c.drawString(ML + 4, y - 9, 'TOWED BY:')
    c.setFont('Helvetica', 8)
    tow_name = _v(data, 'tow_company_name')
    c.drawString(ML + 54, y - 9, tow_name)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML + int(CW * 0.47), y - 9, 'TOWING COST: $')
    c.setFont('Helvetica', 8)
    c.drawString(ML + int(CW * 0.47) + 82, y - 9, _v(data, 'tow_costs'))
    c.setStrokeColor(LINE); c.setLineWidth(0.25)
    c.line(ML, y - 14, PAGE_W - MR, y - 14)
    y -= 14

    c.setFont('Helvetica-Bold', 8); c.setFillColor(DARK)
    c.drawString(ML + 4, y - 9, 'DELIVERED TO:')
    xb = ML + 80
    delivery = _v(data, 'deliver_to', 'delivery_address').upper()
    for yard in ['MANHEIM', 'PICKLES', 'HELD AT TOWING YARD', 'OTHER']:
        xb = _cb(c, xb, y, yard, yard.split()[0] in delivery)
    c.setStrokeColor(LINE); c.setLineWidth(0.25)
    c.line(ML, y - 14, PAGE_W - MR, y - 14)
    y -= 20

    # Signatures
    agent_name = _v(data, 'agent_name')
    sig_w = (CW - 14) / 2
    sig_h = 70
    date_str = _v(data, 'repo_date')
    _sig_box(c, ML, y, sig_w, sig_h, f'Agent: {agent_name}', agent_sig, date_str)
    _sig_box(c, ML + sig_w + 14, y, sig_w, sig_h, 'Customer Signature', customer_sig, date_str)

    c.save()
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
# Form 13 — Notice to Occupier / NCCP Entry to Take Possession
# ─────────────────────────────────────────────────────────────────────────────

def generate_form_13_pdf(data, occupant_sig=None, agent_sig=None):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Form 13 — Notice to Occupier of Premises')

    y = _page_header(c, 'FORM 13 — NOTICE TO OCCUPIER OF PREMISES')
    y -= 4

    c.setFillColor(HexColor('#fef9c3'))
    c.rect(ML, y - 28, CW, 28, fill=1, stroke=0)
    c.setStrokeColor(HexColor('#fde047'))
    c.setLineWidth(0.75)
    c.rect(ML, y - 28, CW, 28, fill=0, stroke=1)
    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(HexColor('#78350f'))
    c.drawString(ML + 8, y - 12,
        'National Consumer Credit Protection Act 2009, Schedule 1 — National Credit Code')
    c.setFont('Helvetica', 7.5)
    c.setFillColor(HexColor('#92400e'))
    c.drawString(ML + 8, y - 22,
        'Required when entering premises to take possession of mortgaged goods under a consumer credit contract.')
    y -= 36

    y = _section_hdr(c, y, 'Creditor Details')
    y = _row(c, y, [('Creditor / Finance Company', _v(data, 'finance_company', 'client_name')),
                    ('Client Reference', _v(data, 'client_reference'))])
    y = _row(c, y, [('SWPI Reference', _v(data, 'swpi_ref')),
                    ('Account Number', _v(data, 'account_number'))], alt=True)
    y -= 3

    y = _section_hdr(c, y, 'Debtor / Mortgagor Details')
    y = _frow(c, y, 'Full Name of Mortgagor', _v(data, 'customer_name'))
    y = _frow(c, y, 'Address of Premises', _v(data, 'repo_address'), alt=True)
    y -= 3

    y = _section_hdr(c, y, 'Goods Subject to Mortgage')
    make_model = ' '.join(filter(None, [_v(data, 'year'), _v(data, 'make'),
                                        _v(data, 'model')])) or _v(data, 'description')
    y = _row(c, y, [('Year / Make / Model', make_model), ('Registration', _v(data, 'registration'))])
    y = _row(c, y, [('VIN / Chassis', _v(data, 'vin')), ('Engine Number', _v(data, 'engine_number'))],
             alt=True)
    y -= 3

    y = _section_hdr(c, y, 'Notice')
    notice_text = (
        "TO THE OCCUPIER: You are hereby given notice that the above-named mercantile agent, acting "
        "on behalf of the above creditor, intends to enter the above premises for the purpose of taking "
        "possession of the above-described mortgaged goods pursuant to the National Consumer Credit "
        "Protection Act 2009 and the terms of the credit contract.\n\n"
        "Pursuant to Section 100 of the National Credit Code, this notice is given to you as an occupier "
        "of the premises. The mortgagor has failed to meet their obligations under the credit contract "
        "and the creditor is entitled to take possession of the mortgaged goods.\n\n"
        "If the goods are not voluntarily surrendered, the creditor may apply to a court for an order to "
        "take possession. You may contact the creditor or seek independent legal advice."
    )
    tx = ML + 6
    ty = y - 10
    c.setFont('Helvetica', 8)
    c.setFillColor(DARK)
    for line in simpleSplit(notice_text, 'Helvetica', 8, CW - 12):
        c.drawString(tx, ty, line)
        ty -= 11
    y = ty - 6

    y = _section_hdr(c, y, 'Acknowledgement by Occupier')
    ack_text = (
        "I, the undersigned occupier of the above premises, acknowledge receipt of this notice and "
        "that a copy of this Form 13 has been delivered to me in accordance with the National Credit Code."
    )
    ty = y - 10
    for line in simpleSplit(ack_text, 'Helvetica', 8, CW - 12):
        c.drawString(tx, ty, line)
        ty -= 11
    y = ty - 10

    agent_name = _v(data, 'agent_name')
    date_str = _v(data, 'repo_date')
    sig_w = (CW - 14) / 2
    sig_h = 80

    _sig_box(c, ML, y, sig_w, sig_h, 'Signature of Occupier / Mortgagor', occupant_sig, date_str)
    _sig_box(c, ML + sig_w + 14, y, sig_w, sig_h,
             f'Mercantile Agent: {agent_name}', agent_sig, date_str)

    c.save()
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
# Voluntary Surrender Form — NCC Section 78(1)
# ─────────────────────────────────────────────────────────────────────────────

def generate_voluntary_surrender_pdf(data, customer_sig=None, agent_sig=None):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Voluntary Surrender of Mortgaged Goods — Section 78(1) NCC')

    y = _page_header(c, 'VOLUNTARY SURRENDER OF MORTGAGED GOODS — SEC 78(1) NCC')
    y -= 4

    c.setFillColor(HexColor('#fef9c3'))
    c.rect(ML, y - 28, CW, 28, fill=1, stroke=0)
    c.setStrokeColor(HexColor('#fde047'))
    c.setLineWidth(0.75)
    c.rect(ML, y - 28, CW, 28, fill=0, stroke=1)
    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(HexColor('#78350f'))
    c.drawString(ML + 8, y - 12,
        'National Consumer Credit Protection Act 2009, Schedule 1, Section 78(1) — Voluntary Surrender')
    c.setFont('Helvetica', 7.5)
    c.setFillColor(HexColor('#92400e'))
    c.drawString(ML + 8, y - 22,
        'A debtor under a consumer credit contract may voluntarily surrender possession of mortgaged goods.')
    y -= 36

    y = _section_hdr(c, y, 'Credit Provider / Creditor Details')
    y = _row(c, y, [('Finance Company', _v(data, 'finance_company', 'client_name')),
                    ('Account Number', _v(data, 'account_number'))])
    y = _row(c, y, [('Client Reference', _v(data, 'client_reference')),
                    ('SWPI Reference', _v(data, 'swpi_ref'))], alt=True)
    y -= 3

    y = _section_hdr(c, y, 'Debtor Details')
    y = _frow(c, y, 'Full Name of Debtor', _v(data, 'customer_name'))
    y = _frow(c, y, 'Address', _v(data, 'repo_address'), alt=True)
    y -= 3

    y = _section_hdr(c, y, 'Goods Being Surrendered')
    make_model = ' '.join(filter(None, [_v(data, 'year'), _v(data, 'make'),
                                        _v(data, 'model')])) or _v(data, 'description')
    y = _row(c, y, [('Year / Make / Model', make_model), ('Registration', _v(data, 'registration'))])
    y = _row(c, y, [('VIN / Chassis', _v(data, 'vin')), ('Engine Number', _v(data, 'engine_number'))],
             alt=True)
    y -= 3

    y = _section_hdr(c, y, 'Declaration')
    cust = _v(data, 'customer_name') or '___________________________________'
    addr = _v(data, 'repo_address') or '___________________________________'
    decl_text = (
        f"I, {cust}, of {addr}, being the debtor/mortgagor under the above-referenced consumer "
        "credit contract, DO HEREBY VOLUNTARILY SURRENDER possession of the above-described goods to "
        "the credit provider pursuant to Section 78(1) of the National Consumer Credit Protection Act "
        "2009, Schedule 1 (National Credit Code).\n\n"
        "I acknowledge and declare that:\n"
        "1. I am surrendering possession of the mortgaged goods of my own free will without duress.\n"
        "2. I understand that voluntarily surrendering the goods does not extinguish my liability under "
        "the credit contract.\n"
        "3. I may be liable for any shortfall between the proceeds of sale and the amount outstanding.\n"
        "4. I have been given the opportunity to seek independent legal advice prior to signing.\n"
        "5. The goods are surrendered on the date below in the condition noted in the Vehicle Inspection Report."
    )
    tx = ML + 6
    ty = y - 10
    c.setFont('Helvetica', 8)
    c.setFillColor(DARK)
    for line in simpleSplit(decl_text, 'Helvetica', 8, CW - 12):
        c.drawString(tx, ty, line)
        ty -= 11
    y = ty - 10

    agent_name = _v(data, 'agent_name')
    date_str = _v(data, 'repo_date')
    sig_w = (CW - 14) / 2
    sig_h = 82

    _sig_box(c, ML, y, sig_w, sig_h, 'Debtor / Customer Signature', customer_sig, date_str)
    _sig_box(c, ML + sig_w + 14, y, sig_w, sig_h,
             f'Mercantile Agent Witness: {agent_name}', agent_sig, date_str)

    c.save()
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
# Auction Manager Letter
# ─────────────────────────────────────────────────────────────────────────────

def generate_auction_letter_pdf(data):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Auction Manager Letter')

    y = _page_header(c, 'LETTER TO AUCTION MANAGER')
    y -= 10

    date_str     = _v(data, 'repo_date', default='')
    deliver_to   = _v(data, 'deliver_to', 'delivery_address', default='Auction House')
    ref_line     = ' / '.join(filter(None, [_v(data, 'swpi_ref'), _v(data, 'client_reference'),
                                            _v(data, 'wise_case_number')]))
    make_model   = ' '.join(filter(None, [_v(data, 'year'), _v(data, 'make'),
                                          _v(data, 'model')])) or _v(data, 'description')
    agent_name   = _v(data, 'agent_name')
    client_name  = _v(data, 'client_name', 'finance_company')

    paras = [
        (True,  f"Date: {date_str}"),
        (False, ""),
        (False, f"Dear Auction Manager — {deliver_to},"),
        (False, ""),
        (True,  f"RE: VEHICLE DELIVERY  |  Reference: {ref_line}"),
        (False, ""),
        (False, f"Please be advised that SWPI, acting on behalf of {client_name}, has repossessed the "
                "following security interest vehicle, which is being delivered to your facility for "
                "storage and auction:"),
        (False, ""),
        (False, f"  Make / Model:     {make_model}"),
        (False, f"  Registration:     {_v(data, 'registration')}"),
        (False, f"  VIN / Chassis:    {_v(data, 'vin')}"),
        (False, f"  Colour:           {_v(data, 'colour')}"),
        (False, f"  Year:             {_v(data, 'year')}"),
        (False, ""),
        (False, f"  Finance Company:  {_v(data, 'finance_company', 'client_name')}"),
        (False, f"  Account Number:   {_v(data, 'account_number')}"),
        (False, f"  Client Reference: {_v(data, 'client_reference')}"),
        (False, ""),
        (False, "Please arrange to store the vehicle securely and prepare for auction in accordance with "
                "standing instructions. Contact our office with any queries."),
        (False, ""),
        (False, f"Please send the invoice for storage and auction charges directly to {client_name}, "
                f"referencing: {ref_line}"),
        (False, ""),
        (True,  "IMPORTANT: Photograph the vehicle on receipt and note any damage."),
        (False, ""),
        (False, "Yours faithfully,"),
        (False, ""),
        (False, ""),
        (True,  agent_name),
        (False, "South West Process Serving & Investigative Agency"),
        (False, "Phone: +61 429 996 260"),
    ]

    tx = ML + 6
    ty = y - 6
    c.setFillColor(DARK)
    for bold, para in paras:
        c.setFont('Helvetica-Bold' if bold else 'Helvetica', 9)
        lines_p = simpleSplit(para, 'Helvetica', 9, CW - 12) if para else ['']
        for ln in lines_p:
            c.drawString(tx, ty, ln)
            ty -= 13
        if not para:
            ty -= 2

    c.save()
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────────────────────────────────────
# Towing Contractor Letter
# ─────────────────────────────────────────────────────────────────────────────

def generate_tow_letter_pdf(data):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Towing Contractor Letter')

    y = _page_header(c, 'LETTER TO TOWING CONTRACTOR')
    y -= 10

    date_str         = _v(data, 'repo_date', default='')
    tow_company      = _v(data, 'tow_company_name', default='Towing Contractor')
    deliver_to       = _v(data, 'deliver_to', default='Auction Yard')
    delivery_address = _v(data, 'delivery_address', default='')
    ref_line         = ' / '.join(filter(None, [_v(data, 'swpi_ref'), _v(data, 'client_reference'),
                                                _v(data, 'wise_case_number')]))
    make_model       = ' '.join(filter(None, [_v(data, 'year'), _v(data, 'make'),
                                              _v(data, 'model')])) or _v(data, 'description')
    agent_name       = _v(data, 'agent_name')
    repo_address     = _v(data, 'repo_address', default='')

    paras = [
        (True,  f"Date: {date_str}"),
        (False, ""),
        (False, f"Dear {tow_company},"),
        (False, ""),
        (True,  f"RE: TOWING INSTRUCTIONS  |  Reference: {ref_line}"),
        (False, ""),
        (False, "Please collect and deliver the following vehicle to the auction facility as detailed below. "
                "Please attend the collection address at the earliest opportunity."),
        (False, ""),
        (True,  "COLLECTION DETAILS:"),
        (False, f"  Address:         {repo_address}"),
        (False, f"  Make / Model:    {make_model}"),
        (False, f"  Registration:    {_v(data, 'registration')}"),
        (False, f"  VIN / Chassis:   {_v(data, 'vin')}"),
        (False, f"  Colour:          {_v(data, 'colour')}"),
        (False, ""),
        (True,  "DELIVERY DETAILS:"),
        (False, f"  Deliver To:      {deliver_to}"),
        (False, f"  Address:         {delivery_address}"),
        (False, f"  Reference:       {ref_line}"),
        (False, ""),
        (True,  "IMPORTANT INSTRUCTIONS:"),
        (False, "  •  Inspect and photograph the vehicle before loading — note all pre-existing damage."),
        (False, "  •  Do not allow removal of goods without written authority from our office."),
        (False, "  •  Contact our office if any issues arise: +61 429 996 260"),
        (False, "  •  Submit invoice directly to the finance company quoting the above reference."),
        (False, ""),
        (False, "Please sign and return a copy of this letter to confirm receipt of instructions."),
        (False, ""),
        (False, "Yours faithfully,"),
        (False, ""),
        (False, ""),
        (True,  agent_name),
        (False, "South West Process Serving & Investigative Agency"),
        (False, "Phone: +61 429 996 260"),
    ]

    tx = ML + 6
    ty = y - 6
    c.setFillColor(DARK)
    for bold, para in paras:
        c.setFont('Helvetica-Bold' if bold else 'Helvetica', 9)
        lines_p = simpleSplit(para, 'Helvetica', 9, CW - 12) if para else ['']
        for ln in lines_p:
            c.drawString(tx, ty, ln)
            ty -= 13
        if not para:
            ty -= 2

    c.save()
    buf.seek(0)
    return buf.read()

