import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
from streamlit_geolocation import streamlit_geolocation
import plotly.express as px
import plotly.graph_objects as go
import ee
from datetime import datetime, timedelta
import google.generativeai as genai
from PIL import Image
import io
import math
import warnings
warnings.filterwarnings('ignore')

# --- 1. CONFIGURACIÓN Y ESTADO DE MEMORIA ---
st.set_page_config(page_title="AgroIA", page_icon="🌿", layout="wide")

if "lat" not in st.session_state: st.session_state.lat = -2.1962
if "lon" not in st.session_state: st.session_state.lon = -79.8862
if "temp_coords" not in st.session_state: st.session_state.temp_coords = []
if "nombre_lote_global" not in st.session_state: st.session_state.nombre_lote_global = ""

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

# --- 2. DISEÑO UI/UX CORPORATIVO ---
st.markdown("""
<style>
    .stApp { background-color: #000000; color: #ffffff; }
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    
    div[role="radiogroup"] {
        display: flex; flex-direction: row; gap: 15px; background-color: transparent;
        justify-content: flex-start; align-items: center; border-bottom: 2px solid #333333; padding-bottom: 0px;
    }
    div[role="radiogroup"] > label {
        background-color: transparent !important; border: none !important; padding: 10px 20px !important;
        color: #ffffff !important; font-weight: 600 !important; font-size: 16px !important;
        cursor: pointer; border-radius: 5px 5px 0px 0px !important; border-bottom: 4px solid transparent !important;
        transition: all 0.3s ease; margin-bottom: -2px;
    }
    div[role="radiogroup"] > label > div:first-child { display: none; }
    div[role="radiogroup"] > label:hover { color: #4DB6AC !important; background-color: #1a1a1a !important; }
    div[role="radiogroup"] > label:has(input:checked) {
        background-color: #004D40 !important; color: #ffffff !important;           
        border-bottom: 4px solid #00E676 !important; font-weight: 700 !important;
    }
    
    .stMetric { 
        background: #121212; border-radius: 8px; padding: 15px; 
        border-left: 5px solid #009688; box-shadow: 0 4px 6px rgba(0,0,0,0.3); color: #ffffff !important;
    }
    div[data-testid="stMetricValue"] > div { color: #ffffff !important; }
    div[data-testid="stMetricLabel"] > div { color: #aaaaaa !important; }
    
    .metric-caption { font-size: 0.90rem; color: #bbbbbb; margin-top: 5px; line-height: 1.4; }
    h1, h2, h3, h4, .stMarkdown { color: #ffffff; }
    
    iframe[title="streamlit_geolocation.streamlit_geolocation"] {
        background-color: transparent !important; color-scheme: dark; border-radius: 5px;
    }
    .time-label { font-size: 14px; font-weight: 600; color: #ffffff; margin-bottom: 5px; display: block; }
</style>
""", unsafe_allow_html=True)

c_logo, c_menu = st.columns([2, 8])
with c_logo: st.markdown("<h2 style='color: #2E7D32; margin-top: 0;'>🌿 AgroIA</h2>", unsafe_allow_html=True)
with c_menu:
    opcion_menu = st.radio(
        "Navegación Principal", 
        ["Mapa", "Meteorología", "Suelo", "Estado de la Planta", "Satélite", "Diagnóstico IA"],
        horizontal=True, label_visibility="collapsed"
    )
st.markdown("<br>", unsafe_allow_html=True) 

# --- FUNCIONES AUXILIARES ---
def grados_a_direccion(grados):
    arr = ["Norte", "Norte-Noreste", "Noreste", "Este-Noreste", "Este", "Este-Sureste", "Sureste", "Sur-Sureste", "Sur", "Sur-Suroeste", "Suroeste", "Oeste-Suroeste", "Oeste", "Oeste-Noroeste", "Noroeste", "Norte-Noroeste"]
    return arr[int((grados/22.5)+.5) % 16]

def obtener_elevacion(lat, lon):
    try: return requests.get(f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}").json()['elevation'][0]
    except: return "No disponible"
        
def obtener_datos_clima(lat, lon):
    try: return requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=temperature_2m,relativehumidity_2m,dewpoint_2m,precipitation_probability,pressure_msl,windspeed_10m,winddirection_10m,et0_fao_evapotranspiration&past_days=3&timezone=America/Guayaquil").json()
    except: return None

def obtener_datos_suelo_copernicus(lat, lon):
    try: 
        res = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=soil_temperature_0_to_7cm,soil_temperature_7_to_28cm,soil_temperature_28_to_100cm,soil_temperature_100_to_255cm,soil_moisture_0_to_7cm,soil_moisture_7_to_28cm,soil_moisture_28_to_100cm,soil_moisture_100_to_255cm&models=ecmwf_ifs&timezone=America/Guayaquil", timeout=10)
        if res.status_code == 200:
            data = res.json()
            if 'hourly' in data and 'time' in data['hourly']:
                idx_valido = next((i for i, v in enumerate(data['hourly'].get('soil_moisture_0_to_7cm', [])) if v is not None), 0)
                res_limpio = {k: v[idx_valido] for k, v in data['hourly'].items() if isinstance(v, list) and len(v) > idx_valido}
                res_limpio['timestamp_extraido'] = data['hourly']['time'][idx_valido]
                return res_limpio
        return None
    except: return None

def obtener_datos_nasa_power(lat, lon, start_date, end_date):
    try:
        res = requests.get(f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=ALLSKY_SFC_SW_DWN,PRECTOTCORR&community=AG&longitude={lon}&latitude={lat}&start={start_date}&end={end_date}&format=JSON", timeout=15)
        if res.status_code == 200:
            df = pd.DataFrame(res.json().get('properties', {}).get('parameter', {}))
            if not df.empty:
                df.index = pd.to_datetime(df.index, format='%Y%m%d')
                return df
        return None
    except: return None

def evaluar_potencial_crecimiento(lat, lon):
    end = (datetime.today() - timedelta(days=7)).strftime('%Y%m%d')
    start = (datetime.today() - timedelta(days=14)).strftime('%Y%m%d')
    df_nasa = obtener_datos_nasa_power(lat, lon, start, end)
    ds = obtener_datos_suelo_copernicus(lat, lon)
    
    if df_nasa is None or df_nasa.empty or ds is None: return None
        
    h_raiz = ds.get('soil_moisture_28_to_100cm', 0.0) or 0.0
    rad = df_nasa['ALLSKY_SFC_SW_DWN'].mean() if 'ALLSKY_SFC_SW_DWN' in df_nasa else 0.0
    lluvia = df_nasa['PRECTOTCORR'].sum() if 'PRECTOTCORR' in df_nasa else 0.0
    
    if rad > 15 and h_raiz > 0.25: e, m = "🟢 Óptimo", "Excelente reserva profunda."
    elif rad > 15 and h_raiz < 0.15: e, m = "🔴 Alerta Crítica (Estrés)", "Acuífero agotado. Riegue ya."
    elif rad <= 15 and h_raiz > 0.30: e, m = "🟡 Alerta Fúngica", "Poca luz y suelo saturado. Riesgo de hongos."
    else: e, m = "🔵 Moderado", "Condiciones estándar."
        
    return {"estado": e, "mensaje": m, "radiacion": round(rad, 2), "humedad": h_raiz, "lluvia": round(lluvia, 2)}

def calcular_area_hectareas(coordenadas):
    if not coordenadas or len(coordenadas) < 3: return 0.0
    area = 0.0
    tc = coordenadas[:]
    if tc[0] != tc[-1]: tc.append(tc[0])
    for i in range(len(tc) - 1):
        lon1, lat1 = math.radians(tc[i][0]), math.radians(tc[i][1])
        lon2, lat2 = math.radians(tc[i+1][0]), math.radians(tc[i+1][1])
        area += (lon2 - lon1) * (2.0 + math.sin(lat1) + math.sin(lat2))
    return abs(area * (6378137.0**2) / 2.0) / 10000.0 

# --- 3. DESARROLLO DE LAS PÁGINAS ---

if opcion_menu == "Mapa":
    st.subheader("📍 Coordenadas de la Parcela")
    c_lat, c_lon, c_gps = st.columns([2, 2, 2])
    with c_lat: nuevo_lat = st.number_input("Latitud", value=st.session_state.lat, format="%.4f")
    with c_lon: nuevo_lon = st.number_input("Longitud", value=st.session_state.lon, format="%.4f")
    with c_gps:
        st.write("O GPS actual:")
        ubicacion_gps = streamlit_geolocation()
        if ubicacion_gps['latitude'] is not None and ubicacion_gps['longitude'] is not None:
            lat_ob = round(ubicacion_gps['latitude'], 4)
            lon_ob = round(ubicacion_gps['longitude'], 4)
            if lat_ob != st.session_state.lat or lon_ob != st.session_state.lon:
                st.session_state.lat, st.session_state.lon = lat_ob, lon_ob
                st.rerun()

    st.write("Haga **clic** sobre su parcela en el mapa para afinar la ubicación.")
    m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=14)
    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Satélite Base').add_to(m)
    folium.Marker([st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="green", icon="leaf")).add_to(m)
    output = st_folium(m, width="100%", height=450, key="mapa_principal", returned_objects=["last_clicked"])

    if output and output.get('last_clicked'):
        click_lat, click_lon = round(output['last_clicked']['lat'], 4), round(output['last_clicked']['lng'], 4)
        if click_lat != st.session_state.lat or click_lon != st.session_state.lon:
            st.session_state.lat, st.session_state.lon = click_lat, click_lon
            st.rerun()

elif opcion_menu == "Meteorología":
    st.subheader(f"🌤️ Pronóstico Agrometeorológico ({st.session_state.lat}, {st.session_state.lon})")
    json_clima = obtener_datos_clima(st.session_state.lat, st.session_state.lon)
    if json_clima and 'hourly' in json_clima:
        cur = json_clima['current_weather']
        st.markdown(f"**Condiciones en superficie:** Viento hacia el **{grados_a_direccion(cur['winddirection'])}** a {cur['windspeed']} km/h")
        
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
        
        st.markdown("<br>", unsafe_allow_html=True)
        fig_et0 = go.Figure()
        fig_et0.add_trace(go.Scatter(
            x=df_hourly['Fecha_Hora'], y=df_hourly['Evapotranspiración (mm)'], fill='tozeroy', mode='lines',
            line=dict(color='#FF5722', width=3), fillcolor='rgba(255, 87, 34, 0.3)', name='ET0'
        ))
        fig_et0.update_layout(title="Demanda Hídrica y Estrés Atmosférico (Evapotranspiración FAO)", template="plotly_dark", xaxis_title="", yaxis_title="Evapotranspiración (mm)", margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_et0, width="stretch", config={'displaylogo': False, 'locale': 'es'})
        st.markdown("<div class='metric-caption'>Este gráfico de área ilustra la cantidad de agua que pierde su cultivo por hora. <b>Picos altos indican un estrés hídrico severo</b> inducido por el ambiente, alertando la necesidad de riego.</div><br>", unsafe_allow_html=True)

        fig_precip = px.bar(
            df_hourly, x='Fecha_Hora', y='Prob_Lluvia (%)', color='Prob_Lluvia (%)',
            color_continuous_scale=['#E1F5FE', '#0D47A1'], title="Certidumbre y Probabilidad de Precipitación (%)", template="plotly_dark"
        )
        fig_precip.update_layout(xaxis_title="", margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_precip, width="stretch", config={'displaylogo': False, 'locale': 'es'})
        st.markdown("<div class='metric-caption'>Las barras muestran la certeza de que llueva. <b>Colores más oscuros y barras más altas indican una probabilidad casi absoluta</b>. Herramienta vital para evitar que la lluvia lave sus agroquímicos recién aplicados.</div>", unsafe_allow_html=True)

