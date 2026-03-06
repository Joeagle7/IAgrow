import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
from streamlit_geolocation import streamlit_geolocation
import plotly.express as px
import ee  #Google Engine#

# --- 1. CONFIGURACIÓN Y ESTADO DE MEMORIA (SESSION STATE) ---
st.set_page_config(page_title="AgroIA - Panel de Decisión", page_icon="🌾", layout="wide")

if "lat" not in st.session_state: st.session_state.lat = -2.1962
if "lon" not in st.session_state: st.session_state.lon = -79.8862

# Inicializar Google Earth Engine
# (Requiere haber ejecutado 'earthengine authenticate' en la terminal previamente)
try:
    ee.Initialize()
    gee_activo = True
except Exception as e:
    gee_activo = False

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
opcion_menu = st.sidebar.radio("📋 Ir a:", ["Menú Principal (Mapa)", "Forecast Clima", "Análisis Suelo", "Mapa Satelital (NDVI)"]) # <-- Nueva opción

# --- FUNCIONES DE CLIMA Y SUELO (Omitidas para brevedad, use las del código anterior) ---
# def obtener_datos_clima...
# def obtener_datos_suelo...

# --- 3. DESARROLLO DE LAS PÁGINAS ---

# [Aquí va el código anterior de "Menú Principal", "Forecast Clima" y "Análisis Suelo"]
# ... (Mantenga el código exactamente igual para esas tres secciones) ...

# NUEVA SECCIÓN: MAPA SATELITAL (NDVI)
elif opcion_menu == "Mapa Satelital (NDVI)":
    st.subheader(f"🛰️ Análisis Satelital de Salud Vegetal (NDVI) en {st.session_state.lat}, {st.session_state.lon}")
    
    if not gee_activo:
        st.error("⚠️ Error de Conexión Satelital: Google Earth Engine no está inicializado. Ejecute 'earthengine authenticate' en su terminal.")
    else:
        with st.spinner("Conectando con satélites Copernicus Sentinel-2. Procesando bandas espectrales..."):
            # 1. Definir el punto de interés
            punto = ee.Geometry.Point([st.session_state.lon, st.session_state.lat])
            
            # 2. Filtrar la colección de imágenes satelitales (Última imagen con menos de 10% de nubes)
            imagen_sentinel = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(punto) \
                .filterDate('2023-01-01', '2024-12-31') \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10)) \
                .sort('system:time_start', False) \
                .first()
            
            # 3. Calcular la ecuación Econométrica/Biofísica del NDVI: (B8 - B4) / (B8 + B4)
            # B8 = Infrarrojo Cercano (NIR), B4 = Rojo
            ndvi = imagen_sentinel.normalizedDifference(['B8', 'B4']).rename('NDVI')
            
            # 4. Parámetros de visualización (Paleta de colores semáforo)
            vis_params = {
                'min': 0.0,
                'max': 0.8,
                'palette': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']
            }
            
            # 5. Obtener el mapa procesado por los servidores de Google para inyectarlo en Folium
            map_id_dict = ee.Image(ndvi).getMapId(vis_params)
            tile_url = map_id_dict['tile_fetcher'].url_format
            
            # 6. Dibujar el mapa en la aplicación
            m_ndvi = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=15)
            
            # Capa base de satélite estándar
            folium.TileLayer(
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri', name='Satélite Base', overlay=False, control=True
            ).add_to(m_ndvi)
            
            # Capa superpuesta del Análisis NDVI
            folium.TileLayer(
                tiles=tile_url, attr='Google Earth Engine', name='NDVI (Salud Vegetal)',
                overlay=True, control=True, opacity=0.7
            ).add_to(m_ndvi)
            
            # Marcador central
            folium.Marker([st.session_state.lat, st.session_state.lon], popup="Mi Parcela").add_to(m_ndvi)
            
            folium.LayerControl().add_to(m_ndvi)
            st_folium(m_ndvi, width=900, height=500)
            
            # Interpretación para el agricultor
            st.info("💡 **Interpretación Agronómica:** Las zonas en **Verde Oscuro** indican cultivos sanos y vigorosos. Las zonas en **Amarillo/Naranja** señalan estrés (falta de agua, plagas o deficiencia de nutrientes). Las zonas en **Rojo** representan suelo desnudo, infraestructura o plantas marchitas.")
