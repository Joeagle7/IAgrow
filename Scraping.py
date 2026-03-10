## Scrapers ##

import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import warnings

# Ignoramos advertencias de seguridad SSL si las páginas del gobierno tienen certificados vencidos (muy común)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

class ArañaSoberanaEcuador:
    """
    Clase maestra para extraer datos oficiales del BCE y el INAMHI.
    Diseñada con manejo de errores para soportar las caídas frecuentes de servidores gubernamentales.
    """
    def __init__(self):
        # Usamos un "User-Agent" para que el servidor del gobierno crea que somos un navegador real de una persona, no un robot.
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
        }

    # ==========================================
    # 1. SCRAPER DEL BANCO CENTRAL (BCE)
    # ==========================================
    def extraer_precios_exportacion_bce(self):
        """
        Rastrea el portal del BCE para encontrar el último Excel de estadísticas 
        macroeconómicas y extrae la pestaña de Exportaciones (FOB).
        """
        # Esta URL es referencial al portal de estadísticas del BCE
        url_base_bce = "https://contenido.bce.fin.ec/documentos/Estadisticas/SectorReal/Previsiones/IndCoyuntura/IndicadoresCoyuntura.html"
        
        try:
            # 1. Entramos a la página web
            respuesta = requests.get(url_base_bce, headers=self.headers, verify=False, timeout=15)
            sopa = BeautifulSoup(respuesta.text, 'lxml')
            
            # 2. Buscamos todos los enlaces (etiquetas <a>) que terminen en .xlsx o .xls
            enlace_excel = None
            for a in sopa.find_all('a', href=True):
                if '.xlsx' in a['href'] or '.xls' in a['href']:
                    enlace_excel = a['href']
                    # Si el enlace es relativo, lo unimos al dominio del BCE
                    if not enlace_excel.startswith('http'):
                        enlace_excel = "https://contenido.bce.fin.ec" + enlace_excel
                    break # Encontramos el primero, nos detenemos
            
            if not enlace_excel:
                return False, "No se encontró el archivo Excel en la página del BCE."

            # 3. Descargamos el archivo Excel directamente a la memoria (sin guardarlo en el disco duro)
            archivo_descargado = requests.get(enlace_excel, headers=self.headers, verify=False)
            
            # 4. Pandas lee el Excel desde la memoria. 
            # (En un caso real, aquí especificaríamos qué hoja 'sheet_name' y qué columnas leer)
            df_bce = pd.read_excel(io.BytesIO(archivo_descargado.content), sheet_name=0)
            
            return True, df_bce
            
        except Exception as e:
            return False, f"Error al conectar con el servidor del BCE: {e}"

    # ==========================================
    # 2. SCRAPER DEL INAMHI
    # ==========================================
    def extraer_boletin_inamhi(self, estacion="QUITO"):
        """
        Rastrea los boletines tabulares del INAMHI buscando datos de temperatura y precipitación.
        """
        # URL referencial de boletines diarios tabulares del INAMHI
        url_inamhi = "http://186.42.174.241/InamhiMeteorologico/estadisticas" 
        
        try:
            # 1. Entramos a la página web
            respuesta = requests.get(url_inamhi, headers=self.headers, verify=False, timeout=15)
            sopa = BeautifulSoup(respuesta.text, 'lxml')
            
            # 2. Buscamos la tabla HTML que contiene los datos climáticos
            # (Normalmente buscamos por el ID o la clase de la tabla HTML)
            tabla_clima = sopa.find('table', {'id': 'tabla_boletin'}) 
            
            if not tabla_clima:
                return False, "La estructura de la página del INAMHI cambió o la tabla no existe hoy."

            # 3. Usamos Pandas para convertir la tabla HTML a un DataFrame directamente
            # read_html devuelve una lista de tablas, tomamos la primera [0]
            df_inamhi = pd.read_html(str(tabla_clima))[0]
            
            # Aquí aplicaríamos filtros para quedarnos solo con la estación requerida
            # df_filtrado = df_inamhi[df_inamhi['Estacion'] == estacion]
            
            return True, df_inamhi
            
        except Exception as e:
            return False, f"Error al conectar con los servidores del INAMHI: {e}"

# PRUEBA DE FUNCIONAMIENTO (Solo se ejecuta si corremos este archivo directamente)
if __name__ == "__main__":
    spider = ArañaSoberanaEcuador()
    print("Iniciando extracción BCE...")
    exito_bce, datos_bce = spider.extraer_precios_exportacion_bce()
    if exito_bce:
        print("Excel descargado y procesado. Primeras filas:")
        print(datos_bce.head())
    else:
        print(datos_bce)
