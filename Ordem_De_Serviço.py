import streamlit as st
import pandas as pd
import os
import hashlib

st.set_page_config(page_title="Gestão de Manutenção - Copa Ambiental", page_icon="🚛", layout="wide")

# ARCHIVOS DE BANCO DE DADOS
ARQUIVO_CSV = 'chamados_manutencao.csv'
ARQUIVO_USUARIOS = 'usuarios.csv'

# LISTA DE VEÍCULOS
VEICULOS = [
    "Caminhão Compactador", "Caminhão Poliguindaste", "Caminhão Roll-On",
    "Caminhão Pipa", "Caminhão Basculante", "Carregadeira",
    "Retroescavadeira", "Trator de Esteira", "Motoniveladora",
    "Pick-up Operacional", "Van de Equipe", "Veículo Leve / Apoio"
]

# FUNÇÕES AUXILIARES PARA CRIPTOGRAFIA E USUÁRIOS
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def carregar_usuarios():
    if not os.path.exists(ARQUIVO_USUARIOS):
        # Cria usuário admin padrão se o arquivo não existir
        df = pd.DataFrame([{
            'usuario': 'admin',
            'senha': hash_senha('admin123'),
            'nome': 'Administrador',
            'nivel': 2
        }])
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return df
    return pd.read_csv(ARQUIVO_USUARIOS)

def salvar_usuario(novo_user, nova_senha, nome, nivel):
    df = carregar_usuarios()
    if novo_user in df['usuario'].values:
        return False, "Usuário já existe!"
    
    novo_df = pd.DataFrame([{
        'usuario': novo_user,
        'senha': hash_senha(nova_senha),
        'nome': nome,
        'nivel': int(nivel)
    }])
    df = pd.concat([df, novo_df], ignore_index=True)
    df.to_csv(ARQUIVO_USUARIOS, index=False)
    return True, "Usuário cadastrado com sucesso!"

def carregar_dados():
    if not os.path.exists(ARQUIVO_CSV):
        df = pd.DataFrame(columns=[
            'ID_OS', 'Data', 'Motorista', 'Veiculo', 'Placa', 
            'Descricao_Problema', 'Status', 'Prioridade', 'Aprovado_Coordenador', 'Mecanico_Responsavel'
        ])
        df.to_csv(ARQUIVO_CSV, index=False)
        return df
    df = pd.read_csv(ARQUIVO_CSV)
    # Garante compatibilidade com colunas novas de controle de fluxo
    for col in ['Prioridade', 'Aprovado_Coordenador', 'Mecanico_Responsavel']:
        if col not in df.columns:
            df[col] = 'Não' if col == 'Aprovado_Coordenador' else 'Pendente'
    return df

def salvar_dados(df):
    df.to_csv(ARQUIVO_CSV, index=False)

# GERENCIAMENTO DE SESSÃO / LOGIN
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_info'] = None

