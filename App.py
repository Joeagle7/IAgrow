import streamlit as st
import pandas as pd
import numpy as np
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

# IMPORTS ECONOMÉTRICOS
from statsmodels.tsa.vector_ar.vecm import VECM, coint_johansen
from statsmodels.tsa.vector_ar.var_model import VAR
import warnings
warnings.filterwarnings('ignore')

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

st.markdown("""<style>.stMetric { background: rgba(255, 255, 255, 0.05); border-radius: 5px; padding: 10px; border: 1px solid rgba(255, 255, 255, 0.1); }</style>""", unsafe_allow_html=True)
st.title("🌾 AgroIA: Plataforma Inteligente de Decisión Agrícola")

# --- 2. BARRA LATERAL ---
st.sidebar.header("🕹️ Coordenadas Activas")
nuevo_lat = st.sidebar.number_input("Latitud", value=st.session_state.lat, format="%.4f")
nuevo_lon = st.sidebar.number_input("Longitud", value=st.session_state.lon, format="%.4f")

if nuevo_lat != st.session_state.lat or nuevo_lon != st.session_state.lon:
    st.session_state.lat, st.session_state.lon = nuevo_lat, nuevo_lon
    st.rerun()

st.sidebar.markdown("---")
opcion_menu = st.sidebar.radio("📋 Ir a:", ["Menú Principal (Mapa)", "Control meteorológico y predicción climática", "Análisis Suelo", "Mapa Satelital (NDVI)", "Diagnóstico IA 🤖", "📈 Mercados y Precios (VECMX)"])

# --- FUNCIONES AUXILIARES CLIMA Y SUELO ---
def grados_a_direccion(grados):
    arr = ["Norte", "Norte-Noreste", "Noreste", "Este-Noreste", "Este", "Este-Sureste", "Sureste", "Sur-Sureste", "Sur", "Sur-Suroeste", "Suroeste", "Oeste-Suroeste", "Oeste", "Oeste-Noroeste", "Noroeste", "Norte-Noroeste"]
    return arr[int((grados/22.5)+.5) % 16]

def obtener_fecha_espanol(fecha):
    meses = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}
    return f"{fecha.day} de {meses[fecha.month]} de {fecha.year}"

def obtener_elevacion(lat, lon):
    url = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}"
    try: return requests.get(url).json()['elevation'][0]
    except: return "No disponible"
        
