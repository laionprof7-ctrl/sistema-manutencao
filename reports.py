import io
import os
from datetime import datetime
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import ARQUIVO_LOGO
from database import agora_brasil


def _texto(valor, padrao="Não registrado"):
    txt = str(valor or "").strip()
    if not txt or txt.lower() in {"nan", "none", "nat"}:
        return padrao
    return txt


def _fmt_data(valor):
    txt = _texto(valor, "")
    if not txt:
        return "Não registrada"
    try:
        return datetime.strptime(txt, "%d/%m/%Y %H:%M").strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return txt


def gerar_relatorio_pdf(df_rel, subtitulo_filtro="") -> bytes:
    """Gera o relatório diretamente em PDF, sem arquivo temporário."""
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Relatório de Manutenção",
        author="Copa Ambiental",
    )

    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloCopa",
        parent=estilos["Title"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        alignment=TA_CENTER,
        spaceAfter=5 * mm,
    )
    subtitulo = ParagraphStyle(
        "SubtituloCopa",
        parent=estilos["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=10,
        leading=13,
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )
    emissao = ParagraphStyle(
        "EmissaoCopa",
        parent=estilos["Normal"],
        fontSize=8.5,
        leading=11,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#555555"),
        spaceAfter=5 * mm,
    )
    os_style = ParagraphStyle(
        "OS",
        parent=estilos["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        spaceBefore=2 * mm,
        spaceAfter=3 * mm,
    )
    normal = ParagraphStyle(
        "NormalCopa",
        parent=estilos["BodyText"],
        fontSize=9.5,
        leading=13,
    )

    story = []

    if os.path.exists(ARQUIVO_LOGO):
        try:
            logo = Image(ARQUIVO_LOGO, width=38 * mm, height=18 * mm, kind="proportional")
            logo.hAlign = "CENTER"
            story.extend([logo, Spacer(1, 3 * mm)])
        except Exception:
            pass

    story.append(Paragraph("RELATÓRIO DE MANUTENÇÃO", titulo))
    if subtitulo_filtro:
        story.append(Paragraph(escape(str(subtitulo_filtro)), subtitulo))
    story.append(Paragraph(f"Emitido em: {escape(agora_brasil())}", emissao))

    for _, row in df_rel.iterrows():
        id_os = _texto(row.get("ID_OS", ""), "Sem identificação")
        campos = [
            ("Veículo / Equipamento", _texto(row.get("Veiculo", ""))),
            ("Identificação / Placa", _texto(row.get("Placa", ""))),
            ("Solicitante", _texto(row.get("Motorista", ""))),
            ("Data do Registro", _fmt_data(row.get("Data", ""))),
            ("Status", _texto(row.get("Status", ""))),
            ("Data de Aprovação", _fmt_data(row.get("Data_Aprovacao", ""))),
            ("Prioridade", _texto(row.get("Prioridade", ""))),
            ("Mecânico Responsável", _texto(row.get("Mecanico_Responsavel", ""))),
            ("Data de Liberação", _fmt_data(row.get("Data_Liberacao", ""))),
            ("Descrição do Problema", _texto(row.get("Descricao_Problema", ""))),
        ]

        linhas = [
            [
                Paragraph(f"<b>{escape(nome)}</b>", normal),
                Paragraph(escape(str(valor)), normal),
            ]
            for nome, valor in campos
        ]

        tabela = Table(linhas, colWidths=[48 * mm, 126 * mm], hAlign="LEFT")
        tabela.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9D9D9")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F4F6F8")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))

        story.append(KeepTogether([
            Paragraph(f"Ordem de Serviço: {escape(id_os)}", os_style),
            tabela,
            Spacer(1, 6 * mm),
        ]))

    def rodape(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(A4[0] / 2, 8 * mm, f"Página {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=rodape, onLaterPages=rodape)
    return buffer.getvalue()
