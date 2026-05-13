import io
import os
import base64
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white, Color as _RLColor
from reportlab.lib.utils import ImageReader, simpleSplit
from pypdf import PdfReader as _PdfReader, PdfWriter as _PdfWriter

# ── Demo mode watermark ────────────────────────────────────────────────────────
# When AXIONX_DEMO_MODE=true every generated PDF receives a visible watermark so
# demo documents cannot be confused with operational documents.
_DEMO_MODE: bool = os.environ.get("AXIONX_DEMO_MODE", "").lower() in ("1", "true", "yes")


def _demo_watermark_pdf(pdf_bytes: bytes) -> bytes:
    """Overlay a visible DEMO watermark on every page of a PDF.
    Returns pdf_bytes unchanged if demo mode is off."""
    if not _DEMO_MODE or not pdf_bytes:
        return pdf_bytes
    try:
        reader = _PdfReader(io.BytesIO(pdf_bytes))
        writer = _PdfWriter()
        for page in reader.pages:
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)
            overlay_buf = io.BytesIO()
            c = rl_canvas.Canvas(overlay_buf, pagesize=(w, h))
            c.saveState()
            c.setFont("Helvetica-Bold", 38)
            c.setFillColor(_RLColor(0.80, 0.10, 0.10, alpha=0.22))
            c.translate(w / 2, h / 2)
            c.rotate(42)
            c.drawCentredString(0, 0, "DEMO — NOT FOR OPERATIONAL USE")
            c.restoreState()
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(_RLColor(0.85, 0.05, 0.05, alpha=0.85))
            c.drawCentredString(w / 2, h - 16, "DEMO DOCUMENT — NOT FOR OPERATIONAL USE")
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(_RLColor(0.85, 0.05, 0.05, alpha=0.75))
            c.drawCentredString(w / 2, 10, "DEMO DOCUMENT — NOT FOR OPERATIONAL USE")
            c.save()
            overlay_buf.seek(0)
            overlay_page = _PdfReader(overlay_buf).pages[0]
            page.merge_page(overlay_page)
            writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        out.seek(0)
        return out.read()
    except Exception:
        return pdf_bytes


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

VIR_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'static', 'templates', 'swpi_vir_blank.pdf')


def _v(d, *keys, default=''):
    for k in keys:
        v = d.get(k)
        if v:
            return str(v)
    return default


def _trunc(val, max_ch=40):
    s = str(val or '')
    return s[:max_ch] + ('\u2026' if len(s) > max_ch else '')


def _sig_to_img(sig_b64):
    raw_b64 = sig_b64.split(',')[-1]
    raw = base64.b64decode(raw_b64)
    return ImageReader(io.BytesIO(raw))


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
# 1. SWPI VIR — Surrendered / Repossession Receipt  (template overlay)
# =============================================================================

def _overlay_sig(c, x, y, w, h, sig_b64):
    if not sig_b64:
        return
    try:
        raw_b64 = sig_b64.split(',')[-1]
        raw = base64.b64decode(raw_b64)
        img = ImageReader(io.BytesIO(raw))
        c.drawImage(img, x, y, width=w, height=h,
                    preserveAspectRatio=True, mask='auto')
    except Exception:
        pass