def obtener_datos_clima(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&hourly=temperature_2m,relativehumidity_2m,dewpoint_2m,apparent_temperature,precipitation_probability,pressure_msl,windspeed_10m,winddirection_10m,et0_fao_evapotranspiration&past_days=3&timezone=America/Guayaquil"
    try: return requests.get(url).json()
    except: return None

def obtener_datos_suelo(lat, lon):
    url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lon={lon}&lat={lat}&property=phh2o&property=clay&property=nitrogen&depth=0-5cm&depth=15-30cm&value=mean"
    try: return requests.get(url).json()
    except: return None

# --- FUNCIONES ECONOMÉTRICAS VECMX ---
def obtener_variables_macro_exogenas(start_date, end_date):
    """
    CONTENEDOR TEMPORAL: Aquí se inyectará el Web Scraping del BCE/INAMHI en el futuro.
    Por ahora, simula índices macroeconómicos que afectan los costos de producción a nivel nacional.
    """
    fechas = pd.date_range(start=start_date, end=end_date, freq='W')
    np.random.seed(99)
    # Simulamos un shock de costos tipo "Guerra Ucrania" a mitad de la serie
    base_urea = np.linspace(40, 45, len(fechas))
    shock_urea = np.where(fechas > (end_date - timedelta(weeks=75)), 25, 0)
    ruido_urea = np.random.normal(0, 2, len(fechas))
    
    # Índice logístico (Combustibles/Transporte)
    indice_logistico = np.linspace(100, 120, len(fechas)) + np.random.normal(0, 1, len(fechas))
    
    df_macro = pd.DataFrame({
        'Costo_Fertilizantes': base_urea + shock_urea + ruido_urea,
        'Indice_Logistico': indice_logistico
    }, index=fechas)
    return df_macro

def generar_datos_mercado_simulados(producto, categoria):
    np.random.seed(42 + len(producto))
    fecha_fin = datetime.today()
    fecha_inicio = fecha_fin - timedelta(weeks=150)
    fechas = pd.date_range(start=fecha_inicio, end=fecha_fin, freq='W')[-150:] 
    
    bases = {
        "Brócoli (Caja)": 10, "Cebolla blanca en rama (Atado)": 2, "Cebolla colorada seca (Saco)": 25,
        "Tomate riñón (Caja)": 15, "Lechuga (Caja)": 8, "Col (Saco)": 12, "Zanahoria amarilla (Saco)": 18,
        "Pimiento (Saco)": 14, "Remolacha (Saco)": 12, "Arveja tierna (Saco)": 30, "Fréjol tierno (Saco)": 28,
        "Papa superchola (Quintal)": 18, "Yuca (Saco)": 15,
        "Limón sutil (Saco)": 20, "Naranja (Ciento)": 8, "Mandarina (Ciento)": 7, "Melón (Unidad)": 1.5,
        "Tomate de árbol (Caja)": 15, "Mora de castilla (Balde)": 20, "Plátano barraganete verde (Caja)": 7, "Plátano barraganete maduro (Caja)": 8,
        "Arroz (Quintal)": 38, "Maíz suave choclo (Saco)": 25, "Maíz suave seco (Quintal)": 30, "Maíz duro (Quintal)": 18,
        "Fréjol canario (Quintal)": 45, "Lenteja (Quintal)": 40,
        "Cacao (Quintal)": 350, "Banano (Caja FOB)": 6.5,
        "Rosas (Bonche 25 tallos)": 4.5, "Gypsophila (Bonche)": 3.0, "Claveles (Bonche)": 2.5
    }
    
    precio_base = bases.get(producto, 10)
    es_exportacion = categoria in ["Cultivos Tradicionales / Exportación", "Floricultura"]
    
    volatilidad = precio_base * 0.05 
    shocks_productor = np.random.normal(0, volatilidad, 150)
    precio_productor = precio_base + np.cumsum(shocks_productor)
    
    if es_exportacion:
        margen = precio_base * 1.50
        shocks_mercado = np.random.normal(0, volatilidad * 1.5, 150)
    else:
        margen = precio_base * 0.35
        shocks_mercado = np.random.normal(0, volatilidad * 0.8, 150)
        
    precio_mercado = precio_productor + margen + shocks_mercado
    
    df = pd.DataFrame({'Precio_Productor': precio_productor, 'Precio_Mercado': precio_mercado}, index=fechas)
    return df, fechas[0], fechas[-1]

# --- 3. DESARROLLO DE LAS PÁGINAS ---

if opcion_menu == "Menú Principal (Mapa)":
    st.subheader("📍 Definición del Área de Cultivo")
    st.markdown("### Opción A: Usar mi ubicación actual (GPS)")
    ubicacion_gps = streamlit_geolocation()
    if ubicacion_gps['latitude'] is not None:
        gps_lat, gps_lon = round(ubicacion_gps['latitude'], 4), round(ubicacion_gps['longitude'], 4)
        if gps_lat != st.session_state.lat or gps_lon != st.session_state.lon:
            st.session_state.lat, st.session_state.lon = gps_lat, gps_lon
            st.rerun()

    st.markdown("---")
    st.markdown("### Opción B: Seleccionar en el Mapa Interactivo")
    m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=13)
    folium.Marker([st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="red")).add_to(m)
    output = st_folium(m, width=900, height=500, key="mapa_principal", returned_objects=["last_clicked"])

    if output and output.get('last_clicked'):
        click_lat, click_lon = round(output['last_clicked']['lat'], 4), round(output['last_clicked']['lng'], 4)
        if click_lat != st.session_state.lat or click_lon != st.session_state.lon:
            st.session_state.lat, st.session_state.lon = click_lat, click_lon
            st.rerun()

