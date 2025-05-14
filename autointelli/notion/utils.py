import logging
import requests # Aunque get_pages_with_filter_util no usa requests directamente, notion_client lo hace. Mantenerlo por si acaso.
from datetime import datetime, timedelta # Aunque estas utils no los usan directamente, podrían ser útiles aquí.
from notion_client import Client
from notion_client.errors import APIResponseError
from typing import Optional, Dict, List, Tuple, Any, Union
from autointelli.notion.constants import NOTION_PROP_MATERIALES_PROYECTO_RELATION, NOTION_PROP_PARTIDA_BUSQUEDA_ID # Importar constantes
import json
import traceback # Aunque estas utils no usan traceback, se mantuvo en el original. Puede que no sea estrictamente necesario aquí, pero no hace daño.

logger = logging.getLogger(__name__)

# --- Funciones Auxiliares Generales ---

def get_database_properties_util(notion_client: Client, database_id: str) -> Dict[str, Dict]:
    """Obtiene el diccionario de propiedades de una base de datos de Notion."""
    if not notion_client or not database_id:
        logger.error("Cliente de Notion o Database ID faltante para obtener propiedades.")
        return {}
    try:
        database_info = notion_client.databases.retrieve(database_id)
        properties = database_info.get("properties", {})
        # logger.debug(f"Propiedades obtenidas de la base de datos {database_id}: {', '.join(properties.keys())}") # Demasiado verbose, descomentar solo para depuración intensa.
        return properties
    except Exception as e:
        logger.error(f"Error al obtener propiedades de la base de datos {database_id}: {str(e)}", exc_info=True)
        return {}

def create_filter_condition_util(property_name: str, property_type: str, value: Any) -> Dict:
     """Construye una condición de filtro para consultas a la API de Notion."""
     if value is None or (isinstance(value, str) and str(value).strip() == ""):
          # Un valor vacío no genera una condición de filtro "positive match" útil aquí.
          # Para buscar campos vacíos {"is_empty": true} se necesitaría lógica adicional.
          logger.warning(f"Valor nulo o vacío para crear filtro de propiedad '{property_name}'. Omitiendo.")
          return {}

     cleaned_value = str(value).strip()

     # Mapeo de tipos de Notion a condiciones de filtro comunes
     if property_type in ["text", "rich_text", "title", "url", "email", "phone_number"]:
          # Filtro 'contains' es flexible para texto
          return { "property": property_name, property_type if property_type != 'text' else 'rich_text' : { "contains": cleaned_value } } # API usa 'rich_text' para title/text
     elif property_type == "number":
         try:
             float_value = float(cleaned_value)
             return { "property": property_name, "number": { "equals": float_value } } # Coincidencia exacta para números
         except (ValueError, TypeError):
             logger.warning(f"Valor '{value}' no es un número válido para filtro 'equals' en propiedad Number '{property_name}'.")
             return {}
     elif property_type == "select":
         return { "property": property_name, "select": { "equals": cleaned_value } } # Coincidencia exacta para Select
     elif property_type == "checkbox":
         bool_value = cleaned_value.lower() in ['true', 'yes', 'on', '1'] # Intenta convertir a booleano
         return { "property": property_name, "checkbox": { "equals": bool_value } } # Coincidencia exacta para Checkbox
     elif property_type == "multi_select":
          return { "property": property_name, "multi_select": { "contains": cleaned_value } } # Contiene una opción específica en multi-select

     else:
         logger.warning(f"Tipo de propiedad no soportado para filtrado en create_filter_condition_util: '{property_type}' para propiedad '{property_name}'.")
         return {}


