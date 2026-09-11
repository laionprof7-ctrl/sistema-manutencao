# Agente biométrico local — Copa SST

Este diretório contém a base do agente Windows que fará a ponte entre o navegador e o leitor **Nitgen/FingerTech Hamster DX HFDU06**.

## Estado atual

O agente já possui:

- servidor local restrito a `127.0.0.1`;
- endpoint `/health`;
- endpoints `/cadastro` e `/verificacao`;
- validação de origem do navegador;
- assinatura HMAC das evidências;
- vínculo da verificação a colaborador, documento e SHA-256 do PDF;
- bloqueio por padrão quando o SDK Nitgen não está instalado/configurado;
- nenhuma persistência de imagem ou template biométrico bruto.

**Importante:** sem o adaptador real do SDK, o agente retorna `SDK_NOT_CONFIGURED`. Isso é intencional: o sistema não deve simular biometria.

## Variáveis do agente

Configure na estação Windows:

- `SST_BIOMETRIC_AGENT_SECRET`: segredo forte (mínimo 32 caracteres), também configurado no backend Streamlit.
- `SST_BIOMETRIC_ALLOWED_ORIGIN`: origem HTTPS exata do app Streamlit autorizado.
- `SST_BIOMETRIC_AGENT_ID`: identificador da estação/agente, por exemplo `almoxarifado-01`.
- `SST_BIOMETRIC_AGENT_PORT`: opcional; padrão `8765`.

O segredo nunca deve entrar no GitHub.

## Executar durante desenvolvimento

No PowerShell da estação Windows, dentro do repositório:

```powershell
$env:SST_BIOMETRIC_AGENT_SECRET="troque-por-um-segredo-forte-de-verdade"
$env:SST_BIOMETRIC_ALLOWED_ORIGIN="https://SEU-APP.streamlit.app"
$env:SST_BIOMETRIC_AGENT_ID="almoxarifado-01"
python .\agent_biometrico\agent.py
```

Depois, localmente:

```text
http://127.0.0.1:8765/health
```

O `health` pode responder normalmente mesmo com `sdk_configurado=false`. Cadastro e verificação continuarão bloqueados até o SDK real existir.

## Adaptador Nitgen

O arquivo `vendor_adapter.example.py` documenta o contrato. Quando tivermos o SDK oficial instalado, criaremos `agent_biometrico/vendor_nitgen.py` (ou ajustaremos o import para a localização escolhida) com chamadas reais ao eNBioBSP/SDK compatível.

O adaptador só pode devolver metadados seguros e o resultado da correspondência. Não deve enviar imagem da digital ou template bruto para o Streamlit/Supabase.

## Próximo passo

Instalar driver/SDK do HFDU06 na estação Windows e testar as operações reais de captura, cadastro e verificação. Depois disso ligamos o botão `🖐️ Ler digital e confirmar identidade` da interface ao agente local.
