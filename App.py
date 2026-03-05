import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests
from streamlit_geolocation import streamlit_geolocation

st.set_page_config(page_title="AgroIA - Panel de Control", layout="wide")
st.title("🌾 AgroIA: Plataforma Inteligente de Decisión Agrícola")

# --- BARRA LATERAL: PARÁMETROS Y GPS ---
st.sidebar.header("1. Ubicación de la Parcela")
st.sidebar.write("Haga clic abajo para obtener su ubicación actual (permita el acceso al GPS en su navegador):")

# Botón mágico de geolocalización
ubicacion = streamlit_geolocation()

# Lógica condicional: Si el GPS captura datos, úsalos; si no, usa coordenadas de Ecuador
if ubicacion['latitude'] is not None and ubicacion['longitude'] is not None:
    latitud = round(ubicacion['latitude'], 4)
    longitud = round(ubicacion['longitude'], 4)
    st.sidebar.success(f"📍 GPS Capturado: {latitud}, {longitud}")
else:
    latitud = -2.1962 # Guayas por defecto
    longitud = -79.8862
    st.sidebar.info("Usando coordenadas por defecto. Active el GPS.")

st.sidebar.markdown("---")
cultivo = st.sidebar.selectbox("Seleccione el cultivo", ["Cacao", "Banano", "Maíz", "Arroz"])

# --- MAPA DE LA PARCELA ---
mapa = folium.Map(location=[latitud, longitud], zoom_start=12)
folium.Marker([latitud, longitud], popup="Mi Parcela").add_to(mapa)
st_folium(mapa, width=700, height=300)

st.markdown("---")

# --- EXTRACCIÓN DE DATOS: SOILGRIDS Y OPEN-METEO ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("🌍 Análisis de Suelo (SoilGrids 0-5cm)")
    if st.button("Analizar Calidad del Suelo"):
        with st.spinner('Consultando base de datos satelital...'):
            # Consulta a la API REST de SoilGrids (pH, Arcilla y Arena)
            url_soil = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lon={longitud}&lat={latitud}&property=phh2o&property=clay&property=sand&depth=0-5cm&value=mean"
            try:
                resp_soil = requests.get(url_soil).json()
                # SoilGrids devuelve el pH multiplicado por 10, hay que dividirlo
                ph = resp_soil['properties']['layers'][1]['depths'][0]['values']['mean'] / 10
                arcilla = resp_soil['properties']['layers'][0]['depths'][0]['values']['mean'] / 10 # Porcentaje
                
                st.metric("Nivel de pH (Acidez)", f"{ph}")
                st.metric("Composición de Arcilla", f"{arcilla}%")
                
                if ph < 5.5:
                    st.warning("⚠️ **Alerta:** Suelo muy ácido. Considerar encalado para que el cultivo absorba el fertilizante.")
                else:
                    st.success("✅ pH dentro de rangos tolerables.")
            except:
                st.error("Error al extraer datos de SoilGrids en esta coordenada.")

with col2:
    st.subheader("🌤️ Clima: Histórico y Pronóstico")
    if st.button("Generar Serie de Tiempo Climática"):
        with st.spinner('Calculando evapotranspiración y lluvia...'):
            # Pedimos temperatura, lluvia y evapotranspiración (3 días pasados + 7 futuros)
            url_meteo = f"https://api.open-meteo.com/v1/forecast?latitude={latitud}&longitude={longitud}&daily=temperature_2m_max,precipitation_sum,et0_fao_evapotranspiration&past_days=3&timezone=America/Guayaquil"
            resp_meteo = requests.get(url_meteo).json()
            
            # Convertimos el JSON en un DataFrame de Pandas (Estructura de tabla)
            df_clima = pd.DataFrame({
                "Fecha": resp_meteo['daily']['time'],
                "Temp. Máxima (°C)": resp_meteo['daily']['temperature_2m_max'],
                "Lluvia (mm)": resp_meteo['daily']['precipitation_sum'],
                "Evapotranspiración (mm)": resp_meteo['daily']['et0_fao_evapotranspiration']
            })
            df_clima['Fecha'] = pd.to_datetime(df_clima['Fecha'])
            df_clima.set_index('Fecha', inplace=True)
            
            # Mostramos el gráfico de series de tiempo
            st.line_chart(df_clima[['Temp. Máxima (°C)', 'Evapotranspiración (mm)']])
            st.bar_chart(df_clima[['Lluvia (mm)']])
            
            st.info("💡 **Interpretación:** La Evapotranspiración (línea) indica el estrés hídrico de la planta. Si este valor es persistentemente mayor que la Lluvia (barras), usted debe programar riego suplementario.")