def get_pages_with_filter_util(notion_client: Client, database_id: str, filters: List[Dict] = None, page_size: int = 100) -> List[Dict]:
    """Ejecuta una consulta filtrada a una base de datos de Notion."""
    if not notion_client or not database_id:
        logger.error("Cliente de Notion o Database ID faltante para obtener páginas con filtro.")
        return []
    all_pages = []
    has_more = True
    start_cursor = None

    try:
        query_args = {
            "database_id": database_id,
            "page_size": page_size,
        }

        filter_arg = None
        if filters and len(filters) > 0:
            if len(filters) == 1:
                filter_arg = filters[0]
            else:
                # Usar filtro 'and' para combinar múltiples condiciones si hay más de una
                filter_arg = { "and": filters }

        if filter_arg is not None:
             query_args["filter"] = filter_arg
             # logger.debug(f"Filtros aplicados a consulta Notion para {database_id}: {json.dumps(filter_arg, ensure_ascii=False)}") # Demasiado verbose


        while has_more:
            if start_cursor:
                query_args["start_cursor"] = start_cursor

            response = notion_client.databases.query(**query_args)

            # El cliente Python de Notion ya devuelve el diccionario, no necesitas response.json()
            data = response

            results = data.get("results", [])
            all_pages.extend(results)

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

            # logger.debug(f"Obtenidas {len(results)} páginas con filtros de {database_id}. Total acumulado: {len(all_pages)}") # Demasiado verbose

    except APIResponseError as e:
        logger.error(f"Error API al consultar base de datos {database_id}: Código={e.code if hasattr(e, 'code') else 'N/A'} Mensaje={e.message if hasattr(e, 'message') else str(e)}", exc_info=True)
        notion_response_body = getattr(e, 'response', None)
        # Intenta obtener el cuerpo JSON del error si está disponible en el objeto de respuesta
        if notion_response_body is not None and hasattr(notion_response_body, 'json'):
             try: logger.error(f"Detalles adicionales del error de Notion (Consulta DB {database_id}): {json.dumps(notion_response_body.json(), ensure_ascii=False)}")
             except Exception: pass # No fallar si no se puede parsear el JSON del error

    except Exception as e:
        logger.error(f"Error inesperado al obtener páginas de Notion con filtros de {database_id}: {str(e)}", exc_info=True)

    logger.info(f"Consulta a DB {database_id} completada. Total de páginas encontradas: {len(all_pages)}")
    return all_pages

def update_notion_page_properties(notion_client: Client, page_id: str, properties_to_update: Dict) -> Tuple[int, Dict]:
    if not notion_client or not page_id or not properties_to_update:
         logger.error("Cliente de Notion, Page ID o propiedades a actualizar faltantes.")
         return 400, {"error": "Request inválido. Faltan parámetros necesarios."}

    try:
        # logger.debug(f"Intentando actualizar propiedades para página {page_id}: {properties_to_update}") # Muy verbose, descomentar con cuidado.
        response = notion_client.pages.update(page_id=page_id, properties=properties_to_update)
        logger.info(f"Página {page_id} actualizada correctamente.")
        # En caso de éxito, el cliente Notion no devuelve un status_code directo en el objeto response,
        # pero la actualización fue exitosa, que corresponde a un 2xx. Asumimos 200.
        return 200, response
    except APIResponseError as e:
        # La excepción APIResponseError contiene el código de estado HTTP en e.status
        logger.error(f"Error API al actualizar página {page_id}: Código={e.code if hasattr(e, 'code') else 'N/A'} Mensaje={e.message if hasattr(e, 'message') else str(e)} Estado HTTP={e.status if hasattr(e, 'status') else 'N/A'}", exc_info=True)
        notion_response_body = getattr(e, 'response', None)
        notion_error_details = None
        if notion_response_body is not None and hasattr(notion_response_body, 'json'):
             try: notion_error_details = notion_response_body.json()
             except Exception: pass

        # Retorna el status code de la API de Notion y un diccionario de error
        return e.status if hasattr(e, 'status') and e.status is not None else 500, { # Fallback a 500 si status no está disponible
            "error": f"Notion API Error: {e.message if hasattr(e, 'message') else str(e)}",
            "code": e.code if hasattr(e, 'code') else 'N/A',
            "notion_error_details": notion_error_details
        }
    except Exception as e:
        # Captura otros errores inesperados durante el proceso de actualización
        logger.error(f"Error inesperado al actualizar página {page_id}: {str(e)}", exc_info=True)
        return 500, {"error": f"Error interno del servidor: {str(e)}"}
    
