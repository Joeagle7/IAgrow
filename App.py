import streamlit as st
import pandas as pd
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import requests
from streamlit_geolocation import streamlit_geolocation
import plotly.express as px
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
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    
    div[role="radiogroup"] {
        display: flex;
        flex-direction: row;
        gap: 15px;
        background-color: transparent;
        justify-content: flex-start;
        align-items: center;
        border-bottom: 2px solid #e0e0e0;
        padding-bottom: 0px;
    }
    
    div[role="radiogroup"] > label {
        background-color: transparent !important;
        border: none !important;
        padding: 10px 20px !important;
        color: #555555 !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        cursor: pointer;
        border-radius: 5px 5px 0px 0px !important;
        border-bottom: 4px solid transparent !important;
        transition: all 0.3s ease;
        margin-bottom: -2px;
    }
    
    div[role="radiogroup"] > label > div:first-child {
        display: none; 
    }
    
    div[role="radiogroup"] > label:hover {
        color: #00796B !important;
        background-color: #f1f8e9 !important;
    }
    
    div[role="radiogroup"] > label:has(input:checked) {
        background-color: #004D40 !important; 
        color: #ffffff !important;           
        border-bottom: 4px solid #00E676 !important; 
        font-weight: 700 !important;
    }
    
    .stMetric { 
        background: #ffffff; 
        border-radius: 8px; 
        padding: 15px; 
        border-left: 5px solid #009688;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    .metric-caption {
        font-size: 0.85rem;
        color: #666666;
        margin-top: -10px;
        padding-left: 15px;
    }
