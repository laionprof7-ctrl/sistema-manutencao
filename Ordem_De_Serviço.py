import streamlit as st
import pandas as pd
import os
import hashlib

st.set_page_config(page_title="Gestão de Manutenção - Copa Ambiental", page_icon="🚛", layout="wide")

# ARQUIVOS DE BANCO DE DADOS
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
        df = pd.DataFrame([{
            'usuario': 'laion',
            'senha': hash_senha('@Laion2004lima'),
            'nome': 'Laion (SuperAdmin)',
            'nivel': 4
        }])
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return df
    
    df = pd.read_csv(ARQUIVO_USUARIOS)
    
    # Garantia de que o usuário 'laion' sempre exista e esteja no nível 4
    if 'laion' not in df['usuario'].values:
        novo_laion = pd.DataFrame([{
            'usuario': 'laion',
            'senha': hash_senha('@Laion2004lima'),
            'nome': 'Laion (SuperAdmin)',
            'nivel': 4
        }])
        df = pd.concat([df, novo_laion], ignore_index=True)
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        
    return df

def salvar_usuario(novo_user, nova_senha, nome, nivel, nivel_criador):
    if int(nivel) == 4 and int(nivel_criador) != 4:
        return False, "Apenas usuários Nível 4 (SuperAdmin) podem criar outros usuários Nível 4!"
        
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

def atualizar_nivel_usuario(user_alvo, novo_nivel, nivel_editor, user_logado):
    if user_alvo == user_logado:
        return False, "Você não pode alterar o seu próprio nível de acesso!"

    if int(novo_nivel) == 4 and int(nivel_editor) != 4:
        return False, "Apenas o SuperAdmin (Nível 4) pode promover usuários ao Nível 4!"
        
    df = carregar_usuarios()
    if user_alvo in df['usuario'].values:
        if user_alvo == 'laion':
            return False, "O usuário principal 'laion' tem seu nível protegido e não pode ser alterado!"
            
        df.loc[df['usuario'] == user_alvo, 'nivel'] = int(novo_nivel)
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return True, f"Nível do usuário '{user_alvo}' atualizado para {novo_nivel}!"
    return False, "Usuário não encontrado!"

def excluir_usuario(user_alvo, user_logado):
    if user_alvo == user_logado:
        return False, "Você não pode excluir a sua própria conta enquanto estiver logado!"

    if user_alvo in ['laion', 'admin']:
        return False, f"O usuário principal '{user_alvo}' está protegido e não pode ser excluído!"
    
    df = carregar_usuarios()
    if user_alvo in df['usuario'].values:
        nivel_user = int(df.loc[df['usuario'] == user_alvo, 'nivel'].values[0])
        if nivel_user == 4:
            return False, "Usuários de Nível 4 são totalmente protegidos contra exclusão!"
            
        df = df[df['usuario'] != user_alvo]
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return True, f"Usuário '{user_alvo}' excluído com sucesso!"
    return False, "Usuário não encontrado!"