def list_available_properties(notion_client: Client, database_id: str) -> List[Dict[str, str]]:
    """
    Lista las propiedades disponibles (nombre, tipo, id) de una base de datos dada.
    Útil para que el frontend conozca los campos disponibles para filtros o visualización.
    """
    if not notion_client or not database_id:
        logger.error("Cliente de Notion o Database ID faltante para listar propiedades.")
        return []
    try:
        properties = get_database_properties_util(notion_client, database_id)
        property_list = []
        for name, info in properties.items():
            prop_type = info.get("type", "unknown")
            prop_id = info.get("id", name) # Usar el ID interno si está disponible, sino el nombre
            property_list.append({
                "name": name,
                "type": prop_type,
                "id": prop_id
            })
        # logger.debug(f"Listadas {len(property_list)} propiedades para DB {database_id}.") # Demasiado verbose
        return property_list
    except Exception as e:
        logger.error(f"Error al listar propiedades de la base de datos {database_id}: {e}", exc_info=True)
        return []
    

def build_filter_from_properties_util(notion_client: Client, database_id: str, property_filters: Dict[str, Any]) -> List[Dict]:

    if not property_filters:
        logger.info("No se proporcionaron filtros de propiedades, build_filter_from_properties_util retorna lista vacía.")
        return []
    if not notion_client or not database_id:
        logger.error("Cliente de Notion o Database ID faltante para construir filtros.")
        return []

    filters = []
    db_properties = get_database_properties_util(notion_client, database_id)

    if not db_properties:
         logger.error(f"No se pudieron obtener las propiedades de la base de datos '{database_id}'. No se construirán filtros.")
         return []

    for prop_name, prop_value in property_filters.items():
        if prop_name not in db_properties:
            logger.warning(f"Propiedad '{prop_name}' proporcionada para filtro no encontrada en la base de datos '{database_id}'. Omitiendo filtro para esta propiedad.")
            continue

        prop_info = db_properties[prop_name]
        prop_type = prop_info.get("type") # Obtiene el tipo de propiedad desde Notion

        # Usa la función auxiliar para crear la condición de filtro específica para el tipo
        filter_condition = create_filter_condition_util(prop_name, prop_type, prop_value)

        if filter_condition:
            filters.append(filter_condition)
        else:
             # La función create_filter_condition_util ya loguea warnings por valores inválidos o tipos no soportados
             pass
    # logger.debug(f"Filtros construidos final: {json.dumps(filters, ensure_ascii=False)}") # Muy verbose
    return filters


def find_partida_by_id(notion_client: Client, database_id_partidas: str, partida_id: str) -> Optional[Dict]:
    """
    Busca una página en la base de datos de Partidas por su 'ID de partida'.
    Retorna la primera página encontrada o None.
    """
    if not notion_client or not database_id_partidas or not partida_id:
        logger.error("Cliente de Notion, Database ID de Partidas o ID de partida faltante para la búsqueda.")
        return None

    logger.debug(f"find_partida_by_id: Buscando partida con ID: '{partida_id}'")
    logger.info(f"Buscando Partida con ID '{partida_id}' en la base de datos '{database_id_partidas}'.")

    # Definir el nombre de la propiedad en Notion que contiene el ID de partida
    # Asumimos que la propiedad se llama exactamente 'ID de partida' y es de tipo texto o similar.
    partida_id_property_name = 'ID de partida'

    # Crear el filtro para buscar la propiedad 'ID de partida' igual al valor proporcionado
    # Necesitamos obtener el tipo de propiedad real de Notion para usar create_filter_condition_util
    # O crear el filtro directamente si asumimos que es texto (rich_text/title)
    # Opción simple: asumir que es rich_text/title y usar 'equals'
    # Consideramos 'rich_text' o 'title' ya que 'ID de partida' suele ser un identificador único.
    # Usaremos 'rich_text' con 'equals' para coincidencia exacta.
    filters = [{ "property": partida_id_property_name, "rich_text": { "equals": partida_id.strip() } }]

    # Ejecutar la consulta con el filtro
    found_pages = get_pages_with_filter_util(notion_client, database_id_partidas, filters=filters, page_size=1) # Solo necesitamos 1 resultado

    # Retornar la primera página encontrada o None
    return found_pages[0] if found_pages else None

