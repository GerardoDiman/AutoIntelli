# --- Constantes (o podrían pasarse como argumentos si fueran configurables) ---
# Asegúrate de que estos nombres coincidan EXACTAMENTE con tus propiedades en Notion
DATE_PROPERTY_NAME = "Date" # Nombre de la propiedad de Fecha para Ajustes (usado solo en funciones de Ajuste)
REQUEST_TIMEOUT = 30
NOTION_VERSION = "2022-06-28"
API_BASE_URL = "https://api.notion.com/v1"

# --- Propiedades en Base(s) de Datos de Materiales ---
NOTION_PROP_FOLIO = "Folio de solicitud" # Asumiendo Rich Text
NOTION_PROP_SOLICITANTE = "Nombre del solicitante" # Asumiendo Select
NOTION_PROP_FECHA_SOLICITUD = "Fecha de solicitud" # Asumiendo Date
NOTION_PROP_PROVEEDOR = "Proveedor" # Asumiendo Select
NOTION_PROP_DEPARTAMENTO = "Departamento/Área" # Asumiendo Select
NOTION_PROP_URGENTE = "Urgente" # <<< Nombre EXACTO de la propiedad Checkbox
NOTION_PROP_RECUPERADO = "Recuperado"
NOTION_PROP_MATERIALES_PROYECTO_RELATION = "Proyecto" # <<<< Nombre EXACTO de la propiedad RELATION en BD Materiales <<<<
NOTION_PROP_ESPECIFICACIONES = "Especificaciones adicionales" # Asumiendo Rich Text

NOTION_PROP_CANTIDAD = "Cantidad solicitada" # Asumiendo Number
NOTION_PROP_TIPO_MATERIAL = "Tipo de material" # Asumiendo Select
NOTION_PROP_NOMBRE_MATERIAL = "Nombre del material" # Asumiendo Select
NOTION_PROP_UNIDAD_MEDIDA = "Unidad de medida" # Asumiendo Select

NOTION_PROP_LARGO = "Largo (dimensión)" # Asumiendo Rich Text
NOTION_PROP_ANCHO = "Ancho (dimensión)" # Asumiendo Rich Text
NOTION_PROP_ALTO = "Alto (dimensión)"   # Asumiendo Rich Text
NOTION_PROP_DIAMETRO = "Diametro (dimensión)" # Asumiendo Rich Text

# Propiedades específicas de Torni (ajusta si es necesario)
NOTION_PROP_TORNI_ID = "ID de producto" # Asumiendo Rich Text
NOTION_PROP_TORNI_DESCRIPTION = "Descripción" # Asumiendo Rich Text

# --- Propiedades en Base de Datos de PROYECTOS ---
# *** NOTION_PROP_PROYECTO_BUSQUEDA_ID: El nombre de la propiedad en tu BD de PROYECTOS que usas para IDENTIFICAR UN PROYECTO (ej. "Número de Proyecto", "Código", "Nombre") ***
NOTION_PROP_PROYECTO_BUSQUEDA_ID = "ID del proyecto" # <<<< Nombre EXACTO de la propiedad para BUSCAR en BD Proyectos <<<<
# --- Fin Nombres de Propiedad ---