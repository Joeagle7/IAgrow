import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests # <--- Nueva librería para conectar con APIs

# 1. Configuración de la página
st.set_page_config(page_title="AgroIA - Panel de Control", layout="wide")
st.title("🌾 AgroIA: Plataforma Inteligente de Decisión Agrícola")

# 2. Barra lateral (Inputs del usuario)
st.sidebar.header("Parámetros del Cultivo y Ubicación")
cultivo = st.sidebar.selectbox("Seleccione el cultivo", ["Maíz", "Trigo", "Soya", "Cacao", "Banano"])
hectareas = st.sidebar.number_input("Área sembrada (Hectáreas)", min_value=1, value=10)

st.sidebar.markdown("---")
st.sidebar.subheader("Coordenadas GPS")
# Coordenadas por defecto (Ej. Guayas, Ecuador)
latitud = st.sidebar.number_input("Latitud", value=-2.1962, format="%.4f")
longitud = st.sidebar.number_input("Longitud", value=-79.8862, format="%.4f")

# 3. Sección de Mapas en Tiempo Real
st.subheader("📍 Mapa de Condiciones Parcelarias")
mapa = folium.Map(location=[latitud, longitud], zoom_start=9)
folium.Marker([latitud, longitud], popup=f"Finca: {cultivo}").add_to(mapa)
st_folium(mapa, width=700, height=400)

st.markdown("---")

# 4. Conexión a la API Meteorológica (Open-Meteo)
st.subheader("🌤️ Condiciones Agrometeorológicas en Tiempo Real")

# Función estadística/computacional para extraer datos
def obtener_clima(lat, lon):
    # Endpoint de la API con las variables que necesitamos (Temperatura, Humedad, Viento)
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=relativehumidity_2m&timezone=America/Guayaquil"
    respuesta = requests.get(url)
    
    if respuesta.status_code == 200: # El código 200 significa "Conexión Exitosa"
        return respuesta.json()
    else:
        return None

if st.button("Consultar Clima Satelital"):
    st.info("Conectando con servidores meteorológicos...")
    datos_clima = obtener_clima(latitud, longitud)
    
    if datos_clima:
        st.success("Datos extraídos con éxito.")
        
        # Extracción de variables del JSON
        temp_actual = datos_clima['current_weather']['temperature']
        viento_actual = datos_clima['current_weather']['windspeed']
        # Tomamos la humedad de la hora actual
        humedad_actual = datos_clima['hourly']['relativehumidity_2m'][0] 
        
        # Visualización de métricas
        m1, m2, m3 = st.columns(3)
        m1.metric(label="Temperatura Actual", value=f"{temp_actual} °C")
        m2.metric(label="Velocidad del Viento", value=f"{viento_actual} km/h")
        m3.metric(label="Humedad Relativa", value=f"{humedad_actual} %")
        
        # Alerta Temprana Basada en Datos
        if temp_actual > 30:
            st.warning("⚠️ **Alerta:** Alta temperatura detectada. Se sugiere incrementar la lámina de riego para evitar estrés hídrico en el cultivo.")
        elif temp_actual < 15:
            st.warning("⚠️ **Alerta:** Temperatura baja. Monitorear riesgo de ralentización del metabolismo de la planta.")
        else:
            st.success("✅ Condiciones térmicas óptimas para el desarrollo fisiológico.")
            
    else:
        st.error("Fallo de conexión con la API.")
