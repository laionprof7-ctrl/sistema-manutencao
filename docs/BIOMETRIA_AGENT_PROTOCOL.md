# Protocolo do agente biométrico — SST/EPI

## Objetivo

Permitir que o módulo SST confirme a identidade do colaborador no momento da entrega de EPI sem simular biometria e sem armazenar imagem bruta de impressão digital.

Leitor definido para o projeto: **Nitgen/FingerTech Hamster DX HFDU06**.

## Arquitetura

O Streamlit roda na nuvem e não acessa diretamente o USB do computador do almoxarifado. A integração real deve usar um **agente local Windows** instalado na estação autorizada:

1. o sistema seleciona o documento e o colaborador;
2. o navegador solicita uma verificação ao agente local;
3. o agente chama o SDK/driver oficial do HFDU06;
4. o colaborador coloca o dedo;
5. o agente verifica a digital cadastrada;
6. o agente devolve somente a evidência técnica da verificação;
7. o backend valida a evidência e vincula a assinatura ao **SHA-256 exato do PDF**.

## Dados que podem retornar ao backend

- `protocolo_versao`
- `evento_id` único
- `aprovado`
- `colaborador_id`
- `documento_id`
- `hash_documento`
- `referencia_biometrica` opaca
- `agente_id`
- modelo e serial do dispositivo
- versão do SDK
- score de verificação, quando o SDK disponibilizar
- `capturado_em` com fuso horário
- assinatura HMAC da evidência

## Dados proibidos

O agente **não deve enviar nem persistir no módulo SST** imagem da impressão digital, bitmap capturado pelo sensor, template biométrico bruto/Base64 ou bytes do template proprietário do SDK.

O banco guarda somente referência opaca e evidência técnica suficiente para auditoria.

## Proteções do protocolo

O módulo `sst_biometria_protocol.py` implementa validações para impedir assinatura se o colaborador ou documento forem diferentes, comparar o SHA-256 exato do PDF, rejeitar leitura expirada ou não aprovada, rejeitar dados biométricos brutos e validar HMAC para detectar adulteração entre agente e backend. O `evento_id` único existente na tabela de assinaturas apoia a proteção contra repetição/replay no banco.

## Próxima etapa física

Para implementar o agente Windows será necessário ter acesso ao equipamento/SDK do fabricante (Nitgen eNBioBSP ou SDK equivalente compatível com o HFDU06). O agente deve ser testado primeiro na branch `desenvolvimento-sst` e nunca marcar um documento como assinado sem resposta real do SDK.