elif opcion_menu == "Suelo":
    st.subheader(f"🌍 Perfil Físico del Suelo (ERA5-Land: Copernicus)")
    st.info("Modelo Termodinámico e Hidrológico Asimilado. Representa el volumen de agua pura contenida en la matriz del suelo y su temperatura.")
    datos_suelo = obtener_datos_suelo_copernicus(st.session_state.lat, st.session_state.lon)
    
    if datos_suelo:
        ts = datos_suelo.get('timestamp_extraido')
        if ts:
            fecha_formateada = datetime.strptime(ts, "%Y-%m-%dT%H:%M").strftime("%d de %B de %Y a las %H:%M")
            st.success(f"⏱️ **Lectura Satelital Procesada:** Los datos corresponden al **{fecha_formateada}**.")
            
        st.markdown("### 💧 Humedad Volumétrica del Suelo (m³/m³)")
        ch1, ch2, ch3, ch4 = st.columns(4)
        ch1.metric("0 - 7 cm", f"{datos_suelo.get('soil_moisture_0_to_7cm')} m³" if datos_suelo.get('soil_moisture_0_to_7cm') is not None else "N/D")
        ch2.metric("7 - 28 cm", f"{datos_suelo.get('soil_moisture_7_to_28cm')} m³" if datos_suelo.get('soil_moisture_7_to_28cm') is not None else "N/D")
        ch3.metric("28 - 100 cm", f"{datos_suelo.get('soil_moisture_28_to_100cm')} m³" if datos_suelo.get('soil_moisture_28_to_100cm') is not None else "N/D")
        ch4.metric("100 - 289 cm", f"{datos_suelo.get('soil_moisture_100_to_255cm')} m³" if datos_suelo.get('soil_moisture_100_to_255cm') is not None else "N/D")
        
        st.markdown("---")
        st.markdown("### 🌡️ Temperatura del Perfil del Suelo (°C)")
        ct1, ct2, ct3, ct4 = st.columns(4)
        ct1.metric("0 - 7 cm", f"{datos_suelo.get('soil_temperature_0_to_7cm')} °C" if datos_suelo.get('soil_temperature_0_to_7cm') is not None else "N/D")
        ct2.metric("7 - 28 cm", f"{datos_suelo.get('soil_temperature_7_to_28cm')} °C" if datos_suelo.get('soil_temperature_7_to_28cm') is not None else "N/D")
        ct3.metric("28 - 100 cm", f"{datos_suelo.get('soil_temperature_28_to_100cm')} °C" if datos_suelo.get('soil_temperature_28_to_100cm') is not None else "N/D")
        ct4.metric("100 - 289 cm", f"{datos_suelo.get('soil_temperature_100_to_255cm')} °C" if datos_suelo.get('soil_temperature_100_to_255cm') is not None else "N/D")
    else:
        st.error("❌ Error de comunicación con los servidores satelitales. Asegúrese de ingresar coordenadas válidas continentales.")

elif opcion_menu == "Estado de la Planta":
    st.subheader("⚡ Potencial de Crecimiento y Estado Termo-Hídrico")
    st.info("Algoritmo de Integración Espacial: Cruza la energía solar acumulada (NASA) con las reservas de agua subterránea (Copernicus) para detectar estrés vegetativo invisible.")
    
    with st.spinner("Analizando matrices satelitales conjuntas (NASA POWER + Copernicus)..."):
        res_sinergia = evaluar_potencial_crecimiento(st.session_state.lat, st.session_state.lon)
        
    if res_sinergia:
        st.markdown(f"### Diagnóstico del Lote: {res_sinergia['estado']}")
        st.write(f"**Análisis:** {res_sinergia['mensaje']}")
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("☀️ Energía PAR (NASA)", f"{res_sinergia['radiacion']} MJ/m²/día")
            st.markdown('<div class="metric-caption">Promedio de Radiación Solar (últimos 7 días)</div>', unsafe_allow_html=True)
        with c2:
            st.metric("💧 Reserva Profunda", f"{res_sinergia['humedad']} m³/m³")
            st.markdown('<div class="metric-caption">Humedad en zona radicular profunda (28-100 cm) extraída de Copernicus</div>', unsafe_allow_html=True)
        with c3:
            st.metric("🌧️ Lluvia Acumulada", f"{res_sinergia['lluvia']} mm")
            st.markdown('<div class="metric-caption">Precipitación total acumulada en la última semana procesada por la NASA</div>', unsafe_allow_html=True)
    else:
        st.error("❌ Error de comunicación con los servidores espaciales. Verifique las coordenadas.")