# Función actualizada para retornar solo el ID de la página
def find_partida_by_id(notion_client: Client, database_id_partidas: str, partida_id: str) -> Optional[str]:
    """
    Busca una página en la base de datos de Partidas por su 'ID de partida'.
    Retorna el ID de la primera página encontrada (como string) o None.
    """
    if not notion_client or not database_id_partidas or not partida_id:
        logger.error("Cliente de Notion, Database ID de Partidas o ID de partida faltante para la búsqueda.")
        return None

    logger.info(f"Buscando Partida con ID '{partida_id}' en la base de datos '{database_id_partidas}'.")

    # Definir el nombre de la propiedad en Notion que contiene el ID de partida
    # Usamos la constante para el nombre de la propiedad de búsqueda de partidas.
    partida_id_property_name = NOTION_PROP_PARTIDA_BUSQUEDA_ID # << Usar la constante

    # Crear el filtro para buscar la propiedad 'ID de partida' igual al valor proporcionado
    # Asumimos que la propiedad 'ID de partida' es de tipo Rich Text o Title en Notion.
    # Usamos 'equals' para una coincidencia exacta del ID.
    filters = [{ "property": partida_id_property_name, "rich_text": { "equals": partida_id.strip() } }]

    # Ejecutar la consulta con el filtro
    logger.debug(f"find_partida_by_id: Filtro construido: {json.dumps(filters, ensure_ascii=False)}")
    found_pages = get_pages_with_filter_util(notion_client, database_id_partidas, filters=filters, page_size=1) # Solo necesitamos 1 resultado

    # Si se encontró una página, extrae su ID y retornalo como string.
    logger.debug(f"find_partida_by_id: Páginas encontradas: {len(found_pages)}")
    # Si no se encontró ninguna página, found_pages estará vacío y retornamos None.
    if found_pages and isinstance(found_pages, list) and len(found_pages) > 0:
        # La respuesta de la API para una página en found_pages[0] es un diccionario con la clave 'id'
        return found_pages[0].get("id") # Extrae el ID como string
    else:
        logger.warning(f"No se encontró ninguna página en la base de datos de Partidas con ID '{partida_id}'.")
        return None

