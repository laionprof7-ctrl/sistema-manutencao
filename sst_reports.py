from __future__ import annotations

import io
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

TZ_BAHIA = ZoneInfo("America/Bahia")
BASE_DIR = Path(__file__).resolve().parent


def _snapshot(valor: str | None) -> dict:
    if not valor:
        return {}
    try:
        obj = json.loads(valor)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _data(valor) -> str:
    if not valor:
        return "—"
    if isinstance(valor, str):
        try:
            from datetime import date
            valor = date.fromisoformat(valor)
        except Exception:
            return valor
    try:
        return valor.strftime("%d/%m/%Y")
    except Exception:
        return str(valor)


def _data_hora(valor) -> str:
    if not valor:
        return "—"
    try:
        return valor.astimezone(TZ_BAHIA).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(valor)


def _p(texto: object, estilo) -> Paragraph:
    import html
    valor = html.escape(str(texto or "—")).replace("\n", "<br/>")
    return Paragraph(valor, estilo)


def _p_raw(texto: str, estilo) -> Paragraph:
    """Markup interno controlado; nunca recebe texto livre do usuário."""
    return Paragraph(texto, estilo)


def _linhas_texto(texto: str | None, estilo) -> list:
    if not texto:
        return [_p("Não informado.", estilo)]
    blocos = []
    for linha in str(texto).splitlines():
        linha = linha.strip()
        if linha:
            blocos.append(_p(linha, estilo))
            blocos.append(Spacer(1, 2 * mm))
    return blocos or [_p("Não informado.", estilo)]


def _cabecalho(story: list, titulo: str, numero: str, styles: dict) -> None:
    logo = BASE_DIR / "logo.png"
    if not logo.exists():
        logo = Path("logo.png")
    esquerda = []
    if logo.exists():
        try:
            esquerda = [Image(str(logo), width=34 * mm, height=14 * mm, kind="proportional")]
        except Exception:
            esquerda = [_p("COPA", styles["brand"])]
    else:
        esquerda = [_p("COPA", styles["brand"])]

    topo = Table(
        [[esquerda, _p_raw("COPA GESTÃO<br/><b>Segurança do Trabalho</b>", styles["right"]) ]],
        colWidths=[90 * mm, 90 * mm],
    )
    topo.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
        ("LINEBELOW", (0, 0), (-1, -1), 0.6, colors.HexColor("#D1D5DB")),
    ]))
    story.extend([topo, Spacer(1, 6 * mm)])
    story.append(_p(titulo, styles["title"]))
    story.append(_p(numero, styles["number"]))
    story.append(Spacer(1, 5 * mm))


def _tabela_identificacao(documento: dict, snap: dict, styles: dict) -> Table:
    col = snap.get("colaborador") if isinstance(snap.get("colaborador"), dict) else {}
    ghe = col.get("ghe") if isinstance(col.get("ghe"), dict) else {}
    dados = {
        "Nome": col.get("nome") or documento.get("colaborador"),
        "CPF": col.get("cpf") or documento.get("cpf"),
        "Matrícula": col.get("matricula") or documento.get("matricula"),
        "Função": col.get("funcao") or documento.get("funcao"),
        "Setor": col.get("setor") or documento.get("setor"),
        "GHE": (f"{ghe.get('codigo')} — {ghe.get('nome')}" if ghe.get("codigo") else documento.get("ghe_codigo") or "—"),
        "Admissão": _data(col.get("data_admissao") or documento.get("data_admissao")),
        "Motivo": documento.get("motivo") or snap.get("motivo_emissao") or snap.get("motivo_entrega") or "—",
    }
    linhas = [
        [_p("Nome", styles["label"]), _p(dados["Nome"], styles["body"]), _p("CPF", styles["label"]), _p(dados["CPF"], styles["body"])],
        [_p("Matrícula", styles["label"]), _p(dados["Matrícula"], styles["body"]), _p("Admissão", styles["label"]), _p(dados["Admissão"], styles["body"])],
        [_p("Função", styles["label"]), _p(dados["Função"], styles["body"]), _p("Setor", styles["label"]), _p(dados["Setor"], styles["body"])],
        [_p("GHE", styles["label"]), _p(dados["GHE"], styles["body"]), _p("Motivo", styles["label"]), _p(dados["Motivo"], styles["body"])],
    ]
    tabela = Table(linhas, colWidths=[22 * mm, 68 * mm, 22 * mm, 68 * mm], repeatRows=0)
    tabela.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F3F4F6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tabela


def _secao(story: list, titulo: str, texto: str | None, styles: dict) -> None:
    story.append(Spacer(1, 4 * mm))
    story.append(_p(titulo, styles["section"]))
    story.extend(_linhas_texto(texto, styles["body"]))


