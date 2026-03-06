import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
from streamlit_geolocation import streamlit_geolocation
import plotly.express as px
import math

# --- CONFIGURACIÓN DE PÁGINA PROFESIONAL ---
st.set_page_config(page_title="AgroIA - Panel de Decisión", page_icon="🌾", layout="wide")

# Estilos CSS para el fondo oscuro y colores profesionales
st.markdown("""
<style>
    .reportview-container { background: #1a1a1a; color: #f0f0f0; }
    .stMetric { background: rgba(255, 255, 255, 0.05); border-radius: 5px; padding: 10px; border: 1px solid rgba(255, 255, 255, 0.1); }
    .stMetric label { color: #aaaaaa; }
    .stMetric div { color: #f0f0f0; }
</style>
""", unsafe_allow_html=True)

st.title("🌾 AgroIA: Plataforma Inteligente de Decisión Agrícola")

# --- BARRA LATERAL (Ubicación y Navegación) ---
st.sidebar.header("🕹️ Control de Ubicación")

# 1. Función para captura de ubicación interactiva
def gestionar_ubicacion():
    # Coordenadas por defecto (Guayaquil, como se ve en Imagen 2)
    lat_def = -2.1962
    lon_def = -79.8862
    
    col1, col2 = st.sidebar.columns(2)
    
    # Inputs manuales (estado actual)
    with col1:
        lat = st.number_input("Latitud", value=lat_def, format="%.4f", key="lat_input")
    with col2:
        lon = st.number_input("Longitud", value=lon_def, format="%.4f", key="lon_input")
    
    st.sidebar.markdown("---")
    
    # Botón para geolocalización automática
    st.sidebar.write("Obtener mi ubicación GPS automática:")
    ubicacion_gps = streamlit_geolocation()
    if ubicacion_gps['latitude'] is not None:
        lat = round(ubicacion_gps['latitude'], 4)
        lon = round(ubicacion_gps['longitude'], 4)
        st.sidebar.success(f"📍 GPS: {lat}, {lon}")
        
    return lat, lon

# Ejecutamos gestor de ubicación
latitud_actual, longitud_actual = gestionar_ubicacion()

st.sidebar.markdown("---")
# Menú de navegación principal
opcion_menu = st.sidebar.radio("📋 Ir a:", ["Menú Principal", "Forecast Clima", "Análisis Suelo"])

# --- FUNCIONES DE SOPORTE CLIMÁTICO Y DE SUELO ---

# Función para convertir grados de viento a Rosa de los Vientos
def grados_a_direccion(grados):
    val = int((grados/22.5)+.5)
    arr = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]
    return arr[(val % 16)]