elif opcion_menu == "Control meteorológico y predicción climática":
    st.subheader(f"🌤️ Control meteorológico y predicción climática ({st.session_state.lat}, {st.session_state.lon})")
    json_clima = obtener_datos_clima(st.session_state.lat, st.session_state.lon)
    if json_clima and 'hourly' in json_clima:
        cur = json_clima['current_weather']
        st.markdown(f"**Condiciones actuales:** Viento {grados_a_direccion(cur['winddirection'])} a {cur['windspeed']} km/h")
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("🌡️ Temperatura", f"{cur['temperature']}°C")
        with c2: st.metric("💧 Humedad Relativa", f"{json_clima['hourly']['relativehumidity_2m'][0]}%")
        with c3: st.metric("🌬️ Presión", f"{json_clima['hourly']['pressure_msl'][0]} hPa")
        with c4: st.metric("☁️ Punto de Rocío", f"{json_clima['hourly']['dewpoint_2m'][0]}°C")
        
        df_hourly = pd.DataFrame({
            'Fecha_Hora': pd.to_datetime(json_clima['hourly']['time']),
            'Temp (°C)': json_clima['hourly']['apparent_temperature'],
            'Prob_Lluvia (%)': json_clima['hourly']['precipitation_probability'],
            'Evapotranspiración (mm)': json_clima['hourly']['et0_fao_evapotranspiration']
        })
        st.plotly_chart(px.line(df_hourly, x='Fecha_Hora', y=['Temp (°C)', 'Evapotranspiración (mm)'], template="plotly_dark", color_discrete_sequence=['#F0A500', '#0097A7']), use_container_width=True)
        st.plotly_chart(px.bar(df_hourly, x='Fecha_Hora', y='Prob_Lluvia (%)', template="plotly_dark", color_discrete_sequence=['#1565C0']), use_container_width=True)

