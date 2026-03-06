import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
from streamlit_geolocation import streamlit_geolocation
import plotly.express as px
import ee
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN Y ESTADO DE MEMORIA ---
st.set_page_config(page_title="AgroIA - Panel de Decisión", page_icon="🌾", layout="wide")

if "lat" not in st.session_state: st.session_state.lat = -2.1962
if "lon" not in st.session_state: st.session_state.lon = -79.8862

@st.cache_resource
def inicializar_google_earth_engine():
    try:
        # 1. Si la aplicación detecta que está en la Nube
        if "EE_CREDENTIALS" in st.secrets:
            import json
            from google.oauth2 import service_account
            
            # Leemos el archivo JSON que ya funciona bien
            creds_dict = json.loads(st.secrets["EE_CREDENTIALS"])
            
            # Creamos la credencial base
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
            
            # LA SOLUCIÓN: Le decimos a Google exactamente qué puerta queremos abrir
            scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/earthengine'])
            
            # Inicializamos pasando la credencial con el permiso asignado
            ee.Initialize(scoped_credentials)
            
        # 2. Si está en su computadora local (localhost)
        else:
            ee.Initialize()
            
        return True
    except Exception as e:
        st.error(f"⚠️ Detalle técnico del fallo satelital: {e}")
        return False

gee_activo = inicializar_google_earth_engine()
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
opcion_menu = st.sidebar.radio("📋 Ir a:", ["Menú Principal (Mapa)", "Forecast Clima", "Análisis Suelo", "Mapa Satelital (NDVI)"])

# --- FUNCIONES DE CLIMA Y SUELO ---
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
    
    st.markdown("### Opción A: Usar mi ubicación actual (GPS)")
    ubicacion_gps = streamlit_geolocation()
    if ubicacion_gps['latitude'] is not None:
        gps_lat = round(ubicacion_gps['latitude'], 4)
        gps_lon = round(ubicacion_gps['longitude'], 4)
        if gps_lat != st.session_state.lat or gps_lon != st.session_state.lon:
            st.session_state.lat, st.session_state.lon = gps_lat, gps_lon
            st.rerun()

    st.markdown("---")
    st.markdown("### Opción B: Seleccionar en el Mapa Interactivo")
    st.write("Haga **clic** sobre su parcela. El marcador rojo se moverá exactamente a su selección.")
    
    m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=13)
    folium.Marker([st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="red", icon="info-sign")).add_to(m)
    
    output = st_folium(m, width=900, height=500, key="mapa_principal", returned_objects=["last_clicked"])

    if output and output.get('last_clicked'):
        click_lat = round(output['last_clicked']['lat'], 4)
        click_lon = round(output['last_clicked']['lng'], 4)
        if click_lat != st.session_state.lat or click_lon != st.session_state.lon:
            st.session_state.lat, st.session_state.lon = click_lat, click_lon
            st.rerun()

elif opcion_menu == "Forecast Clima":
    st.subheader(f"🌤️ Forecast Agrícola Detallado ({st.session_state.lat}, {st.session_state.lon})")
    json_clima = obtener_datos_clima(st.session_state.lat, st.session_state.lon)
    if json_clima and 'hourly' in json_clima:
        cur = json_clima['current_weather']
        st.markdown(f"**Condiciones actuales:** Viento {grados_a_direccion(cur['winddirection'])} a {cur['windspeed']} km/h")
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric(label="🌡️ Temperatura", value=f"{cur['temperature']}°C")
        with c2: st.metric(label="💧 Humedad Relativa", value=f"{json_clima['hourly']['relativehumidity_2m'][0]}%")
        with c3: st.metric(label="🌬️ Presión", value=f"{json_clima['hourly']['pressure_msl'][0]} hPa")
        with c4: st.metric(label="☁️ Punto de Rocío", value=f"{json_clima['hourly']['dewpoint_2m'][0]}°C")
        
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
        def extraer_dato(json_data, capa_idx, prof_idx):
            try:
                valor = json_data['properties']['layers'][capa_idx]['depths'][prof_idx]['values']['mean']
                return round(valor / 10, 2) if valor is not None else "Sin datos"
            except:
                return "Sin datos"

        c1, c2 = st.columns(2)
        with c1:
            st.write("**Capa Superficial (0-5cm)**")
            st.metric("pH", extraer_dato(json_suelo, 1, 0))
            st.metric("Nitrógeno (cg/kg)", extraer_dato(json_suelo, 2, 0))
        with c2:
            st.write("**Capa Profunda (15-30cm)**")
            st.metric("pH", extraer_dato(json_suelo, 1, 1))
            st.metric("Nitrógeno (cg/kg)", extraer_dato(json_suelo, 2, 1))
    else:
        st.warning("⚠️ No se encontraron datos edafológicos para esta ubicación.")