def generate_vir_pdf(data, agent_sig=None, customer_sig=None):
    if not os.path.isfile(VIR_TEMPLATE_PATH):
        return _generate_vir_pdf_fallback(data, agent_sig, customer_sig)

    overlay_buf = io.BytesIO()
    c = rl_canvas.Canvas(overlay_buf, pagesize=A4)

    try:
        tpl = _PdfReader(VIR_TEMPLATE_PATH)
        tpl_page = tpl.pages[0]
        if '/Annots' in tpl_page:
            c.setFillColor(white)
            c.setStrokeColor(white)
            for annot_ref in tpl_page['/Annots']:
                a = annot_ref.get_object()
                if a.get('/Subtype') == '/Stamp':
                    continue
                r = a.get('/Rect')
                if r:
                    x0, y0, x1, y1 = float(r[0]), float(r[1]), float(r[2]), float(r[3])
                    if y0 > 700 and x0 < 200:
                        continue
                    c.rect(x0 - 1, y0 - 1, (x1 - x0) + 2, (y1 - y0) + 2, fill=1, stroke=0)
    except Exception:
        pass

    FONT = 'Helvetica'
    FONT_B = 'Helvetica-Bold'
    FS = 9
    c.setFillColor(DARK)

    def _put(x, y, val, font=FONT, fs=FS, max_ch=0):
        if not val:
            return
        c.setFont(font, fs)
        txt = str(val)
        if max_ch:
            txt = txt[:max_ch]
        c.drawString(x, y, txt)

    def _fmtdate(val):
        if not val:
            return ''
        s = str(val).strip()
        for fmt_in, fmt_out in [('%Y-%m-%d', '%d/%m/%Y'), ('%Y-%m-%dT%H:%M:%S', '%d/%m/%Y')]:
            try:
                from datetime import datetime as _dtm
                return _dtm.strptime(s[:len(fmt_in)+2], fmt_in).strftime(fmt_out)
            except (ValueError, IndexError):
                continue
        return s

    client_ref = _v(data, 'client_reference')
    registration = _v(data, 'registration')
    ref_display = client_ref or ''
    if registration and registration not in ref_display:
        ref_display = f'{ref_display} / {registration}' if ref_display else registration
    _put(321, 746, ref_display, max_ch=30)

    _put(481, 684, _v(data, 'swpi_ref'), max_ch=20)

    _put(130, 664, _v(data, 'finance_company'), max_ch=36)
    _put(459, 665, _fmtdate(_v(data, 'repo_date')), max_ch=12)

    _put(130, 642, _v(data, 'customer_name'), max_ch=36)
    _put(424, 643, _v(data, 'account_number'), max_ch=18)

    _put(211, 621, _v(data, 'repo_address'), max_ch=48)

    _put(32, 587, _v(data, 'year'), max_ch=6)
    _put(105, 587, _v(data, 'make'), max_ch=12)
    _put(185, 587, _v(data, 'model'), max_ch=14)
    _put(284, 587, _v(data, 'colour'), max_ch=16)
    _put(394, 586, _v(data, 'registration'), max_ch=10)
    _put(470, 586, _fmtdate(_v(data, 'rego_expiry')), max_ch=12)

    _put(110, 559, _v(data, 'vin'), max_ch=22)
    _put(110, 538, _v(data, 'engine_number'), max_ch=22)
    _put(110, 517, _v(data, 'speedometer'), max_ch=12)

    _put(135, 474, _v(data, 'person_present'), max_ch=14)

    keys_val = _v(data, 'keys_obtained')
    _put(303, 473, keys_val, max_ch=6)
    how_many = _v(data, 'how_many_keys')
    if how_many:
        _put(372, 473, how_many, max_ch=4)

    _put(504, 472, _v(data, 'vol_surrender'), max_ch=6)

    _put(135, 453, _v(data, 'form_13'), max_ch=6)
    _put(328, 453, _v(data, 'security_drivable'), max_ch=6)
    _put(505, 453, _v(data, 'police_notified'), max_ch=6)
    _put(505, 433, _v(data, 'station_officer'), max_ch=18)

    _put(207, 411, _v(data, 'personal_effects_removed'), max_ch=6)
    _put(83, 391, _v(data, 'personal_effects_list'), max_ch=72)

    _put(84, 327, _v(data, 'tyres'), max_ch=14)
    _put(221, 327, _v(data, 'body'), max_ch=14)
    _put(356, 327, _v(data, 'duco'), max_ch=14)
    _put(513, 327, _v(data, 'interior'), max_ch=14)

    _put(85, 306, _v(data, 'engine_condition'), max_ch=20)
    _put(265, 306, _v(data, 'transmission'), max_ch=20)

    _put(93, 281, _v(data, 'fuel_level'), max_ch=10)

    dmg = _v(data, 'damage_list') if _v(data, 'any_damage').upper() == 'YES' else _v(data, 'any_damage')
    _put(93, 260, dmg, max_ch=72)

    agent_name = _v(data, 'agent_name', default='')
    if agent_name:
        _put(44, 207, agent_name, font=FONT_B, max_ch=30)

    notice_del = _v(data, 'notice_delivery', default='')
    if notice_del:
        _put(32, 173, notice_del, fs=8, max_ch=80)

    date_str = _fmtdate(_v(data, 'repo_date'))
    _put(67, 81, date_str, max_ch=12)
    _put(427, 84, date_str, max_ch=12)

    from datetime import datetime as _dt
    signed_at = _dt.now().strftime('%d-%m-%Y %H:%M:%S')
    _put(452, 123, 'Signed at:', fs=7)
    _put(452, 115, signed_at, fs=7)

    _overlay_sig(c, 32, 95, 240, 65, customer_sig)
    _overlay_sig(c, 310, 95, 240, 65, agent_sig)

    c.save()
    overlay_buf.seek(0)

    template_reader = _PdfReader(VIR_TEMPLATE_PATH)
    overlay_reader = _PdfReader(overlay_buf)

    template_page = template_reader.pages[0]
    if '/Annots' in template_page:
        del template_page['/Annots']
    overlay_page = overlay_reader.pages[0]
    template_page.merge_page(overlay_page)

    writer = _PdfWriter()
    writer.add_page(template_page)
    out_buf = io.BytesIO()
    writer.write(out_buf)
    out_buf.seek(0)
    return out_buf.read()


