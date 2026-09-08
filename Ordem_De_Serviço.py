import streamlit as st
import pandas as pd
import os
import hashlib
from datetime import datetime, timedelta
from PIL import Image
import io

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

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
    
    div.stButton > button {
        width: 100%;
        height: 48px;
        font-size: 16px !important;
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
        df = pd.DataFrame(columns=['usuario', 'senha', 'nome', 'nivel'])
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return df
    
    df = pd.read_csv(ARQUIVO_USUARIOS)
    df['nivel'] = df['nivel'].astype(float)
    return df

def salvar_usuario(novo_user, nova_senha, nome, nivel, nivel_criador):
    df = carregar_usuarios()
    nome_limpo = nome.strip()
    if " " not in nome_limpo:
        return False, "Por favor, digite o Nome e o Sobrenome completo!"

    if float(nivel) >= 4.0:
        return False, "Não é permitido cadastrar novos usuários de nível 4.0!"

    if novo_user in df['usuario'].values:
        return False, "Usuário já existe!"
    
    senha_h = hash_senha(nova_senha)
    if senha_h in df['senha'].values:
        return False, "Esta senha já está em uso por outro usuário."
    
    novo_df = pd.DataFrame([{
        'usuario': novo_user,
        'senha': senha_h,
        'nome': nome_limpo,
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
        nivel_alvo = float(df.loc[df['usuario'] == user_alvo, 'nivel'].values[0])
        if float(novo_nivel) >= 4.0 or nivel_alvo >= 4.0:
            return False, "Não é permitido alterar níveis de Administrador Global (4.0)!"
        if float(nivel_editor) <= nivel_alvo:
            return False, "Você não tem permissão para alterar o nível deste usuário!"
            
        df.loc[df['usuario'] == user_alvo, 'nivel'] = float(novo_nivel)
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return True, f"Nível atualizado com sucesso!"
    return False, "Usuário não encontrado!"

def atualizar_nome_usuario(user_alvo, novo_nome, nivel_editor):
    if float(nivel_editor) < 3.5:
        return False, "Sem permissão!"
    nome_limpo = novo_nome.strip()
    if " " not in nome_limpo:
        return False, "Digite nome e sobrenome!"

    df = carregar_usuarios()
    if user_alvo in df['usuario'].values:
        df.loc[df['usuario'] == user_alvo, 'nome'] = nome_limpo
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return True, "Nome atualizado!"
    return False, "Usuário não encontrado!"

def redefinir_senha_usuario(user_alvo, nova_senha, nivel_editor, user_logado):
    df = carregar_usuarios()
    if user_alvo in df['usuario'].values:
        senha_h = hash_senha(nova_senha)
        df.loc[df['usuario'] == user_alvo, 'senha'] = senha_h
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return True, "Senha alterada!"
    return False, "Usuário não encontrado!"

def excluir_usuario(user_alvo, user_logado, nivel_editor):
    if user_alvo == user_logado:
        return False, "Não pode excluir sua própria conta!"
    df = carregar_usuarios()
    if user_alvo in df['usuario'].values:
        df = df[df['usuario'] != user_alvo]
        df.to_csv(ARQUIVO_USUARIOS, index=False)
        return True, "Usuário excluído!"
    return False, "Usuário não encontrado!"

def limpar_chamados_expirados(df):
    if df.empty or 'Data' not in df.columns:
        return df
    agora = datetime.now()
    indices_para_remover = []
    for idx, row in df.iterrows():
        if str(row.get('Aprovado_Coordenador', 'Não')).strip() == 'Não':
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
        'Descricao_Problema', 'Status', 'Prioridade', 'Aprovado_Coordenador', 
        'Data_Aprovacao', 'Mecanico_Responsavel', 'Data_Liberacao', 'Arquivado'
    ]
    if not os.path.exists(ARQUIVO_CSV):
        df = pd.DataFrame(columns=colunas_obrigatorias)
        df.to_csv(ARQUIVO_CSV, index=False)
        return df
    
    df = pd.read_csv(ARQUIVO_CSV)
    for col in colunas_obrigatorias:
        if col not in df.columns:
            df[col] = ''
            
    df = df.fillna({
        'Motorista': 'Não Identificado',
        'Descricao_Problema': 'Sem descrição',
        'Mecanico_Responsavel': 'Não Atribuído',
        'Prioridade': 'Média',
        'Arquivado': 'Não',
        'Status': 'Aguardando Aprovação',
        'Data_Aprovacao': '',
        'Data_Liberacao': ''
    })
    df = limpar_chamados_expirados(df)
    salvar_dados(df)
    return df

def salvar_dados(df):
    df.to_csv(ARQUIVO_CSV, index=False)

def gerar_relatorio_word(df_rel, subtitulo_filtro=""):
    doc = Document()
    
    p_empresa = doc.add_paragraph()
    p_empresa.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_emp = p_empresa.add_run("COPA ENGENHARIA AMBIENTAL E LOCAÇÃO DE EQUIPAMENTOS LTDA")
    run_emp.bold = True
    run_emp.font.size = Pt(12)
    run_emp.font.color.rgb = RGBColor(0, 100, 0)
    
    p_cnpj = doc.add_paragraph()
    p_cnpj.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_cnpj = p_cnpj.add_run("CNPJ: 08.545.322/0001-28")
    run_cnpj.font.size = Pt(10)
    
    doc.add_paragraph().alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    p_titulo = doc.add_paragraph()
    p_titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_tit = p_titulo.add_run("RELATÓRIO DE MANUTENÇÃO DO VEÍCULO")
    run_tit.bold = True
    run_tit.font.size = Pt(16)
    
    if subtitulo_filtro:
        p_sub = doc.add_paragraph()
        p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_sub = p_sub.add_run(subtitulo_filtro)
        run_sub.font.size = Pt(11)
        run_sub.font.italic = True
    
    p_data_geracao = doc.add_paragraph()
    p_data_geracao.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_data_geracao.add_run(f"Emitido em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
    
    doc.add_paragraph()

    tabela = doc.add_table(rows=1, cols=8)
    tabela.alignment = WD_TABLE_ALIGNMENT.CENTER
    tabela.style = 'Table Grid'
    
    hdr_cells = tabela.rows[0].cells
    cabecalhos = [
        'Nº OS', 'Veículo / Equipamento', 'Identificação / Placa', 
        'Data Registro', 'Data Aprovação', 'Prioridade', 
        'Mecânico Responsável', 'Data Liberação'
    ]
    
    for i, nome_col in enumerate(cabecalhos):
        hdr_cells[i].text = nome_col
        for paragraph in hdr_cells[i].paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(9)
                
    for _, row in df_rel.iterrows():
        row_cells = tabela.add_row().cells
        
        def formatar_data_hora(val):
            if not val or str(val).lower() == 'nan' or str(val).strip() == '':
                return ''
            val_str = str(val).strip()
            try:
                dt = datetime.strptime(val_str, '%d/%m/%Y %H:%M')
                return dt.strftime('%d/%m/%Y %H:%M')
            except ValueError:
                try:
                    dt = datetime.fromisoformat(val_str)
                    return dt.strftime('%d/%m/%Y %H:%M')
                except Exception:
                    return val_str

        valores = [
            str(row.get('ID_OS', '')),
            str(row.get('Veiculo', '')),
            str(row.get('Placa', '')),
            formatar_data_hora(row.get('Data', '')),
            formatar_data_hora(row.get('Data_Aprovacao', '')),
            str(row.get('Prioridade', '')),
            str(row.get('Mecanico_Responsavel', '')),
            formatar_data_hora(row.get('Data_Liberacao', ''))
        ]
        
        for i, val in enumerate(valores):
            row_cells[i].text = val if val != 'nan' else ''
            for paragraph in row_cells[i].paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(8.5)

    f = io.BytesIO()
    doc.save(f)
    f.seek(0)
    return f

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

else:
    user_data = st.session_state['user_info']
    nivel_user = float(user_data['nivel'])
    usuario_atual = str(user_data['usuario'])
    lbl_nivel = str(int(nivel_user)) if nivel_user.is_integer() else str(nivel_user)

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

    if st.session_state['aba_ativa'] == 'Menu':
        st.title("Menu Principal")
        st.caption(f"Bem-vindo, {user_data['nome']}")
        
        opcoes = [
            ("📝 Abrir Chamado", "Abrir Chamado"),
            ("🔍 Consultar Chamados", "Consultar Chamados")
        ]
        
        if nivel_user == 2.0 or nivel_user >= 4.0:
            opcoes.append(("🛠️ Painel da Oficina", "Oficina"))
            
        if nivel_user >= 3.0:
            opcoes.append(("🎯 Triagem e Prioridade", "Triagem"))
            opcoes.append(("👤 Gestão de Usuários", "Usuarios"))

        opcoes.append(("🚪 Sair / Logout", "Logout"))

        col_m1, col_m2 = st.columns(2)
        for idx, (label, chave) in enumerate(opcoes):
            coluna = col_m1 if idx % 2 == 0 else col_m2
            with coluna:
                if st.button(label, key=f"btn_menu_{chave}", use_container_width=True):
                    if chave == "Logout":
                        st.session_state['logged_in'] = False
                        st.session_state['user_info'] = None
                        st.session_state['aba_ativa'] = 'Menu'
                        st.rerun()
                    else:
                        st.session_state['aba_ativa'] = chave
                        st.rerun()

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
                            'Data_Aprovacao': '',
                            'Mecanico_Responsavel': 'Não Atribuído',
                            'Data_Liberacao': '',
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
                busca_placa = st.text_input("Buscar por Placa ou Identificação").upper()
            with c2:
                ver_arquivados = st.selectbox("Exibir", ["Ativos", "Arquivados"])
            
            df_exibicao = df_os.copy()
            status_arq = "Sim" if ver_arquivados == "Arquivados" else "Não"
            df_exibicao = df_exibicao[df_exibicao['Arquivado'] == status_arq]
            
            if nivel_user == 1.0:
                colunas_nivel_1 = ['ID_OS', 'Data', 'Veiculo', 'Placa', 'Descricao_Problema', 'Status']
                df_exibicao = df_exibicao[colunas_nivel_1]
                df_exibicao['Status'] = df_exibicao['Status'].replace({
                    'Aguardando Aprovação': 'Em Aberto',
                    'Aguardando Manutenção': 'Em Aberto'
                })
                df_exibicao.columns = ['Nº OS', 'Data', 'Veículo', 'Placa', 'Descrição', 'Status']
            else:
                colunas_gestao = ['ID_OS', 'Data', 'Motorista', 'Veiculo', 'Placa', 'Descricao_Problema', 'Status', 'Prioridade', 'Mecanico_Responsavel']
                df_exibicao = df_exibicao[colunas_gestao]
                df_exibicao.columns = ['Nº OS', 'Data', 'Solicitante', 'Veículo', 'Placa', 'Descrição', 'Status', 'Prioridade', 'Mecânico']

            if busca_placa:
                df_exibicao = df_exibicao[df_exibicao['Placa'].astype(str).str.contains(busca_placa, na=False)]

            st.dataframe(df_exibicao, use_container_width=True)

            # Seção de Relatório Individual por Veículo/Equipamento para Níveis 3.0+
            if nivel_user >= 3.0:
                st.markdown("")
                with st.container(border=True):
                    st.subheader("📥 Baixar Relatório Individual")
                    
                    df_rel_base = df_os.copy()
                    if status_arq == "Sim":
                        df_rel_base = df_rel_base[df_rel_base['Arquivado'] == 'Sim']
                    else:
                        df_rel_base = df_rel_base[df_rel_base['Arquivado'] != 'Sim']

                    if busca_placa:
                        df_rel_base = df_rel_base[df_rel_base['Placa'].astype(str).str.contains(busca_placa, na=False)]

                    veiculos_disponiveis = df_rel_base['Veiculo'].dropna().unique().tolist()
                    
                    if not veiculos_disponiveis:
                        st.info("Nenhum veículo disponível para exportação com os filtros atuais.")
                    else:
                        col_sel_v, col_btn_v = st.columns([2, 1])
                        with col_sel_v:
                            veiculo_escolhido = st.selectbox("Selecione o Veículo/Equipamento", veiculos_disponiveis)
                        
                        with col_btn_v:
                            st.write("")
                            df_veiculo_especifico = df_rel_base[df_rel_base['Veiculo'] == veiculo_escolhido]
                            arquivo_docx = gerar_relatorio_word(df_veiculo_especifico, subtitulo_filtro=f"Veículo / Equipamento: {veiculo_escolhido}")

                            st.download_button(
                                label=f"Baixar ({veiculo_escolhido})",
                                data=arquivo_docx,
                                file_name=f"relatorio_manutencao_{veiculo_escolhido.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True
                            )

            if nivel_user >= 4.0:
                st.markdown("")
                with st.container(border=True):
                    st.subheader("⚙️ Gestão de OS (Administrador Global)")
                    lista_os = df_os['ID_OS'].tolist()
                    if lista_os:
                        os_selecionada = st.selectbox("Selecione a OS para Ação", lista_os)
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

        # PÁGINA 3: TRIAGEM
        elif st.session_state['aba_ativa'] == "Triagem":
            if nivel_user < 3.0:
                st.error("Acesso não autorizado!")
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
                                df_os.at[idx, 'Data_Aprovacao'] = datetime.now().strftime('%d/%m/%Y %H:%M')
                                salvar_dados(df_os)
                                st.success(f"{row['ID_OS']} aprovada!")
                                st.rerun()

        # PÁGINA 4: OFICINA
        elif st.session_state['aba_ativa'] == "Oficina":
            if nivel_user != 2.0 and nivel_user < 4.0:
                st.error("Acesso não autorizado!")
            else:
                st.header("🛠️ Painel da Oficina")
                aprovados = df_os[(df_os['Aprovado_Coordenador'] == 'Sim') & (df_os['Arquivado'] != 'Sim')]
                
                aba_pend, aba_and, aba_conc = st.tabs(["⏳ Em Aberto", "🔄 Em Andamento", "✅ Concluídos"])
                
                def renderizar_cards(df_sub, aba_nome):
                    if df_sub.empty:
                        st.info(f"Nenhum chamado em '{aba_nome}'.")
                    else:
                        for idx, row in df_sub.iterrows():
                            with st.expander(f"[{row['Prioridade']}] {row['ID_OS']} - {row['Veiculo']} ({row['Placa']})"):
                                st.write(f"**Solicitante:** {row['Motorista']} | **Data do Registro:** {row['Data']}")
                                st.write(f"**Problema:** {row['Descricao_Problema']}")
                                
                                novo_status = st.selectbox("Status", ["Aguardando Manutenção", "Em Andamento", "Concluído"], index=["Aguardando Manutenção", "Em Andamento", "Concluído"].index(row['Status']) if row['Status'] in ["Aguardando Manutenção", "Em Andamento", "Concluído"] else 0, key=f"st_{idx}")
                                
                                mec_atual = str(row['Mecanico_Responsavel']).strip()
                                mec_bloqueado = mec_atual and mec_atual != 'Não Atribuído' and mec_atual != ''
                                
                                if mec_bloqueado:
                                    st.text_input("Mecânico Responsável", value=mec_atual, disabled=True, key=f"mec_dis_{idx}")
                                    mecanico = mec_atual
                                    st.caption("🔒 Mecânico bloqueado após registro inicial.")
                                else:
                                    mecanico = st.text_input("Mecânico Responsável", value="", key=f"mec_{idx}")
                                
                                chave_confirma = f"confirma_mec_{idx}"
                                if chave_confirma not in st.session_state:
                                    st.session_state[chave_confirma] = False

                                if st.button(f"Salvar Alterações", key=f"btn_m_{idx}", use_container_width=True):
                                    if not mec_bloqueado:
                                        if not mecanico or mecanico.strip() == '' or mecanico == 'Não Atribuído':
                                            st.warning("Informe o nome do mecânico responsável.")
                                        else:
                                            st.session_state[chave_confirma] = True
                                            st.session_state[f"temp_mec_{idx}"] = mecanico.strip()
                                            st.session_state[f"temp_status_{idx}"] = novo_status
                                            st.rerun()
                                    else:
                                        df_os.at[idx, 'Status'] = novo_status
                                        if novo_status == 'Concluído' and not str(row['Data_Liberacao']).strip():
                                            df_os.at[idx, 'Data_Liberacao'] = datetime.now().strftime('%d/%m/%Y %H:%M')
                                        elif novo_status != 'Concluído':
                                            df_os.at[idx, 'Data_Liberacao'] = ''
                                        salvar_dados(df_os)
                                        st.success("Atualizado com sucesso!")
                                        st.rerun()

                                if st.session_state.get(chave_confirma, False):
                                    nome_temp = st.session_state[f"temp_mec_{idx}"]
                                    st.warning(f"⚠️ **Atribuir {nome_temp} a função?** (Esta ação bloqueará a alteração futura do mecânico).")
                                    col_conf1, col_conf2 = st.columns(2)
                                    with col_conf1:
                                        if st.button("✅ Sim, Confirmar", key=f"sim_{idx}", use_container_width=True):
                                            df_os.at[idx, 'Status'] = st.session_state[f"temp_status_{idx}"]
                                            df_os.at[idx, 'Mecanico_Responsavel'] = nome_temp
                                            
                                            st_fin = st.session_state[f"temp_status_{idx}"]
                                            if st_fin == 'Concluído' and not str(row['Data_Liberacao']).strip():
                                                df_os.at[idx, 'Data_Liberacao'] = datetime.now().strftime('%d/%m/%Y %H:%M')
                                            
                                            salvar_dados(df_os)
                                            st.session_state[chave_confirma] = False
                                            st.success("Mecânico atribuído e bloqueado com sucesso!")
                                            st.rerun()
                                    with col_conf2:
                                        if st.button("❌ Cancelar", key=f"nao_{idx}", use_container_width=True):
                                            st.session_state[chave_confirma] = False
                                            st.rerun()

                with aba_pend:
                    renderizar_cards(aprovados[aprovados['Status'] == 'Aguardando Manutenção'], "Em Aberto")
                with aba_and:
                    renderizar_cards(aprovados[aprovados['Status'] == 'Em Andamento'], "Em Andamento")
                with aba_conc:
                    renderizar_cards(aprovados[aprovados['Status'] == 'Concluído'], "Concluídos")

        # PÁGINA 5: GESTÃO DE USUÁRIOS
        elif st.session_state['aba_ativa'] == "Usuarios":
            if nivel_user < 3.5:
                st.error("Acesso não autorizado!")
            else:
                st.header("👤 Gestão de Usuários")
                opcoes_nivel = ["1 - Motorista", "2 - Operacional", "3 - Coordenador"]
                if nivel_user >= 4.0:
                    opcoes_nivel.append("3.5 - Coordenador Plus")
                
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
                    if df_u.empty:
                        st.info("Nenhum usuário cadastrado.")
                    else:
                        opcoes_select = []
                        mapa_usuarios = {}
                        for _, r in df_u.iterrows():
                            nome_limpo = str(r['nome']).replace("SuperAdmin", "").strip()
                            rotulo = f"{nome_limpo} ({r['usuario']})"
                            opcoes_select.append(rotulo)
                            mapa_usuarios[rotulo] = r['usuario']

                        user_selecionado_rotulo = st.selectbox("Selecione o Usuário", opcoes_select)
                        user_selecionado = mapa_usuarios[user_selecionado_rotulo]
                        
                        if user_selecionado:
                            dados_u = df_u[df_u['usuario'] == user_selecionado].iloc[0]
                            st.write(f"**Nome:** {dados_u['nome']} | **Usuário:** `{dados_u['usuario']}` | **Nível:** {dados_u['nivel']}")
                            
                            with st.expander("Alterar Nome"):
                                novo_nome_input = st.text_input("Novo Nome Completo", value=str(dados_u['nome']), key=f"nome_{user_selecionado}")
                                if st.button("Salvar Novo Nome", use_container_width=True):
                                    sucesso, msg = atualizar_nome_usuario(user_selecionado, novo_nome_input, nivel_user)
                                    if sucesso:
                                        st.success(msg); st.rerun()
                                    else:
                                        st.error(msg)

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
                if not df_u.empty:
                    st.dataframe(df_u[['usuario', 'nome', 'nivel']], use_container_width=True)
