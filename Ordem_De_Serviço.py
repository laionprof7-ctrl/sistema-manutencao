import streamlit as st
import pandas as pd
from datetime import datetime
import os

# Configuração da página
st.set_page_config(page_title="Sistema de Manutenção", page_icon="🚛", layout="wide")

ARQUIVO_DADOS = 'chamados_manutencao.csv'

# Função para carregar os dados
def carregar_dados():
    if os.path.exists(ARQUIVO_DADOS):
        df = pd.read_csv(ARQUIVO_DADOS, dtype=str)
        # Garante que a coluna de data exista para conversão
        if not df.empty and 'Data/Hora' in df.columns:
            df['Data_dt'] = pd.to_datetime(df['Data/Hora'], format='%d/%m/%Y %H:%M', errors='coerce')
        else:
            df['Data_dt'] = pd.NaT
        return df
    else:
        return pd.DataFrame(columns=[
            'Protocolo', 'Data/Hora', 'Modelo', 'Placa', 
            'Anomalia_Texto', 'Parecer_Mecanico', 'Previsao', 'Status', 'Data_dt'
        ])

# Função para salvar os dados
def salvar_dados(df):
    # Remove a coluna auxiliar de data antes de salvar no CSV
    df_salvar = df.drop(columns=['Data_dt'], errors='ignore')
    df_salvar.to_csv(ARQUIVO_DADOS, index=False)

# Carrega base existente
df_chamados = carregar_dados()

st.title("🚛 Gestão de Ordens de Serviço & Manutenção")

# Menu de Navegação Superior
aba = st.sidebar.radio("Selecione seu perfil:", ["1. Motorista (Abrir Chamado)", "2. Mecânico (Atender/Encerrar)", "3. Consultar Chamados"])

OPCOES_MODELO = [
    "Compactador", "Poliguindaste", "Baú", "Rollon", "Caçamba",
    "Reboque Julieta", "Veículo Leve", "Trator", "Escavadeira",
    "Retroescavadeira", "Sugador", "Carrinho Puxe"
]

