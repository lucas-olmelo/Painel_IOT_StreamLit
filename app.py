import streamlit as st
import paho.mqtt.client as mqtt
import requests
import json
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÕES ---
BROKER_IP = "52.87.253.232"
BROKER_PORT = 1883
TOPICO_COMANDO_LAMP = "/TEF/lamp001/cmd"
TOPICO_COMANDO_RGB  = "/TEF/rgb001/cmd"
ORION_URL = "http://52.87.253.232:1026/v2/entities/urn:ngsi-ld:Lamp:001/attrs"
ORION_HEADERS = {
    'Fiware-Service': 'smart',
    'Fiware-ServicePath': '/'
}

# --- INICIALIZAÇÃO DO HISTÓRICO NA SESSÃO ---
if "historico_luz" not in st.session_state:
    st.session_state.historico_luz = []

# --- FUNÇÃO DE ENVIO DE COMANDO MQTT ---
def enviar_comando_mqtt(comando: str, topico: str = TOPICO_COMANDO_LAMP):
    try:
        client = mqtt.Client()
        client.connect(BROKER_IP, BROKER_PORT, 60)
        client.publish(topico, comando)
        client.disconnect()
        return True
    except Exception as e:
        st.error(f"Erro de conexão MQTT: {e}")
        return False

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Painel IoT - Controle de Luz", page_icon="💡")
st.title("💡 Painel IoT - Controle e Monitoramento")
st.markdown("Controle o LED e monitore o sensor LDR do ESP32 via FIWARE na AWS.")
st.divider()


# --- MONITORAMENTO EM TEMPO REAL (GRÁFICO AUTOMÁTICO) ---
st.subheader("📈 Monitoramento de Luminosidade (Tempo Real)")

col_cfg1, col_cfg2 = st.columns([2, 1])
with col_cfg1:
    monitorar = st.toggle("Ativar coleta automática", value=True)
with col_cfg2:
    if st.button("🗑️ Limpar Gráfico", use_container_width=True):
        st.session_state.historico_luz = []

# Fragmento que roda automaticamente a cada x segundos sem travar o resto da página
@st.fragment(run_every="5s" if monitorar else None)
def atualizar_grafico_luminosidade():
    try:
        response = requests.get(ORION_URL, headers=ORION_HEADERS, timeout=2)
        if response.status_code == 200:
            dados = response.json()
            luz = dados.get('luminosity', {}).get('value')
            estado = dados.get('state', {}).get('value', 'N/D')

            if luz is not None:
                agora = datetime.now().strftime("%H:%M:%S")
                st.session_state.historico_luz.append({
                    "Horário": agora,
                    "Luminosidade (%)": float(luz)
                })
                # Mantém apenas as últimas 30 leituras para o gráfico deslizar suavemente
                if len(st.session_state.historico_luz) > 30:
                    st.session_state.historico_luz.pop(0)

                # Exibe métricas rápidas acima do gráfico
                m1, m2 = st.columns(2)
                m1.metric("Luminosidade Atual", f"{luz}%")
                m2.metric("Estado do LED", str(estado).upper())
            else:
                st.warning("Conectado ao Orion, mas o atributo 'luminosity' ainda está vazio (null).")
        else:
            st.error(f"Erro ao consultar Orion: HTTP {response.status_code}")
    except Exception as e:
        st.error(f"Falha de comunicação com a EC2: {e}")

    # Renderiza o gráfico de linha se houver dados coletados
    if st.session_state.historico_luz:
        df = pd.DataFrame(st.session_state.historico_luz)
        st.line_chart(df, x="Horário", y="Luminosidade (%)", color="#FFA500", height=250)

atualizar_grafico_luminosidade()
st.divider()

# --- CONTROLE POR BOTÕES ---
st.subheader("🎛️ Controle Manual (Botões)")
col1, col2 = st.columns(2)

with col1:
    if st.button("🟢 Acender Luz", use_container_width=True):
        if enviar_comando_mqtt("lamp001@on|"):
            st.success("Comando enviado: LIGAR")

with col2:
    if st.button("🔴 Apagar Luz", use_container_width=True):
        if enviar_comando_mqtt("lamp001@off|"):
            st.success("Comando enviado: DESLIGAR")

st.divider()

# --- CONTROLE DE COR DO LED RGB ---
st.subheader("🎨 Controle de Cor (LED RGB)")

col_cor, col_aplicar, col_apagar = st.columns([1, 2, 1])

with col_cor:
    cor_hex = st.color_picker("Escolha a cor do LED", "#00FF88")

with col_aplicar:
    st.write("") # Espaçamento para alinhar o botão ao seletor
    st.write("")
    if st.button("🌈 Aplicar Cor no LED", use_container_width=True):
        # Converte Hex (#RRGGBB) para valores inteiros R, G, B (0-255)
        hex_limpo = cor_hex.lstrip('#')
        r, g, b = tuple(int(hex_limpo[i:i+2], 16) for i in (0, 2, 4))
        
        if enviar_comando_mqtt(f"rgb001@color|{r},{g},{b}", TOPICO_COMANDO_RGB):
            st.success(f"Enviado para rgb001: RGB({r}, {g}, {b})")

with col_apagar:
    st.write("")
    st.write("")
    if st.button("⬛ Apagar RGB", use_container_width=True):
        if enviar_comando_mqtt("rgb001@off|", TOPICO_COMANDO_RGB):
            st.info("LED RGB apagado.")