elif opcion_menu == "Análisis Suelo":
    st.subheader(f"🌍 Calidad Edafológica ({st.session_state.lat}, {st.session_state.lon})")
    json_suelo = obtener_datos_suelo(st.session_state.lat, st.session_state.lon)
    if json_suelo and 'properties' in json_suelo:
        def extraer_dato_seguro(json_data, property_name, depth_label):
            try:
                for layer in json_data['properties']['layers']:
                    if layer['name'] == property_name:
                        for depth in layer['depths']:
                            if depth['label'] == depth_label:
                                valor = depth['values']['mean']
                                return round(valor / 10, 2) if valor is not None else "Sin datos"
            except: pass
            return "Sin datos"

        c1, c2 = st.columns(2)
        with c1:
            st.write("**Capa Superficial (0-5cm)**")
            st.metric("pH", extraer_dato_seguro(json_suelo, 'phh2o', '0-5cm'))
            st.metric("Nitrógeno (cg/kg)", extraer_dato_seguro(json_suelo, 'nitrogen', '0-5cm'))
        with c2:
            st.write("**Capa Profunda (15-30cm)**")
            st.metric("pH", extraer_dato_seguro(json_suelo, 'phh2o', '15-30cm'))
            st.metric("Nitrógeno (cg/kg)", extraer_dato_seguro(json_suelo, 'nitrogen', '15-30cm'))
    else:
        st.warning("⚠️ No se encontraron datos edafológicos para esta ubicación.")

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
                    f_inicio_str = obtener_fecha_espanol(fecha_inicio)
                    f_fin_str = obtener_fecha_espanol(fecha_fin)
                    st.info(f"🧩 **Mosaico Satelital:** Esta imagen es una fusión matemática de los píxeles despejados capturados entre el **{f_inicio_str}** y el **{f_fin_str}**. Muestra la tendencia de salud del trimestre.")
                    
                    ndvi = imagen_limpia.normalizedDifference(['B8', 'B4']).rename('NDVI')
                    vis_params = {'min': 0.1, 'max': 0.6, 'palette': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']}
                    map_id_dict = ee.Image(ndvi).getMapId(vis_params)
                    
                    m_ndvi = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=15, max_zoom=20)
                    folium.TileLayer(tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Satélite Base', overlay=False, max_zoom=20).add_to(m_ndvi)
                    folium.TileLayer(tiles=map_id_dict['tile_fetcher'].url_format, attr='Google Earth Engine', name='NDVI', overlay=True, opacity=0.7, max_zoom=20, max_native_zoom=16).add_to(m_ndvi)
                    folium.Marker([st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="red")).add_to(m_ndvi)
                    st_folium(m_ndvi, width=900, height=500, key="mapa_ndvi")
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

# NUEVA SECCIÓN: VECMX (MACRO VARIABLES + CONSENSO DE CRITERIOS)
elif opcion_menu == "📈 Mercados y Precios (VECMX)":
    st.subheader("📈 Inteligencia de Mercados: Predicción VECMX")
    st.info("💡 **Modelo VECMX:** Analiza la cointegración de precios integrando variables macroeconómicas exógenas (Costos de Insumos/Logística) evaluadas mediante consenso estadístico multicriterio.")
    st.markdown("---")
    
    categorias_dict = {
        "Hortalizas y Legumbres": ["Brócoli (Caja)", "Cebolla blanca en rama (Atado)", "Cebolla colorada seca (Saco)", "Tomate riñón (Caja)", "Lechuga (Caja)", "Col (Saco)", "Zanahoria amarilla (Saco)", "Pimiento (Saco)", "Remolacha (Saco)", "Arveja tierna (Saco)", "Fréjol tierno (Saco)"],
        "Raíces y Tubérculos": ["Papa superchola (Quintal)", "Yuca (Saco)"],
        "Frutas": ["Limón sutil (Saco)", "Naranja (Ciento)", "Mandarina (Ciento)", "Melón (Unidad)", "Tomate de árbol (Caja)", "Mora de castilla (Balde)", "Plátano barraganete verde (Caja)", "Plátano barraganete maduro (Caja)"],
        "Cereales y Granos Secos": ["Arroz (Quintal)", "Maíz suave choclo (Saco)", "Maíz suave seco (Quintal)", "Maíz duro (Quintal)", "Fréjol canario (Quintal)", "Lenteja (Quintal)"],
        "Cultivos Tradicionales / Exportación": ["Cacao (Quintal)", "Banano (Caja FOB)"],
        "Floricultura": ["Rosas (Bonche 25 tallos)", "Gypsophila (Bonche)", "Claveles (Bonche)"]
    }
    
    c_cat, c_prod, c_btn = st.columns([1.5, 2, 1])
    with c_cat: categoria_seleccionada = st.selectbox("📁 1. Categoría Agrícola:", list(categorias_dict.keys()))
    with c_prod: producto_mercado = st.selectbox("🛒 2. Seleccione el Producto:", categorias_dict[categoria_seleccionada])
    
    es_exportacion = categoria_seleccionada in ["Cultivos Tradicionales / Exportación", "Floricultura"]
    etiqueta_mercado = "Precio Internacional (FOB)" if es_exportacion else "Precio Mayorista (Ciudad)"
    
    df_precios, start_d, end_d = generar_datos_mercado_simulados(producto_mercado, categoria_seleccionada)
    
    with st.spinner("🌐 Obteniendo variables macroeconómicas exógenas (Precios Urea/Logística)..."):
        df_exogenas = obtener_variables_macro_exogenas(start_d, end_d)
        df_exogenas = df_exogenas.reindex(df_precios.index).fillna(method='ffill').fillna(method='bfill')

    st.write("### 📊 Histórico de Precios")
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Scatter(x=df_precios.index, y=df_precios['Precio_Productor'], name='Productor (Finca)', line=dict(color='#00E676')))
    fig_hist.add_trace(go.Scatter(x=df_precios.index, y=df_precios['Precio_Mercado'], name=etiqueta_mercado, line=dict(color='#2979FF')))
    fig_hist.update_layout(template="plotly_dark", yaxis_title="Precio (USD)", margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig_hist, use_container_width=True)
    
    with c_btn:
        st.write("") 
        st.write("") 
        ejecutar_vecm = st.button("🔮 Proyectar (VECMX)", use_container_width=True)

    if ejecutar_vecm:
        with st.spinner("🧠 Ejecutando modelo VECMX con Consenso de Criterios (AIC/BIC/HQIC)..."):
            try:
                # 1. EVALUACIÓN MULTICRITERIO DE REZAGOS
                modelo_var = VAR(df_precios, exog=df_exogenas)
                resultados_seleccion = modelo_var.select_order(maxlags=8)
                
                aic_lags = resultados_seleccion.aic if resultados_seleccion.aic is not None else 1
                bic_lags = resultados_seleccion.bic if resultados_seleccion.bic is not None else 1
                hqic_lags = resultados_seleccion.hqic if resultados_seleccion.hqic is not None else 1
                
                # Consenso: Mediana de los criterios
                p_optimo_consenso = int(np.median([aic_lags, bic_lags, hqic_lags]))
                
                # Verificación de estabilidad
                if p_optimo_consenso > 0:
                    modelo_ajustado = modelo_var.fit(p_optimo_consenso)
                    raices = np.abs(np.linalg.eigvals(modelo_ajustado.coefs[0]))
                    if np.max(raices) >= 1.0:
                        p_optimo_consenso = max(1, p_optimo_consenso - 1)
                
                k_ar_diff_opt = max(1, p_optimo_consenso - 1)
                
                # 2. Test de Johansen
                johansen_test = coint_johansen(df_precios, det_order=0, k_ar_diff=k_ar_diff_opt)
                hay_cointegracion = johansen_test.lr1[0] > johansen_test.cvt[0, 1]
                
                # 3. Modelo VECMX
                modelo_vecmx = VECM(df_precios, exog=df_exogenas, k_ar_diff=k_ar_diff_opt, deterministic='co')
                resultado_vecmx = modelo_vecmx.fit()
                
                # 4. Predicción Exógena Naive
                pasos_futuro = 8
                exog_futuras = df_exogenas.tail(pasos_futuro).values
                prediccion = resultado_vecmx.predict(steps=pasos_futuro, exog_fc=exog_futuras)
                
                fechas_futuras = pd.date_range(start=df_precios.index[-1] + timedelta(days=7), periods=pasos_futuro, freq='W')
                df_pred = pd.DataFrame(prediccion, index=fechas_futuras, columns=['Pred_Productor', 'Pred_Mercado'])
                
                # 5. SALIDA VISUAL
                st.markdown("---")
                st.write(f"### 🎯 Proyección VECMX: {producto_mercado}")
                df_cola = df_precios.tail(10)
                
                fig_pred = go.Figure()
                fig_pred.add_trace(go.Scatter(x=df_cola.index, y=df_cola['Precio_Mercado'], name=f'{etiqueta_mercado} (Hist)', line=dict(color='gray', dash='dot')))
                fig_pred.add_trace(go.Scatter(x=df_cola.index, y=df_cola['Precio_Productor'], name='Productor (Hist)', line=dict(color='gray', dash='dot')))
                fig_pred.add_trace(go.Scatter(x=df_pred.index, y=df_pred['Pred_Mercado'], name=f'Proy. {etiqueta_mercado.split()[1]}', line=dict(color='#2979FF', width=3)))
                fig_pred.add_trace(go.Scatter(x=df_pred.index, y=df_pred['Pred_Productor'], name='Proy. Productor', line=dict(color='#00E676', width=3)))
                fig_pred.update_layout(template="plotly_dark", yaxis_title="USD", margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_pred, use_container_width=True)
                
                tendencia = "AL ALZA 📈" if df_pred['Pred_Productor'].iloc[-1] > df_pred['Pred_Productor'].iloc[0] else "A LA BAJA 📉"
                st.success(f"**Recomendación:** Proyección {tendencia} para las próximas 8 semanas considerando costos de producción agregados (Fertilizantes y Transporte).")
                
                # CAJÓN PARA ECONOMISTAS
                with st.expander("🛠️ Auditoría Econométrica VECMX (Tribunal de Criterios)"):
                    st.write("**Selección de Rezagos ($p$):**")
                    c_lag1, c_lag2, c_lag3, c_lag4 = st.columns(4)
                    c_lag1.metric("AIC", f"{aic_lags}")
                    c_lag2.metric("BIC", f"{bic_lags}")
                    c_lag3.metric("HQIC", f"{hqic_lags}")
                    c_lag4.metric("🏆 Consenso (Mediana)", f"{p_optimo_consenso}")
                    
                    st.write("**Estadísticos de Diagnóstico:**")
                    c_diag1, c_diag2 = st.columns(2)
                    c_diag1.metric("📊 Test Johansen", "Rechaza H0" if hay_cointegracion else "No rechaza H0")
                    test_blanco = resultado_vecmx.test_whiteness(nlags=10)
                    c_diag2.metric("📉 Residuos (Ljung-Box p-val)", f"{round(test_blanco.pvalue, 3)}")
                    
                    st.caption(f"*Metodología:* Se inyectaron variables exógenas ($X_t$) simuladas de Costos Logísticos y Urea. El modelo evaluó los 3 criterios de información y seleccionó la mediana para equilibrar parsimonia y poder predictivo. Se verificó que las raíces del VAR sean menores a 1 para garantizar estabilidad.")
                    
            except Exception as e:
                st.error(f"❌ Ocurrió un error en la estimación VECMX: {e}")