# ---------------------------------------------------------
# ABA 1: MOTORISTA
# ---------------------------------------------------------
if aba == "1. Motorista (Abrir Chamado)":
    st.header("📋 Abertura de Chamado - Motorista")
    
    with st.form("form_motorista", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            modelo = st.selectbox("Modelo do Veículo / Equipamento", OPCOES_MODELO)
        with col2:
            placa = st.text_input("Placa / Identificação", placeholder="Ex: RPG4G65").upper()
            
        anomalia_texto = st.text_area("Descreva a anomalia ou problema identificado:")
        
        btn_enviar = st.form_submit_button("Enviar Chamado")
        
        if btn_enviar:
            if not placa:
                st.error("Por favor, informe a placa ou identificação do veículo.")
            elif not anomalia_texto:
                st.error("Por favor, descreva o problema no campo de anomalia.")
            else:
                novo_id = len(df_chamados) + 1001
                protocolo = f"OS-{novo_id}"
                data_atual_str = datetime.now().strftime("%d/%m/%Y %H:%M")
                
                novo_registro = pd.DataFrame([{
                    'Protocolo': protocolo,
                    'Data/Hora': data_atual_str,
                    'Modelo': modelo,
                    'Placa': placa,
                    'Anomalia_Texto': anomalia_texto,
                    'Parecer_Mecanico': 'Aguardando avaliação',
                    'Previsao': 'A definir',
                    'Status': 'Em Aberto',
                    'Data_dt': pd.to_datetime(data_atual_str, format='%d/%m/%Y %H:%M')
                }])
                
                df_chamados = pd.concat([df_chamados, novo_registro], ignore_index=True)
                salvar_dados(df_chamados)
                
                st.success(f"✅ Chamado **{protocolo}** gerado com sucesso às {data_atual_str}!")

# ---------------------------------------------------------
# ABA 2: MECÂNICO
# ---------------------------------------------------------
elif aba == "2. Mecânico (Atender/Encerrar)":
    st.header("🔧 Painel de Manutenção - Mecânico / Encarregado")
    
    chamados_abertos = df_chamados[df_chamados['Status'] != 'Concluído']
    
    if chamados_abertos.empty:
        st.info("Nenhum chamado pendente no momento.")
    else:
        lista_protocolos = chamados_abertos['Protocolo'].tolist()
        protocolo_sel = st.selectbox("Selecione a OS para atualizar:", lista_protocolos)
        
        dados_os = df_chamados[df_chamados['Protocolo'] == protocolo_sel].iloc[0]
        
        st.subheader(f"Detalhes do Chamado: {dados_os['Protocolo']}")
        st.write(f"**Veículo/Equipamento:** {dados_os['Modelo']} - **Placa/ID:** {dados_os['Placa']}")
        st.write(f"**Abertura:** {dados_os['Data/Hora']}")
        st.write(f"**Relato do Motorista:** {dados_os['Anomalia_Texto']}")
        st.divider()
        
        with st.form("form_mecanico"):
            parecer = st.text_area("Parecer do Mecânico / O que precisa ser feito:", value=dados_os['Parecer_Mecanico'])
            previsao = st.text_input("Previsão de Conclusão (ex: 15:00 ou DD/MM):", value=dados_os['Previsao'])
            novo_status = st.selectbox("Status da OS", ["Em Aberto", "Em Andamento", "Concluído"], 
                                      index=["Em Aberto", "Em Andamento", "Concluído"].index(dados_os['Status']))
            
            btn_salvar = st.form_submit_button("Salvar Atualização")
            
            if btn_salvar:
                idx = df_chamados[df_chamados['Protocolo'] == protocolo_sel].index[0]
                df_chamados.at[idx, 'Parecer_Mecanico'] = parecer
                df_chamados.at[idx, 'Previsao'] = previsao
                df_chamados.at[idx, 'Status'] = novo_status
                
                salvar_dados(df_chamados)
                st.success(f"OS {protocolo_sel} atualizada com sucesso!")
                st.rerun()

# ---------------------------------------------------------
# ABA 3: CONSULTAR CHAMADOS (COM FILTROS)
# ---------------------------------------------------------
elif aba == "3. Consultar Chamados":
    st.header("📊 Consulta Geral de Chamados")
    
    if df_chamados.empty:
        st.info("Nenhum chamado cadastrado ainda.")
    else:
        st.subheader("🔍 Filtros de Busca")
        
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            # Filtro de Placa/Busca por texto
            busca_placa = st.text_input("Buscar por Placa ou Modelo:", placeholder="Digite para buscar...").strip().upper()
            
        with col_f2:
            # Filtro por modelo (caixa de seleção)
            modelos_disponiveis = ["Todos"] + sorted(list(df_chamados['Modelo'].dropna().unique()))
            modelo_filtrado = st.selectbox("Filtrar por Equipamento:", modelos_disponiveis)
            
        with col_f3:
            # Filtro por intervalo de datas
            data_inicio = st.date_input("Data Inicial:", value=None)
            data_fim = st.date_input("Data Final:", value=None)

        # Aplicando os filtros
        df_exibir = df_chamados.copy()
        
        if busca_placa:
            df_exibir = df_exibir[
                df_exibir['Placa'].str.contains(busca_placa, case=False, na=False) |
                df_exibir['Modelo'].str.contains(busca_placa, case=False, na=False)
            ]
            
        if modelo_filtrado != "Todos":
            df_exibir = df_exibir[df_exibir['Modelo'] == modelo_filtrado]
            
        if data_inicio:
            df_exibir = df_exibir[df_exibir['Data_dt'].dt.date >= data_inicio]
            
        if data_fim:
            df_exibir = df_exibir[df_exibir['Data_dt'].dt.date <= data_fim]

        # Remove a coluna técnica de data do DataFrame visual
        df_tabela = df_exibir.drop(columns=['Data_dt'], errors='ignore')
        
        st.write(f"**Registros encontrados:** {len(df_tabela)}")
        st.dataframe(df_tabela, width="stretch")
        
        # Botão para baixar apenas o resultado filtrado
        if not df_tabela.empty:
            df_tabela.to_excel("ordens_de_servico.xlsx", index=False)
            with open("ordens_de_servico.xlsx", "rb") as file:
                st.download_button(
                    label="📥 Baixar Dados Filtrados (Excel)",
                    data=file,
                    file_name="ordens_de_servico.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )