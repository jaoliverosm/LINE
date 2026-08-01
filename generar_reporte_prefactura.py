# -*- coding: utf-8 -*-
"""
Generador de reporte PDF estilo FACTURA MEDICA (gris/negro elegante)
para resultados de auditoria de prefactura - Proyecto LINE.

Para reusarlo: edita el diccionario DATA con los datos del paciente/
prefactura y corre el script. Todo se arma en una sola pagina, como
una factura clinica formal.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
import io
from datetime import datetime


# ------------------------------------------------------------------
# 1. DATOS DE ENTRADA (edita esto para cada reporte nuevo)
# ------------------------------------------------------------------
DATA = {
    "no_factura": "PRE-2026-000117",
    "fecha": "01 de agosto de 2026",

    "paciente": "Jefersson Aldair Oliveros Monroy",
    "documento": "CC 100571881",
    "regimen": "Contributivo",
    "eps": "Salud Total EPS",
    "archivo": "prefactura_JEF-001.csv",

    "items_facturados": [
        # codigo, descripcion, cantidad, valor unit, estado
        ["890205", "Consulta medica general", "1", "$45.000", "OK"],
        ["902201", "Hemograma completo",       "1", "$18.000", "OK"],
        ["903302", "Ecografia abdominal",      "1", "$65.000", "INCONSISTENTE"],
    ],
    "total_facturado": "$128.000",
    "total_inconsistencias": "$65.000",
    "items_con_inconsistencia": 1,
    "items_totales": 3,

    "datos_verificados": [
        ["ADRES", "OK"],
        ["BD Local", "OK"],
        ["Logica Set CUPS (ACTIVO)", "OK"],
        ["Documento (CC 100571881)", "OK"],
        ["EPS (Salud Total EPS)", "OK"],
        ["Regimen (Contributivo)", "OK"],
    ],

    "historia_clinica": [
        # codigo, descripcion, resultado, motivo
        ["890205", "Consulta medica general", "OK",
         "Autorizacion EPS / Soporte medico / No alto costo / Coherencia temporal"],
        ["903302", "Ecografia abdominal", "CODIGO_NO_COINCIDE",
         "El CUPS facturado 903302 no coincide con ningun CUPS registrado "
         "en la HC (HC items: 890205)"],
    ],

    "modelo": {
        "nombre": "CNN MobileNetV2",
        "consistentes": 2,
        "inconsistentes": 1,
        "threshold": "42.7%",
        "validaciones": [
            "Comparacion set CUPS por atencion",
            "Validacion autorizacion EPS",
            "Soporte medico diario completo",
            "Deteccion servicios alto costo",
        ],
    },
}


# ------------------------------------------------------------------
# 2. PALETA GRIS / NEGRO ELEGANTE
# ------------------------------------------------------------------
NEGRO = colors.HexColor("#1a1a1a")
GRIS_OSCURO = colors.HexColor("#333333")
GRIS_MEDIO = colors.HexColor("#6e6e6e")
GRIS_CLARO = colors.HexColor("#f4f4f4")
GRIS_LINEA = colors.HexColor("#d9d9d9")
ROJO = colors.HexColor("#a33")
VERDE = colors.HexColor("#3a6b35")
BLANCO = colors.white

styles = getSampleStyleSheet()

marca_style = ParagraphStyle("Marca", parent=styles["Normal"], fontSize=18,
                              textColor=BLANCO, fontName="Helvetica-Bold", leading=20)
marca_sub_style = ParagraphStyle("MarcaSub", parent=styles["Normal"], fontSize=8.5,
                                  textColor=colors.HexColor("#cccccc"), leading=11)
factura_titulo_style = ParagraphStyle("FactTit", parent=styles["Normal"], fontSize=13,
                                       textColor=BLANCO, fontName="Helvetica-Bold",
                                       alignment=TA_RIGHT, leading=16)
factura_meta_style = ParagraphStyle("FactMeta", parent=styles["Normal"], fontSize=8.5,
                                     textColor=colors.HexColor("#cccccc"),
                                     alignment=TA_RIGHT, leading=11)
etiqueta_style = ParagraphStyle("Etiqueta", parent=styles["Normal"], fontSize=7.5,
                                 textColor=GRIS_MEDIO, fontName="Helvetica-Bold",
                                 leading=9)
valor_style = ParagraphStyle("Valor", parent=styles["Normal"], fontSize=9.5,
                              textColor=NEGRO, leading=12)
seccion_style = ParagraphStyle("Seccion", parent=styles["Normal"], fontSize=9,
                                textColor=NEGRO, fontName="Helvetica-Bold",
                                spaceBefore=10, spaceAfter=4,
                                leading=11)
celda_style = ParagraphStyle("Celda", parent=styles["Normal"], fontSize=8, leading=10)
celda_bold = ParagraphStyle("CeldaBold", parent=styles["Normal"], fontSize=8,
                             leading=10, fontName="Helvetica-Bold")
alerta_style = ParagraphStyle("Alerta", parent=styles["Normal"], fontSize=9,
                               textColor=ROJO, fontName="Helvetica-Bold", leading=11)


def campo(etiqueta, valor):
    return Table(
        [[Paragraph(etiqueta.upper(), etiqueta_style)],
         [Paragraph(valor, valor_style)]],
        colWidths=[None],
    )


def linea():
    return HRFlowable(width="100%", thickness=0.6, color=GRIS_LINEA,
                       spaceBefore=2, spaceAfter=8)


MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def _fecha_espanol(dt=None):
    """Retorna la fecha en formato 'DD de mes de AAAA' en espanol."""
    if dt is None:
        dt = datetime.now()
    return f"{dt.day} de {MESES_ES[dt.month]} de {dt.year}"


def _fmt_valor(v):
    """Formatea un valor numerico como moneda colombiana."""
    try:
        n = float(v)
        return f"${n:,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(v) if v else "$0"


def convertir_resultado_a_data(resultado: dict, formData: dict = None) -> dict:
    """
    Convierte el resultado del endpoint /api/prefactura/analizar
    al formato DATA que espera construir_pdf.

    Args:
        resultado: Dict devuelto por analizar_prefactura()
        formData: Dict con datos del formulario (nombre, tipoDoc, numDoc, eps, etc.)

    Returns:
        Dict en formato DATA para construir_pdf
    """
    fd = formData or {}
    res = resultado.get("resumen", {})
    pac = resultado.get("paciente", {})
    cruces = resultado.get("cruces", [])
    fugas = resultado.get("fugas", [])
    verif = resultado.get("verificaciones", {})

    # Nombre del paciente
    nombre_paciente = f"{fd.get('nombres', '')} {fd.get('apellidos', '')}".strip()
    if not nombre_paciente:
        nombre_paciente = pac.get("id", "No especificado")

    tipo_doc = fd.get("tipoDoc", pac.get("tipo_documento", "CC"))
    num_doc = fd.get("numDoc", pac.get("id", ""))

    # Items facturados
    items_facturados = []
    for c in cruces:
        estado = "OK" if c.get("resultado") == "CONSISTENTE" else "INCONSISTENTE"
        items_facturados.append([
            str(c.get("codigo_cups_pf", "")),
            str(c.get("descripcion_pf", "")),
            str(c.get("cantidad_pf", 1)),
            _fmt_valor(c.get("valor_total_pf", 0)),
            estado,
        ])

    # Si no hay cruces pero hay items del modelo
    if not items_facturados and resultado.get("modelos", {}).get("nemotron_externo"):
        nemotron = resultado["modelos"]["nemotron_externo"].get("resultado", {})
        for item in nemotron.get("items_detectados", []):
            items_facturados.append([
                str(item.get("codigo", "")),
                str(item.get("descripcion", "")),
                str(item.get("cantidad", 1)),
                _fmt_valor(item.get("valor_total", 0)),
                "OK",
            ])

    # Datos verificados
    datos_verificados = []

    # ADRES
    adres_verif = verif.get("adres", {})
    if adres_verif.get("verificado"):
        estado_adres = "OK" if adres_verif.get("encontrado") else "NO ENCONTRADO"
        datos_verificados.append([f"ADRES ({adres_verif.get('mensaje', '')[:50]})", estado_adres])

    # BD Local
    bd_verif = verif.get("bd_local", {})
    if bd_verif.get("verificado"):
        estado_bd = "OK" if bd_verif.get("encontrado") else "NO ENCONTRADO"
        datos_verificados.append([f"BD Local ({bd_verif.get('mensaje', '')[:50]})", estado_bd])

    # EPS
    eps_verif = verif.get("eps_adres", {})
    if eps_verif.get("verificado"):
        estado_eps = "OK" if eps_verif.get("coincide") else "NO COINCIDE"
        datos_verificados.append([
            f"EPS ({eps_verif.get('formulario', '')} vs {eps_verif.get('adres', '')})",
            estado_eps
        ])

    # Cruce ADRES
    cruce_adres = verif.get("cruce_adres", {})
    if cruce_adres:
        estado_cruce = "OK" if cruce_adres.get("validacion_pasa") else "DISCREPANCIA"
        datos_verificados.append([
            f"Cruce ADRES: {cruce_adres.get('conclusion', '')[:50]}",
            estado_cruce
        ])

    # Si no hay verificaciones, agregar por defecto
    if not datos_verificados:
        datos_verificados.append(["Verificaciones", "NO DISPONIBLE"])

    # Historia clinica (contraste)
    historia_clinica = []
    for c in cruces:
        resultado_hc = c.get("resultado", "SIN_DATOS")
        motivo = c.get("tipo_alerta", "N/A")
        if c.get("explicacion"):
            motivo = c["explicacion"][:100]
        historia_clinica.append([
            str(c.get("codigo_cups_pf", "")),
            str(c.get("descripcion_pf", "")),
            resultado_hc,
            motivo,
        ])

    # Modelo
    modelo_usado = "IA (No especificado)"
    modelos = resultado.get("modelos", {})
    if modelos.get("cnn_local"):
        modelo_usado = "CNN MobileNetV2"
    elif modelos.get("xgboost_local"):
        modelo_usado = "XGBoost"
    elif modelos.get("nemotron_externo"):
        modelo_usado = "NVIDIA Nemotron"

    # Valor total
    valor_total = res.get("valor_total_prefactura", 0)
    valor_inconsistente = res.get("valor_en_inconsistencias", 0)

    # Determinar numero de factura
    no_factura = fd.get("numDoc", "S/N")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    data = {
        "no_factura": f"PF-{no_factura}-{timestamp}",
        "fecha": _fecha_espanol(),
        "paciente": nombre_paciente,
        "documento": f"{tipo_doc} {num_doc}",
        "regimen": fd.get("tipo_afiliacion", pac.get("tipo_afiliacion", "No especificado")),
        "eps": fd.get("eps", pac.get("eps", "No especificada")),
        "archivo": fd.get("file", "N/A"),

        "items_facturados": items_facturados if items_facturados else [
            ["N/A", "Sin items para mostrar", "0", "$0", "N/A"]
        ],
        "total_facturado": _fmt_valor(valor_total),
        "total_inconsistencias": _fmt_valor(valor_inconsistente),
        "items_con_inconsistencia": res.get("inconsistentes", 0),
        "items_totales": res.get("total_items", len(cruces)),

        "datos_verificados": datos_verificados,

        "historia_clinica": historia_clinica if historia_clinica else [
            ["N/A", "Sin datos de contraste", "N/A", "No hay cruces disponibles"]
        ],

        "modelo": {
            "nombre": modelo_usado,
            "consistentes": res.get("consistentes", 0),
            "inconsistentes": res.get("inconsistentes", 0),
            "threshold": "N/A",
            "validaciones": [
                "Comparacion set CUPS por atencion",
                "Validacion autorizacion EPS",
                "Verificacion ADRES/BDUA",
                res.get("motivo_recomendacion", "Analisis automatico"),
            ],
        },
    }

    return data


def _build_story(data):
    """Construye la lista de elementos ReportLab (story) para el PDF."""
    story = []

    # ---------------- ENCABEZADO NEGRO ----------------
    header_tbl = Table(
        [[
            Paragraph("LINE", marca_style),
            Paragraph(
                f"RESULTADO DE PREFACTURA<br/>No. {data['no_factura']}",
                factura_titulo_style
            ),
        ]],
        colWidths=[9.3 * cm, 8.5 * cm],
    )
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NEGRO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 20),
        ("RIGHTPADDING", (1, 0), (1, 0), 20),
        ("TOPPADDING", (0, 0), (-1, -1), 22),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(header_tbl)

    sub_tbl = Table(
        [[
            Paragraph("Auditoria automatizada de prefactura &mdash; Health &amp; Life IPS",
                      marca_sub_style),
            Paragraph(f"Fecha: {data['fecha']}", factura_meta_style),
        ]],
        colWidths=[9.3 * cm, 8.5 * cm],
    )
    sub_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NEGRO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 20),
        ("RIGHTPADDING", (1, 0), (1, 0), 20),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
    ]))
    story.append(sub_tbl)
    story.append(Spacer(1, 16))

    # ---------------- DATOS DEL PACIENTE (como "facturar a") ----------------
    datos_tbl = Table(
        [[
            campo("Paciente", data["paciente"]),
            campo("Documento", data["documento"]),
        ], [
            campo("EPS", data["eps"]),
            campo("Regimen", data["regimen"]),
        ], [
            campo("Archivo origen", data["archivo"]),
            campo("Items evaluados", str(data["items_totales"])),
        ]],
        colWidths=[8.9 * cm, 8.9 * cm],
    )
    datos_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(datos_tbl)
    story.append(Spacer(1, 6))
    story.append(linea())

    # ---------------- ALERTA DE INCONSISTENCIA ----------------
    story.append(Paragraph(
        f"&#9888; {data['items_con_inconsistencia']} de {data['items_totales']} items "
        f"presentan inconsistencia &mdash; valor en disputa: {data['total_inconsistencias']}",
        alerta_style
    ))
    story.append(Spacer(1, 10))

    # ---------------- TABLA DE ITEMS (estilo factura) ----------------
    header = ["Codigo", "Descripcion", "Cant.", "Valor", "Estado"]
    rows = data["items_facturados"]
    tabla_data = [header] + rows
    t_items = Table(tabla_data, colWidths=[2 * cm, 8 * cm, 1.5 * cm, 2.6 * cm, 3.7 * cm])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NEGRO),
        ("TEXTCOLOR", (0, 0), (-1, 0), BLANCO),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("LINEBELOW", (0, 1), (-1, -2), 0.5, GRIS_LINEA),
        ("LINEBELOW", (0, -1), (-1, -1), 0.8, NEGRO),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (2, 0), (4, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i, row in enumerate(rows, start=1):
        if len(row) >= 5:
            if row[4] == "OK":
                style.append(("TEXTCOLOR", (4, i), (4, i), VERDE))
            else:
                style.append(("TEXTCOLOR", (4, i), (4, i), ROJO))
                style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
    t_items.setStyle(TableStyle(style))
    story.append(t_items)

    # ---------------- TOTALES ----------------
    totales_tbl = Table(
        [
            ["", "Total facturado", data["total_facturado"]],
            ["", "Total en inconsistencias", data["total_inconsistencias"]],
        ],
        colWidths=[9.8 * cm, 4.5 * cm, 3.5 * cm],
    )
    totales_tbl.setStyle(TableStyle([
        ("FONTSIZE", (1, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TEXTCOLOR", (1, 1), (-1, 1), ROJO),
        ("FONTNAME", (1, 1), (-1, 1), "Helvetica-Bold"),
        ("LINEABOVE", (1, 0), (-1, 0), 0.5, GRIS_LINEA),
    ]))
    story.append(totales_tbl)
    story.append(Spacer(1, 12))
    story.append(linea())

    # ---------------- VERIFICACIONES + HISTORIA CLINICA ----------------
    story.append(Paragraph("VERIFICACIONES DE FUENTE", seccion_style))
    verif_rows = [[f, Paragraph(("&#10003;" if e == "OK" else "&#10007;"), celda_bold)]
                  for f, e in data["datos_verificados"]]
    t_verif = Table(verif_rows, colWidths=[13.5 * cm, 3.8 * cm])
    t_verif.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (1, 0), (1, -1), VERDE),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRIS_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_verif)
    story.append(Spacer(1, 10))

    story.append(Paragraph("HISTORIA CLINICA &mdash; CONTRASTE", seccion_style))
    header_hc = ["Codigo", "Descripcion", "Resultado", "Motivo"]
    hc_rows = []
    for row in data["historia_clinica"]:
        codigo, desc, resultado, motivo = row[0], row[1], row[2], row[3]
        color_res = VERDE if resultado == "OK" else ROJO
        res_par = Paragraph(f'<font color="{color_res.hexval()}"><b>{resultado}</b></font>',
                             celda_style)
        hc_rows.append([codigo, Paragraph(str(desc), celda_style), res_par,
                         Paragraph(str(motivo), celda_style)])
    t_hc = Table([header_hc] + hc_rows, colWidths=[1.8 * cm, 4 * cm, 3.5 * cm, 8 * cm])
    t_hc.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), GRIS_CLARO),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRIS_LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_hc)
    story.append(Spacer(1, 10))

    # ---------------- RESULTADO DEL MODELO ----------------
    story.append(Paragraph(f"RESULTADO DEL MODELO &mdash; {data['modelo']['nombre']}",
                            seccion_style))
    modelo_txt = (
        f"Consistentes: <b>{data['modelo']['consistentes']}</b> &nbsp;|&nbsp; "
        f"Inconsistentes: <b>{data['modelo']['inconsistentes']}</b> &nbsp;|&nbsp; "
        f"Threshold: <b>{data['modelo']['threshold']}</b><br/>"
        f"Validaciones aplicadas: {', '.join(data['modelo']['validaciones'])}"
    )
    story.append(Paragraph(modelo_txt, celda_style))
    story.append(Spacer(1, 14))
    story.append(linea())
    story.append(Paragraph(
        "Este documento es un resultado automatizado del sistema LINE de auditoria "
        "de prefacturacion y no reemplaza la revision del area de auditoria medica.",
        ParagraphStyle("Foot", parent=styles["Normal"], fontSize=7, textColor=GRIS_MEDIO)
    ))
    return story


def construir_pdf(data, salida="reporte_prefactura.pdf"):
    doc = SimpleDocTemplate(
        salida, pagesize=letter,
        topMargin=0, bottomMargin=1.3 * cm,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
    )
    doc.build(_build_story(data))
    print(f"PDF generado: {salida}")


def construir_pdf_bytes(data) -> bytes:
    """
    Genera el PDF en memoria y retorna los bytes.
    Util para endpoints que devuelven el PDF como Response.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=0, bottomMargin=1.3 * cm,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
    )
    doc.build(_build_story(data))
    return buf.getvalue()


if __name__ == "__main__":
    import os
    out_dir = os.path.join(os.path.dirname(__file__), "outputs")
    os.makedirs(out_dir, exist_ok=True)
    construir_pdf(DATA, salida=os.path.join(out_dir, "reporte_prefactura.pdf"))
