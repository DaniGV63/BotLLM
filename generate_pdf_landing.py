"""Genera atendoo_comercial.pdf - one-pager comercial para reuniones con clientes."""

from fpdf import FPDF, XPos, YPos

WA_GREEN       = (7, 94, 84)
WA_GREEN_LIGHT = (37, 211, 102)
WHITE          = (255, 255, 255)
LIGHT_GRAY     = (248, 249, 250)
DARK_GRAY      = (55, 65, 81)
MID_GRAY       = (107, 114, 128)
GREEN_TEXT     = (22, 101, 52)
GREEN_BG       = (220, 252, 231)


class PDF(FPDF):
    def header(self) -> None:
        pass

    def footer(self) -> None:
        self.set_y(-11)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*MID_GRAY)
        self.cell(
            0, 5,
            "Atendoo · Asistente de WhatsApp para clinicas · atendoo.app",
            align="C",
        )

    def colored_rect(self, x: float, y: float, w: float, h: float, color: tuple) -> None:
        self.set_fill_color(*color)
        self.rect(x, y, w, h, style="F")

    def cell_nl(self, w: float, h: float, text: str, **kw) -> None:
        """cell con new_x/new_y para evitar el DeprecationWarning de ln=True."""
        self.cell(w, h, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, **kw)


def build_pdf() -> None:
    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_margins(14, 14, 14)
    W = 182  # ancho util

    # ── CABECERA ──────────────────────────────────────────────────────────────
    pdf.colored_rect(0, 0, 210, 36, WA_GREEN)

    pdf.set_xy(14, 5)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*WHITE)
    pdf.cell_nl(W, 9, "Atendoo")

    pdf.set_xy(14, 15)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell_nl(W, 6, "Tu asistente de WhatsApp que agenda citas por ti")

    pdf.set_xy(14, 23)
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(190, 235, 215)
    pdf.cell_nl(W, 5, "Disponible 24/7  |  Sin apps nuevas  |  Sin permanencia")

    # ── BENEFICIOS (3 tarjetas) ───────────────────────────────────────────────
    pdf.set_y(41)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*DARK_GRAY)
    pdf.cell_nl(W, 6, "Por que Atendoo?", align="C")

    cards = [
        ("Disponible 24/7",   "Los pacientes reservan a cualquier hora.\nTu duermes, el bot trabaja."),
        ("Sin no-shows",      "Recordatorio automatico 24h antes.\nMenos olvidos, menos huecos vacios."),
        ("Sin apps nuevas",   "Funciona en el WhatsApp que ya usan\ntodos. Cero friccion."),
    ]
    card_w, gap, cy = 57, 5.5, pdf.get_y() + 2

    for i, (title, body) in enumerate(cards):
        cx = 14 + i * (card_w + gap)
        pdf.colored_rect(cx, cy, card_w, 22, GREEN_BG)
        pdf.set_xy(cx + 3, cy + 2)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*GREEN_TEXT)
        pdf.cell(card_w - 6, 5, title)
        pdf.set_xy(cx + 3, cy + 8)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*DARK_GRAY)
        pdf.multi_cell(card_w - 6, 3.8, body)

    # ── QUE HACE (lista 2 columnas) ───────────────────────────────────────────
    pdf.set_y(cy + 27)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*DARK_GRAY)
    pdf.cell_nl(W, 6, "Que puede hacer el bot?", align="C")

    features = [
        ("Agendar citas",        "Muestra huecos disponibles y crea la cita en Google Calendar."),
        ("Modificar / cancelar", "El paciente cambia su cita sin llamar ni esperar respuesta."),
        ("Responder dudas",      "Precios, horarios, servicios, politica de cancelacion."),
        ("Recordatorios 24h",    "Avisa automaticamente antes de cada sesion por WhatsApp."),
    ]
    feat_y = pdf.get_y()
    col_w = 87

    for i, (title, desc) in enumerate(features):
        col = i % 2
        row = i // 2
        fx = 14 + col * (col_w + 8)
        fy = feat_y + row * 12

        pdf.set_xy(fx, fy)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*WA_GREEN)
        pdf.cell(5, 4, "->")
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*DARK_GRAY)
        pdf.cell(col_w - 5, 4, title)

        pdf.set_xy(fx + 5, fy + 5)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*MID_GRAY)
        pdf.multi_cell(col_w - 7, 3.5, desc)

    # ── DEMO WHATSAPP ─────────────────────────────────────────────────────────
    demo_y = feat_y + 25
    pdf.set_y(demo_y)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*DARK_GRAY)
    pdf.cell_nl(W, 6, "Asi funciona en WhatsApp", align="C")

    chat_x, chat_y = 52, pdf.get_y() + 1
    chat_w, chat_h = 106, 52

    pdf.colored_rect(chat_x, chat_y, chat_w, chat_h, (238, 238, 235))
    pdf.colored_rect(chat_x, chat_y, chat_w, 7, WA_GREEN)
    pdf.set_xy(chat_x + 3, chat_y + 1.5)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*WHITE)
    pdf.cell(chat_w - 6, 4, "Clinica Fisio  |  en linea")

    messages = [
        ("out", "Queria pedir cita para esta semana"),
        ("in",  "Claro! Tengo estos huecos:\n* Miercoles 26 a las 16:00\n* Jueves 27 a las 11:00\nCual te viene mejor?"),
        ("out", "El jueves a las 11"),
        ("in",  "Perfecto! Jueves 27 a las 11:00.\nDime tu nombre completo."),
        ("out", "Maria Garcia"),
        ("in",  "Cita confirmada: Maria Garcia,\njueves 27 a las 11:00. OK"),
    ]

    my = chat_y + 9
    for side, text in messages:
        lines = text.split("\n")
        bw = min(max(len(l) for l in lines) * 1.65 + 4, 80)
        bh = len(lines) * 4 + 3
        if my + bh > chat_y + chat_h - 2:
            break
        bx = chat_x + chat_w - bw - 2 if side == "out" else chat_x + 2
        bg = (220, 248, 198) if side == "out" else WHITE
        pdf.colored_rect(bx, my, bw, bh, bg)
        pdf.set_font("Helvetica", "", 6.2)
        pdf.set_text_color(*DARK_GRAY)
        for j, line in enumerate(lines):
            pdf.set_xy(bx + 1.5, my + 1.5 + j * 3.8)
            pdf.cell(bw - 3, 3.5, line)
        my += bh + 2

    # ── PRECIOS ───────────────────────────────────────────────────────────────
    price_y = demo_y + chat_h + 10
    pdf.set_y(price_y)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*DARK_GRAY)
    pdf.cell_nl(W, 6, "Precios transparentes  -  sin permanencia", align="C")

    tiers = [
        ("Prueba gratuita",  "0 EUR",       "15 dias sin compromiso", WHITE,     DARK_GRAY),
        ("Puesta en marcha", "300 EUR",     "Configuracion completa + formacion", WA_GREEN, WHITE),
        ("Mantenimiento",    "49 EUR/mes",  "Servidor + soporte + actualizaciones", WHITE, DARK_GRAY),
    ]
    p_card_w = 57
    py = pdf.get_y() + 1

    for i, (label, price, note, bg, fg) in enumerate(tiers):
        px = 14 + i * (p_card_w + 5.5)
        is_featured = i == 1
        pdf.colored_rect(px, py, p_card_w, 25, bg if not is_featured else WA_GREEN)

        if is_featured:
            pdf.colored_rect(px + 12, py - 3, p_card_w - 24, 6, WA_GREEN_LIGHT)
            pdf.set_xy(px + 12, py - 3)
            pdf.set_font("Helvetica", "B", 6)
            pdf.set_text_color(*DARK_GRAY)
            pdf.cell(p_card_w - 24, 6, "MAS POPULAR", align="C")

        pdf.set_xy(px + 3, py + 2)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*(WHITE if is_featured else DARK_GRAY))
        pdf.cell(p_card_w - 6, 5, label)

        pdf.set_xy(px + 3, py + 8)
        pdf.set_font("Helvetica", "B", 12)
        price_color = WA_GREEN_LIGHT if is_featured else WA_GREEN
        pdf.set_text_color(*price_color)
        pdf.cell(p_card_w - 6, 6, price)

        pdf.set_xy(px + 3, py + 15)
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_text_color(*((190, 235, 215) if is_featured else MID_GRAY))
        pdf.multi_cell(p_card_w - 6, 3.5, note)

    # ── COMPARATIVA ───────────────────────────────────────────────────────────
    cmp_y = price_y + 31
    pdf.set_y(cmp_y)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*DARK_GRAY)
    pdf.cell_nl(W, 6, "Comparativa rapida", align="C")

    headers   = ["", "Atendoo", "Doctoralia", "Tidio"]
    col_ws    = [58, 34, 45, 45]
    rows = [
        ["WhatsApp nativo",          "Si",        "No",         "Extra"],
        ["Sin app para el paciente", "Si",         "No",         "Si"],
        ["Google Calendar",          "Si",         "Parcial",    "No"],
        ["Precio mensual",           "49 EUR",     "99-199 EUR", "79-149 EUR"],
        ["Permanencia",              "Sin contrato","12 meses",  "3-6 meses"],
    ]

    th      = 5
    table_y = pdf.get_y()
    tx      = 14

    for j, (h, cw) in enumerate(zip(headers, col_ws)):
        bg   = WA_GREEN if j == 1 else (220, 225, 232)
        fg   = WHITE    if j == 1 else MID_GRAY
        pdf.colored_rect(tx, table_y, cw, th, bg)
        pdf.set_xy(tx, table_y)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(*fg)
        pdf.cell(cw, th, h, align="C" if j > 0 else "L")
        tx += cw

    for ri, row in enumerate(rows):
        ty = table_y + th + ri * th
        tx = 14
        for j, (val, cw) in enumerate(zip(row, col_ws)):
            even_bg = LIGHT_GRAY if ri % 2 == 0 else WHITE
            bg = GREEN_BG    if j == 1 else even_bg
            fg = GREEN_TEXT  if j == 1 else (DARK_GRAY if j == 0 else MID_GRAY)
            pdf.colored_rect(tx, ty, cw, th, bg)
            pdf.set_xy(tx, ty)
            pdf.set_font("Helvetica", "B" if j == 1 else "", 7.5)
            pdf.set_text_color(*fg)
            pdf.cell(cw, th, val, align="C" if j > 0 else "L")
            tx += cw

    # ── CTA ───────────────────────────────────────────────────────────────────
    cta_y = cmp_y + 10 + th + len(rows) * th + 4
    pdf.colored_rect(0, cta_y, 210, 20, WA_GREEN)

    pdf.set_xy(14, cta_y + 3)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*WHITE)
    pdf.cell_nl(W, 5, "Empieza gratis 15 dias  |  Sin tarjeta  |  Sin permanencia", align="C")

    pdf.set_xy(14, cta_y + 10)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(190, 235, 215)
    pdf.cell(W, 5, "atendoo.app  ·  atendoo.app@gmail.com  ·  Instalacion en 48h", align="C")

    pdf.output("atendoo_comercial.pdf")
    print("PDF generado: atendoo_comercial.pdf")


if __name__ == "__main__":
    build_pdf()