def _conteudo_os(story: list, snap: dict, styles: dict) -> None:
    conteudo = snap.get("ghe_conteudo") if isinstance(snap.get("ghe_conteudo"), dict) else {}
    _secao(story, "Riscos ocupacionais", conteudo.get("riscos"), styles)
    _secao(story, "Medidas preventivas", conteudo.get("medidas_preventivas"), styles)
    _secao(story, "EPIs recomendados", conteudo.get("epis_recomendados"), styles)
    _secao(story, "Orientações / procedimentos de segurança", conteudo.get("orientacoes"), styles)


def _conteudo_entrega(story: list, snap: dict, styles: dict) -> None:
    story.append(Spacer(1, 4 * mm))
    story.append(_p("Itens entregues", styles["section"]))
    linhas = [[_p("EPI", styles["label"]), _p("CA", styles["label"]), _p("Validade do CA", styles["label"]), _p("Qtd.", styles["label"])]]
    for item in snap.get("itens", []):
        linhas.append([
            _p(item.get("nome"), styles["body"]),
            _p(item.get("ca"), styles["body"]),
            _p(_data(item.get("validade_ca")), styles["body"]),
            _p(f"{item.get('quantidade', '')} {item.get('unidade', '')}", styles["body"]),
        ])
    tabela = Table(linhas, colWidths=[82 * mm, 28 * mm, 38 * mm, 32 * mm], repeatRows=1)
    tabela.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tabela)
    story.append(Spacer(1, 4 * mm))
    story.append(_p("Motivo da entrega: " + str(snap.get("motivo_entrega") or "—"), styles["body"]))
    story.append(Spacer(1, 3 * mm))
    story.append(_p(
        "Declaro ter recebido os equipamentos de proteção individual acima relacionados, em condições de uso, "
        "bem como as orientações relativas ao uso, guarda, conservação e substituição.", styles["body"]
    ))


def gerar_pdf_documento(documento: dict) -> bytes:
    """Gera o PDF que será preservado e vinculado ao hash do documento."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=14 * mm, bottomMargin=15 * mm,
        title=documento.get("titulo") or "Documento SST",
        author="Copa Gestão - SST/EPI",
    )
    base = getSampleStyleSheet()
    styles = {
        "brand": ParagraphStyle("brand", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=14, leading=16),
        "right": ParagraphStyle("right", parent=base["Normal"], fontSize=8.5, leading=11, alignment=2, textColor=colors.HexColor("#374151")),
        "title": ParagraphStyle("title", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=15, leading=18, spaceAfter=2, textColor=colors.HexColor("#111827")),
        "number": ParagraphStyle("number", parent=base["Normal"], fontSize=9, leading=11, textColor=colors.HexColor("#6B7280")),
        "section": ParagraphStyle("section", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, leading=13, spaceAfter=4, textColor=colors.HexColor("#111827")),
        "label": ParagraphStyle("label", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8.3, leading=10),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=8.8, leading=12, textColor=colors.HexColor("#1F2937")),
        "foot": ParagraphStyle("foot", parent=base["Normal"], fontSize=7.5, leading=10, textColor=colors.HexColor("#6B7280"), alignment=TA_CENTER),
    }

    snap = _snapshot(documento.get("conteudo_snapshot"))
    tipo = documento.get("tipo") or "Documento SST"
    titulo = "ORDEM DE SERVIÇO DE SEGURANÇA E SAÚDE NO TRABALHO" if tipo == "Ordem de Serviço de SST" else "COMPROVANTE DE ENTREGA DE EPI"
    story: list = []
    _cabecalho(story, titulo, documento.get("numero") or "—", styles)
    story.append(_tabela_identificacao(documento, snap, styles))

    if snap.get("modelo") == "ordem_servico_sst":
        _conteudo_os(story, snap, styles)
    elif snap.get("modelo") == "entrega_epi" or snap.get("entrega_id"):
        _conteudo_entrega(story, snap, styles)
    else:
        _secao(story, "Conteúdo / ciência", documento.get("conteudo_snapshot"), styles)

    story.append(Spacer(1, 8 * mm))
    story.append(KeepTogether([
        _p("Registro eletrônico", styles["section"]),
        _p(
            f"Documento {documento.get('numero') or '—'} criado em {_data_hora(documento.get('criado_em'))}. "
            "Após o fechamento, este PDF é preservado no banco de dados e associado ao seu hash SHA-256 para o fluxo de assinatura.",
            styles["body"],
        ),
    ]))
    story.append(Spacer(1, 8 * mm))
    story.append(_p("Copa Gestão • Segurança do Trabalho", styles["foot"]))

    doc.build(story)
    return buffer.getvalue()
