# Copa Ambiental — Sistema de Manutenção

Versão de produção do sistema de ordens de serviço da Copa Ambiental.

## O que mudou

- PostgreSQL obrigatório em produção; SQLite somente para desenvolvimento local.
- Senhas em Argon2id, com upgrade automático de hashes PBKDF2/SHA-256 antigos após login válido.
- Regras de negócio e permissões fora da interface (`services.py`).
- Auditoria de ações administrativas e operacionais.
- Numeração de OS monotônica e independente do ID interno do banco.
- Controle de concorrência otimista por versão para impedir que duas pessoas sobrescrevam a mesma OS sem perceber.
- Exclusão lógica de OS e desativação de usuários para preservar histórico e rastreabilidade.
- Datas salvas em UTC e exibidas no horário da Bahia/Brasil.
- Timeout de sessão, sem bloqueio por quantidade de tentativas de login.
- Restrições e índices no banco para status, prioridade, placa e datas.
- Testes automatizados básicos.
- Migração dos CSVs legados.

## Estrutura

```text
app.py              Interface Streamlit
services.py         Regras de negócio, autorização e auditoria
database.py         Banco, tabelas, transações e consultas
security.py         Senhas, validação e compatibilidade com hashes legados
permissions.py      Matriz de permissões
reports.py          Relatórios PDF
create_admin.py     Criação segura do administrador inicial
migrate_csv.py      Migração dos CSVs antigos
config.py           Configurações
.streamlit/         Configuração do Streamlit
/tests              Testes
```

## Desenvolvimento local

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
set APP_ENV=development
set DATABASE_URL=sqlite:///copa_manutencao_dev.db
python create_admin.py
streamlit run app.py
```

No PowerShell, use `$env:APP_ENV="development"` e `$env:DATABASE_URL="sqlite:///copa_manutencao_dev.db"`.

## Produção no Streamlit Community Cloud

1. Crie um banco PostgreSQL gerenciado (ex.: Supabase, Neon, Render ou outro provedor confiável).
2. Em **Settings > Secrets** do aplicativo, defina:

```toml
DATABASE_URL = "postgresql://USUARIO:SENHA@HOST:5432/BANCO?sslmode=require"
```

3. No mesmo bloco de Secrets, defina `APP_ENV = "production"` (o arquivo de exemplo já mostra isso).
4. Nunca versione `.env` nem `.streamlit/secrets.toml`.
5. Rode `python create_admin.py` apontando para o mesmo `DATABASE_URL` antes do primeiro uso.

Em `APP_ENV=production`, o sistema recusa iniciar sem PostgreSQL.

## Migrar dados antigos

Faça backup dos CSVs e execute:

```bash
python migrate_csv.py --usuarios usuarios.csv --chamados chamados_manutencao.csv
```

Os hashes antigos de senha são preservados durante a migração e atualizados para Argon2id no primeiro login correto de cada usuário.

## Testes

```bash
pytest -q
python -m py_compile *.py
```

## Arquivos opcionais

Para manter a identidade visual nos relatórios, coloque na raiz do projeto:

- `logo.png`

Se o logo não existir, o relatório PDF ainda é gerado normalmente.

## Observação de produção

Esta versão foi desenhada para um sistema interno de manutenção. Para ambientes sujeitos a requisitos formais de compliance, SSO corporativo, LGPD específica, retenção legal ou alta disponibilidade, as políticas da organização ainda devem ser aplicadas à infraestrutura e ao processo operacional.