def carregar_dados():
    colunas_obrigatorias = [
        'ID_OS', 'Data', 'Motorista', 'Veiculo', 'Placa', 
        'Descricao_Problema', 'Status', 'Prioridade', 'Aprovado_Coordenador', 'Mecanico_Responsavel'
    ]
    
    if not os.path.exists(ARQUIVO_CSV):
        df = pd.DataFrame(columns=colunas_obrigatorias)
        df.to_csv(ARQUIVO_CSV, index=False)
        return df
    
    df = pd.read_csv(ARQUIVO_CSV)
    
    if 'Aprovado_Coordenador' not in df.columns:
        df['Aprovado_Coordenador'] = 'Sim'
    if 'Prioridade' not in df.columns:
        df['Prioridade'] = 'Média'
    if 'Mecanico_Responsavel' not in df.columns:
        df['Mecanico_Responsavel'] = 'Não Atribuído'
        
    for col in colunas_obrigatorias:
        if col not in df.columns:
            df[col] = ''
            
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
        user_input = st.text_input("Usuário").strip().lower()
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
    # BARRA LATERAL
    user_data = st.session_state['user_info']
    nivel_user = int(user_data['nivel'])
    usuario_atual = str(user_data['usuario'])
    
    st.sidebar.write(f"👤 **{user_data['nome']}**")
    st.sidebar.caption(f"Nível de Acesso: {nivel_user}")
    if st.sidebar.button("Sair / Logout"):
        st.session_state['logged_in'] = False
        st.session_state['user_info'] = None
        st.rerun()

    # MONTAGEM DAS ABAS DE ACORDO COM O NÍVEL (1, 2, 3, 4)
    abas_disponiveis = ["📝 Abrir Chamado", "🔍 Consultar Chamados"]
    
    if nivel_user in [2, 3, 4]:
        abas_disponiveis.append("🎯 Triagem & Prioridade (Coordenador)")
        
    if nivel_user in [2, 4]:
        abas_disponiveis.append("🛠️ Painel do Mecânico")
        abas_disponiveis.append("👤 Gestão de Usuários")

    aba_selecionada = st.sidebar.radio("Navegação", abas_disponiveis)

    df_os = carregar_dados()

    # ABA 1: ABRIR CHAMADO
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

    # ABA 2: CONSULTAR CHAMADOS
    elif aba_selecionada == "🔍 Consultar Chamados":
        st.header("Consulta de Ordens de Serviço")
        busca_placa = st.text_input("Filtrar por Placa").upper()
        if busca_placa:
            st.dataframe(df_os[df_os['Placa'].astype(str).str.contains(busca_placa, na=False)], use_container_width=True)
        else:
            st.dataframe(df_os, use_container_width=True)

    # ABA 3: TRIAGEM & PRIORIDADE
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
                    if st.button(f"Aprovar e Enviar para Oficina ({row['ID_OS']})", key=f"btn_aprov_{row['ID_OS']}"):
                        df_os.at[idx, 'Aprovado_Coordenador'] = 'Sim'
                        df_os.at[idx, 'Prioridade'] = prioridade
                        df_os.at[idx, 'Status'] = 'Aguardando Manutenção'
                        salvar_dados(df_os)
                        st.success(f"{row['ID_OS']} aprovada com sucesso!")
                        st.rerun()

    # ABA 4: PAINEL DO MECÂNICO
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
                    
                    if st.button(f"Atualizar OS ({row['ID_OS']})", key=f"btn_mec_{row['ID_OS']}"):
                        df_os.at[idx, 'Status'] = novo_status
                        df_os.at[idx, 'Mecanico_Responsavel'] = mecanico
                        salvar_dados(df_os)
                        st.success(f"{row['ID_OS']} atualizada!")
                        st.rerun()

    # ABA 5: GESTÃO DE USUÁRIOS
    elif aba_selecionada == "👤 Gestão de Usuários":
        st.header("Gerenciamento de Usuários")
        
        col1, col2 = st.columns(2)
        
        # Opções de níveis filtrados conforme quem está cadastrando
        opcoes_nivel = [
            "1 - Motorista (Abrir/Consultar)",
            "2 - Administrador (Acesso Total)",
            "3 - Coordenador (Aprovação/Prioridade)"
        ]
        if nivel_user == 4:
            opcoes_nivel.append("4 - SuperAdmin / Direção (Acesso Total - Protegido)")
        
        # COLUNA 1: CADASTRAR NOVO USUÁRIO
        with col1:
            st.subheader("➕ Cadastrar Novo Usuário")
            with st.form("form_novo_user", clear_on_submit=True):
                nome_user = st.text_input("Nome Completo do Colaborador")
                username = st.text_input("Nome de Usuário (Login)").lower()
                senha_user = st.text_input("Senha Inicial", type="password")
                nivel_acesso = st.selectbox("Nível de Acesso", opcoes_nivel)
                btn_cadastrar = st.form_submit_button("Criar Usuário")

                if btn_cadastrar:
                    if username and senha_user and nome_user:
                        num_nivel = int(nivel_acesso.split(" - ")[0])
                        sucesso, msg = salvar_usuario(username, senha_user, nome_user, num_nivel, nivel_user)
                        if sucesso:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("Preencha todos os campos do formulário.")

        # COLUNA 2: ALTERAR NÍVEL OU EXCLUIR
        with col2:
            st.subheader("⚙️ Alterar Nível ou Excluir Usuário")
            df_u = carregar_usuarios()
            lista_usuarios = df_u['usuario'].tolist()
            
            user_selecionado = st.selectbox("Selecione o Usuário", lista_usuarios)
            
            if user_selecionado:
                dados_u = df_u[df_u['usuario'] == user_selecionado].iloc[0]
                st.write(f"**Nome:** {dados_u['nome']}")
                st.write(f"**Nível Atual:** {dados_u['nivel']}")
                
                with st.expander("✏️ Alterar Nível de Acesso"):
                    novo_niv = st.selectbox("Novo Nível", opcoes_nivel, key="sel_novo_niv")
                    if st.button("Salvar Novo Nível"):
                        num_n = int(novo_niv.split(" - ")[0])
                        sucesso, msg = atualizar_nivel_usuario(user_selecionado, num_n, nivel_user, usuario_atual)
                        if sucesso:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

                with st.expander("🗑️ Excluir Usuário"):
                    st.warning(f"Tem certeza que deseja excluir o usuário '{user_selecionado}'?")
                    if st.button("Confirmar Exclusão", type="primary"):
                        sucesso, msg = excluir_usuario(user_selecionado, usuario_atual)
                        if sucesso:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        st.markdown("---")
        st.subheader("📋 Usuários Cadastrados")
        st.dataframe(df_u[['usuario', 'nome', 'nivel']], use_container_width=True)