# Función para extraer datos climáticos avanzados (Con control de errores de Imagen 1)
def obtener_datos_clima(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=temperature_2m,relativehumidity_2m,dewpoint_2m,apparent_temperature,precipitation_probability,pressure_msl,windspeed_10m,winddirection_10m,et0_fao_evapotranspiration&past_days=3&timezone=America/Guayaquil"
    try:
        respuesta = requests.get(url).json()
        return respuesta
    except Exception as e:
        st.error(f"Fallo de conexión con Open-Meteo API: {e}")
        return None

# Función para extraer datos de suelo a distintas profundidades
def obtener_datos_suelo(lat, lon):
    url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lon={lon}&lat={lat}&property=phh2o&property=clay&property=nitrogen&depth=0-5cm&depth=15-30cm&value=mean"
    try:
        respuesta = requests.get(url).json()
        return respuesta
    except Exception as e:
        st.error(f"Fallo de conexión con SoilGrids API: {e}")
        return None

# --- DESARROLLO DE LAS PÁGINAS DEL MENÚ ---

# Sección 1: MENÚ PRINCIPAL (Mapa Interactivo)
if opcion_menu == "Menú Principal":
    st.subheader("📍 Mi Parcela y Ubicación Interactiva")
    st.write("Seleccione el punto exacto de su cultivo en el mapa.")
    
    # Crear Mapa Folium
    m = folium.Map(location=[latitud_actual, longitud_actual], zoom_start=14)
    folium.Marker([latitud_actual, longitud_actual], popup="Ubicación Definida").add_to(m)
    # Habilitar captura de clics
    m.add_child(folium.LatLngPopup())
    
    # Renderizar mapa interactivo y capturar clics
    output = st_folium(m, width=900, height=500, key="mapa_interactivo")
    
    # Lógica de actualización por mapa (Si hace clic en el mapa)
    if output['last_clicked'] is not None:
        new_lat = round(output['last_clicked']['lat'], 4)
        new_lon = round(output['last_clicked']['lng'], 4)
        st.info(f"📍 Ha seleccionado una nueva coordenada en el mapa: Lat: {new_lat}, Lon: {new_lon}")
        st.write("La aplicación usará estas coordenadas para el análisis climático y de suelo detallado.")
        
    st.markdown("---")
    st.write("💡 Use los botones de la barra lateral o el mapa para definir su ubicación y luego acceda a las secciones 'Forecast Clima' o 'Análisis Suelo' en el menú.")

# Sección 2: CLIMA DETALLADO (Estilo Imagen 2 y organizado por tiempo)
elif opcion_menu == "Forecast Clima":
    st.subheader(f"🌤️ Forecast Agrícola Detallado ({latitud_actual}, {longitud_actual})")
    
    # Extracción de datos con control de errores (Solución a Imagen 1)
    json_clima = obtener_datos_clima(latitud_actual, longitud_actual)
    
    if json_clima and 'hourly' in json_clima:
        # 1. Sección de Clima Actual (Métricas estilo Imagen 2)
        cur = json_clima['current_weather']
        st.markdown(f"**Condiciones actuales:** Viento {grados_a_direccion(cur['winddirection'])} a {cur['windspeed']} km/h")
        
        c1, c2, c3, c4 = st.columns(4)
        
        # Uso de colores en métricas (Verde, Amarillo, Turquesa, Azul)
        with c1: st.metric(label="🌡️ Temperatura", value=f"{cur['temperature']}°C", delta_color="normal")
        with c2: st.metric(label="💧 Humedad Relativa", value=f"{json_clima['hourly']['relativehumidity_2m'][0]}%")
        with c3: st.metric(label="🌬️ Presión del Viento", value=f"{json_clima['hourly']['pressure_msl'][0]} hPa")
        with c4: st.metric(label="☁️ Punto de Rocío", value=f"{json_clima['hourly']['dewpoint_2m'][0]}°C")
        
        st.markdown("---")
        
        # 2. Pronóstico Horario organizedo como serie de tiempo (Series de Tiempo)
        st.write("🗓️ Proyección de condiciones horarias (Próximas 24h)")
        
        # Crear DataFrame para gráficos interactivos (Librería Plotly)
        df_hourly = pd.DataFrame({
            'Fecha_Hora': pd.to_datetime(json_clima['hourly']['time']),
            'Temp_App (°C)': json_clima['hourly']['apparent_temperature'],
            'Prob_Lluvia (%)': json_clima['hourly']['precipitation_probability'],
            'Evapotranspiración (mm)': json_clima['hourly']['et0_fao_evapotranspiration']
        })
        
        # Gráfico interactivo: Temperatura y EvapotranspiraciónFAO
        # Paleta de colores: Amarillo (Temp), Azul (ET0)
        fig_temp = px.line(df_hourly, x='Fecha_Hora', y=['Temp_App (°C)', 'Evapotranspiración (mm)'],
                           title='Evolución de Temperatura Aparente y Estrés Hídrico (ET0)',
                           color_discrete_sequence=['#F0A500', '#0097A7'], # Amarillo, Turquesa
                           template="plotly_dark")
        st.plotly_chart(fig_temp, use_container_width=True)
        
        # Gráfico interactivo: Probabilidad de Lluvia
        # Paleta de colores: Azul
        fig_rain = px.bar(df_hourly, x='Fecha_Hora', y='Prob_Lluvia (%)',
                          title='Probabilidad de Precipitaciones Horarias',
                          color_discrete_sequence=['#1565C0'], # Azul
                          template="plotly_dark")
        st.plotly_chart(fig_rain, use_container_width=True)
        
        st.info("💡 **Análisis Agrometeorológico:** Si la evapotranspiración FAO (línea turquesa) es persistentemente alta y la probabilidad de lluvia es baja, su cultivo necesita riego suplementario inmediato.")

    else:
        st.warning("⚠️ No se pudieron obtener datos climáticos para esta coordenada.")

# Sección 3: ANÁLISIS DE SUELO (Múltiples profundidades y calidad)
elif opcion_menu == "Análisis Suelo":
    st.subheader(f"🌍 Análisis de Suelo Detailed SoilGrids ({latitud_actual}, {longitud_actual})")
    
    json_suelo = obtener_datos_suelo(latitud_actual, longitud_actual)
    
    if json_suelo and 'properties' in json_suelo:
        # 1. Visualización por profundidades (Organizado como serie de tiempo)
        
        c1, c2 = st.columns(2)
        
        # Capa Superficial (0-5cm)
        with c1:
            st.write("**Capa Superficial (0-5cm)**")
            
            # Extracción del pH (viedienodo entre 10 para normalizar)
            ph_0_5 = json_suelo['properties']['layers'][1]['depths'][0]['values']['mean'] / 10
            nitro_0_5 = json_suelo['properties']['layers'][2]['depths'][0]['values']['mean'] / 10 # cg/kg
            
            st.metric("pH", ph_0_5)
            st.metric("Nitrógeno (cg/kg)", nitro_0_5)
            
            if ph_0_5 < 5.5: st.warning("⚠️ Suelo superficial Ácido. Requiere encalado.")
            else: st.success("Suelo superficial óptimo.")
            
        # Capa Profunda (15-30cm)
        with c2:
            st.write("**Capa Profunda (15-30cm)**")
            
            # pH profundo
            ph_15_30 = json_suelo['properties']['layers'][1]['depths'][1]['values']['mean'] / 10
            nitro_15_30 = json_suelo['properties']['layers'][2]['depths'][1]['values']['mean'] / 10
            
            st.metric("pH", ph_15_30)
            st.metric("Nitrógeno (cg/kg)", nitro_15_30)
            
            if ph_15_30 < 5.5: st.warning("⚠️ Suelo profundo Ácido.")
            else: st.success("Suelo profundo aceptable.")
            
        st.markdown("---")
        st.info("💡 **Análisis de Fertilidad:** Si el nivel de nitrógeno es muy bajo en la capa superficial, se recomienda aplicar fertilizante nitrogenado foliar o localizado antes del próximo riego o lluvia proyectada.")

    else:
        st.warning("⚠️ No se pudieron obtener datos de suelo en esta coordenada satelital.")
