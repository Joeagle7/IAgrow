import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
from streamlit_geolocation import streamlit_geolocation
import plotly.express as px

# --- 1. CONFIGURACIÓN Y ESTADO DE MEMORIA (SESSION STATE) ---
st.set_page_config(page_title="AgroIA - Panel de Decisión", page_icon="🌾", layout="wide")

# Inicializamos la "memoria" de la aplicación con coordenadas por defecto (Ecuador)
if "lat" not in st.session_state:
    st.session_state.lat = -2.1962
if "lon" not in st.session_state:
    st.session_state.lon = -79.8862

# Estilos CSS profesionales
st.markdown("""
<style>
    .stMetric { background: rgba(255, 255, 255, 0.05); border-radius: 5px; padding: 10px; border: 1px solid rgba(255, 255, 255, 0.1); }
</style>
""", unsafe_allow_html=True)

st.title("🌾 AgroIA: Plataforma Inteligente de Decisión Agrícola")

# --- 2. BARRA LATERAL (Navegación y Control Manual) ---
st.sidebar.header("🕹️ Coordenadas Activas")
st.sidebar.write("Estas coordenadas dirigen todo el análisis:")

# Entradas manuales que se sincronizan con la memoria
nuevo_lat = st.sidebar.number_input("Latitud", value=st.session_state.lat, format="%.4f")
nuevo_lon = st.sidebar.number_input("Longitud", value=st.session_state.lon, format="%.4f")

# Si el usuario cambia los números manualmente, actualizamos la memoria y recargamos
if nuevo_lat != st.session_state.lat or nuevo_lon != st.session_state.lon:
    st.session_state.lat = nuevo_lat
    st.session_state.lon = nuevo_lon
    st.rerun()

st.sidebar.markdown("---")
opcion_menu = st.sidebar.radio("📋 Ir a:", ["Menú Principal (Mapa)", "Forecast Clima", "Análisis Suelo"])

# --- FUNCIONES DE SOPORTE CLIMÁTICO Y SUELO ---
def grados_a_direccion(grados):
    arr = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]
    return arr[int((grados/22.5)+.5) % 16]

def obtener_datos_clima(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=temperature_2m,relativehumidity_2m,dewpoint_2m,apparent_temperature,precipitation_probability,pressure_msl,windspeed_10m,winddirection_10m,et0_fao_evapotranspiration&past_days=3&timezone=America/Guayaquil"
    try: return requests.get(url).json()
    except: return None

def obtener_datos_suelo(lat, lon):
    url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lon={lon}&lat={lat}&property=phh2o&property=clay&property=nitrogen&depth=0-5cm&depth=15-30cm&value=mean"
    try: return requests.get(url).json()
    except: return None


# --- 3. DESARROLLO DE LAS PÁGINAS ---

if opcion_menu == "Menú Principal (Mapa)":
    st.subheader("📍 Definición del Área de Cultivo")
    
    # Nuevo bloque de GPS en la pantalla principal
    st.markdown("### Opción A: Usar mi ubicación actual (GPS)")
    st.write("Haga clic en el botón de abajo y permita el acceso en su navegador para ubicarse automáticamente.")
    ubicacion_gps = streamlit_geolocation()
    
    # Si el GPS captura algo diferente a lo que tenemos en memoria, lo actualizamos
    if ubicacion_gps['latitude'] is not None:
        gps_lat = round(ubicacion_gps['latitude'], 4)
        gps_lon = round(ubicacion_gps['longitude'], 4)
        if gps_lat != st.session_state.lat or gps_lon != st.session_state.lon:
            st.session_state.lat = gps_lat
            st.session_state.lon = gps_lon
            st.rerun()

    st.markdown("---")
    st.markdown("### Opción B: Seleccionar en el Mapa Interactivo")
    st.write("Navegue por el mapa y haga **clic** sobre su parcela. El marcador rojo se moverá a su selección.")
    
    # Crear Mapa Folium centrado en la memoria actual
    m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=13)
    
    # Añadimos un marcador rojo en la ubicación activa
    folium.Marker(
        [st.session_state.lat, st.session_state.lon], 
        popup="Ubicación Activa", 
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)
    
    # Habilitar captura de clics del usuario
    m.add_child(folium.LatLngPopup())
    
    # Renderizar mapa
    output = st_folium(m, width=900, height=500, key="mapa_interactivo")
    
    # Si el usuario hace clic en el mapa, actualizamos la memoria y recargamos
    if output and output.get('last_clicked'):
        click_lat = round(output['last_clicked']['lat'], 4)
        click_lon = round(output['last_clicked']['lng'], 4)
        
        if click_lat != st.session_state.lat or click_lon != st.session_state.lon:
            st.session_state.lat = click_lat
            st.session_state.lon = click_lon
            st.rerun() # Esto refresca la página para mostrar el nuevo marcador y barra lateral

