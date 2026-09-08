import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
import os
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Configuração da Página (Correção do parâmetro layout)
st.set_page_config(
    page_title="Sistema Integrado de Gestão de Manutenção de Frota",
    layout="wide"
)

# Caminhos dos Arquivos CSV (Persistência Flat-File)
ARQ_USUARIOS = "usuarios.csv"
ARQ_CHAMADOS = "chamados_manutencao.csv"

# Função para gerar hash SHA-256 das senhas
def gerar_hash(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# Inicialização de Dados Padrão (Caso os arquivos não existam)
def inicializar_dados():
    if not os.path.exists(ARQ_USUARIOS):
        df_usuarios = pd.DataFrame([
            {"usuario": "admin", "senha": gerar_hash("admin123"), "nivel": 4.0},
            {"usuario": "coordenacao", "senha": gerar_hash("coord123"), "nivel": 3.0},
            {"usuario": "mecanico", "senha": gerar_hash("meca123"), "nivel": 2.0},
            {"usuario": "motorista", "senha": gerar_hash("moto123"), "nivel": 1.0}
        ])
        df_usuarios.to_csv(ARQ_USUARIOS, index=False)

    if not os.path.exists(ARQ_CHAMADOS):
        df_chamados = pd.DataFrame(columns=[
            "ID", "Data Abertura", "Motorista", "Veiculo", "Placa", 
            "Descricao_Defeito", "Status", "Prioridade", "Mecanico_Responsavel", "Data_Liberacao"
        ])
        df_chamados.to_csv(ARQ_CHAMADOS, index=False)

inicializar_dados()

# Rotina Autônoma: Limpeza de chamados não aprovados com mais de 7 dias
def limpar_chamados_expirados():
    if os.path.exists(ARQ_CHAMADOS):
        df = pd.read_csv(ARQ_CHAMADOS)
        if not df.empty and "Data Abertura" in df.columns:
            hoje = datetime.now()
            df['Data_Obj'] = pd.to_datetime(df['Data Abertura'], errors='coerce')
            condicao = (df['Status'] != 'Aguardando Aprovação') | ((hoje - df['Data_Obj']).dt.days <= 7)
            df_filtrado = df[condicao].drop(columns=['Data_Obj'])
            df_filtrado.to_csv(ARQ_CHAMADOS, index=False)

limpar_chamados_expirados()

# Função para Gerar Ficha Individual de OS em PDF
def gerar_pdf_os(os_data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elementos = []
    
    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle('TituloOS', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1f2937'), spaceAfter=15, alignment=1)
    estilo_label = ParagraphStyle('Label', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#4b5563'), fontName='Helvetica-Bold')
    estilo_valor = ParagraphStyle('Valor', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#111827'))

    elementos.append(Paragraph(f"<b>ORDEM DE SERVIÇO — {os_data.get('ID', 'N/A')}</b>", estilo_titulo))
    elementos.append(Spacer(1, 10))

    dados_tabela = [
        [Paragraph("Veículo:", estilo_label), Paragraph(str(os_data.get('Veiculo', '')), estilo_valor)],
        [Paragraph("Placa:", estilo_label), Paragraph(str(os_data.get('Placa', '')), estilo_valor)],
        [Paragraph("Data de Abertura:", estilo_label), Paragraph(str(os_data.get('Data Abertura', '')), estilo_valor)],
        [Paragraph("Solicitante:", estilo_label), Paragraph(str(os_data.get('Motorista', '')), estilo_valor)],
        [Paragraph("Relato do Problema:", estilo_label), Paragraph(str(os_data.get('Descricao_Defeito', '')), estilo_valor)],
        [Paragraph("Mecânico Responsável:", estilo_label), Paragraph(str(os_data.get('Mecanico_Responsavel', 'Não atribuído')), estilo_valor)],
        [Paragraph("Status Atual:", estilo_label), Paragraph(str(os_data.get('Status', '')), estilo_valor)],
        [Paragraph("Data de Liberação:", estilo_label), Paragraph(str(os_data.get('Data_Liberacao', 'Pendente / Em andamento')), estilo_valor)]
    ]

    tabela = Table(dados_tabela, colWidths=[150, 390])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
    ]))

    elementos.append(tabela)
    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

# Controle de Sessão
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

# Tela de Login
if not st.session_state.logged_in:
    st.title("Copa Ambiental — Gestão de Manutenção")
    st.subheader("Autenticação de Usuário")
    
    usuario_input = st.text_input("Usuário")
    senha_input = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        df_u = pd.read_csv(ARQ_USUARIOS)
        hash_senha = gerar_hash(senha_input)
        user_match = df_u[(df_u['usuario'] == usuario_input) & (df_u['senha'] == hash_senha)]
        
        if not user_match.empty:
            st.session_state.logged_in = True
            st.session_state.user_info = {
                "usuario": user_match.iloc[0]['usuario'],
                "nivel": float(user_match.iloc[0]['nivel'])
            }
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")
else:
    # Sistema Principal (Pós-Login)
    user = st.session_state.user_info
    st.sidebar.title(f"Painel: {user['usuario']}")
    st.sidebar.markdown(f"**Nível de Acesso:** {user['nivel']}")
    
    if st.sidebar.button("Sair do Sistema"):
        st.session_state.logged_in = False
        st.session_state.user_info = None
        st.rerun()

    st.title("Sistema Integrado de Gestão de Manutenção de Frota")
    
    df_chamados = pd.read_csv(ARQ_CHAMADOS)

    # Abas por perfil / funcionalidade
    aba_opcao = st.sidebar.radio("Navegação", ["Consultar / Ficha OS", "Abertura de Chamado", "Painel da Oficina (Mecânico)", "Coordenação / Triagem", "Gestão de Usuários"])

    if aba_opcao == "Consultar / Ficha OS":
        st.header("Consulta de Ordens de Serviço e Emissão de Ficha")
        if df_chamados.empty:
            st.info("Nenhuma OS registrada no momento.")
        else:
            pesquisa = st.text_input("Filtrar por Placa ou ID da OS")
            df_exibicao = df_chamados.copy()
            if pesquisa:
                df_exibicao = df_exibicao[df_exibicao['Placa'].str.contains(pesquisa, case=False, na=False) | df_exibicao['ID'].str.contains(pesquisa, case=False, na=False)]
            
            st.dataframe(df_exibicao, use_container_width=True)
            
            st.markdown("---")
            st.subheader("Gerar Relatório Individual (PDF)")
            os_ids = df_chamados['ID'].tolist() if not df_chamados.empty else []
            if os_ids:
                os_escolhida = st.selectbox("Selecione o ID da OS para emitir a ficha:", os_ids)
                os_dados_linha = df_chamados[df_chamados['ID'] == os_escolhida].iloc[0].to_dict()
                
                if st.button("📄 Gerar PDF da Ficha de OS"):
                    pdf_bytes = gerar_pdf_os(os_dados_linha)
                    st.download_button(
                        label="📥 Clique para baixar o PDF",
                        data=pdf_bytes,
                        file_name=f"Ficha_{os_escolhida}.pdf",
                        mime="application/pdf"
                    )

    elif aba_opcao == "Abertura de Chamado":
        if user['nivel'] >= 1.0:
            st.header("Abertura de Nova Ordem de Serviço")
            with st.form("form_abertura"):
                veiculo = st.text_input("Modelo do Veículo")
                placa = st.text_input("Placa do Veículo")
                defeito = st.text_area("Relato Detalhado do Defeito")
                submitted = st.form_submit_button("Enviar Chamado")
                
                if submitted:
                    if veiculo and placa and defeito:
                        novo_id = f"OS-{1001 + len(df_chamados)}"
                        novo_registro = {
                            "ID": novo_id,
                            "Data Abertura": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "Motorista": user['usuario'],
                            "Veiculo": veiculo,
                            "Placa": placa,
                            "Descricao_Defeito": defeito,
                            "Status": "Aguardando Aprovação",
                            "Prioridade": "Não Definida",
                            "Mecanico_Responsavel": "",
                            "Data_Liberacao": ""
                        }
                        df_novo = pd.concat([df_chamados, pd.DataFrame([novo_registro])], ignore_index=True)
                        df_novo.to_csv(ARQ_CHAMADOS, index=False)
                        st.success(f"Chamado {novo_id} aberto com sucesso!")
                    else:
                        st.error("Preencha todos os campos obrigatórios.")
        else:
            st.error("Acesso negado.")

    elif aba_opcao == "Painel da Oficina (Mecânico)":
        if user['nivel'] >= 2.0:
            st.header("Painel da Oficina")
            aprovados = df_chamados[df_chamados['Status'].isin(['Aguardando Manutenção', 'Em Andamento'])]
            if aprovados.empty:
                st.info("Nenhuma OS disponível para atendimento na oficina.")
            else:
                for idx, row in aprovados.iterrows():
                    with st.expander(f"{row['ID']} - {row['Veiculo']} ({row['Placa']}) - Status: {row['Status']}"):
                        st.write(f"**Defeito:** {row['Descricao_Defeito']}")
                        st.write(f"**Prioridade:** {row['Prioridade']}")
                        
                        novo_status = st.selectbox("Atualizar Status", ["Aguardando Manutenção", "Em Andamento", "Concluído"], key=f"status_{row['ID']}")
                        mecanico_resp = st.text_input("Mecânico Responsável", value=str(row['Mecanico_Responsavel']), key=f"mec_{row['ID']}")
                        
                        if st.button("Salvar Alteração", key=f"btn_{row['ID']}"):
                            df_chamados.loc[df_chamados['ID'] == row['ID'], 'Status'] = novo_status
                            df_chamados.loc[df_chamados['ID'] == row['ID'], 'Mecanico_Responsavel'] = mecanico_resp
                            if novo_status == "Concluído":
                                df_chamados.loc[df_chamados['ID'] == row['ID'], 'Data_Liberacao'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            df_chamados.to_csv(ARQ_CHAMADOS, index=False)
                            st.success("Atualizado com sucesso!")
                            st.rerun()
        else:
            st.error("Acesso restrito a mecânicos e superiores (Nível 2.0+).")

    elif aba_opcao == "Coordenação / Triagem":
        if user['nivel'] >= 3.0:
            st.header("Triagem e Aprovação de Chamados")
            pendentes = df_chamados[df_chamados['Status'] == 'Aguardando Aprovação']
            if pendentes.empty:
                st.info("Nenhum chamado aguardando aprovação.")
            else:
                for idx, row in pendentes.iterrows():
                    with st.expander(f"{row['ID']} - {row['Veiculo']} ({row['Placa']})"):
                        st.write(f"**Solicitante:** {row['Motorista']} em {row['Data Abertura']}")
                        st.write(f"**Relato:** {row['Descricao_Defeito']}")
                        
                        prioridade = st.selectbox("Definir Prioridade", ["Baixa", "Média", "Alta"], key=f"prio_{row['ID']}")
                        acao = st.radio("Ação", ["Aprovar", "Rejeitar/Excluir"], key=f"acao_{row['ID']}")
                        
                        if st.button("Confirmar Triagem", key=f"triagem_{row['ID']}"):
                            if acao == "Aprovar":
                                df_chamados.loc[df_chamados['ID'] == row['ID'], 'Status'] = 'Aguardando Manutenção'
                                df_chamados.loc[df_chamados['ID'] == row['ID'], 'Prioridade'] = prioridade
                            else:
                                df_chamados = df_chamados[df_chamados['ID'] != row['ID']]
                            df_chamados.to_csv(ARQ_CHAMADOS, index=False)
                            st.success("Triagem processada!")
                            st.rerun()
        else:
            st.error("Acesso restrito à Coordenação (Nível 3.0+).")

    elif aba_opcao == "Gestão de Usuários":
        if user['nivel'] >= 4.0:
            st.header("Gestão de Contas e Credenciais")
            df_u = pd.read_csv(ARQ_USUARIOS)
            st.dataframe(df_u, use_container_width=True)
            
            with st.form("novo_usuario"):
                st.subheader("Cadastrar Novo Usuário")
                novo_user = st.text_input("Nome de Usuário")
                nova_senha = st.text_input("Senha", type="password")
                novo_nivel = st.selectbox("Nível de Acesso", [1.0, 2.0, 3.0, 3.5, 4.0])
                cadastrar = st.form_submit_button("Cadastrar Usuário")
                
                if cadastrar:
                    if novo_user and nova_senha:
                        novo_registro_u = pd.DataFrame([{"usuario": novo_user, "senha": gerar_hash(nova_senha), "nivel": novo_nivel}])
                        df_u_novo = pd.concat([df_u, novo_registro_u], ignore_index=True)
                        df_u_novo.to_csv(ARQ_USUARIOS, index=False)
                        st.success(f"Usuário {novo_user} cadastrado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Preencha todos os campos.")
        else:
            st.error("Acesso exclusivo para SuperAdmin (Nível 4.0).")