if not st.session_state['logged_in']:
    st.title("🚛 Copa Ambiental | Login do Sistema")
    
    with st.form("form_login"):
        user_input = st.text_input("Usuário")
        password_input = st.text_input("Senha", type="password")
        btn_login = st.form_submit_button("Entrar")
        
        if btn_login:
            df_users = carregar_usuarios()
            senha_enc = hash_senha(password_input)
            user_match = df_users[(df_users['usuario'] == user_input) & (df_users['senha'] == senha_enc)]
            
            if not user_match.empty:
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = user_match.iloc[0].to_dict()
                st.success(f"Bem-vindo, {st.session_state['user_info']['nome']}!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
else:
    # BARRA LATERAL (Informa usuário logado e botão de sair)
    user_data = st.session_state['user_info']
    nivel_user = int(user_data['nivel'])
    
    st.sidebar.write(f"👤 **{user_data['nome']}**")
    st.sidebar.caption(f"Nível de Acesso: {nivel_user}")
    if st.sidebar.button("Sair / Logout"):
        st.session_state['logged_in'] = False
        st.session_state['user_info'] = None
        st.rerun()

    # MONTAGEM DAS ABAS DE ACORDO COM O NÍVEL
    abas_disponiveis = []
    
    # Nível 1, 2 e 3 acessam abertura e consulta
    abas_disponiveis.extend(["📝 Abrir Chamado", "🔍 Consultar Chamados"])
    
    # Nível 3 e Nível 2 acessam Triagem do Coordenador
    if nivel_user in [2, 3]:
        abas_disponiveis.append("🎯 Triagem & Prioridade (Coordenador)")
        
    # Nível 2 (Admin) e Nível 3/Mecânico acessam Manutenção
    if nivel_user in [2]: # Pode ajustar se o mecânico for outro nível específico
        abas_disponiveis.append("🛠️ Painel do Mecânico")
        abas_disponiveis.append("👤 Gestão de Usuários")

    aba_selecionada = st.sidebar.radio("Navegação", abas_disponiveis)

    df_os = carregar_dados()

    # ABA 1: ABRIR CHAMADO (Nível 1, 2, 3)
    if aba_selecionada == "📝 Abrir Chamado":
        st.header("Abertura de Ordem de Serviço")
        with st.form("form_chamado", clear_on_submit=True):
            veiculo = st.selectbox("Selecione o Veículo/Equipamento", VEICULOS)
            placa = st.text_input("Placa / Identificação").upper()
            descricao = st.text_area("Descrição do Defeito / Problema")
            btn_submeter = st.form_submit_button("Enviar Chamado")

            if btn_submeter:
                if placa and descricao:
                    novo_id = f"OS-{len(df_os) + 1001}"
                    nova_os = {
                        'ID_OS': novo_id,
                        'Data': pd.Timestamp.now().strftime('%d/%m/%Y %H:%M'),
                        'Motorista': user_data['nome'],
                        'Veiculo': veiculo,
                        'Placa': placa,
                        'Descricao_Problema': descricao,
                        'Status': 'Aguardando Aprovação',
                        'Prioridade': 'Pendente',
                        'Aprovado_Coordenador': 'Não',
                        'Mecanico_Responsavel': 'Não Atribuído'
                    }
                    df_os = pd.concat([df_os, pd.DataFrame([nova_os])], ignore_index=True)
                    salvar_dados(df_os)
                    st.success(f"Chamado {novo_id} registrado com sucesso!")
                else:
                    st.warning("Preencha a placa e a descrição do problema.")

    # ABA 2: CONSULTAR CHAMADOS (Nível 1, 2, 3)
    elif aba_selecionada == "🔍 Consultar Chamados":
        st.header("Consulta de Ordens de Serviço")
        busca_placa = st.text_input("Filtrar por Placa").upper()
        if busca_placa:
            st.dataframe(df_os[df_os['Placa'].str.contains(busca_placa, na=False)], use_container_width=True)
        else:
            st.dataframe(df_os, use_container_width=True)

    # ABA 3: TRIAGEM & PRIORIDADE (Nível 3 e Nível 2)
    elif aba_selecionada == "🎯 Triagem & Prioridade (Coordenador)":
        st.header("Aprovação e Definição de Prioridades")
        pendentes = df_os[df_os['Aprovado_Coordenador'] == 'Não']

        if pendentes.empty:
            st.info("Não há chamados aguardando aprovação.")
        else:
            for idx, row in pendentes.iterrows():
                with st.expander(f"{row['ID_OS']} - {row['Veiculo']} ({row['Placa']})"):
                    st.write(f"**Motorista:** {row['Motorista']}")
                    st.write(f"**Problema:** {row['Descricao_Problema']}")
                    
                    prioridade = st.selectbox(f"Defina a Prioridade ({row['ID_OS']})", ["Alta", "Média", "Baixa"], key=f"prio_{row['ID_OS']}")
                    if st.button(f"Aprovar e Enviar para Oficina ({row['ID_OS']})"):
                        df_os.at[idx, 'Aprovado_Coordenador'] = 'Sim'
                        df_os.at[idx, 'Prioridade'] = prioridade
                        df_os.at[idx, 'Status'] = 'Aguardando Manutenção'
                        salvar_dados(df_os)
                        st.success(f"{row['ID_OS']} aprovada com sucesso!")
                        st.rerun()

    # ABA 4: PAINEL DO MECÂNICO (Nível 2)
    elif aba_selecionada == "🛠️ Painel do Mecânico":
        st.header("Atendimento de Oficina")
        aprovados = df_os[df_os['Aprovado_Coordenador'] == 'Sim']
        
        if aprovados.empty:
            st.info("Nenhuma OS aprovada na fila da oficina.")
        else:
            for idx, row in aprovados.iterrows():
                with st.expander(f"[{row['Prioridade']}] {row['ID_OS']} - {row['Veiculo']} ({row['Placa']})"):
                    st.write(f"**Problema:** {row['Descricao_Problema']}")
                    st.write(f"**Status Atual:** {row['Status']}")
                    
                    novo_status = st.selectbox(f"Atualizar Status ({row['ID_OS']})", ["Aguardando Manutenção", "Em Andamento", "Concluído"], key=f"status_{row['ID_OS']}")
                    mecanico = st.text_input(f"Mecânico Responsável", value=row['Mecanico_Responsavel'], key=f"mec_{row['ID_OS']}")
                    
                    if st.button(f"Atualizar OS ({row['ID_OS']})"):
                        df_os.at[idx, 'Status'] = novo_status
                        df_os.at[idx, 'Mecanico_Responsavel'] = mecanico
                        salvar_dados(df_os)
                        st.success(f"{row['ID_OS']} atualizada!")
                        st.rerun()

    # ABA 5: GESTÃO DE USUÁRIOS (Apenas Nível 2 - Administração)
    elif aba_selecionada == "👤 Gestão de Usuários":
        st.header("Cadastro de Novos Usuários")
        with st.form("form_novo_user", clear_on_submit=True):
            nome_user = st.text_input("Nome Completo do Colaborador")
            username = st.text_input("Nome de Usuário (Login)").lower()
            senha_user = st.text_input("Senha Inicial", type="password")
            nivel_acesso = st.selectbox("Nível de Acesso", [
                "1 - Motorista (Abrir/Consultar)",
                "2 - Administrador (Acesso Total)",
                "3 - Coordenador (Aprovação/Prioridade)"
            ])
            btn_cadastrar = st.form_submit_button("Criar Usuário")

            if btn_cadastrar:
                if username and senha_user and nome_user:
                    num_nivel = int(nivel_acesso.split(" - ")[0])
                    sucesso, msg = salvar_usuario(username, senha_user, nome_user, num_nivel)
                    if sucesso:
                        st.success(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("Preencha todos os campos do formulário.")
                    
        st.subheader("Usuários Cadastrados")
        df_u = carregar_usuarios()
        st.dataframe(df_u[['usuario', 'nome', 'nivel']], use_container_width=True)
