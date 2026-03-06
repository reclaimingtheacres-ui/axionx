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