def _generate_vir_pdf_fallback(data, agent_sig=None, customer_sig=None):
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
    y -= 11

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
    y -= 11

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
    y -= 11

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
    y -= 8

    title = 'TRANSPORT INSTRUCTIONS / TOW RECEIPT'
    c.setFont('Helvetica-Bold', 11)
    c.setFillColor(DARK)
    c.drawCentredString(PAGE_W / 2, y, title)
    y -= 4
    _hr(c, y, strong=True)
    y -= 16

    def _fmtdate_t(val):
        if not val: return ''
        s = str(val).strip()
        try:
            from datetime import datetime as _dtm
            return _dtm.strptime(s[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
        except (ValueError, IndexError):
            return s

    swpi_ref = _v(data, 'swpi_ref')
    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'SWPI REFERENCE:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 96, y, swpi_ref)
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'FINANCE COMPANY:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 100, y, _trunc(_v(data, 'finance_company'), 28))
    c.setFont('Helvetica-Bold', 8)
    c.drawString(PAGE_W - MR - 130, y, 'DATE:')
    c.setFont('Helvetica', 8)
    c.drawString(PAGE_W - MR - 100, y, _fmtdate_t(_v(data, 'repo_date')))
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'CUSTOMER NAME:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 88, y, _trunc(_v(data, 'customer_name'), 38))
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'REPOSSESSION ADDRESS:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 126, y, _trunc(_v(data, 'repo_address'), 42))
    y -= 8
    _hr(c, y)
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'SECURITY DETAILS')
    y -= 14

    make_model = ' '.join(filter(None, [_v(data, 'make'), _v(data, 'model')])) or ''
    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'MAKE / MODEL:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 78, y, _trunc(make_model, 30))
    c.setFont('Helvetica-Bold', 8)
    c.drawString(PAGE_W - MR - 130, y, 'REGO:')
    c.setFont('Helvetica', 8)
    c.drawString(PAGE_W - MR - 98, y, _v(data, 'registration'))
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'VIN:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 28, y, _v(data, 'vin'))
    y -= 8
    _hr(c, y)
    y -= 14

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
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'TOW COSTS:')
    c.setFont('Helvetica', 8)
    c.drawString(ML + 62, y, _v(data, 'tow_costs') or 'TBA')
    y -= 8
    _hr(c, y)
    y -= 10

    delivery_label = 'PLEASE DELIVER THE ABOVE ASSET TO THE FOLLOWING AUCTION FACILITY'
    c.setFont('Helvetica-Bold', 8.5)
    c.setFillColor(DARK)
    c.drawCentredString(PAGE_W / 2, y, delivery_label)
    y -= 8
    _hr(c, y)
    y -= 14

    deliver_to = _v(data, 'deliver_to', 'delivery_address')
    delivery_addr = _v(data, 'delivery_address')
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(PAGE_W / 2, y, _trunc(deliver_to, 60))
    if delivery_addr and delivery_addr != deliver_to:
        y -= 14
        c.setFont('Helvetica', 9)
        c.drawCentredString(PAGE_W / 2, y, _trunc(delivery_addr, 70))
    y -= 10
    _hr(c, y)
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'SEND YOUR INVOICE DIRECT TO:')
    y -= 14
    client_name  = _v(data, 'client_name')
    client_email = _v(data, 'client_email')
    c.setFont('Helvetica', 8.5)
    c.drawString(ML, y, _trunc(client_name, 50))
    if client_email:
        y -= 14
        c.setFont('Helvetica-Bold', 8)
        c.drawString(ML, y, 'EMAIL:')
        c.setFont('Helvetica', 8.5)
        c.drawString(ML + 38, y, _trunc(client_email, 50))
    y -= 10
    _hr(c, y)
    y -= 14

    c.setFont('Helvetica-Bold', 8)
    c.drawString(ML, y, 'REFERENCE / JOB NUMBER:')
    y -= 14
    ref = ' / '.join(filter(None, [_v(data, 'client_reference'),
                                   _v(data, 'registration')])) or _v(data, 'swpi_ref')
    c.setFont('Helvetica', 9)
    c.drawString(ML, y, ref)
    y -= 22

    agent_name = _v(data, 'agent_name', default='Agent')
    sig_w = (CW - 14) / 2
    sig_h = 80
    date_str = _fmtdate_t(_v(data, 'repo_date'))
    _sig_box(c, ML, y, sig_w, sig_h, f'AGENT SIGNATURE: {agent_name}', agent_sig, date_str)
    _sig_box(c, ML + sig_w + 14, y, sig_w, sig_h, 'TOW SIGNATURE:', tow_sig, date_str)

    c.save()
    buf.seek(0)
    return buf.read()


