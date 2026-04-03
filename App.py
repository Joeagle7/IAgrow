import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
from streamlit_geolocation import streamlit_geolocation
import plotly.express as px
import ee
from datetime import datetime, timedelta
import google.generativeai as genai
from PIL import Image
import io

# --- 1. CONFIGURACIÓN Y ESTADO DE MEMORIA ---
st.set_page_config(page_title="AgroIA - Panel de Decisión", page_icon="🌾", layout="wide")

if "lat" not in st.session_state: st.session_state.lat = -2.1962
if "lon" not in st.session_state: st.session_state.lon = -79.8862

@st.cache_resource
def inicializar_google_earth_engine():
    try:
        if "EE_CREDENTIALS" in st.secrets:
            import json
            from google.oauth2 import service_account
            creds_dict = json.loads(st.secrets["EE_CREDENTIALS"])
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
            scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/earthengine'])
            ee.Initialize(scoped_credentials)
        else:
            ee.Initialize()
        return True
    except Exception as e:
        return False

gee_activo = inicializar_google_earth_engine()

try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        gemini_activo = True
    else:
        gemini_activo = False
except Exception as e:
    gemini_activo = False

# --- 2. DISEÑO UI/UX EJECUTIVO (VERDE Y TURQUESA) ---
st.markdown("""
<style>
    /* Estilos del contenedor principal del menú */
    div[data-testid="stRadio"] > div {
        display: flex;
        flex-direction: row;
        justify-content: center;
        background: linear-gradient(90deg, #f4fdfb 0%, #e8f5e9 100%);
        padding: 15px;
        border-radius: 8px;
        border-bottom: 4px solid #009688;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        gap: 15px;
        flex-wrap: wrap;
    }
    /* Estilo de las opciones del menú */
    div[data-testid="stRadio"] > div > label {
        background-color: white;
        padding: 10px 20px;
        border-radius: 5px;
        border: 1px solid #c8e6c9;
        color: #2e7d32 !important;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    div[data-testid="stRadio"] > div > label:hover {
        background-color: #e0f2f1;
        border-color: #009688;
        transform: translateY(-2px);
    }
    /* Tarjetas de métricas */
    .stMetric { 
        background: #ffffff; 
        border-radius: 8px; 
        padding: 15px; 
        border-left: 5px solid #009688;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

c_logo, c_title = st.columns([1, 11])
with c_logo:
    st.markdown("## 🌿")
with c_title:
    st.title("AgroIA: Terminal de Precisión Climática")

st.markdown("---")

# Menú Horizontal
opcion_menu = st.radio(
    "Navegación:", 
    ["Menú Principal (Mapa)", "Control Meteorológico", "Perfil de Suelo (Copernicus)", "Mapa Satelital (NDVI)", "Diagnóstico IA 🤖"],
    horizontal=True,
    label_visibility="collapsed"
)
st.markdown("<br>", unsafe_allow_html=True) # Espaciador

# --- FUNCIONES AUXILIARES ---
def grados_a_direccion(grados):
    arr = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]
    return arr[int((grados/22.5)+.5) % 16]

def obtener_elevacion(lat, lon):
    url = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}"
    try: return requests.get(url).json()['elevation'][0]
    except: return "No disponible"
        
def obtener_datos_clima(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=temperature_2m,relativehumidity_2m,dewpoint_2m,precipitation_probability,pressure_msl,windspeed_10m,winddirection_10m,et0_fao_evapotranspiration&past_days=3&timezone=America/Guayaquil"
    try: return requests.get(url).json()
    except: return None

# NUEVA FUNCIÓN: COPERNICUS ERA5-LAND
def obtener_datos_suelo_copernicus(lat, lon):
    # Llama a la asimilación física del suelo en 4 capas de profundidad
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=soil_temperature_0_to_7cm,soil_temperature_7_to_28cm,soil_temperature_28_to_100cm,soil_temperature_100_to_255cm,soil_moisture_0_to_7cm,soil_moisture_7_to_28cm,soil_moisture_28_to_100cm,soil_moisture_100_to_255cm&timezone=America/Guayaquil"
    try: return requests.get(url).json()
    except: return None

# --- 3. DESARROLLO DE LAS PÁGINAS ---

if opcion_menu == "Menú Principal (Mapa)":
    st.subheader("📍 Coordenadas de la Parcela")
    
    c_lat, c_lon, c_gps = st.columns([2, 2, 2])
    with c_lat: nuevo_lat = st.number_input("Latitud", value=st.session_state.lat, format="%.4f")
    with c_lon: nuevo_lon = st.number_input("Longitud", value=st.session_state.lon, format="%.4f")
    with c_gps:
        st.write("O GPS actual:")
        ubicacion_gps = streamlit_geolocation()
        if ubicacion_gps['latitude'] is not None:
            nuevo_lat, nuevo_lon = round(ubicacion_gps['latitude'], 4), round(ubicacion_gps['longitude'], 4)

    if nuevo_lat != st.session_state.lat or nuevo_lon != st.session_state.lon:
        st.session_state.lat, st.session_state.lon = nuevo_lat, nuevo_lon
        st.rerun()

    st.write("Haga **clic** sobre su parcela en el mapa para afinar la ubicación.")
    m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=14)
    folium.Marker([st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="green", icon="leaf")).add_to(m)
    output = st_folium(m, width=1000, height=450, key="mapa_principal", returned_objects=["last_clicked"])

    if output and output.get('last_clicked'):
        click_lat, click_lon = round(output['last_clicked']['lat'], 4), round(output['last_clicked']['lng'], 4)
        if click_lat != st.session_state.lat or click_lon != st.session_state.lon:
            st.session_state.lat, st.session_state.lon = click_lat, click_lon
            st.rerun()

elif opcion_menu == "Control Meteorológico":
    st.subheader(f"🌤️ Pronóstico Agrometeorológico ({st.session_state.lat}, {st.session_state.lon})")
    json_clima = obtener_datos_clima(st.session_state.lat, st.session_state.lon)
    if json_clima and 'hourly' in json_clima:
        cur = json_clima['current_weather']
        st.markdown(f"**Condiciones en superficie:** Viento {grados_a_direccion(cur['winddirection'])} a {cur['windspeed']} km/h")
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("🌡️ Temperatura", f"{cur['temperature']}°C")
        with c2: st.metric("💧 Humedad Relativa", f"{json_clima['hourly']['relativehumidity_2m'][0]}%")
        with c3: st.metric("🌬️ Presión Atmosférica", f"{json_clima['hourly']['pressure_msl'][0]} hPa")
        with c4: st.metric("☁️ Punto de Rocío", f"{json_clima['hourly']['dewpoint_2m'][0]}°C")
        
        df_hourly = pd.DataFrame({
            'Fecha_Hora': pd.to_datetime(json_clima['hourly']['time']),
            'Prob_Lluvia (%)': json_clima['hourly']['precipitation_probability'],
            'Evapotranspiración (mm)': json_clima['hourly']['et0_fao_evapotranspiration']
        })
        st.plotly_chart(px.line(df_hourly, x='Fecha_Hora', y='Evapotranspiración (mm)', title="Estrés Atmosférico (Evapotranspiración)", template="plotly_white", color_discrete_sequence=['#FF7043']), use_container_width=True)
        st.plotly_chart(px.bar(df_hourly, x='Fecha_Hora', y='Prob_Lluvia (%)', title="Probabilidad de Precipitación", template="plotly_white", color_discrete_sequence=['#42A5F5']), use_container_width=True)

# LA NUEVA SECCIÓN DE SUELO (COPERNICUS)
elif opcion_menu == "Perfil de Suelo (Copernicus)":
    st.subheader(f"🌍 Perfil Físico del Suelo (ERA5-Land: Copernicus)")
    st.info("Modelo Termodinámico e Hidrológico Asimilado. Representa el volumen de agua pura contenida en la matriz del suelo y su temperatura, vital para la raíz y microbiología.")
    
    json_suelo = obtener_datos_suelo_copernicus(st.session_state.lat, st.session_state.lon)
    
    if json_suelo and 'current' in json_suelo:
        datos = json_suelo['current']
        
        st.markdown("### 💧 Humedad Volumétrica del Suelo (m³/m³)")
        ch1, ch2, ch3, ch4 = st.columns(4)
        ch1.metric("0 - 7 cm (Siembra)", f"{datos.get('soil_moisture_0_to_7cm', 'N/A')} m³")
        ch2.metric("7 - 28 cm (Raíz Corta)", f"{datos.get('soil_moisture_7_to_28cm', 'N/A')} m³")
        ch3.metric("28 - 100 cm (Raíz Profunda)", f"{datos.get('soil_moisture_28_to_100cm', 'N/A')} m³")
        ch4.metric("100 - 289 cm (Acuífero)", f"{datos.get('soil_moisture_100_to_255cm', 'N/A')} m³")
        
        st.markdown("---")
        st.markdown("### 🌡️ Temperatura del Perfil del Suelo (°C)")
        ct1, ct2, ct3, ct4 = st.columns(4)
        ct1.metric("0 - 7 cm (Superficie)", f"{datos.get('soil_temperature_0_to_7cm', 'N/A')} °C")
        ct2.metric("7 - 28 cm (Zona Fúngica)", f"{datos.get('soil_temperature_7_to_28cm', 'N/A')} °C")
        ct3.metric("28 - 100 cm", f"{datos.get('soil_temperature_28_to_100cm', 'N/A')} °C")
        ct4.metric("100 - 289 cm", f"{datos.get('soil_temperature_100_to_255cm', 'N/A')} °C")
        
        st.caption("*Interpretación Técnica: Humedad < 0.15 indica sequía severa en arcillas. Temperaturas > 28°C en zona radicular pueden acelerar patógenos como Fusarium o Phytophthora.*")
    else:
        st.error("❌ Error al conectar con la asimilación del modelo Copernicus.")

elif opcion_menu == "Mapa Satelital (NDVI)":
    st.subheader(f"🛰️ Análisis Satelital de Salud Vegetal (NDVI)")
    if not gee_activo:
        st.error("⚠️ Error: Google Earth Engine no está inicializado.")
    else:
        with st.spinner("Procesando mosaico satelital libre de nubes..."):
            try:
                punto = ee.Geometry.Point([st.session_state.lon, st.session_state.lat])
                fecha_fin = datetime.today()
                fecha_inicio = fecha_fin - timedelta(days=90)
                
                def enmascarar_nubes(imagen):
                    qa = imagen.select('QA60') 
                    mascara = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
                    return imagen.updateMask(mascara)
                
                coleccion = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(punto).filterDate(fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d')).map(enmascarar_nubes) 
                
                if coleccion.size().getInfo() == 0:
                    st.warning("☁️ Cobertura nubosa total y permanente en este trimestre.")
                else:
                    imagen_limpia = coleccion.median()
                    st.info("🧩 **Mosaico Satelital:** Fusión matemática de los píxeles despejados en los últimos 90 días.")
                    
                    ndvi = imagen_limpia.normalizedDifference(['B8', 'B4']).rename('NDVI')
                    vis_params = {'min': 0.1, 'max': 0.6, 'palette': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']}
                    map_id_dict = ee.Image(ndvi).getMapId(vis_params)
                    
                    m_ndvi = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=15, max_zoom=20)
                    folium.TileLayer(tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Satélite Base', overlay=False, max_zoom=20).add_to(m_ndvi)
                    folium.TileLayer(tiles=map_id_dict['tile_fetcher'].url_format, attr='Google Earth Engine', name='NDVI', overlay=True, opacity=0.7, max_zoom=20, max_native_zoom=16).add_to(m_ndvi)
                    folium.Marker([st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="red")).add_to(m_ndvi)
                    st_folium(m_ndvi, width=1000, height=450, key="mapa_ndvi")
            except Exception as e:
                st.error(f"❌ Error satelital: {e}")

elif opcion_menu == "Diagnóstico IA 🤖":
    st.subheader("🤖 Diagnóstico Fitosanitario Asistido por IA")
    st.warning("**⚠️ Aviso Legal:** Los resultados son probabilísticos. Verifique con un agrónomo.")
    
    elevacion_actual = obtener_elevacion(st.session_state.lat, st.session_state.lon)
    clima_actual = obtener_datos_clima(st.session_state.lat, st.session_state.lon)
    
    clima_texto = "No disponible"
    if clima_actual and 'current_weather' in clima_actual:
        temp = clima_actual['current_weather']['temperature']
        hum = clima_actual['hourly']['relativehumidity_2m'][0]
        clima_texto = f"{temp}°C, Humedad {hum}%"
        
    st.success(f"📍 **Contexto Extraído:** Altitud: {elevacion_actual} m.s.n.m. | 🌤️ **Clima Reciente:** {clima_texto}")
    st.markdown("---")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        cultivo_seleccionado = st.selectbox("🌱 Cultivo", ["Cacao", "Banano", "Arroz", "Maíz", "Otro"])
        if cultivo_seleccionado == "Otro": cultivo_seleccionado = st.text_input("Especifique:")
        dias_siembra = st.number_input("📅 Días desde la siembra", min_value=0, value=30)
    with c2:
        col_val, col_uni = st.columns([1.5, 1])
        with col_val: area_terreno = st.number_input("📏 Tamaño", min_value=0.1, value=1.0)
        with col_uni: unidad_area = st.selectbox("Unidad", ["Hectáreas", "m²"])
        tipo_riego = st.selectbox("💧 Tipo de Riego", ["Secano", "Goteo", "Aspersión", "Gravedad", "Río"])
    with c3:
        archivo_terreno = st.file_uploader("🗺️ Adjuntar polígono (Opcional)", type=['geojson', 'kml', 'json'])

    st.markdown("---")
    
    c4, c5 = st.columns(2)
    with c4:
        parte_afectada = st.selectbox("🍂 Parte afectada", ["Hojas", "Tallo o Tronco", "Fruto o Espiga", "Raíz", "Toda la planta"])
        dias_sintomas = st.slider("⏱️ Días con síntomas", 1, 30, 5)
        sintomas_texto = st.text_area("✍️ Describa el problema detalladamente:")
    with c5:
        foto_planta = st.file_uploader("📸 Subir foto clara del problema", type=['jpg', 'jpeg', 'png'])
        if foto_planta is not None: st.image(foto_planta, use_container_width=True)

    if st.button("🧠 Analizar Cultivo con IA", use_container_width=True):
        if not gemini_activo:
            st.error("⚠️ La API de Gemini no está configurada.")
        elif len(sintomas_texto) < 10 and not foto_planta:
            st.warning("⚠️ Describa el problema o suba una foto.")
        else:
            with st.spinner("🧠 El Sistema Experto está analizando..."):
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    prompt_experto = f"""
                    Eres un sistema experto en agronomía tropical y fitopatología.
                    CONTEXTO ACTUAL DEL LOTE:
                    - Cultivo: {cultivo_seleccionado}
                    - Edad del cultivo: {dias_siembra} días desde la siembra.
                    - Área: {area_terreno} {unidad_area}
                    - Altitud: {elevacion_actual} m.s.n.m.
                    - Riego: {tipo_riego}
                    - Clima reciente: {clima_texto}
                    SÍNTOMAS REPORTADOS POR EL AGRICULTOR:
                    - Órgano afectado: {parte_afectada}
                    - Días con síntomas: {dias_sintomas} días
                    - Descripción: {sintomas_texto}
                    
                    INSTRUCCIONES DE RAZONAMIENTO (Chain-of-Thought):
                    Redacta un breve "Análisis Técnico" relacionando edad, clima y síntomas.
                    Debes responder SIEMPRE en este formato exacto Markdown:
                    **🔬 ANÁLISIS TÉCNICO:**
                    [Razonamiento]
                    **🚨 DIAGNÓSTICO PRELIMINAR:**
                    [2-3 causas probables]
                    **📋 RECOMENDACIONES DE MANEJO:**
                    1. **Inmediatas (0-24h):** [Acciones]
                    2. **Corto plazo (1-7 días):** [Acciones]
                    3. **Preventivas:** [Acciones]
                    **⚠️ NIVEL DE URGENCIA:** [Bajo / Medio / Alto / Crítico]
                    """
                    paquete_analisis = [prompt_experto]
                    if foto_planta is not None:
                        imagen_pil = Image.open(foto_planta)
                        paquete_analisis.append(imagen_pil)
                        
                    respuesta = model.generate_content(paquete_analisis)
                    st.success("✅ Diagnóstico Completado")
                    st.markdown("---")
                    st.write(respuesta.text)
                except Exception as e:
                    st.error(f"❌ Error de IA: {e}")