elif opcion_menu == "Mapa Satelital (NDVI)":
    st.subheader(f"🛰️ Análisis Satelital de Salud Vegetal (NDVI)")
    
    if not gee_activo:
        st.error("⚠️ Error: Google Earth Engine no está inicializado.")
    else:
        with st.spinner("Procesando mosaico satelital libre de nubes (Algoritmo QA60)..."):
            try:
                punto = ee.Geometry.Point([st.session_state.lon, st.session_state.lat])
                
                # 1. Ventana de tiempo (últimos 90 días para garantizar datos en invierno)
                fecha_fin = datetime.today()
                fecha_inicio = fecha_fin - timedelta(days=90)
                
                # 2. EL BISTURÍ DIGITAL: Función para borrar nubes píxel por píxel
                def enmascarar_nubes(imagen):
                    qa = imagen.select('QA60') # Banda de calidad del satélite
                    # Los bits 10 y 11 detectan nubes opacas y cirros translúcidos
                    mascara = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
                    return imagen.updateMask(mascara)
                
                # 3. Descargamos las fotos, borramos las nubes y fusionamos lo limpio (median)
                coleccion = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                    .filterBounds(punto) \
                    .filterDate(fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d')) \
                    .map(enmascarar_nubes) 
                
                if coleccion.size().getInfo() == 0:
                    st.warning("☁️ Cobertura nubosa total y permanente. No hay datos útiles en este trimestre.")
                else:
                    # Fusionamos la colección en una sola imagen perfecta
                    imagen_limpia = coleccion.median()
                    
                    # 4. Mensaje de transparencia para el usuario
                    f_inicio_str = fecha_inicio.strftime('%d de %b de %Y')
                    f_fin_str = fecha_fin.strftime('%d de %b de %Y')
                    st.info(f"🧩 **Mosaico Satelital de Invierno:** Debido a la nubosidad, esta imagen es una fusión de los píxeles más despejados capturados entre el **{f_inicio_str} y el {f_fin_str}**. Muestra la tendencia de salud más reciente de su cultivo.")
                    
                    # Calculamos el NDVI
                    ndvi = imagen_limpia.normalizedDifference(['B8', 'B4']).rename('NDVI')
                    vis_params = {'min': 0.1, 'max': 0.6, 'palette': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']}
                    map_id_dict = ee.Image(ndvi).getMapId(vis_params)
                    
                    m_ndvi = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=15, max_zoom=20)
                    
                    folium.TileLayer(
                        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                        attr='Esri', name='Satélite Base', overlay=False, max_zoom=20
                    ).add_to(m_ndvi)
                    
                    folium.TileLayer(
                        tiles=map_id_dict['tile_fetcher'].url_format, attr='Google Earth Engine', 
                        name='NDVI', overlay=True, opacity=0.7, max_zoom=20, max_native_zoom=16
                    ).add_to(m_ndvi)
                    
                    folium.Marker([st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="red")).add_to(m_ndvi)
                    
                    st_folium(m_ndvi, width=900, height=500, key="mapa_ndvi")
                    
                    st.success("✅ Interpretación: Verde Oscuro (Cultivo Sano), Amarillo/Naranja (Estrés), Rojo (Suelo desnudo/Infraestructura).")
                    
            except Exception as e:
                st.error(f"❌ Ocurrió un error al extraer los datos satelitales: {e}")
