from pathlib import Path

import copa_brand


def test_tema_aplica_os_mesmos_icones_a_manutencao_e_sst(monkeypatch):
    renderizados = []
    monkeypatch.setattr(copa_brand.st, "markdown", lambda texto, **_: renderizados.append(texto))

    copa_brand.aplicar_tema_global()

    css = "\n".join(renderizados)
    assert ".st-key-sst_menu_cards button::before," in css
    assert ".st-key-manutencao_menu_cards button::before" in css
    assert ".st-key-manutencao_menu_cards button p::first-letter" not in css


def test_entrada_publicada_nao_executa_reset_destrutivo():
    codigo = Path("sst_teste.py").read_text(encoding="utf-8")
    assert "aplicar_reset_final_uma_vez" not in codigo
    assert "from final_reset import" not in codigo
