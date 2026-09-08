import streamlit as st
import pandas as pd
import os
import hashlib
from datetime import datetime, timedelta
from PIL import Image

# CARREGAMENTO DA LOGO
ARQUIVO_LOGO = "logo.png"
logo_img = None

if os.path.exists(ARQUIVO_LOGO):
    try:
        logo_img = Image.open(ARQUIVO_LOGO)
    except Exception:
        logo_img = None

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(
    page_title="Copa Ambiental - Manutenção", 
    page_icon=logo_img if logo_img else "🚛", 
    layout="wide"
)

# CSS MINIMALISTA E LIMPO
estilo_limpo = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    
    /* Botões do Menu Principal */
    div.stButton > button {
        width: 100%;
        height: 60px;
        font-size: 17px !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: 1px solid #e0e0e0 !important;
        transition: all 0.2s ease;
    }
    div.stButton > button:hover {
        border-color: #008000 !important;
        color: #008000 !important;
    }
    </style>
"""
st.markdown(estilo_limpo, unsafe_allow_html=True)

# ARQUIVOS DE BANCO DE DADOS
ARQUIVO_CSV = 'chamados_manutencao.csv'
ARQUIVO_USUARIOS = 'usuarios.csv'

VEICULOS = [
    "Caminhão Compactador", "Caminhão Poliguindaste", "Caminhão Roll-On",
    "Caminhão Pipa", "Caminhão Basculante", "Carregadeira",
    "Retroescavadeira", "Trator de Esteira", "Motoniveladora",
    "Pick-up Operacional", "Van de Equipe", "Veículo Leve / Apoio"
]

def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def carregar_usuarios():
    if not os.path.exists(ARQUIVO_USUARIOS):
        df = pd.DataFrame([{
            'usuario': 'laion',
            'senha': hash_senha('@Laion2004lima'),
            'nome': 'Laion (SuperAdmin)',
            'nivel': 4.0
        }])
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return df
    
    df = pd.read_csv(ARQUIVO_USUARIOS)
    df['nivel'] = df['nivel'].astype(float)
    
    if 'laion' not in df['usuario'].values:
        novo_laion = pd.DataFrame([{
            'usuario': 'laion',
            'senha': hash_senha('@Laion2004lima'),
            'nome': 'Laion (SuperAdmin)',
            'nivel': 4.0
        }])
        df = pd.concat([df, novo_laion], ignore_index=True)
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        
    return df

def salvar_usuario(novo_user, nova_senha, nome, nivel, nivel_criador):
    if float(nivel) >= 3.5 and float(nivel_criador) < 4.0:
        return False, "Apenas o SuperAdmin (Nível 4) pode criar usuários Nível 3+ ou Nível 4!"
        
    df = carregar_usuarios()
    if novo_user in df['usuario'].values:
        return False, "Usuário já existe!"
    
    novo_df = pd.DataFrame([{
        'usuario': novo_user,
        'senha': hash_senha(nova_senha),
        'nome': nome,
        'nivel': float(nivel)
    }])
    df = pd.concat([df, novo_df], ignore_index=True)
    df.to_csv(ARQUIVO_USUARIOS, index=False)
    return True, "Usuário cadastrado com sucesso!"

def atualizar_nivel_usuario(user_alvo, novo_nivel, nivel_editor, user_logado):
    if user_alvo == user_logado:
        return False, "Você não pode alterar o seu próprio nível de acesso!"

    df = carregar_usuarios()
    if user_alvo in df['usuario'].values:
        if user_alvo == 'laion':
            return False, "O usuário principal 'laion' tem seu nível protegido!"
            
        nivel_alvo = float(df.loc[df['usuario'] == user_alvo, 'nivel'].values[0])
        
        if float(nivel_editor) < 4.0:
            if nivel_alvo >= 3.5:
                return False, "Você não tem permissão para alterar o nível deste usuário!"
            if float(novo_nivel) >= 3.5:
                return False, "Apenas o SuperAdmin (Nível 4) pode promover usuários para Nível 3+ ou Nível 4!"
            
        df.loc[df['usuario'] == user_alvo, 'nivel'] = float(novo_nivel)
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return True, f"Nível do usuário '{user_alvo}' atualizado com sucesso!"
    return False, "Usuário não encontrado!"

def redefinir_senha_usuario(user_alvo, nova_senha, nivel_editor, user_logado):
    df = carregar_usuarios()
    if user_alvo in df['usuario'].values:
        nivel_alvo = float(df.loc[df['usuario'] == user_alvo, 'nivel'].values[0])
        
        if float(nivel_editor) < 4.0 and nivel_alvo >= float(nivel_editor):
            return False, "Você não tem permissão para alterar a senha deste usuário!"

        df.loc[df['usuario'] == user_alvo, 'senha'] = hash_senha(nova_senha)
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return True, f"Senha do usuário '{user_alvo}' alterada com sucesso!"
    return False, "Usuário não encontrado!"

def excluir_usuario(user_alvo, user_logado, nivel_editor):
    if user_alvo == user_logado:
        return False, "Você não pode excluir a sua própria conta enquanto estiver logado!"

    if user_alvo in ['laion', 'admin']:
        return False, f"O usuário principal '{user_alvo}' está protegido!"
    
    df = carregar_usuarios()
    if user_alvo in df['usuario'].values:
        nivel_alvo = float(df.loc[df['usuario'] == user_alvo, 'nivel'].values[0])
        
        if nivel_alvo == 4.0:
            return False, "Usuários de Nível 4 são totalmente protegidos contra exclusão!"
            
        if float(nivel_editor) < 4.0:
            if float(nivel_editor) == 3.5 and nivel_alvo >= 3.5:
                return False, "Usuários Nível 3+ só podem excluir usuários inferiores!"
            elif float(nivel_editor) == 3.0:
                return False, "Apenas usuários de Nível 3+ ou Nível 4 podem excluir contas!"
            
        df = df[df['usuario'] != user_alvo]
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return True, f"Usuário '{user_alvo}' excluído com sucesso!"
    return False, "Usuário não encontrado!"

def limpar_chamados_expirados(df):
    if df.empty or 'Data' not in df.columns:
        return df

    agora = datetime.now()
    indices_para_remover = []

    for idx, row in df.iterrows():
        aprovado = str(row.get('Aprovado_Coordenador', 'Não')).strip()
        if aprovado == 'Não':
            try:
                data_chamado = datetime.strptime(str(row['Data']), '%d/%m/%Y %H:%M')
                if agora - data_chamado > timedelta(days=7):
                    indices_para_remover.append(idx)
            except Exception:
                pass

    if indices_para_remover:
        df = df.drop(index=indices_para_remover).reset_index(drop=True)
        salvar_dados(df)

    return df

def carregar_dados():
    colunas_obrigatorias = [
        'ID_OS', 'Data', 'Motorista', 'Veiculo', 'Placa', 
        'Descricao_Problema', 'Status', 'Prioridade', 'Aprovado_Coordenador', 'Mecanico_Responsavel', 'Arquivado'
    ]
    
    if not os.path.exists(ARQUIVO_CSV):
        df = pd.DataFrame(columns=colunas_obrigatorias)
        df.to_csv(ARQUIVO_CSV, index=False)
        return df
    
    df = pd.read_csv(ARQUIVO_CSV)
    
    mapeamento = {
        'Protocolo': 'ID_OS',
        'Data/Hora': 'Data',
        'Modelo': 'Veiculo',
        'Anamalia_Texto': 'Descricao_Problema'
    }
    
    for antiga, nova in mapeamento.items():
        if antiga in df.columns:
            if nova not in df.columns or df[nova].isnull().all():
                df[nova] = df[antiga]
            df.drop(columns=[antiga], inplace=True)

    if 'Aprovado_Coordenador' not in df.columns:
        df['Aprovado_Coordenador'] = 'Sim'
    if 'Prioridade' not in df.columns:
        df['Prioridade'] = 'Média'
    if 'Mecanico_Responsavel' not in df.columns:
        df['Mecanico_Responsavel'] = 'Não Atribuído'
    if 'Motorista' not in df.columns:
        df['Motorista'] = 'Não Identificado'
    if 'Arquivado' not in df.columns:
        df['Arquivado'] = 'Não'
        
    for col in colunas_obrigatorias:
        if col not in df.columns:
            df[col] = ''
            
    df = df.fillna({
        'Motorista': 'Não Identificado',
        'Descricao_Problema': 'Sem descrição',
        'Mecanico_Responsavel': 'Não Atribuído',
        'Prioridade': 'Média',
        'Arquivado': 'Não',
        'Status': 'Aguardando Aprovação'
    })

    df = limpar_chamados_expirados(df)
    salvar_dados(df)

    return df

def salvar_dados(df):
    df.to_csv(ARQUIVO_CSV, index=False)

# CONTROLE DE SESSÃO
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_info'] = None

if 'aba_ativa' not in st.session_state:
    st.session_state['aba_ativa'] = 'Menu'

# TELA DE LOGIN
if not st.session_state['logged_in']:
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        if logo_img:
            st.image(logo_img, width=280)
        st.subheader("Acesso ao Sistema")
        
        with st.form("form_login"):
            user_input = st.text_input("Usuário").strip().lower()
            password_input = st.text_input("Senha", type="password")
            btn_login = st.form_submit_button("Entrar", use_container_width=True)
            
            if btn_login:
                df_users = carregar_usuarios()
                senha_enc = hash_senha(password_input)
                user_match = df_users[(df_users['usuario'] == user_input) & (df_users['senha'] == senha_enc)]
                
                if not user_match.empty:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = user_match.iloc[0].to_dict()
                    st.session_state['aba_ativa'] = 'Menu'
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

# ÁREA LOGADA
else:
    user_data = st.session_state['user_info']
    nivel_user = float(user_data['nivel'])
    usuario_atual = str(user_data['usuario'])
    lbl_nivel = "3+" if nivel_user == 3.5 else str(int(nivel_user))

    # BARRA LATERAL SIMPLIFICADA
    if logo_img:
        st.sidebar.image(logo_img, use_container_width=True)
    st.sidebar.write(f"👤 **{user_data['nome']}**")
    st.sidebar.caption(f"Nível de Acesso: {lbl_nivel}")
    st.sidebar.markdown("---")
    
    if st.sidebar.button("🏠 Menu Principal", key="sb_home", use_container_width=True):
        st.session_state['aba_ativa'] = 'Menu'
        st.rerun()
        
    if st.sidebar.button("🚪 Sair / Logout", key="sb_logout", use_container_width=True):
        st.session_state['logged_in'] = False
        st.session_state['user_info'] = None
        st.session_state['aba_ativa'] = 'Menu'
        st.rerun()

    df_os = carregar_dados()

    # TELA DO MENU PRINCIPAL (PERMISSÕES AJUSTADAS)
    if st.session_state['aba_ativa'] == 'Menu':
        st.title("Menu Principal")
        st.caption(f"Bem-vindo, {user_data['nome']}")
        
        # Nível 1+: Todos podem abrir e consultar
        opcoes = [
            ("📝 Abrir Chamado", "Abrir Chamado"),
            ("🔍 Consultar Chamados", "Consultar Chamados")
        ]
        
        # Nível 2+: Operacional / Mecânicos ganham o painel da oficina
        if nivel_user >= 2.0:
            opcoes.append(("🛠️ Painel da Oficina", "Oficina"))
            
        # Nível 3+: Coordenadores e SuperAdmins ganham a Triagem e Prioridades
        if nivel_user >= 3.0:
            opcoes.append(("🎯 Triagem e Prioridade", "Triagem"))
            opcoes.append(("👤 Gestão de Usuários", "Usuarios"))

        # Exibição dos botões em grade responsiva
        col_m1, col_m2 = st.columns(2)
        
        for idx, (label, chave) in enumerate(opcoes):
            coluna = col_m1 if idx % 2 == 0 else col_m2
            with coluna:
                if st.button(label, key=f"btn_menu_{chave}", use_container_width=True):
                    st.session_state['aba_ativa'] = chave
                    st.rerun()

    # PÁGINAS INTERNAS
    else:
        col_voltar, col_titulo = st.columns([1, 4])
        with col_voltar:
            if st.button("← Voltar"):
                st.session_state['aba_ativa'] = 'Menu'
                st.rerun()

        # PÁGINA 1: ABRIR CHAMADO
        if st.session_state['aba_ativa'] == "Abrir Chamado":
            st.header("📝 Nova Ordem de Serviço")
            
            col_veic, col_chk = st.columns([3, 1])
            with col_veic:
                veiculo_sel = st.selectbox("Veículo / Equipamento", VEICULOS)
            with col_chk:
                st.write("")
                st.write("")
                outro_marcado = st.checkbox("Outros")

            outros_veiculo = ""
            if outro_marcado:
                outros_veiculo = st.text_input("Especifique o veículo/equipamento")

            with st.form("form_chamado", clear_on_submit=True):
                placa = st.text_input("Placa ou Identificação").upper()
                descricao = st.text_area("Descrição do Problema / Defeito")
                btn_submeter = st.form_submit_button("Enviar Chamado", use_container_width=True)

                if btn_submeter:
                    veiculo_final = outros_veiculo if outro_marcado else veiculo_sel
                    
                    if outro_marcado and not outros_veiculo.strip():
                        st.warning("Por favor, especifique o veículo.")
                    elif placa and descricao:
                        novo_id = f"OS-{len(df_os) + 1001}"
                        nova_os = {
                            'ID_OS': novo_id,
                            'Data': pd.Timestamp.now().strftime('%d/%m/%Y %H:%M'),
                            'Motorista': user_data['nome'],
                            'Veiculo': veiculo_final,
                            'Placa': placa,
                            'Descricao_Problema': descricao,
                            'Status': 'Aguardando Aprovação',
                            'Prioridade': 'Pendente',
                            'Aprovado_Coordenador': 'Não',
                            'Mecanico_Responsavel': 'Não Atribuído',
                            'Arquivado': 'Não'
                        }
                        df_os = pd.concat([df_os, pd.DataFrame([nova_os])], ignore_index=True)
                        salvar_dados(df_os)
                        st.success(f"Chamado {novo_id} enviado com sucesso!")
                    else:
                        st.warning("Preencha a placa e a descrição.")

        # PÁGINA 2: CONSULTAR CHAMADOS
        elif st.session_state['aba_ativa'] == "Consultar Chamados":
            st.header("🔍 Consultar Ordens de Serviço")
            
            c1, c2 = st.columns([3, 1])
            with c1:
                busca_placa = st.text_input("Buscar por Placa").upper()
            with c2:
                ver_arquivados = st.selectbox("Exibir", ["Ativos", "Arquivados"])
            
            df_exibicao = df_os.copy()
            status_arq = "Sim" if ver_arquivados == "Arquivados" else "Não"
            df_exibicao = df_exibicao[df_exibicao['Arquivado'] == status_arq]
            
            if nivel_user == 1.0:
                colunas_nivel_1 = ['ID_OS', 'Data', 'Veiculo', 'Placa', 'Descricao_Problema', 'Status']
                df_exibicao = df_exibicao[colunas_nivel_1]
                df_exibicao.columns = ['Nº OS', 'Data', 'Veículo', 'Placa', 'Descrição', 'Status']
            else:
                colunas_gestao = ['ID_OS', 'Data', 'Motorista', 'Veiculo', 'Placa', 'Descricao_Problema', 'Status', 'Prioridade', 'Mecanico_Responsavel']
                df_exibicao = df_exibicao[colunas_gestao]
                df_exibicao.columns = ['Nº OS', 'Data', 'Solicitante', 'Veículo', 'Placa', 'Descrição', 'Status', 'Prioridade', 'Mecânico']

            if busca_placa:
                df_exibicao = df_exibicao[df_exibicao['Placa'].astype(str).str.contains(busca_placa, na=False)]

            st.dataframe(df_exibicao, use_container_width=True)

            if nivel_user == 4.0:
                st.markdown("---")
                st.subheader("⚙️ Gestão de OS (SuperAdmin)")
                
                lista_os = df_os['ID_OS'].tolist()
                if lista_os:
                    os_selecionada = st.selectbox("Selecione a OS", lista_os)
                    dados_os_sel = df_os[df_os['ID_OS'] == os_selecionada].iloc[0]
                    idx_os = df_os[df_os['ID_OS'] == os_selecionada].index[0]

                    col_arq, col_del = st.columns(2)
                    with col_arq:
                        status_atual_arq = dados_os_sel.get('Arquivado', 'Não')
                        lbl_btn = "Desarquivar" if status_atual_arq == "Sim" else "Arquivar"
                        if st.button(lbl_btn, use_container_width=True):
                            df_os.at[idx_os, 'Arquivado'] = "Não" if status_atual_arq == "Sim" else "Sim"
                            salvar_dados(df_os)
                            st.success("Status atualizado!")
                            st.rerun()

                    with col_del:
                        if st.button("🗑️ Excluir Definitivamente", type="primary", use_container_width=True):
                            df_os = df_os.drop(index=idx_os).reset_index(drop=True)
                            salvar_dados(df_os)
                            st.success("OS excluída!")
                            st.rerun()

        # PÁGINA 3: TRIAGEM (Nível 3+)
        elif st.session_state['aba_ativa'] == "Triagem":
            if nivel_user < 3.0:
                st.error("Acesso não autorizado! Apenas Coordenadores (Nível 3+) possuem acesso à Triagem.")
            else:
                st.header("🎯 Triagem & Prioridades")
                pendentes = df_os[(df_os['Aprovado_Coordenador'] == 'Não') & (df_os['Arquivado'] != 'Sim')]

                if pendentes.empty:
                    st.info("Nenhum chamado pendente de aprovação.")
                else:
                    for idx, row in pendentes.iterrows():
                        with st.expander(f"{row['ID_OS']} - {row['Veiculo']} ({row['Placa']})"):
                            st.write(f"**Solicitante:** {row['Motorista']} | **Data:** {row['Data']}")
                            st.write(f"**Problema:** {row['Descricao_Problema']}")
                            
                            prioridade = st.selectbox(f"Prioridade", ["Alta", "Média", "Baixa"], key=f"prio_{idx}")
                            if st.button(f"Aprovar e Enviar para Oficina", key=f"btn_aprov_{idx}", use_container_width=True):
                                df_os.at[idx, 'Aprovado_Coordenador'] = 'Sim'
                                df_os.at[idx, 'Prioridade'] = prioridade
                                df_os.at[idx, 'Status'] = 'Aguardando Manutenção'
                                salvar_dados(df_os)
                                st.success(f"{row['ID_OS']} aprovada!")
                                st.rerun()

        # PÁGINA 4: OFICINA
        elif st.session_state['aba_ativa'] == "Oficina":
            st.header("🛠️ Painel da Oficina")
            aprovados = df_os[(df_os['Aprovado_Coordenador'] == 'Sim') & (df_os['Arquivado'] != 'Sim')]
            
            aba_pend, aba_and, aba_conc = st.tabs(["⏳ Em Aberto", "🔄 Em Andamento", "✅ Concluídos"])
            
            def renderizar_cards(df_sub, aba_nome):
                if df_sub.empty:
                    st.info(f"Nenhum chamado em '{aba_nome}'.")
                else:
                    for idx, row in df_sub.iterrows():
                        with st.expander(f"[{row['Prioridade']}] {row['ID_OS']} - {row['Veiculo']} ({row['Placa']})"):
                            st.write(f"**Solicitante:** {row['Motorista']} | **Data:** {row['Data']}")
                            st.write(f"**Problema:** {row['Descricao_Problema']}")
                            
                            novo_status = st.selectbox("Status", ["Aguardando Manutenção", "Em Andamento", "Concluído"], index=["Aguardando Manutenção", "Em Andamento", "Concluído"].index(row['Status']) if row['Status'] in ["Aguardando Manutenção", "Em Andamento", "Concluído"] else 0, key=f"st_{idx}")
                            mecanico = st.text_input("Mecânico Responsável", value=row['Mecanico_Responsavel'], key=f"mec_{idx}")
                            
                            if st.button(f"Salvar Alterações", key=f"btn_m_{idx}", use_container_width=True):
                                df_os.at[idx, 'Status'] = novo_status
                                df_os.at[idx, 'Mecanico_Responsavel'] = mecanico
                                salvar_dados(df_os)
                                st.success("Atualizado!")
                                st.rerun()

            with aba_pend:
                renderizar_cards(aprovados[aprovados['Status'] == 'Aguardando Manutenção'], "Em Aberto")
            with aba_and:
                renderizar_cards(aprovados[aprovados['Status'] == 'Em Andamento'], "Em Andamento")
            with aba_conc:
                renderizar_cards(aprovados[aprovados['Status'] == 'Concluído'], "Concluídos")

        # PÁGINA 5: GESTÃO DE USUÁRIOS
        elif st.session_state['aba_ativa'] == "Usuarios":
            if nivel_user < 3.0:
                st.error("Acesso não autorizado! Apenas Nível 3+ possui acesso à Gestão de Usuários.")
            else:
                st.header("👤 Gestão de Usuários")
                
                opcoes_nivel = [
                    "1 - Motorista",
                    "2 - Operacional",
                    "3 - Coordenador"
                ]
                if nivel_user == 4.0:
                    opcoes_nivel.extend(["3.5 - Coordenador Plus", "4 - SuperAdmin"])
                
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("➕ Novo Usuário")
                    with st.form("form_novo_user", clear_on_submit=True):
                        nome_user = st.text_input("Nome Completo")
                        username = st.text_input("Usuário (Login)").lower()
                        senha_user = st.text_input("Senha", type="password")
                        nivel_acesso = st.selectbox("Nível de Acesso", opcoes_nivel)
                        btn_cadastrar = st.form_submit_button("Cadastrar", use_container_width=True)

                        if btn_cadastrar:
                            if username and senha_user and nome_user:
                                num_nivel = float(nivel_acesso.split(" - ")[0])
                                sucesso, msg = salvar_usuario(username, senha_user, nome_user, num_nivel, nivel_user)
                                if sucesso:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                            else:
                                st.warning("Preencha todos os campos.")

                with col2:
                    st.subheader("⚙️ Gerenciar Usuário")
                    df_u = carregar_usuarios()
                    user_selecionado = st.selectbox("Selecione o Usuário", df_u['usuario'].tolist())
                    
                    if user_selecionado:
                        dados_u = df_u[df_u['usuario'] == user_selecionado].iloc[0]
                        st.write(f"**Nome:** {dados_u['nome']} | **Nível:** {dados_u['nivel']}")
                        
                        with st.expander("Alterar Nível"):
                            novo_niv = st.selectbox("Novo Nível", opcoes_nivel, key="sel_nn")
                            if st.button("Salvar Nível", use_container_width=True):
                                num_n = float(novo_niv.split(" - ")[0])
                                sucesso, msg = atualizar_nivel_usuario(user_selecionado, num_n, nivel_user, usuario_atual)
                                if sucesso:
                                    st.success(msg); st.rerun()
                                else:
                                    st.error(msg)

                        with st.expander("Redefinir Senha"):
                            nova_senha = st.text_input("Nova Senha", type="password", key=f"pwd_{user_selecionado}")
                            if st.button("Atualizar Senha", use_container_width=True):
                                if nova_senha:
                                    sucesso, msg = redefinir_senha_usuario(user_selecionado, nova_senha, nivel_user, usuario_atual)
                                    if sucesso:
                                        st.success(msg); st.rerun()
                                    else:
                                        st.error(msg)

                        with st.expander("Excluir Conta"):
                            if st.button("Confirmar Exclusão", type="primary", use_container_width=True):
                                sucesso, msg = excluir_usuario(user_selecionado, usuario_atual, nivel_user)
                                if sucesso:
                                    st.success(msg); st.rerun()
                                else:
                                    st.error(msg)

                st.markdown("---")
                st.dataframe(df_u[['usuario', 'nome', 'nivel']], use_container_width=True)