</style>
""", unsafe_allow_html=True)

c_logo, c_menu = st.columns([2, 8])

with c_logo:
    st.markdown("<h2 style='color: #2E7D32; margin-top: 0;'>🌿 AgroIA</h2>", unsafe_allow_html=True)

with c_menu:
    opcion_menu = st.radio(
        "Navegación Principal", 
        ["Mapa", "Meteorología", "Suelo", "Estado de la Planta", "Satélite", "Diagnóstico IA"],
        horizontal=True,
        label_visibility="collapsed"
    )
st.markdown("<br>", unsafe_allow_html=True) 

# --- FUNCIONES AUXILIARES Y APIs ---
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

def obtener_datos_suelo_copernicus(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=soil_temperature_0_to_7cm,soil_temperature_7_to_28cm,soil_temperature_28_to_100cm,soil_temperature_100_to_255cm,soil_moisture_0_to_7cm,soil_moisture_7_to_28cm,soil_moisture_28_to_100cm,soil_moisture_100_to_255cm&models=ecmwf_ifs&timezone=America/Guayaquil"
    try: 
        respuesta = requests.get(url, timeout=10)
        if respuesta.status_code == 200:
            data = respuesta.json()
            if 'hourly' in data and 'time' in data['hourly']:
                tiempos = data['hourly']['time']
                humedad_sup = data['hourly'].get('soil_moisture_0_to_7cm', [])
                
                idx_valido = 0
                for i, val in enumerate(humedad_sup):
                    if val is not None:
                        idx_valido = i
                        break
                
                resultado_limpio = {}
                for key, values in data['hourly'].items():
                    if isinstance(values, list) and len(values) > idx_valido:
                        resultado_limpio[key] = values[idx_valido]
                        
                resultado_limpio['timestamp_extraido'] = tiempos[idx_valido]
                return resultado_limpio
        return None
    except: return None

def obtener_datos_nasa_power(lat, lon, start_date, end_date):
    url = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=ALLSKY_SFC_SW_DWN,PRECTOTCORR&community=AG&longitude={lon}&latitude={lat}&start={start_date}&end={end_date}&format=JSON"
    try:
        respuesta = requests.get(url, timeout=15)
        if respuesta.status_code == 200:
            datos = respuesta.json()
            if 'properties' in datos and 'parameter' in datos['properties']:
                df = pd.DataFrame(datos['properties']['parameter'])
                if not df.empty:
                    df.index = pd.to_datetime(df.index, format='%Y%m%d')
                    return df
        return None
    except:
        return None

def evaluar_potencial_crecimiento(lat, lon):
    end_date = (datetime.today() - timedelta(days=7)).strftime('%Y%m%d')
    start_date = (datetime.today() - timedelta(days=14)).strftime('%Y%m%d')
    
    df_nasa = obtener_datos_nasa_power(lat, lon, start_date, end_date)
    datos_suelo = obtener_datos_suelo_copernicus(lat, lon)
    
    if df_nasa is None or df_nasa.empty or datos_suelo is None:
        return None
        
    humedad_raiz = datos_suelo.get('soil_moisture_28_to_100cm', 0.0)
    if humedad_raiz is None: 
        humedad_raiz = 0.0
        
    radiacion_promedio = df_nasa['ALLSKY_SFC_SW_DWN'].mean() if 'ALLSKY_SFC_SW_DWN' in df_nasa else 0.0
    lluvia_acumulada = df_nasa['PRECTOTCORR'].sum() if 'PRECTOTCORR' in df_nasa else 0.0
    
    if radiacion_promedio > 15 and humedad_raiz > 0.25:
        estado = "🟢 Óptimo"
        mensaje = "Alta energía solar respaldada por excelente reserva de agua profunda. El cultivo está en condiciones ideales."
    elif radiacion_promedio > 15 and humedad_raiz < 0.15:
        estado = "🔴 Alerta Crítica (Estrés Termo-Hídrico)"
        mensaje = "Alta radiación solar pero el acuífero radicular está severamente agotado. Riesgo inminente de marchitez permanente."
    elif radiacion_promedio <= 15 and humedad_raiz > 0.30:
        estado = "🟡 Alerta Fúngica"
        mensaje = "Baja radiación solar y suelo saturado de agua. Las raíces corren riesgo de asfixia y proliferación de hongos."
    else:
        estado = "🔵 Moderado"
        mensaje = "Condiciones de crecimiento estándar. Continúe con sus prácticas de manejo habituales."
        
    return {
        "estado": estado,
        "mensaje": mensaje,
        "radiacion": round(radiacion_promedio, 2),
        "humedad": humedad_raiz,
        "lluvia": round(lluvia_acumulada, 2)
    }

# NUEVA FUNCIÓN: CÁLCULO DE ÁREA DE POLÍGONO EN HECTÁREAS (GEOMETRÍA ESFÉRICA)
def calcular_area_hectareas(coordenadas):
    """Calcula el área de un polígono en la superficie terrestre usando trigonometría esférica."""
    if not coordenadas or len(coordenadas) < 3:
        return 0.0
    radio_tierra = 6378137.0 # metros
    area = 0.0
    for i in range(len(coordenadas) - 1):
        lon1, lat1 = math.radians(coordenadas[i][0]), math.radians(coordenadas[i][1])
        lon2, lat2 = math.radians(coordenadas[i+1][0]), math.radians(coordenadas[i+1][1])
        area += (lon2 - lon1) * (2.0 + math.sin(lat1) + math.sin(lat2))
    area = abs(area * radio_tierra * radio_tierra / 2.0)
    return area / 10000.0 # Conversión de m² a Hectáreas

# --- 3. DESARROLLO DE LAS PÁGINAS ---

if opcion_menu == "Mapa":
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

elif opcion_menu == "Meteorología":
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

elif opcion_menu == "Suelo":
    st.subheader(f"🌍 Perfil Físico del Suelo (ERA5-Land: Copernicus)")
    st.info("Modelo Termodinámico e Hidrológico Asimilado. Representa el volumen de agua pura contenida en la matriz del suelo y su temperatura.")
    
    datos_suelo = obtener_datos_suelo_copernicus(st.session_state.lat, st.session_state.lon)
    
    if datos_suelo:
        ts = datos_suelo.get('timestamp_extraido')
        if ts:
            dt_obj = datetime.strptime(ts, "%Y-%m-%dT%H:%M")
            fecha_formateada = dt_obj.strftime("%d de %B de %Y a las %H:%M")
            st.success(f"⏱️ **Lectura Satelital Procesada:** Los datos corresponden al **{fecha_formateada}**.")
            
        st.markdown("### 💧 Humedad Volumétrica del Suelo (m³/m³)")
        ch1, ch2, ch3, ch4 = st.columns(4)
        
        m_0_7 = datos_suelo.get('soil_moisture_0_to_7cm')
        m_7_28 = datos_suelo.get('soil_moisture_7_to_28cm')
        m_28_100 = datos_suelo.get('soil_moisture_28_to_100cm')
        m_100_255 = datos_suelo.get('soil_moisture_100_to_255cm')
        
        ch1.metric("0 - 7 cm (Siembra)", f"{m_0_7} m³" if m_0_7 is not None else "N/D")
        ch2.metric("7 - 28 cm (Raíz Corta)", f"{m_7_28} m³" if m_7_28 is not None else "N/D")
        ch3.metric("28 - 100 cm (Raíz Profunda)", f"{m_28_100} m³" if m_28_100 is not None else "N/D")
        ch4.metric("100 - 289 cm (Acuífero)", f"{m_100_255} m³" if m_100_255 is not None else "N/D")
        
        st.markdown("---")
        st.markdown("### 🌡️ Temperatura del Perfil del Suelo (°C)")
        ct1, ct2, ct3, ct4 = st.columns(4)
        
        t_0_7 = datos_suelo.get('soil_temperature_0_to_7cm')
        t_7_28 = datos_suelo.get('soil_temperature_7_to_28cm')
        t_28_100 = datos_suelo.get('soil_temperature_28_to_100cm')
        t_100_255 = datos_suelo.get('soil_temperature_100_to_255cm')
        
        ct1.metric("0 - 7 cm (Superficie)", f"{t_0_7} °C" if t_0_7 is not None else "N/D")
        ct2.metric("7 - 28 cm (Zona Fúngica)", f"{t_7_28} °C" if t_7_28 is not None else "N/D")
        ct3.metric("28 - 100 cm", f"{t_28_100} °C" if t_28_100 is not None else "N/D")
        ct4.metric("100 - 289 cm", f"{t_100_255} °C" if t_100_255 is not None else "N/D")
    else:
        st.error("❌ Error de comunicación con los servidores satelitales. Asegúrese de ingresar coordenadas válidas.")

elif opcion_menu == "Estado de la Planta":
    st.subheader("⚡ Potencial de Crecimiento y Estado Termo-Hídrico")
    st.info("Algoritmo de Integración Espacial: Cruza la energía solar acumulada (NASA) con las reservas de agua subterránea (Copernicus) para detectar estrés vegetativo invisible.")
    
    with st.spinner("Analizando matrices satelitales conjuntas (NASA POWER + Copernicus)..."):
        resultado_sinergia = evaluar_potencial_crecimiento(st.session_state.lat, st.session_state.lon)
        
    if resultado_sinergia:
        st.markdown(f"### Diagnóstico del Lote: {resultado_sinergia['estado']}")
        st.write(f"**Análisis:** {resultado_sinergia['mensaje']}")
        
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("☀️ Energía PAR (NASA)", f"{resultado_sinergia['radiacion']} MJ/m²/día")
            st.markdown('<div class="metric-caption">Promedio de Radiación Solar (últimos 7 días)</div>', unsafe_allow_html=True)
        with c2:
            st.metric("💧 Reserva Profunda (Copernicus)", f"{resultado_sinergia['humedad']} m³/m³")
            st.markdown('<div class="metric-caption">Humedad en zona radicular profunda (28-100 cm)</div>', unsafe_allow_html=True)
        with c3:
            st.metric("🌧️ Lluvia Acumulada (NASA)", f"{resultado_sinergia['lluvia']} mm")
            st.markdown('<div class="metric-caption">Precipitación total acumulada (últimos 7 días)</div>', unsafe_allow_html=True)
    else:
        st.error("❌ Error de comunicación con los servidores espaciales. Verifique las coordenadas.")

elif opcion_menu == "Satélite":
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

# NUEVA SECCIÓN DE DIAGNÓSTICO IA (CON MAPA DE POLÍGONOS)
elif opcion_menu == "Diagnóstico IA":
    st.subheader("🤖 Diagnóstico Fitosanitario y Dosificación (IA)")
    st.warning("**⚠️ Aviso Legal:** Los resultados son probabilísticos. Verifique con un agrónomo.")
    
    elevacion_actual = obtener_elevacion(st.session_state.lat, st.session_state.lon)
    clima_actual = obtener_datos_clima(st.session_state.lat, st.session_state.lon)
    clima_texto = "No disponible"
    if clima_actual and 'current_weather' in clima_actual:
        clima_texto = f"{clima_actual['current_weather']['temperature']}°C, Humedad {clima_actual['hourly']['relativehumidity_2m'][0]}%"
        
    st.success(f"📍 **Contexto Extraído:** Altitud: {elevacion_actual} m.s.n.m. | 🌤️ **Clima Reciente:** {clima_texto}")
    st.markdown("---")
    
    # PASO 1: IDENTIFICACIÓN DEL LOTE
    st.markdown("### 1. Perfil del Lote")
    c_lote, c_cultivo, c_dias, c_riego = st.columns(4)
    with c_lote:
        nombre_lote = st.text_input("Nombre del Lote:", placeholder="Ej: Lote del Río", help="Asignar un nombre le permitirá llevar un registro histórico de sus tratamientos futuros.")
    with c_cultivo:
        cultivo_seleccionado = st.selectbox("Cultivo:", ["Cacao", "Banano", "Arroz", "Maíz", "Otro"])
        if cultivo_seleccionado == "Otro": cultivo_seleccionado = st.text_input("Especifique:")
    with c_dias:
        dias_siembra = st.number_input("Días desde siembra:", min_value=0, value=30)
    with c_riego:
        tipo_riego = st.selectbox("Tipo de Riego:", ["Secano", "Goteo", "Aspersión", "Gravedad"])

    # PASO 2: ESTACADO VIRTUAL (Trazado de Polígono)
    st.markdown("### 2. Delimitación del Terreno")
    st.write("Utilice la herramienta de polígono (**⬟**) en el mapa para marcar las esquinas de su lote. Al cerrar la figura, calcularemos el área automáticamente.")
    
    m_diag = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=16, max_zoom=20)
    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Satélite Base').add_to(m_diag)
    
    # Inyectamos la herramienta de dibujo (Solo permitimos Polígonos)
    Draw(export=False, position='topleft', draw_options={'polyline':False, 'rectangle':False, 'circle':False, 'circlemarker':False, 'marker':False, 'polygon':True}).add_to(m_diag)
    
    out_diag = st_folium(m_diag, width=1000, height=450, key="mapa_diagnostico")
    
    area_calculada = 0.0
    if out_diag and out_diag.get('all_drawings'):
        drawings = out_diag['all_drawings']
        if len(drawings) > 0:
            # Extraemos las coordenadas del último polígono dibujado
            coords = drawings[0]['geometry']['coordinates'][0]
            area_calculada = calcular_area_hectareas(coords)
            st.success(f"✅ Área calculada por satélite: **{area_calculada:.2f} Hectáreas**")
    
    if area_calculada == 0.0:
        st.info("ℹ️ Dibuje el perímetro de su parcela en el mapa para poder calcular la dosis exacta de sus tratamientos.")

    st.markdown("---")

    # PASO 3: SÍNTOMAS Y FOTOS
    st.markdown("### 3. Reporte Fitosanitario")
    c_sint1, c_sint2 = st.columns(2)
    with c_sint1:
        parte_afectada = st.selectbox("Órgano afectado:", ["Hojas", "Tallo o Tronco", "Fruto o Espiga", "Raíz", "Toda la planta"])
        dias_sintomas = st.slider("Días con síntomas:", 1, 30, 5)
        sintomas_texto = st.text_area("Describa el problema detalladamente:")
    with c_sint2:
        foto_planta = st.file_uploader("Subir evidencia fotográfica:", type=['jpg', 'jpeg', 'png'])
        if foto_planta is not None: st.image(foto_planta, use_container_width=True)

    # PASO 4: ANÁLISIS IA
    if st.button("🧠 Ejecutar Diagnóstico Inteligente", use_container_width=True):
        if not gemini_activo:
            st.error("⚠️ La API de Gemini no está configurada.")
        elif area_calculada == 0.0:
            st.warning("⚠️ Por favor, dibuje el perímetro de su lote en el mapa satelital arriba para poder calcular la dosis de los insumos.")
        elif len(sintomas_texto) < 5 and not foto_planta:
            st.warning("⚠️ Describa el problema o suba una foto.")
        else:
            with st.spinner("🧠 Procesando variables climáticas, espaciales y patológicas..."):
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    nombre_terreno = nombre_lote if nombre_lote else "Lote sin nombre"
                    
                    prompt_experto = f"""
                    Eres un sistema experto en agronomía tropical y fitopatología.
                    
                    CONTEXTO ESPACIAL Y CLIMÁTICO DEL LOTE:
                    - Nombre del Lote: {nombre_terreno}
                    - Área exacta calculada satelitalmente: {area_calculada:.2f} Hectáreas.
                    - Cultivo: {cultivo_seleccionado} ({dias_siembra} días desde la siembra).
                    - Riego: {tipo_riego}
                    - Clima reciente: {clima_texto}
                    
                    SÍNTOMAS REPORTADOS:
                    - Órgano afectado: {parte_afectada} ({dias_sintomas} días con síntomas).
                    - Descripción: {sintomas_texto}
                    
                    INSTRUCCIONES CRÍTICAS (Chain-of-Thought):
                    Debes responder SIEMPRE en este formato exacto Markdown:
                    **🔬 ANÁLISIS TÉCNICO:**
                    [Razonamiento conectando clima, edad y síntomas]
                    
                    **🚨 DIAGNÓSTICO PRELIMINAR:**
                    [2-3 causas probables]
                    
                    **📋 RECOMENDACIONES DE MANEJO Y DOSIFICACIÓN:**
                    1. **Tratamiento Inmediato:** [Acciones]
                    2. **Receta Agronómica (CRÍTICO):** Si recomiendas la aplicación de un producto agroquímico u orgánico, DEBES CALCULAR LA DOSIS TOTAL EXACTA para el área de {area_calculada:.2f} Hectáreas de este lote. (Ejemplo: Si la dosis es 2L/ha, indica "Aplique 4.68 L en total").
                    3. **Manejo Preventivo:** [Acciones agronómicas]
                    
                    **⚠️ NIVEL DE URGENCIA:** [Bajo / Medio / Alto / Crítico]
                    """
                    paquete_analisis = [prompt_experto]
                    if foto_planta is not None:
                        imagen_pil = Image.open(foto_planta)
                        paquete_analisis.append(imagen_pil)
                        
                    respuesta = model.generate_content(paquete_analisis)
                    st.success(f"✅ Diagnóstico Completado para: **{nombre_terreno}**")
                    st.markdown("---")
                    st.write(respuesta.text)
                except Exception as e:
                    st.error(f"❌ Error al procesar el modelo de IA: {e}")