# =============================================================================
# 3. Wise Group — Vehicle Inspection Report
# =============================================================================

_WISE_VIR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'static', 'templates', 'wise', 'wise_vir.pdf')
_WISE_AUCTION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'static', 'templates', 'wise', 'wise_auction.pdf')
_WISE_TOW_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'static', 'templates', 'wise', 'wise_tow.pdf')


def _wise_tick(c, x, y, sz=8):
    c.setFont('ZapfDingbats', sz)
    c.drawString(x, y, '\u2714')


def generate_wise_vir_pdf(data, agent_sig=None, customer_sig=None):
    from pypdf import PdfReader, PdfWriter

    tmpl_reader = PdfReader(_WISE_VIR_PATH)
    tmpl_page = tmpl_reader.pages[0]

    overlay_buf = io.BytesIO()
    c = rl_canvas.Canvas(overlay_buf, pagesize=A4)
    c.setFillColor(DARK)
    F = 'Helvetica'
    FB = 'Helvetica-Bold'
    SZ = 9

    wise_ref = _v(data, 'wise_case_number')
    if wise_ref:
        c.setFont(FB, 9)
        c.drawString(274, 760, wise_ref)
        c.setFont(F, SZ)

    c.setFont(F, SZ)
    c.drawString(173, 720, _v(data, 'customer_name'))

    from reportlab.pdfbase.pdfmetrics import stringWidth as _sw
    _make_str = _v(data, 'make')
    _model_str = _v(data, 'model')
    _ymm_sz = SZ
    while _ymm_sz > 6.5 and (_sw(_make_str, F, _ymm_sz) > 55 or _sw(_model_str, F, _ymm_sz) > 80):
        _ymm_sz -= 0.5
    c.setFont(F, _ymm_sz)
    c.drawString(126, 664, _v(data, 'year'))
    c.drawString(251, 664, _make_str)
    c.drawString(371, 664, _model_str)
    c.setFont(F, SZ)

    c.drawString(152, 651, _v(data, 'body_type'))
    c.drawString(270, 651, _v(data, 'colour'))
    c.drawString(376, 651, _v(data, 'registration'))
    c.drawString(167, 638, _v(data, 'vin'))

    def _check_condition(val, option):
        if not val:
            return False
        return val.strip().upper() == option.upper()

    body_val = _v(data, 'body')
    paint_val = _v(data, 'duco')
    bumper_val = _v(data, 'bumpers') or body_val
    glass_val = _v(data, 'glass')
    tyres_val = _v(data, 'tyres')

    ext4_xs = [255, 339, 425, 517]
    cond_rows = [
        (567, body_val,   ['POOR', 'GOOD', 'EXCELLENT', 'DAMAGED'], ext4_xs),
        (552, paint_val,  ['POOR', 'GOOD', 'EXCELLENT', 'DAMAGED'], ext4_xs),
        (536, bumper_val, ['POOR', 'GOOD', 'EXCELLENT', 'DAMAGED'], ext4_xs),
        (521, glass_val,  ['BROKEN', 'CRACKED', 'GOOD', None],      [255, 339, 425]),
        (506, tyres_val,  ['BALD', 'FAIR', 'GOOD', 'EXCELLENT'],    [255, 339, 425, 517]),
    ]

    for row_y, val, opts, xs in cond_rows:
        for j, opt in enumerate(opts):
            if opt and _check_condition(val, opt):
                _wise_tick(c, xs[j], row_y)

    drive_val = _v(data, 'security_drivable')
    if drive_val:
        if drive_val.strip().upper() in ('YES', 'Y', 'TRUE'):
            _wise_tick(c, 277, 463)
        else:
            _wise_tick(c, 341, 463)

    eng = _v(data, 'engine_condition').lower()
    if eng:
        eng_ok = eng not in ('damaged', 'poor', 'missing', 'no', 'n/a')
        if eng_ok:
            _wise_tick(c, 511, 463)
        else:
            _wise_tick(c, 555, 463)

    interior_val = _v(data, 'interior')
    int_xs = [243, 315, 425]
    int_rows = [
        (419, interior_val, ['POOR', 'GOOD', 'EXCELLENT']),
        (404, interior_val, ['POOR', 'GOOD', 'EXCELLENT']),
        (388, interior_val, ['POOR', 'GOOD', 'EXCELLENT']),
    ]
    for row_y, val, opts in int_rows:
        for j, opt in enumerate(opts):
            if _check_condition(val, opt):
                _wise_tick(c, int_xs[j], row_y)

    c.setFont(F, SZ)
    km = _v(data, 'speedometer')
    if km:
        c.drawString(181, 346, km)

    keys_val = _v(data, 'keys_obtained')
    if keys_val and keys_val.strip().upper() in ('YES', 'Y', 'TRUE'):
        c.drawString(440, 346, 'YES')
    elif keys_val:
        c.drawString(440, 346, 'NO')

    keys_qty = _v(data, 'how_many_keys')
    if keys_qty:
        c.drawString(498, 346, keys_qty)

    accessories = _v(data, 'accessories')
    if accessories:
        c.setFont(F, 8)
        for i, ln in enumerate(simpleSplit(accessories[:200], F, 8, CW - 20)[:2]):
            c.drawString(57, 302 - i * 12, ln)

    dmg_val = _v(data, 'damage_list')
    if dmg_val:
        c.setFont(F, 8)
        for i, ln in enumerate(simpleSplit(dmg_val[:300], F, 8, CW - 20)[:3]):
            c.drawString(57, 245 - i * 12, ln)

    c.setFont(F, SZ)
    tow_name = _v(data, 'tow_company_name')
    if tow_name:
        c.drawString(148, 184, tow_name)

    tow_cost = _v(data, 'tow_costs')
    if tow_cost:
        cost_str = '$' + tow_cost if not tow_cost.startswith('$') else tow_cost
        c.drawString(426, 184, cost_str)

    # DELIVERED TO: keep name and address on separate lines, each constrained
    # to max 255pts so they cannot overflow into the HELD AT TOWING YARD column
    # (which starts at x=426 with its template label beginning around x=310).
    _DELIV_MAX_W = 255
    deliver_to = _v(data, 'deliver_to')
    delivery_addr = _v(data, 'delivery_address')
    c.setFont(F, 8)
    _deliv_y = 170
    if deliver_to:
        ln = simpleSplit(deliver_to[:100], F, 8, _DELIV_MAX_W)
        c.drawString(162, _deliv_y, ln[0] if ln else deliver_to[:40])
        _deliv_y -= 11
    if delivery_addr and delivery_addr != deliver_to:
        ln = simpleSplit(delivery_addr[:100], F, 8, _DELIV_MAX_W)
        c.drawString(162, _deliv_y, ln[0] if ln else delivery_addr[:40])

    held_at = _v(data, 'tow_company_name')
    if held_at:
        c.drawString(426, 170, held_at[:30])
    c.setFont(F, SZ)

    redeem = _v(data, 'vol_surrender')
    if redeem:
        if redeem.strip().upper() in ('YES', 'Y', 'TRUE'):
            _wise_tick(c, 423, 124)
        else:
            _wise_tick(c, 526, 124)

    if agent_sig:
        try:
            sig_img = _sig_to_img(agent_sig)
            c.drawImage(sig_img, 57, 65, width=120, height=35,
                        preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    if customer_sig:
        try:
            sig_img = _sig_to_img(customer_sig)
            c.drawImage(sig_img, 310, 65, width=120, height=35,
                        preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    c.save()
    overlay_buf.seek(0)

    overlay_reader = PdfReader(overlay_buf)
    tmpl_page.merge_page(overlay_reader.pages[0])

    writer = PdfWriter()
    writer.add_page(tmpl_page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def generate_wise_auction_pdf(data):
    from pypdf import PdfReader, PdfWriter

    tmpl_reader = PdfReader(_WISE_AUCTION_PATH)
    tmpl_page = tmpl_reader.pages[0]

    overlay_buf = io.BytesIO()
    c = rl_canvas.Canvas(overlay_buf, pagesize=A4)
    c.setFillColor(DARK)
    F = 'Helvetica'
    FB = 'Helvetica-Bold'
    SZ = 10

    c.setFont(F, SZ)

    lender = _v(data, 'lender', 'finance_company', 'client_name')
    if lender:
        lsz = SZ
        max_w = 75
        while c.stringWidth(lender, F, lsz) > max_w and lsz > 5:
            lsz -= 0.5
        if c.stringWidth(lender, F, lsz) > max_w:
            while len(lender) > 1 and c.stringWidth(lender + '…', F, lsz) > max_w:
                lender = lender[:-1]
            lender = lender.rstrip() + '…'
        c.setFont(F, lsz)
        c.drawString(280, 681, lender)
        c.setFont(F, SZ)

    third_party = _v(data, 'third_party')
    if third_party:
        c.setFont(F, 8)
        c.drawString(360, 664, '3rd Party: ' + third_party)
        c.setFont(F, SZ)

    ref = _v(data, 'wise_case_number')
    if ref:
        c.drawString(100, 625, ref)

    unit = ' '.join(filter(None, [_v(data, 'year'), _v(data, 'make'), _v(data, 'model')]))
    if unit:
        c.drawString(130, 610, unit)

    rego = _v(data, 'registration')
    if rego:
        c.drawString(115, 595, rego)

    engine = _v(data, 'engine_number')
    if engine:
        c.drawString(160, 581, engine)

    vin = _v(data, 'vin')
    if vin:
        c.drawString(82, 566, vin)

    c.save()
    overlay_buf.seek(0)

    overlay_reader = PdfReader(overlay_buf)
    tmpl_page.merge_page(overlay_reader.pages[0])

    writer = PdfWriter()
    writer.add_page(tmpl_page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def generate_wise_tow_pdf(data):
    from pypdf import PdfReader, PdfWriter

    tmpl_reader = PdfReader(_WISE_TOW_PATH)
    tmpl_page = tmpl_reader.pages[0]

    overlay_buf = io.BytesIO()
    c = rl_canvas.Canvas(overlay_buf, pagesize=A4)
    c.setFillColor(DARK)
    F = 'Helvetica'
    SZ = 10

    c.setFont(F, SZ)

    ref = _v(data, 'wise_case_number')
    if ref:
        c.drawString(160, 548, ref)

    matter = _v(data, 'customer_name')
    if matter:
        ref_w = c.stringWidth(ref or '', F, SZ)
        matter_x = 160 + ref_w + 15 if ref else 160
        c.drawString(matter_x, 548, matter)

    unit = ' '.join(filter(None, [_v(data, 'year'), _v(data, 'make'), _v(data, 'model')]))
    if unit:
        c.drawString(130, 522, unit)

    rego = _v(data, 'registration')
    if rego:
        c.drawString(110, 495, rego)

    engine = _v(data, 'engine_number')
    if engine:
        c.drawString(155, 468, engine)

    vin = _v(data, 'vin')
    if vin:
        c.drawString(125, 441, vin)

    yard_name = _v(data, 'auction_yard_name', 'deliver_to')
    if yard_name:
        c.drawString(170, 361, yard_name)

    yard_addr = _v(data, 'delivery_address')
    if yard_addr:
        c.drawString(100, 334, yard_addr)

    c.save()
    overlay_buf.seek(0)

    overlay_reader = PdfReader(overlay_buf)
    tmpl_page.merge_page(overlay_reader.pages[0])

    writer = PdfWriter()
    writer.add_page(tmpl_page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


# =============================================================================
# 4. Form 13 — Consent to Enter Premises (NCCP Schedule 1)
# =============================================================================

def generate_form_13_pdf(data, occupant_sig=None, agent_sig=None):
    import os
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.colors import white as RL_WHITE

    TMPL_PATH = os.path.join(os.path.dirname(__file__),
                             'static', 'templates', 'generic_form_13.pdf')
    reader = PdfReader(TMPL_PATH)
    tmpl_page = reader.pages[0]
    pw = float(tmpl_page.mediabox.width)
    ph = float(tmpl_page.mediabox.height)

    overlay_buf = io.BytesIO()
    c = rl_canvas.Canvas(overlay_buf, pagesize=(pw, ph))

    def _fmtdate13(val):
        if not val: return ''
        s = str(val).strip()
        try:
            from datetime import datetime as _dtm
            return _dtm.strptime(s[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
        except (ValueError, IndexError):
            return s

    c.setFillColor(RL_WHITE)
    c.rect(465, 670, 85, 16, fill=1, stroke=0)
    c.rect(370, 627, 170, 16, fill=1, stroke=0)
    c.rect(350, 555, 200, 16, fill=1, stroke=0)
    c.rect(320, 473, 230, 14, fill=1, stroke=0)
    c.rect(320, 447, 230, 14, fill=1, stroke=0)
    c.rect(49, 350, 290, 18, fill=1, stroke=0)
    c.rect(55, 183, 490, 16, fill=1, stroke=0)

    annots = tmpl_page.get('/Annots')
    if annots:
        for a in annots:
            obj = a.get_object()
            rect = obj.get('/Rect')
            ic = obj.get('/IC')
            if rect and ic and list(ic) == [1]:
                x0, y0, x1, y1 = [float(v) for v in rect]
                c.rect(x0 - 1, y0 - 1, (x1 - x0) + 2, (y1 - y0) + 2, fill=1, stroke=0)

    c.setFillColor(DARK)
    FONT = 'Helvetica'
    FONT_B = 'Helvetica-Bold'

    SZ = 10

    c.setFont(FONT_B, 10)
    c.drawString(420, 673, 'Date')

    date_str = _fmtdate13(_v(data, 'repo_date'))
    if date_str:
        c.setFont(FONT, SZ)
        c.drawString(470, 673, date_str)

    credit_provider = _v(data, 'finance_company', 'client_name')
    if credit_provider:
        c.setFont(FONT, SZ)
        c.drawString(370, 633, _trunc(credit_provider, 35))

    occupier_name = _v(data, 'customer_name')
    if occupier_name:
        c.setFont(FONT, SZ)
        c.drawString(350, 562, _trunc(occupier_name, 35))

    occupier_addr = _v(data, 'repo_address')
    if occupier_addr:
        parts = occupier_addr.split(',', 1)
        addr_line1 = parts[0].strip()
        addr_line2 = parts[1].strip() if len(parts) > 1 else ''
        c.setFont(FONT, SZ)
        c.drawString(320, 477, _trunc(addr_line1, 40))
        if addr_line2:
            c.drawString(320, 450, _trunc(addr_line2, 40))

    make_model = ' '.join(filter(None, [_v(data, 'year'), _v(data, 'make').upper(),
                                        _v(data, 'model').upper()])) or _v(data, 'description')
    vin = _v(data, 'vin')
    goods_desc = make_model
    if vin:
        goods_desc += f', VIN/CHASSIS: {vin}'
    if goods_desc:
        c.setFont(FONT, SZ)
        c.drawString(57, 357, _trunc(goods_desc, 80))

    if occupant_sig:
        try:
            sig_img = _sig_to_img(occupant_sig)
            c.drawImage(sig_img, 240, 245, width=130, height=40,
                        preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    agent_name = _v(data, 'agent_name')
    swpi_addr = 'C/o SWPi Recoveries, PO Box 651 Sunshine Vic 3020'
    rep_line = f'{agent_name}, {swpi_addr}' if agent_name else swpi_addr
    c.setFont(FONT, 7.5)
    c.drawString(57, 190, _trunc(rep_line, 100))

    if agent_sig:
        try:
            sig_img = _sig_to_img(agent_sig)
            c.drawImage(sig_img, 380, 180, width=130, height=40,
                        preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    c.save()
    overlay_buf.seek(0)

    overlay_reader = PdfReader(overlay_buf)
    overlay_page = overlay_reader.pages[0]

    if annots:
        if '/Annots' in tmpl_page:
            del tmpl_page['/Annots']

    tmpl_page.merge_page(overlay_page)

    writer = PdfWriter()
    writer.add_page(tmpl_page)
    out_buf = io.BytesIO()
    writer.write(out_buf)
    out_buf.seek(0)
    return out_buf.read()


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
# 8. Previous File Notes — historical record attached on job clone
# =============================================================================

def generate_previous_file_notes_pdf(job_data: dict, notes: list) -> bytes:
    """
    Generate a worksheet-style PDF of all original file notes for a cloned job.

    job_data keys: job_number, client_name, customer_name, lender_name,
                   job_address, asset_details, generated_date
    notes: list of dicts with keys: created_at, author_name, note_type, note_text
           sorted oldest-first
    Returns: PDF bytes
    """
    from datetime import datetime as _dt

    BOTTOM   = 58        # bottom margin — trigger new page
    HDR_H    = 14        # note-header bar height
    LINE_H   = 11        # body line height
    LABEL_W  = 112       # width reserved for row labels

    buf = io.BytesIO()
    c   = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Previous File Notes')

    y = [PAGE_H - MT]    # mutable via closure

    def _new_page():
        c.showPage()
        y[0] = PAGE_H - MT
        job_no = job_data.get('job_number', '')
        c.setFont('Helvetica-Bold', 8.5)
        c.setFillColor(MUTED)
        c.drawString(ML, y[0], f'PREVIOUS FILE NOTES \u2014 {job_no} (continued)')
        y[0] -= 8
        _hr(c, y[0])
        y[0] -= 14

    def _det(label, val):
        if not val:
            return
        lines = simpleSplit(str(val), 'Helvetica', 8.5, CW - LABEL_W)
        c.setFont('Helvetica-Bold', 8.5)
        c.setFillColor(MUTED)
        c.drawString(ML, y[0], label)
        c.setFont('Helvetica', 8.5)
        c.setFillColor(DARK)
        for ln in lines:
            c.drawString(ML + LABEL_W, y[0], ln)
            y[0] -= 13

    # ── Page 1 letterhead + title ──────────────────────────────────────────
    y[0] = _swpi_letterhead(c)
    y[0] -= 8

    c.setFont('Helvetica-Bold', 13)
    c.setFillColor(DARK)
    c.drawCentredString(PAGE_W / 2, y[0], 'PREVIOUS FILE NOTES')
    y[0] -= 6
    _hr(c, y[0], strong=True)
    y[0] -= 16

    # ── Job details header block ───────────────────────────────────────────
    _det('Original Job No.:',   job_data.get('job_number'))
    _det('Client:',             job_data.get('client_name'))
    _det('Customer Name:',      job_data.get('customer_name'))
    if job_data.get('lender_name'):
        _det('Lender:',         job_data.get('lender_name'))
    _det('Address:',            job_data.get('job_address'))
    if job_data.get('asset_details'):
        _det('Security / Asset:', job_data.get('asset_details'))
    _det('PDF Generated:',      job_data.get('generated_date'))

    y[0] -= 4
    _hr(c, y[0])
    y[0] -= 16

    # ── No notes case ──────────────────────────────────────────────────────
    if not notes:
        c.setFont('Helvetica', 9)
        c.setFillColor(MUTED)
        c.drawCentredString(PAGE_W / 2, y[0], 'No previous file notes recorded.')
        c.save()
        buf.seek(0)
        return buf.read()

    # ── Note count line ────────────────────────────────────────────────────
    n = len(notes)
    c.setFont('Helvetica-Bold', 8.5)
    c.setFillColor(MUTED)
    c.drawString(ML, y[0], f'{n} note{"s" if n != 1 else ""} — oldest to newest')
    y[0] -= 16

    # ── Notes ──────────────────────────────────────────────────────────────
    for note in notes:
        # Format timestamp
        raw_ts = note.get('created_at', '')
        try:
            parsed  = _dt.strptime(str(raw_ts)[:19], '%Y-%m-%d %H:%M:%S')
            date_str = parsed.strftime('%d/%m/%Y %H:%M')
        except Exception:
            date_str = str(raw_ts)[:16]

        author     = (note.get('author_name') or 'System').strip()
        note_type  = (note.get('note_type')   or '').strip()
        note_text  = (note.get('note_text')   or '').strip()

        # Header line text
        header_line = f'{date_str}  \u2014  {author}'
        if note_type:
            header_line += f'  [{note_type}]'

        # Wrap body text — split on newlines first, then wrap each paragraph
        body_lines = []
        for para in note_text.split('\n'):
            stripped = para.strip()
            if stripped:
                body_lines.extend(simpleSplit(stripped, 'Helvetica', 8.5, CW - 12))
            else:
                body_lines.append('')   # blank line between paragraphs

        needed_h = HDR_H + len(body_lines) * LINE_H + 10
        if y[0] - needed_h < BOTTOM:
            _new_page()

        # Note header bar
        c.setFillColor(HexColor('#f3f4f6'))
        c.rect(ML, y[0] - HDR_H + 2, CW, HDR_H, fill=1, stroke=0)
        c.setFont('Helvetica-Bold', 8.5)
        c.setFillColor(DARK)
        c.drawString(ML + 4, y[0] - HDR_H + 5, header_line)
        y[0] -= HDR_H

        # Note body
        c.setFont('Helvetica', 8.5)
        c.setFillColor(DARK)
        for line in body_lines:
            if y[0] < BOTTOM:
                _new_page()
            if line:
                c.drawString(ML + 8, y[0], line)
            y[0] -= LINE_H

        y[0] -= 8   # gap between notes

    c.save()
    buf.seek(0)
    return buf.read()


# =============================================================================
# 9. Complete Repo Pack — merge all applicable docs into one PDF
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


# ── Demo watermark wrappers ────────────────────────────────────────────────────
# In demo mode (AXIONX_DEMO_MODE=true) wrap every public document generator so
# its output is stamped "DEMO DOCUMENT — NOT FOR OPERATIONAL USE" on every page.
if _DEMO_MODE:
    def _wrap_pdf(fn):
        from functools import wraps as _fw
        @_fw(fn)
        def _inner(*a, **kw):
            return _demo_watermark_pdf(fn(*a, **kw))
        return _inner

    generate_vir_pdf             = _wrap_pdf(generate_vir_pdf)
    generate_transport_pdf       = _wrap_pdf(generate_transport_pdf)
    generate_wise_vir_pdf        = _wrap_pdf(generate_wise_vir_pdf)
    generate_wise_auction_pdf    = _wrap_pdf(generate_wise_auction_pdf)
    generate_wise_tow_pdf        = _wrap_pdf(generate_wise_tow_pdf)
    generate_form_13_pdf         = _wrap_pdf(generate_form_13_pdf)
    generate_voluntary_surrender_pdf = _wrap_pdf(generate_voluntary_surrender_pdf)
    generate_auction_letter_pdf  = _wrap_pdf(generate_auction_letter_pdf)
    generate_tow_letter_pdf      = _wrap_pdf(generate_tow_letter_pdf)
    generate_previous_file_notes_pdf = _wrap_pdf(generate_previous_file_notes_pdf)
    generate_repo_pack_pdf       = _wrap_pdf(generate_repo_pack_pdf)