def submit_request_for_material_logic(
    notion_client: Client,
    data: Dict,
    database_id_db1: str,
    database_id_db2: str,
    database_id_partidas: str, # Nuevo argumento para el ID de la base de datos de Partidas
    current_user_full_name: str,
    user_id: str # Para vincular al usuario de la app
):
    """
    Procesa la solicitud estándar de material, valida datos, busca la partida en Notion,
    y crea páginas en las dos bases de datos de materiales (DB1 y DB2) en Notion.
    """
    logger.info("Iniciando procesamiento de solicitud estándar de material.")

    # --- 1. Validar y extraer datos del diccionario 'data' ---
    # Los nombres de las claves deben coincidir con los nombres esperados del frontend.
    # Asegurarse de que 'partida' se extrae aquí en lugar de 'proyecto'.
    folio_solicitud = data.get('folio_solicitud')
    fecha_solicitud_str = data.get('fecha_solicitud') # Viene como 'YYYY-MM-DD' del frontend
    urgente = data.get('urgente', False)
    recuperado = data.get('recuperado', False)
    nombre_solicitante = data.get('nombre_solicitante')
    partida_id_from_form = data.get('partida') # Extraer el ID de partida del formulario
    cantidad_solicitada = data.get('cantidad_solicitada') # Debería ser un número (float o int)
    nombre_material = data.get('nombre_material')
    unidad_medida = data.get('unidad_medida')
    tipo_material = data.get('tipo_material') # Asumimos que lo envía el frontend basado en material

    # Dimensiones - pueden ser string (vacío, 'N/A') o numérico si el frontend validó.
    largo = data.get('largo')
    ancho = data.get('ancho')
    alto = data.get('alto')
    diametro = data.get('diametro')

    especificaciones_adicionales = data.get('especificaciones_adicionales')
    proveedor_logistica = data.get('proveedor') # Viene de campo oculto en HTML, fijo a 'ProveedorLogistica'
    departamento_logistica = data.get('departamento_area') # Viene de campo oculto, fijo a 'Logística'

    # Validaciones básicas de presencia. La validación detallada de dimensiones y existencia de partida/material ocurre más abajo.
    # Asegurarse de que 'partida_id_from_form' sea validado como requerido.
    if not all([folio_solicitud, fecha_solicitud_str, nombre_solicitante, partida_id_from_form,
                cantidad_solicitada, nombre_material, unidad_medida]):
        logger.error("Datos de formulario estándar incompletos.")
        missing_fields = [k for k, v in data.items() if v is None or (isinstance(v, str) and v.strip() == '') and k in ['folio_solicitud', 'fecha_solicitud', 'nombre_solicitante', 'partida', 'cantidad_solicitada', 'nombre_material', 'unidad_medida']]
        return 400, {"error": f"Datos de formulario incompletos. Campos faltantes: {', '.join(missing_fields)}"}

    # Convertir fecha_solicitud_str a formato ISO 8601 para Notion (solo la fecha)
    try:
        # Si la fecha viene en 'YYYY-MM-DD', ya es un formato válido para el campo Date de Notion (sin hora).
        # Si necesitara ser un objeto datetime, usar: fecha_solicitud_dt = datetime.strptime(fecha_solicitud_str, '%Y-%m-%d')
        fecha_solicitud_iso = fecha_solicitud_str # Ya está en el formato correcto para Notion Date property (YYYY-MM-DD)
    except ValueError:
        logger.error(f"Formato de fecha inválido recibido: {fecha_solicitud_str}")
        return 400, {"error": "Formato de fecha de solicitud inválido."}

    # Asegurarse de que cantidad_solicitada es un número
    try:
        cantidad_solicitada_num = float(cantidad_solicitada)
        if cantidad_solicitada_num <= 0:
             logger.error(f"Cantidad solicitada inválida: {cantidad_solicitada}. Debe ser > 0.")
             return 400, {"error": "Cantidad solicitada debe ser un número positivo."}
    except (ValueError, TypeError):
        logger.error(f"Cantidad solicitada no es un número válido: {cantidad_solicitada}")
        return 400, {"error": "Cantidad solicitada inválida. Debe ser un número."}

    # --- 2. Buscar la Partida en Notion ---
    # Usar la función find_partida_by_id que creamos anteriormente.
    partida_page = find_partida_by_id(notion_client, database_id_partidas, partida_id_from_form)
    
    if not partida_page:
        logger.warning(f"Partida con ID '{partida_id_from_form}' no encontrada en la base de datos de Partidas.")
        # Podrías decidir si esto es un error fatal o un warning. Para solicitudes estándar, asumimos que la partida debe existir.
        return 404, {"error": f"La Partida con ID '{partida_id_from_form}' no fue encontrada en Notion. Por favor, verifica el ID."}

    partida_page_id = partida_page.get("id")
    logger.info(f"Partida encontrada: ID de página de Notion '{partida_page_id}' para ID de partida '{partida_id_from_form}'.")

    # --- 3. Preparar los payloads de propiedades para las nuevas páginas de Materiales (DB1 y DB2) ---    
    # NOTA: Los nombres de las propiedades (keys del diccionario 'properties') deben coincidir
    # EXACTAMENTE con los nombres definidos en tus bases de datos de Notion.
    # Asumimos que ambas bases de datos (DB1 y DB2) tienen nombres de propiedades compatibles.

    # Propiedades comunes a ambas bases de datos.
    # Incluir la relación con la Partida encontrada.
    common_properties = {
        "Folio Solicitud": {"rich_text": [{"text": {"content": folio_solicitud}}]},
        "Fecha de Solicitud": {"date": {"start": fecha_solicitud_iso}},
        "Nombre del solicitante": {"rich_text": [{"text": {"content": nombre_solicitante}}]},
        # NOTA: Aquí vinculamos la Partida. Usamos la constante para el nombre de la propiedad Relation.
        # El valor es un array de objetos con el id de la página relacionada.
        NOTION_PROP_MATERIALES_PROYECTO_RELATION: {"relation": [{"id": partida_page_id}]},
        "Cantidad solicitada": {"number": cantidad_solicitada_num},
        "Nombre del material": {"rich_text": [{"text": {"content": nombre_material}}]},
        "Unidad de medida": {"select": {"name": unidad_medida}},
        "Tipo de material": {"rich_text": [{"text": {"content": tipo_material}}]}, # Asumimos que es texto

        # Dimensiones - enviar como texto. Convertir 'N/A' o vacío a null si es necesario,
        # o enviar como string 'N/A' o '' y manejarlo en Notion o reportes.
        # Vamos a enviar "" si está vacío, y "N/A" si se marcó como N/A en el frontend.
        # La función collectFormData ya maneja si enviar "" o "N/A" o el valor.
        # Solo debemos asegurarnos de que el tipo de propiedad en Notion sea Rich Text.
        "Largo": {"rich_text": [{"text": {"content": str(largo) if largo is not None else ""}}]},
        "Ancho": {"rich_text": [{"text": {"content": str(ancho) if ancho is not None else ""}}]},
        "Alto": {"rich_text": [{"text": {"content": str(alto) if alto is not None else ""}}]},
        "Diámetro": {"rich_text": [{"text": {"content": str(diametro) if diametro is not None else ""}}]},

        # Especificaciones adicionales (opcional)
        "Especificaciones adicionales": {"rich_text": [{"text": {"content": especificaciones_adicionales.strip()}}]} if especificaciones_adicionales else None,

        # Checkboxes
        "Urgente": {"checkbox": urgente},
        "Recuperado": {"checkbox": recuperado},

        # Campos fijos para Logística
        "Proveedor": {"rich_text": [{"text": {"content": proveedor_logistica}}]}, # Asumimos texto
        "Departamento/Área": {"rich_text": [{"text": {"content": departamento_logistica}}], "type": "rich_text"}, # Asegurar tipo si es necesario

        # Propiedad de Relación con Usuarios (si aplica y la BD la tiene)
        # Asumimos que hay una propiedad de tipo Relation llamada 'Usuario de la App' que se vincula a la BD de Usuarios.
        # Puedes ajustar el nombre de la propiedad ('Usuario de la App') si es diferente en tu DB de Materiales.
        # La lógica para encontrar la página del usuario en la BD de Usuarios NO está aquí.
        # Si user_id es el ID de la página de Notion del usuario en tu BD de Usuarios:
        "Usuario de la App": {"relation": [{"id": user_id}]},
    }

    # Limpiar propiedades None (como especificaciones_adicionales si está vacío)
    properties_db1 = {k: v for k, v in common_properties.items() if v is not None}
    properties_db2 = {k: v for k, v in common_properties.items() if v is not None}

    # Propiedades específicas de DB1 si las hubiera... (ej. "Estado Solicitud DB1": {"status": {"name": "Pendiente"}})
    # properties_db1["Estado Solicitud"] = {"status": {"name": "Pendiente"}} # Ejemplo

    # Propiedades específicas de DB2 si las hubiera...
    # properties_db2["Otro Campo DB2"] = {"checkbox": False} # Ejemplo


    # --- 4. Crear páginas en ambas bases de datos ---
    url_db1 = None
    url_db2 = None

    # Crear página en DB1
    try:
        logger.info(f"Creando página en DB1 ({database_id_db1}) para Folio: {folio_solicitud}")
        # El título de la página podría ser el Folio o la combinación de Material y Folio
        # Asumimos que el título es una propiedad de tipo 'title', cuyo nombre es 'Folio/Material' o similar.
        # Debes ajustar el nombre de la propiedad 'title' ('Name' por defecto en Notion a veces) si es diferente.
        properties_db1["Name"] = {"title": [{"text": {"content": f"{folio_solicitud} - {nombre_material}"}}]} # Asumir 'Name' es el campo title

        response_db1 = notion_client.pages.create(parent={"database_id": database_id_db1}, properties=properties_db1)
        url_db1 = response_db1.get("url")
        logger.info(f"Página creada exitosamente en DB1. Folio: {folio_solicitud}. URL: {url_db1}")

    except APIResponseError as e:
        logger.error(f"Error API al crear página en DB1 ({database_id_db1}): Código={e.code if hasattr(e, 'code') else 'N/A'} Mensaje={e.message if hasattr(e, 'message') else str(e)} Estado HTTP={e.status if hasattr(e, 'status') else 'N/A'}", exc_info=True)
        notion_response_body = getattr(e, 'response', None)
        notion_error_details = None
        if notion_response_body is not None and hasattr(notion_response_body, 'json'):
             try: notion_error_details = notion_response_body.json()
             except Exception: pass

        # Si falla la creación en DB1, reportar el error. No intentamos crear en DB2 si la primera falla crucialmente.
        return e.status if hasattr(e, 'status') and e.status is not None else 500, { # Fallback a 500
            "error": f"Error al crear registro en base de datos interna de Notion: {e.message if hasattr(e, 'message') else str(e)}",
            "notion_error_details": notion_error_details
        }
    except Exception as e:
        logger.error(f"Error inesperado al crear página en DB1 ({database_id_db1}): {str(e)}", exc_info=True)
        return 500, {"error": f"Error interno del servidor al crear registro: {str(e)}"}


    # Crear página en DB2
    # NOTA: Puedes decidir si la falla en DB2 debe anular el éxito en DB1.
    # Actualmente, si DB1 tiene éxito y DB2 falla, DB1 se queda. Reportamos el error de DB2.
    try:
        logger.info(f"Creando página en DB2 ({database_id_db2}) para Folio: {folio_solicitud}")
        # Asumimos que DB2 tiene la misma estructura de propiedades o compatible.
        # Asegurarse de que el campo 'title' también se llame 'Name' o ajustar.
        properties_db2["Name"] = {"title": [{"text": {"content": f"{folio_solicitud} - {nombre_material}"}}]} # Asumir 'Name' es el campo title

        response_db2 = notion_client.pages.create(parent={"database_id": database_id_db2}, properties=properties_db2)
        url_db2 = response_db2.get("url")
        logger.info(f"Página creada exitosamente en DB2. Folio: {folio_solicitud}. URL: {url_db2}")

    except APIResponseError as e:
        logger.error(f"Error API al crear página en DB2 ({database_id_db2}): Código={e.code if hasattr(e, 'code') else 'N/A'} Mensaje={e.message if hasattr(e, 'message') else str(e)} Estado HTTP={e.status if hasattr(e, 'status') else 'N/A'}", exc_info=True)
        notion_response_body = getattr(e, 'response', None)
        notion_error_details = None
        if notion_response_body is not None and hasattr(notion_response_body, 'json'):
             try: notion_error_details = notion_response_body.json()
             except Exception: pass

        # Si falla la creación en DB2, retornamos un warning y la URL de la página creada en DB1.
        return 201, { # Status 201 (Created) porque al menos una página se creó.
            "warning": f"Solicitud registrada en base de datos interna (DB1), pero hubo un error al registrar en la base de datos externa (DB2): {e.message if hasattr(e, 'message') else str(e)}",
            "notion_url": url_db1, # Retornar la URL de la página creada en DB1
            "notion_error_details": notion_error_details # Opcional: incluir detalles del error de DB2
        }
    except Exception as e:
        logger.error(f"Error inesperado al crear página en DB2 ({database_id_db2}): {str(e)}", exc_info=True)
        # Si falla la creación en DB2, retornamos un warning y la URL de la página creada en DB1.
        return 201, { # Status 201 (Created) porque al menos una página se creó.
            "warning": f"Solicitud registrada en base de datos interna (DB1), pero hubo un error inesperado al registrar en la base de datos externa (DB2): {str(e)}",
            "notion_url": url_db1, # Retornar la URL de la página creada en DB1
            # No hay notion_error_details para errores no APIResponseError
        }

