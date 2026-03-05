import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta

# 1. Configuración inicial de la interfaz
st.set_page_config(page_title="AgroIA - MVP", page_icon="🌱", layout="centered")

st.title("🌱 AgroIA: Asistente Agrícola")
st.write("Bienvenido. Esta herramienta le ayuda a tomar decisiones basadas en datos climáticos y modelos estadísticos de mercado.")

st.markdown("---")

# 2. Geolocalización (Entrada de datos espaciales)
st.subheader("📍 1. Ubicación de su Parcela")
st.write("Ingrese sus coordenadas. En la versión móvil final, esto se detectará con el GPS del celular.")

# Coordenadas por defecto (Ejemplo: cerca de Quevedo, zona cacaotera)
col1, col2 = st.columns(2)
with col1:
    latitud = st.number_input("Latitud", value=-1.0286, format="%.4f")
with col2:
    longitud = st.number_input("Longitud", value=-79.4635, format="%.4f")

# Mostrar la ubicación en un mapa simple
df_mapa = pd.DataFrame({'lat': [latitud], 'lon': [longitud]})
st.map(df_mapa, zoom=8)

st.markdown("---")

# 3. Simulación de API Meteorológica y Alertas
st.subheader("🌤️ 2. Condiciones Agrometeorológicas")
st.write("Consulta a la base de datos abierta (Simulación de Open-Meteo).")

if st.button("Consultar Clima Actual"):
    # En un entorno real, aquí Python haría una petición HTTP a la API de Open-Meteo
    st.success("Datos obtenidos con éxito.")
    
    # Métricas clave para el agricultor
    m1, m2, m3 = st.columns(3)
    m1.metric(label="Temperatura", value="26°C", delta="-1°C (Frente frío)")
    m2.metric(label="Humedad Relativa", value="85%", delta="5%")
    m3.metric(label="Precipitación Esperada", value="15 mm", delta="Alta")
    
    # Sistema de alerta lógica simple
    st.warning("⚠️ **Alerta Temprana:** Alta probabilidad de lluvias fuertes en las próximas 48 horas. Se recomienda postergar la aplicación de fertilizantes foliares para evitar el lavado del producto.")

st.markdown("---")

# 4. Simulación de Modelo Econométrico (Proyección de Precios)
st.subheader("📈 3. Proyección de Precio del Cacao")
st.write("Estimación basada en modelo VECM (Vectores de Corrección de Errores).")

# Generación de datos simulados para ilustrar la predicción a 6 meses
fechas = [date.today() + timedelta(days=30*i) for i in range(6)]
# Simulamos una tendencia alcista con cierta volatilidad estocástica
precios_base = np.array([3200, 3250, 3180, 3300, 3450, 3400]) 
df_precios = pd.DataFrame({
    "Fecha": fechas,
    "Precio Proyectado (USD/Tonelada)": precios_base
})
df_precios.set_index("Fecha", inplace=True)

# Gráfico de líneas nativo de Streamlit
st.line_chart(df_precios)
st.info("💡 **Análisis de Mercado:** El modelo sugiere una tendencia al alza hacia el trimestre final. Se sugiere retener el inventario seco si sus costos de almacenamiento lo permiten.")