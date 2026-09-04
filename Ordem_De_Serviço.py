import streamlit as st
import pandas as pd
import os
import hashlib
from datetime import datetime, timedelta

st.set_page_config(page_title="Gestão de Manutenção - Copa Ambiental", page_icon="🚛", layout="wide")

# ARQUIVOS DE BANCO DE DADOS
ARQUIVO_CSV = 'chamados_manutencao.csv'
ARQUIVO_USUARIOS = 'usuarios.csv'

# LISTA DE VEÍCULOS
VEICULOS = [
    "Caminhão Compactador", "Caminhão Poliguindaste", "Caminhão Roll-On",
    "Caminhão Pipa", "Caminhão Basculante", "Carregadeira",
    "Retroescavadeira", "Trator de Esteira", "Motoniveladora",
    "Pick-up Operacional", "Van de Equipe", "Veículo Leve / Apoio",
    "Outros (Digitar manualmente)"
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

def redefinir_senha_usuario(user_alvo, nova_senha):
    df = carregar_usuarios()
    if user_alvo in df['usuario'].values:
        df.loc[df['usuario'] == user_alvo, 'senha'] = hash_senha(nova_senha)
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return True, f"Senha do usuário '{user_alvo}' alterada com sucesso!"
    return False, "Usuário não encontrado!"

def excluir_usuario(user_alvo, user_logado, nivel_editor):
    if user_alvo == user_logado:
        return False, "Você não pode excluir a sua própria conta enquanto estiver logado!"

    if user_alvo in ['laion', 'admin']:
        return False, f"O usuário principal '{user_alvo}' está protegido e não pode ser excluído!"
    
    df = carregar_usuarios()
    if user_alvo in df['usuario'].values:
        nivel_user = int(df.loc[df['usuario'] == user_alvo, 'nivel'].values[0])
        
        if nivel_user == 4:
            return False, "Usuários de Nível 4 são totalmente protegidos contra exclusão!"
            
        if nivel_user == 3 and int(nivel_editor) != 4:
            return False, "Apenas usuários de Nível 4 (SuperAdmin) podem excluir um usuário de Nível 3!"
            
        df = df[df['usuario'] != user_alvo]
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return True, f"Usuário '{user_alvo}' excluído com sucesso!"
    return False, "Usuário não encontrado!"

def limpar_chamados_expirados(df):
    if df.empty:
        return df

    # Identifica a coluna de data equivalente
    col_data = 'Data' if 'Data' in df.columns else ('Data/Hora' if 'Data/Hora' in df.columns else None)
    if not col_data:
        return df

    agora = datetime.now()
    indices_para_remover = []

    for idx, row in df.iterrows():
        # Checa status de aprovação
        aprovado = str(row.get('Aprovado_Coordenador', 'Não')).strip()
        if aprovado == 'Não':
            try:
                data_chamado = datetime.strptime(str(row[col_data]), '%d/%m/%Y %H:%M')
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
        if col not in df.columns and col not in ['Protocolo', 'Data/Hora', 'Modelo', 'Anamalia_Texto']:
            df[col] = ''
            
    df = limpar_chamados_expirados(df)

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
        abas_disponiveis.append("🛠️ Painel do Mecânico")
        
    if nivel_user in [3, 4]:
        abas_disponiveis.append("👤 Gestão de Usuários")

    aba_selecionada = st.sidebar.radio("Navegação", abas_disponiveis)

    df_os = carregar_dados()

    # ABA 1: ABRIR CHAMADO
    if aba_selecionada == "📝 Abrir Chamado":
        st.header("Abertura de Ordem de Serviço")
        with st.form("form_chamado", clear_on_submit=True):
            veiculo_sel = st.selectbox("Selecione o Veículo/Equipamento", VEICULOS)
            
            outros_veiculo = ""
            if veiculo_sel == "Outros (Digitar manualmente)":
                outros_veiculo = st.text_input("Especifique o Veículo/Equipamento")
                
            placa = st.text_input("Placa / Identificação").upper()
            descricao = st.text_area("Descrição do Defeito / Problema")
            btn_submeter = st.form_submit_button("Enviar Chamado")

            if btn_submeter:
                veiculo_final = outros_veiculo if veiculo_sel == "Outros (Digitar manualmente)" else veiculo_sel
                
                if veiculo_sel == "Outros (Digitar manualmente)" and not outros_veiculo.strip():
                    st.warning("Por favor, especifique o nome do veículo/equipamento no campo indicado.")
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
        
        df_exibicao = df_os.copy()
        
        # Filtro estrito de colunas para Usuário Nível 1
        if nivel_user == 1:
            colunas_permitidas = [
                'ID_OS', 'Protocolo', 
                'Data', 'Data/Hora', 
                'Veiculo', 'Modelo', 
                'Placa', 
                'Descricao_Problema', 'Anamalia_Texto', 
                'Status'
            ]
            cols_existentes = [c for c in df_exibicao.columns if c in colunas_permitidas]
            df_exibicao = df_exibicao[cols_existentes]

        # Busca por Placa
        if busca_placa:
            col_placa = 'Placa' if 'Placa' in df_exibicao.columns else ('placa' if 'placa' in df_exibicao.columns else None)
            if col_placa:
                st.dataframe(df_exibicao[df_exibicao[col_placa].astype(str).str.contains(busca_placa, na=False)], use_container_width=True)
            else:
                st.dataframe(df_exibicao, use_container_width=True)
        else:
            st.dataframe(df_exibicao, use_container_width=True)

    # ABA 3: TRIAGEM & PRIORIDADE
    elif aba_selecionada == "🎯 Triagem & Prioridade (Coordenador)":
        st.header("Aprovação e Definição de Prioridades")
        pendentes = df_os[df_os['Aprovado_Coordenador'] == 'Não']

        if pendentes.empty:
            st.info("Não há chamados aguardando aprovação.")
        else:
            for idx, row in pendentes.iterrows():
                id_exibir = row.get('Protocolo', row.get('ID_OS', f"OS-{idx}"))
                veiculo_exibir = row.get('Modelo', row.get('Veiculo', 'Veículo'))
                placa_exibir = row.get('Placa', '')
                desc_exibir = row.get('Anamalia_Texto', row.get('Descricao_Problema', ''))
                data_exibir = row.get('Data/Hora', row.get('Data', ''))

                with st.expander(f"{id_exibir} - {veiculo_exibir} ({placa_exibir})"):
                    st.write(f"**Data da Abertura:** {data_exibir}")
                    st.write(f"**Problema:** {desc_exibir}")
                    
                    prioridade = st.selectbox(f"Defina a Prioridade ({id_exibir})", ["Alta", "Média", "Baixa"], key=f"prio_{idx}")
                    if st.button(f"Aprovar e Enviar para Oficina ({id_exibir})", key=f"btn_aprov_{idx}"):
                        df_os.at[idx, 'Aprovado_Coordenador'] = 'Sim'
                        df_os.at[idx, 'Prioridade'] = prioridade
                        df_os.at[idx, 'Status'] = 'Aguardando Manutenção'
                        salvar_dados(df_os)
                        st.success(f"{id_exibir} aprovada com sucesso!")
                        st.rerun()

    # ABA 4: PAINEL DO MECÂNICO
    elif aba_selecionada == "🛠️ Painel do Mecânico":
        st.header("Atendimento de Oficina")
        aprovados = df_os[df_os['Aprovado_Coordenador'] == 'Sim']
        
        if aprovados.empty:
            st.info("Nenhuma OS aprovada na fila da oficina.")
        else:
            for idx, row in aprovados.iterrows():
                id_exibir = row.get('Protocolo', row.get('ID_OS', f"OS-{idx}"))
                veiculo_exibir = row.get('Modelo', row.get('Veiculo', 'Veículo'))
                placa_exibir = row.get('Placa', '')
                desc_exibir = row.get('Anamalia_Texto', row.get('Descricao_Problema', ''))
                prio_exibir = row.get('Prioridade', 'Média')
                status_exibir = row.get('Status', 'Em Andamento')
                mec_exibir = row.get('Mecanico_Responsavel', 'Não Atribuído')

                with st.expander(f"[{prio_exibir}] {id_exibir} - {veiculo_exibir} ({placa_exibir})"):
                    st.write(f"**Problema:** {desc_exibir}")
                    st.write(f"**Status Atual:** {status_exibir}")
                    
                    novo_status = st.selectbox(f"Atualizar Status ({id_exibir})", ["Aguardando Manutenção", "Em Andamento", "Concluído"], key=f"status_{idx}")
                    mecanico = st.text_input(f"Mecânico Responsável", value=mec_exibir, key=f"mec_{idx}")
                    
                    if st.button(f"Atualizar OS ({id_exibir})", key=f"btn_mec_{idx}"):
                        df_os.at[idx, 'Status'] = novo_status
                        df_os.at[idx, 'Mecanico_Responsavel'] = mecanico
                        salvar_dados(df_os)
                        st.success(f"{id_exibir} atualizada!")
                        st.rerun()

    # ABA 5: GESTÃO DE USUÁRIOS (APENAS NÍVEL 3 E 4)
    elif aba_selecionada == "👤 Gestão de Usuários":
        st.header("Gerenciamento de Usuários")
        
        col1, col2 = st.columns(2)
        
        opcoes_nivel = [
            "1 - Motorista (Abrir/Consultar)",
            "2 - Administrador / Operacional (Apenas Chamados)",
            "3 - Coordenador (Gestão + Chamados)"
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

        # COLUNA 2: ALTERAR NÍVEL, MUDAR SENHA OU EXCLUIR
        with col2:
            st.subheader("⚙️ Alterar Permissões / Senha / Excluir")
            df_u = carregar_usuarios()
            lista_usuarios = df_u['usuario'].tolist()
            
            user_selecionado = st.selectbox("Selecione o Usuário", lista_usuarios)
            
            if user_selecionado:
                dados_u = df_u[df_u['usuario'] == user_selecionado].iloc[0]
                st.write(f"**Nome:** {dados_u['nome']}")
                st.write(f"**Nível Atual:** {dados_u['nivel']}")
                
                # ALTERAR NÍVEL DE ACESSO
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

                # ALTERAR SENHA
                with st.expander("🔑 Redefinir Senha do Usuário"):
                    nova_senha = st.text_input("Nova Senha", type="password", key=f"pwd_{user_selecionado}")
                    if st.button("Atualizar Senha"):
                        if nova_senha:
                            sucesso, msg = redefinir_senha_usuario(user_selecionado, nova_senha)
                            if sucesso:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.warning("Digite uma nova senha.")

                # EXCLUIR USUÁRIO
                with st.expander("🗑️ Excluir Usuário"):
                    st.warning(f"Tem certeza que deseja excluir o usuário '{user_selecionado}'?")
                    if st.button("Confirmar Exclusão", type="primary"):
                        sucesso, msg = excluir_usuario(user_selecionado, usuario_atual, nivel_user)
                        if sucesso:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        st.markdown("---")
        st.subheader("📋 Usuários Cadastrados")
        st.dataframe(df_u[['usuario', 'nome', 'nivel']], use_container_width=True)