elif opcion_menu == "Forecast Clima":
    st.subheader(f"🌤️ Forecast Agrícola Detallado ({st.session_state.lat}, {st.session_state.lon})")
    json_clima = obtener_datos_clima(st.session_state.lat, st.session_state.lon)
    
    if json_clima and 'hourly' in json_clima:
        cur = json_clima['current_weather']
        st.markdown(f"**Condiciones actuales:** Viento {grados_a_direccion(cur['winddirection'])} a {cur['windspeed']} km/h")
        
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric(label="🌡️ Temperatura", value=f"{cur['temperature']}°C")
        with c2: st.metric(label="💧 Humedad Relativa", value=f"{json_clima['hourly']['relativehumidity_2m'][0]}%")
        with c3: st.metric(label="🌬️ Presión del Viento", value=f"{json_clima['hourly']['pressure_msl'][0]} hPa")
        with c4: st.metric(label="☁️ Punto de Rocío", value=f"{json_clima['hourly']['dewpoint_2m'][0]}°C")
        
        st.markdown("---")
        df_hourly = pd.DataFrame({
            'Fecha_Hora': pd.to_datetime(json_clima['hourly']['time']),
            'Temp_App (°C)': json_clima['hourly']['apparent_temperature'],
            'Prob_Lluvia (%)': json_clima['hourly']['precipitation_probability'],
            'Evapotranspiración (mm)': json_clima['hourly']['et0_fao_evapotranspiration']
        })
        
        fig_temp = px.line(df_hourly, x='Fecha_Hora', y=['Temp_App (°C)', 'Evapotranspiración (mm)'],
                           title='Evolución Térmica y Estrés Hídrico',
                           color_discrete_sequence=['#F0A500', '#0097A7'], template="plotly_dark")
        st.plotly_chart(fig_temp, use_container_width=True)
        
        fig_rain = px.bar(df_hourly, x='Fecha_Hora', y='Prob_Lluvia (%)',
                          title='Probabilidad de Precipitaciones',
                          color_discrete_sequence=['#1565C0'], template="plotly_dark")
        st.plotly_chart(fig_rain, use_container_width=True)

elif opcion_menu == "Análisis Suelo":
    st.subheader(f"🌍 Calidad Edafológica ({st.session_state.lat}, {st.session_state.lon})")
    json_suelo = obtener_datos_suelo(st.session_state.lat, st.session_state.lon)
    
    if json_suelo and 'properties' in json_suelo:
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Capa Superficial (0-5cm)**")
            st.metric("pH", json_suelo['properties']['layers'][1]['depths'][0]['values']['mean'] / 10)
            st.metric("Nitrógeno (cg/kg)", json_suelo['properties']['layers'][2]['depths'][0]['values']['mean'] / 10)
        with c2:
            st.write("**Capa Profunda (15-30cm)**")
            st.metric("pH", json_suelo['properties']['layers'][1]['depths'][1]['values']['mean'] / 10)
            st.metric("Nitrógeno (cg/kg)", json_suelo['properties']['layers'][2]['depths'][1]['values']['mean'] / 10)
