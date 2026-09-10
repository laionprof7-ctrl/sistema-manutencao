from __future__ import annotations

import io
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


TZ_BAHIA = ZoneInfo("America/Bahia")


def _texto_snapshot(valor: str | None) -> str:
    if not valor:
        return ""
    try:
        obj = json.loads(valor)
        if isinstance(obj, dict):
            if obj.get("entrega_id"):
                linhas = [f"Entrega de EPI #{obj['entrega_id']}"]
                for item in obj.get("itens", []):
                    linhas.append(
                        f"- {item.get('nome','')} | CA {item.get('ca','')} | "
                        f"Qtd.: {item.get('quantidade','')} {item.get('unidade','')}"
                    )
                if obj.get("observacao"):
                    linhas.append(f"Observação: {obj['observacao']}")
                return "\n".join(linhas)
            return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return str(valor)


def gerar_pdf_documento(documento: dict) -> bytes:
    """Gera PDF simples e estável para o documento SST."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4, invariant=1)
    largura, altura = A4
    margem = 50
    y = altura - 55

    c.setTitle(documento.get("titulo") or "Documento SST")
    c.setAuthor("Copa Gestão - SST/EPI")

    logo = Path("logo.png")
    if logo.exists():
        try:
            c.drawImage(str(logo), margem, y - 22, width=105, height=42, preserveAspectRatio=True, mask="auto")
            y -= 50
        except Exception:
            c.setFont("Helvetica-Bold", 16)
            c.drawString(margem, y, "COPA — SST / EPI")
            y -= 26
    else:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margem, y, "COPA — SST / EPI")
        y -= 26
    c.setFont("Helvetica-Bold", 13)
    c.drawString(margem, y, documento.get("titulo") or "Documento SST")
    y -= 22

    c.setFont("Helvetica", 9)
    campos = [
        ("Número", documento.get("numero")),
        ("Tipo", documento.get("tipo")),
        ("Motivo", documento.get("motivo") or "—"),
        ("Colaborador", documento.get("colaborador")),
        ("Matrícula", documento.get("matricula") or "—"),
        ("Função", documento.get("funcao") or "—"),
        ("Setor", documento.get("setor") or "—"),
    ]
    for rotulo, valor in campos:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margem, y, f"{rotulo}:")
        c.setFont("Helvetica", 9)
        c.drawString(margem + 85, y, str(valor or "—")[:100])
        y -= 15

    y -= 8
    c.line(margem, y, largura - margem, y)
    y -= 22
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margem, y, "Conteúdo / ciência:")
    y -= 18

    texto = _texto_snapshot(documento.get("conteudo_snapshot"))
    c.setFont("Helvetica", 9)
    for bloco in texto.splitlines() or [""]:
        palavras = bloco.split()
        linha = ""
        if not palavras:
            y -= 12
            continue
        for palavra in palavras:
            teste = f"{linha} {palavra}".strip()
            if c.stringWidth(teste, "Helvetica", 9) > largura - 2 * margem:
                c.drawString(margem, y, linha)
                y -= 13
                linha = palavra
            else:
                linha = teste
            if y < 70:
                c.showPage()
                y = altura - 55
                c.setFont("Helvetica", 9)
        if linha:
            c.drawString(margem, y, linha)
            y -= 13

    if y < 130:
        c.showPage()
        y = altura - 55

    y -= 18
    c.line(margem, y, largura - margem, y)
    y -= 22
    c.setFont("Helvetica", 8)
    criado = documento.get("criado_em")
    if criado:
        try:
            criado = criado.astimezone(TZ_BAHIA).strftime("%d/%m/%Y %H:%M")
        except Exception:
            criado = str(criado)
    c.drawString(margem, y, f"Documento gerado a partir do registro {documento.get('numero', '')}.")
    y -= 13
    c.drawString(margem, y, f"Criado em: {criado or '—'}")
    y -= 13
    c.drawString(
        margem, y,
        "Após o fechamento, o PDF é armazenado com hash SHA-256 para futura assinatura biométrica."
    )

    c.save()
    return buffer.getvalue()
