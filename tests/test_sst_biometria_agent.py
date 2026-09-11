from agent_biometrico.agent import BACKEND_READER_MODEL, _origin_allowed


def test_modelo_do_agente_compativel_com_backend_sst():
    assert BACKEND_READER_MODEL == "Nitgen Hamster DX HFDU06"


def test_sem_origem_permitida_bloqueia_origem_web(monkeypatch):
    import agent_biometrico.agent as agent

    monkeypatch.setattr(agent, "ALLOWED_ORIGIN", "")
    assert agent._origin_allowed(None) is True
    assert agent._origin_allowed("") is True
    assert agent._origin_allowed("https://exemplo.streamlit.app") is False


def test_origem_exata_quando_configurada(monkeypatch):
    import agent_biometrico.agent as agent

    monkeypatch.setattr(agent, "ALLOWED_ORIGIN", "https://copa-exemplo.streamlit.app")
    assert agent._origin_allowed("https://copa-exemplo.streamlit.app") is True
    assert agent._origin_allowed("https://outro.streamlit.app") is False