# Añadir esta función a autointelli/notion/utils.py

def find_page_id_by_property_value(notion_client, database_id, property_name, property_value, property_types):
    """
    Busca el ID de una página en una base de datos de Notion basándose en el valor de una propiedad.

    Args:
        notion_client: Instancia del cliente de Notion.
        database_id: ID de la base de datos donde buscar.
        property_name: Nombre de la propiedad a buscar.
        property_value: Valor exacto que debe tener la propiedad.
        property_types: Lista de tipos de propiedad esperados (ej: ['rich_text', 'title']).

    Returns:
        El ID de la página encontrada (el primero que coincida), o None si no se encuentra ninguna.
    """
    # Construir el filtro para la consulta
    # Esta es una simplificación; deberías ajustar la construcción del filtro
    # basándote en los property_types que esperas (ej: text, number, select, etc.)
    # Para rich_text y title, podemos usar el filtro 'contains'.
    # Para otros tipos, podrías necesitar otros filtros (ej: 'equals' para select/number)
    filter_condition = None
    if 'rich_text' in property_types or 'title' in property_types:
         filter_condition = {
             "property": property_name,
             "rich_text": { # O "title" si solo buscas títulos
                 "equals": property_value
             }
         }
    # Aquí podrías añadir lógica para otros tipos de propiedad si es necesario


    if not filter_condition:
        logger.warning(f"No se pudo construir un filtro para la propiedad '{property_name}' con los tipos {property_types}.")
        return None

    try:
        # Realizar la consulta a la base de datos
        response = notion_client.databases.query(
            database_id=database_id,
            filter=filter_condition
        )

        # Si se encontraron resultados, devolver el ID de la primera página
        if response and response.get('results'):
            # logger.debug(f"Encontrada página con ID: {response['results'][0]['id']} para '{property_name}' = '{property_value}'")
            return response['results'][0]['id']
        else:
            logger.warning(f"No se encontró ninguna página en la base de datos '{database_id}' donde la propiedad '{property_name}' sea igual a '{property_value}'.")
            return None

    except Exception as e:
        logger.error(f"Error al buscar página por propiedad '{property_name}' con valor '{property_value}' en base de datos '{database_id}': {e}", exc_info=True)
        return None


    # --- 5. Éxito en la creación de ambas páginas ---
    # Si llegamos aquí, ambas páginas se crearon correctamente.
    return 201, {"message": "Solicitud de material registrada exitosamente en ambas bases de datos.", "notion_url": url_db1, "notion_url_db2": url_db2}