elif opcion_menu == "Satélite":
    st.subheader(f"🛰️ Análisis Satelital de Salud Vegetal (NDVI)")
    if not gee_activo: st.error("⚠️ Error: Google Earth Engine no está inicializado.")
    else:
        with st.spinner("Procesando mosaico satelital libre de nubes..."):
            try:
                punto = ee.Geometry.Point([st.session_state.lon, st.session_state.lat])
                fecha_fin = datetime.today()
                fecha_inicio = fecha_fin - timedelta(days=90)
                def enmascarar_nubes(imagen):
                    qa = imagen.select('QA60') 
                    return imagen.updateMask(qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0)))
                
                coleccion = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(punto).filterDate(fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d')).map(enmascarar_nubes) 
                
                if coleccion.size().getInfo() == 0: st.warning("☁️ Cobertura nubosa total y permanente en este trimestre.")
                else:
                    st.info("🧩 **Mosaico Satelital:** Fusión matemática de los píxeles despejados en los últimos 90 días.")
                    ndvi = coleccion.median().normalizedDifference(['B8', 'B4']).rename('NDVI')
                    map_id_dict = ee.Image(ndvi).getMapId({'min': 0.1, 'max': 0.6, 'palette': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']})
                    
                    m_ndvi = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=15, max_zoom=20)
                    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Satélite Base').add_to(m_ndvi)
                    folium.TileLayer(tiles=map_id_dict['tile_fetcher'].url_format, attr='Google Earth Engine', overlay=True, opacity=0.7).add_to(m_ndvi)
                    folium.Marker([st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="red")).add_to(m_ndvi)
                    st_folium(m_ndvi, width="100%", height=450, key="mapa_ndvi")
            except Exception as e: st.error(f"❌ Error satelital: {e}")

# --- SECCIÓN DIAGNÓSTICO IA MEJORADA (Categorías y Tiempo Compuesto) ---
elif opcion_menu == "Diagnóstico IA":
    st.subheader("🤖 Diagnóstico Fitosanitario y Dosificación (Múltiples IA)")
    st.warning("**⚠️ Aviso Legal:** Sistema operado por Comité Agéntico. Verifique con un agrónomo.")
    
    # 1. PERFIL DEL LOTE (NUEVA CLASIFICACIÓN DE CULTIVOS)
    st.markdown("### 1. Perfil del Lote")
    
    # Diccionario de categorías y cultivos
    cultivos_dict = {
        "🌾 Granos y Cereales (Ciclo Corto)": ["Arroz", "Maíz Suave", "Maíz Duro", "Soya", "Trigo", "Avena"],
        "🍫 Perennes / Exportación (Larga Duración)": ["Cacao", "Banano", "Plátano", "Café", "Palma Aceitera", "Mango"],
        "🥔 Raíces y Tubérculos": ["Papa", "Yuca", "Camote", "Zanahoria"],
        "🍅 Hortícolas y Legumbres": ["Tomate", "Cebolla", "Pimiento", "Brócoli", "Lechuga", "Fréjol", "Arveja"],
        "Otro (Especifique)": ["Otro"]
    }
    
    c_cat, c_cultivo = st.columns(2)
    with c_cat:
        categoria_seleccionada = st.selectbox("Categoría de Cultivo:", list(cultivos_dict.keys()))
    with c_cultivo:
        cultivo_seleccionado = st.selectbox("Especifique el Cultivo:", cultivos_dict[categoria_seleccionada])
        if cultivo_seleccionado == "Otro": cultivo_seleccionado = st.text_input("Ingrese el nombre del cultivo:")

    # LÓGICA DE TIEMPO DINÁMICA (COMPUESTA)
    st.markdown("#### Cronología del Cultivo")
    es_perenne = categoria_seleccionada == "🍫 Perennes / Exportación (Larga Duración)"
    
    if es_perenne:
        st.info("🌳 Para cultivos perennes, indique la edad total de la planta y la fecha de la última intervención (poda/cosecha).")
        col_ed1, col_ed2, col_ed3 = st.columns(3)
        with col_ed1:
            edad_anios = st.number_input("Años:", min_value=0, value=3)
        with col_ed2:
            edad_meses = st.number_input("Meses:", min_value=0, max_value=11, value=0)
        with col_ed3:
            fecha_ultima_cosecha = st.date_input("Última Cosecha / Poda:", value=datetime.today() - timedelta(days=30))
        
        tiempo_planta_str = f"Planta adulta de {edad_anios} años y {edad_meses} meses. Última cosecha/poda hace {(datetime.today().date() - fecha_ultima_cosecha).days} días."
    else:
        st.info("🌱 Para cultivos de ciclo corto, indique la fecha exacta de siembra.")
        fecha_siembra = st.date_input("Fecha de Siembra:", value=datetime.today() - timedelta(days=45))
        dias_desde_siembra = (datetime.today().date() - fecha_siembra).days
        tiempo_planta_str = f"Cultivo de ciclo corto con {dias_desde_siembra} días desde la siembra."

    st.markdown("---")

    # 2. GPS Y DELIMITACIÓN
    st.markdown("### 2. Geolocalice y Delimite su Terreno")
    c_desc_gps, c_btn_gps = st.columns([4, 1])
    with c_desc_gps: st.write("Presione el botón para centrar el mapa. Luego marque las esquinas de su lote.")
    with c_btn_gps:
        ubicacion_gps = streamlit_geolocation()
        if ubicacion_gps['latitude'] is not None and ubicacion_gps['longitude'] is not None:
            lat_obtenida = round(ubicacion_gps['latitude'], 4)
            lon_obtenida = round(ubicacion_gps['longitude'], 4)
            if lat_obtenida != st.session_state.lat or lon_obtenida != st.session_state.lon:
                st.session_state.lat = lat_obtenida
                st.session_state.lon = lon_obtenida
                st.rerun()

    c_btn_marcar, c_btn_deshacer, c_btn_cerrar = st.columns(3)
    puntos_mapeo = st.session_state.temp_coords
    poligono_cerrado = False
    
    with c_btn_marcar:
        if st.button("📍 Marcar Esquina (GPS)"):
            puntos_mapeo.append([st.session_state.lon, st.session_state.lat])
            st.session_state.temp_coords = puntos_mapeo
            st.rerun()
    with c_btn_deshacer:
        if st.button("↩️ Deshacer Punto"):
            if puntos_mapeo:
                puntos_mapeo.pop()
                st.session_state.temp_coords = puntos_mapeo
                st.rerun()
    with c_btn_cerrar:
        if len(puntos_mapeo) >= 3:
            if st.button("✅ Cerrar Polígono"):
                puntos_mapeo.append(puntos_mapeo[0])
                st.session_state.temp_coords = puntos_mapeo
                st.rerun()
    
    m_diag = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=16, max_zoom=20)
    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Satélite Base').add_to(m_diag)
    
    if puntos_mapeo:
        for i, punto in enumerate(puntos_mapeo):
            folium.Marker([punto[1], punto[0]], icon=folium.DivIcon(html=f'<div style="font-size: 14pt; color: white; background-color: blue; border-radius: 50%; width: 25px; height: 25px; text-align: center; font-weight: bold; border: 2px solid white;">{i+1}</div>')).add_to(m_diag)
        coordenadas_linea = [[p[1], p[0]] for p in puntos_mapeo]
        if len(puntos_mapeo) > 1:
            if puntos_mapeo[0] == puntos_mapeo[-1]:
                folium.Polygon(locations=coordenadas_linea, color="#00E676", weight=3, fill=True, fill_color="#00E676", fill_opacity=0.3).add_to(m_diag)
                poligono_cerrado = True
            else:
                folium.PolyLine(locations=coordenadas_linea, color="#2196F3", weight=3, dash_array='5, 5').add_to(m_diag)
    
    st_folium(m_diag, width="100%", height=450, key="mapa_diag_puntos", returned_objects=[])
    
    area_calculada = 0.0
    if poligono_cerrado:
        area_calculada = calcular_area_hectareas(puntos_mapeo[:-1])
        st.success(f"✅ Superficie satelital: **{area_calculada:.2f} Hectáreas**")

    st.markdown("---")

    # 3. REPORTE FITOSANITARIO
    st.markdown("### 3. Reporte de Síntomas")
    
    elevacion_actual = obtener_elevacion(st.session_state.lat, st.session_state.lon)
    clima_actual = obtener_datos_clima(st.session_state.lat, st.session_state.lon)
    clima_texto = "No disponible"
    if clima_actual and 'current_weather' in clima_actual:
        clima_texto = f"{clima_actual['current_weather']['temperature']}°C, Humedad {clima_actual['hourly']['relativehumidity_2m'][0]}%"
    
    c_sint1, c_sint2 = st.columns(2)
    with c_sint1:
        nombre_lote_form = st.text_input("Asigne un nombre a este Lote:", value=st.session_state.nombre_lote_global, placeholder="Ej: Lote de la Loma")
        if nombre_lote_form: st.session_state.nombre_lote_global = nombre_lote_form
        
        parte_afectada = st.selectbox("🍂 Órgano visiblemente afectado:", ["Hojas", "Tallo o Tronco", "Fruto o Espiga", "Raíz", "Toda la planta"])
        
        # TIEMPO CON SÍNTOMAS (Compuesto para mayor precisión)
        st.markdown("<span class='time-label'>⏱️ Tiempo exacto de evolución del síntoma:</span>", unsafe_allow_html=True)
        col_sin1, col_sin2 = st.columns(2)
        with col_sin1: sint_num = st.number_input("Cantidad", min_value=1, value=5, label_visibility="collapsed")
        with col_sin2: sint_uni = st.selectbox("Unidad", ["Días", "Semanas", "Meses"], label_visibility="collapsed")
        tiempo_sintomas_str = f"{sint_num} {sint_uni}"
        
    with c_sint2:
        tipo_riego = st.selectbox("💧 Tipo de Riego:", ["Secano", "Goteo", "Aspersión", "Gravedad", "Río"])
        sintomas_texto = st.text_area("✍️ Describa el problema detalladamente:")
        foto_planta = st.file_uploader("📸 Subir foto clara del problema:", type=['jpg', 'jpeg', 'png'])
        if foto_planta is not None: st.image(foto_planta, use_container_width=True)

    if st.button("🧠 Ejecutar Comité de IA (Diagnóstico Multi-Agente)"):
        if not gemini_activo: st.error("⚠️ La API de Gemini no está configurada.")
        elif not poligono_cerrado: st.warning("⚠️ Por favor, delimite primero el perímetro de su lote en el mapa (Paso 2).")
        elif len(sintomas_texto) < 5 and not foto_planta: st.warning("⚠️ Describa el problema o suba una foto.")
        else:
            with st.spinner("🧠 Inicializando flujo multi-agente. El Fisiólogo (Gemini) está analizando la fenología y clima..."):
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    nombre_terreno = st.session_state.nombre_lote_global if st.session_state.nombre_lote_global else "Lote sin nombre"
                    
                    prompt_experto = f"""
                    Eres el 'Fisiólogo', un sistema experto en epidemiología y agronomía tropical.
                    
                    CONTEXTO ESPACIAL Y FENOLÓGICO:
                    - Área de la plantación: {area_calculada:.2f} Hectáreas.
                    - Estado del Cultivo: {tiempo_planta_str}
                    - Altitud: {elevacion_actual} m.s.n.m.
                    - Clima reciente: {clima_texto}
                    
                    SÍNTOMAS (CRONOLOGÍA EXACTA):
                    - Órgano afectado: {parte_afectada}
                    - Tiempo exacto de evolución del síntoma: {tiempo_sintomas_str}
                    - Descripción: {sintomas_texto}
                    
                    INSTRUCCIONES DE RAZONAMIENTO:
                    Considerando si la enfermedad ha evolucionado en días (agudo) o meses (crónico) y el estado fenológico de la planta, responde:
                    **🔬 ANÁLISIS TÉCNICO (El Fisiólogo):**
                    [Razonamiento conectando clima, tiempo de existencia y velocidad de avance del síntoma]
                    **🚨 DIAGNÓSTICO PRELIMINAR:**
                    [2-3 causas probables]
                    **📋 RECETA AGRONÓMICA (Dosis exacta requerida):**
                    Calcula la dosis total de producto químico/orgánico que se debe mezclar para fumigar las {area_calculada:.2f} Hectáreas de este lote.
                    """
                    paquete_analisis = [prompt_experto]
                    if foto_planta is not None:
                        imagen_pil = Image.open(foto_planta)
                        paquete_analisis.append(imagen_pil)
                        
                    respuesta = model.generate_content(paquete_analisis)
                    
                    st.success(f"✅ Diagnóstico Fisiológico Completado para: **{nombre_terreno}**")
                    st.markdown("---")
                    st.write(respuesta.text)
                except Exception as e:
                    st.error(f"❌ Error de IA: {e}")
