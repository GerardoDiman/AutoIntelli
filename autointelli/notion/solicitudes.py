import logging
from datetime import datetime
from notion_client import Client
from notion_client.errors import APIResponseError
from typing import Optional, Dict, List, Tuple, Any, Union
import json
import traceback # Para el error general

# Importar funciones auxiliares y constantes
from .utils import update_notion_page_properties # submit_request_for_material_logic usa create_page indirectamente via client, y update_page_properties (no se usa aquí)
from .proyectos import find_project_page_by_property_value # Importa la búsqueda de proyecto desde el nuevo módulo de proyectos

from .constants import ( # Importa todas las constantes de propiedades que necesita
    NOTION_PROP_FOLIO,
    NOTION_PROP_SOLICITANTE,
    NOTION_PROP_FECHA_SOLICITUD,
    NOTION_PROP_PROVEEDOR,
    NOTION_PROP_DEPARTAMENTO,
    NOTION_PROP_URGENTE, # <<< Importante importar esta constante
    NOTION_PROP_RECUPERADO,
 # <<< Importante importar esta constante
    NOTION_PROP_MATERIALES_PROYECTO_RELATION,
    NOTION_PROP_ESPECIFICACIONES,
    NOTION_PROP_CANTIDAD,
    NOTION_PROP_TIPO_MATERIAL,
    NOTION_PROP_NOMBRE_MATERIAL,
    NOTION_PROP_UNIDAD_MEDIDA,
    NOTION_PROP_LARGO,
    NOTION_PROP_ANCHO,
    NOTION_PROP_ALTO,
    NOTION_PROP_DIAMETRO,
    NOTION_PROP_TORNI_ID,
    NOTION_PROP_TORNI_DESCRIPTION,
    NOTION_PROP_PROYECTO_BUSQUEDA_ID, # Necesita esta constante para pasarla a find_project_page_by_property_value
)


logger = logging.getLogger(__name__)

# --- Lógica para Solicitudes de Materiales (FINAL CON RELATION DE PROYECTO Y CHECKBOX URGENTE) ---

def submit_request_for_material_logic(
        notion_client: Client,
        database_id_db1: str, # ID de la primera BD de Materiales
        database_id_db2: str, # ID de la segunda BD de Materiales
        database_id_proyectos: str, # ID de la BD de Proyectos para la Relation
        data: Dict, # Diccionario con los datos de la solicitud del frontend
        user_id: Optional[int] = None # Opcional: ID del usuario para logging/trazabilidad
    ) -> Tuple[Dict, int]:

    # Inicializa un prefijo básico de log. Se actualizará si se obtiene o genera un folio.
    user_log_prefix = f"[User ID: {user_id or 'N/A'}] Folio: N/A"
    logger.info(f"{user_log_prefix} Iniciando procesamiento de solicitud de material.")

    logger.debug(f"{user_log_prefix}: Datos de solicitud recibidos: {json.dumps(data, ensure_ascii=False)}")

    try:
        # 1. Validaciones iniciales y obtención/generación de Folio
        folio_solicitud = data.get("folio_solicitud")
        if not folio_solicitud:
             # Genera un folio simple si el frontend no lo proporcionó (fallback)
             folio_solicitud = f"EMG-BE-{datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]}"
             logger.warning(f"{user_log_prefix} Folio de solicitud no recibido del frontend. Generando fallback: {folio_solicitud}")

        # Actualiza el prefijo de log con el folio para trazabilidad
        user_log_prefix = f"[User ID: {user_id or 'N/A'}] Folio: {folio_solicitud}"
        logger.info(f"{user_log_prefix} Prefijo de log actualizado.")

        # Validar IDs de bases de datos esenciales
        if not notion_client or not database_id_db1 or not database_id_db2 or not database_id_proyectos:
             error_msg = "La integración con Notion para Solicitudes o Proyectos no está configurada correctamente en el servidor (IDs o cliente Notion faltante)."
             logger.error(f"{user_log_prefix} {error_msg}")
             # Este es un problema de configuración del backend, no de la solicitud del usuario.
             return {"error": error_msg, "folio_solicitud": folio_solicitud}, 503 # Service Unavailable


        if not isinstance(data, dict) or not data:
            logger.warning(f"{user_log_prefix} No se recibieron datos válidos (diccionario no vacío) en submit_request_for_material_logic.")
            return {"error": "No se recibieron datos válidos en la solicitud.", "folio_solicitud": folio_solicitud}, 400 # Bad Request


        selected_proveedor = data.get("proveedor")
        is_torni_mode = selected_proveedor == 'Torni' # Determinar si se procesa en modo Torni


        # 2. Manejar la propiedad del Proyecto (buscar ID y preparar Relation)
        proyecto_valor_frontend = data.get("proyecto", "") # Valor ingresado en el formulario para identificar el proyecto
        project_page_id = None # Variable para guardar el ID de la página de proyecto encontrada

        # Busca la página del proyecto si se proporcionó un valor en el frontend Y el ID de la BD de Proyectos está configurado.
        if proyecto_valor_frontend and database_id_proyectos:
             logger.info(f"{user_log_prefix}: Buscando ID de página para proyecto: '{proyecto_valor_frontend}' usando propiedad '{NOTION_PROP_PROYECTO_BUSQUEDA_ID}' en BD Proyectos '{database_id_proyectos}'...")
             project_page_id = find_project_page_by_property_value(
                 notion_client,
                 database_id_proyectos,
                 NOTION_PROP_PROYECTO_BUSQUEDA_ID, # Nombre de la propiedad en la BD de Proyectos para buscar (definido en constantes)
                 proyecto_valor_frontend # El valor ingresado por el usuario
             )
             if project_page_id:
                  logger.info(f"{user_log_prefix}: ID de página de proyecto encontrado: {project_page_id}")
             else:
                  logger.warning(f"{user_log_prefix}: No se encontró página de proyecto para '{proyecto_valor_frontend}'. La propiedad Relation '{NOTION_PROP_MATERIALES_PROYECTO_RELATION}' en las páginas de Notion quedará vacía.")

        # Prepara el payload para la propiedad Relation 'Proyecto' que se usará en las páginas de materiales
        # Se añadirá a common_properties. Si no se encontró project_page_id, será una Relation vacía.
        project_relation_property_payload = {"relation": []} # Relación vacía por defecto (formato API Notion)
        if project_page_id:
            # Si se encontró un ID de página de proyecto, crea el payload de Relation con ese ID
            project_relation_property_payload = {"relation": [{"id": project_page_id}]}
        # common_properties se inicializará más abajo e incluirá esto.


        # 3. Inicializar common_properties (Propiedades que aplican a toda la solicitud/todos los items)
        # Estas propiedades se incluirán en CADA página creada para cada item.
        common_properties = {}

        # Folio (Generalmente Rich Text o Title)
        if folio_solicitud:
             # Asegúrate de usar el tipo de propiedad correcto para el Folio. Si es Rich Text:
             common_properties[NOTION_PROP_FOLIO] = {"rich_text": [{"type": "text", "text": {"content": folio_solicitud}}]}

        # Añadir la propiedad Relation del Proyecto (usando la constante correcta para la DB de Materiales)
        common_properties[NOTION_PROP_MATERIALES_PROYECTO_RELATION] = project_relation_property_payload
        logger.debug(f"{user_log_prefix}: Propiedad Relation de Proyecto agregada a common_properties.")

        # 4. Añadir la propiedad URGENTE (Checkbox) a common_properties
        # Obtener el valor del campo 'es_urgente' del diccionario data. Asumimos que la clave es 'es_urgente'.
        es_urgente_value_raw = data.get("urgente", False) # Default a False si la clave no existe

        # Convertir el valor a booleano de forma robusta para manejar varios tipos de entrada
        is_urgent_bool = False # Valor booleano final para la propiedad Checkbox
        if isinstance(es_urgente_value_raw, bool):
            is_urgent_bool = es_urgente_value_raw # Si ya es booleano (ej. de JSON)
        elif isinstance(es_urgente_value_raw, str):
             # Convierte strings como "true", "false", "1", "0" a booleano (case-insensitive)
             is_urgent_bool = es_urgente_value_raw.lower() in ['true', 'yes', 'on', '1']
        elif isinstance(es_urgente_value_raw, (int, float)):
             # Convierte números: 0 es False, cualquier otro número es True
             is_urgent_bool = bool(es_urgente_value_raw)
        # Para None u otros tipos, is_urgent_bool se queda en su valor inicial False.

        # Añadir la propiedad 'Urgente' a common_properties con el valor booleano resultante
        # Usa la constante NOTION_PROP_URGENTE para el nombre de la propiedad Checkbox en Notion
        common_properties[NOTION_PROP_URGENTE] = {"checkbox": is_urgent_bool}
        logger.info(f"{user_log_prefix}: Propiedad '{NOTION_PROP_URGENTE}' (Checkbox) agregada a common_properties con valor: {is_urgent_bool}")

        # 5. Añadir la propiedad RECUPERADO (Checkbox) a common_properties
        # Obtener el valor del campo 'recuperado' del diccionario data. Asumimos que la clave es 'recuperado'.
        recuperado_value_raw = data.get("recuperado", False) # Default a False si la clave no existe

        # Convertir el valor a booleano de forma robusta para manejar varios tipos de entrada (igual que urgente)
        is_recuperado_bool = False # Valor booleano final para la propiedad Checkbox
        if isinstance(recuperado_value_raw, bool):
            is_recuperado_bool = recuperado_value_raw # Si ya es booleano (ej. de JSON)
        elif isinstance(recuperado_value_raw, str):
             # Convierte strings como "true", "false", "1", "0" a booleano (case-insensitive)
             is_recuperado_bool = recuperado_value_raw.lower() in ['true', 'yes', 'on', '1']
        elif isinstance(recuperado_value_raw, (int, float)):
             # Convierte números: 0 es False, cualquier otro número es True
             is_recuperado_bool = bool(recuperado_value_raw)
        # Para None u otros tipos, is_recuperado_bool se queda en su valor inicial False.

        # Añadir la propiedad 'Recuperado' a common_properties con el valor booleano resultante
        # Usa la constante NOTION_PROP_RECUPERADO para el nombre de la propiedad Checkbox en Notion
        common_properties[NOTION_PROP_RECUPERADO] = {"checkbox": is_recuperado_bool}
        logger.info(f"{user_log_prefix}: Propiedad '{NOTION_PROP_RECUPERADO}' (Checkbox) agregada a common_properties con valor: {is_recuperado_bool}")
        # <<< FIN DE ADICIÓN PARA CHECKBOX RECUPERADO >>>



        # 5. Añadir las propiedades comunes restantes del diccionario data
        # Solicitante, Proveedor, Departamento/Área (ASUMIMOS SELECT)
        solicitante_val = data.get("nombre_solicitante", "")
        if solicitante_val:
            # Asegurarse de enviar el nombre de la opción Select en el formato correcto {"name": "Nombre Opcion"}
            common_properties[NOTION_PROP_SOLICITANTE] = {"select": {"name": solicitante_val}}
        # Si la propiedad Select es obligatoria en Notion y permites enviar vacío, descomenta:
        # elif NOTION_PROP_SOLICITANTE: common_properties[NOTION_PROP_SOLICITANTE] = {"select": None}


        proveedor_val = selected_proveedor or "" # selected_proveedor ya fue determinado antes
        if proveedor_val:
             common_properties[NOTION_PROP_PROVEEDOR] = {"select": {"name": proveedor_val}}
        # Si la propiedad Select es obligatoria en Notion y permites enviar vacío, descomenta:
        # elif NOTION_PROP_PROVEEDOR: common_properties[NOTION_PROP_PROVEEDOR] = {"select": None}


        departamento_val = data.get("departamento_area", "")
        if departamento_val:
             common_properties[NOTION_PROP_DEPARTAMENTO] = {"select": {"name": departamento_val}}
        # Si la propiedad Select es obligatoria en Notion y permites enviar vacío, descomenta:
        # elif NOTION_PROP_DEPARTAMENTO: common_properties[NOTION_PROP_DEPARTamento] = {"select": None}


        # Fecha de solicitud (Date)
        fecha_solicitud_str = data.get("fecha_solicitud")
        if fecha_solicitud_str:
             try:
                 # Validar que es un formato de fecha/datetime ISO válido antes de añadir.
                 # Notion Date property expects ISO 8601 (YYYY-MM-DD or YYYY-MM-DDTHH:mm:ss.sssZ etc)
                 datetime.fromisoformat(fecha_solicitud_str.replace('Z', '+00:00')) # Intentar parsear para validar
                 # Si la validación es exitosa, añadir al payload. Si es solo fecha AAAA-MM-DD, Notion lo acepta.
                 common_properties[NOTION_PROP_FECHA_SOLICITUD] = {"date": {"start": fecha_solicitud_str}}
             except ValueError:
                 logger.warning(f"{user_log_prefix} Fecha de solicitud en formato inválido '{fecha_solicitud_str}'. Se esperaba formato ISO 8601. No se añadirá la propiedad de fecha a Notion.")
                 # Opcional: Si la propiedad fecha es requerida en Notion pero permite null, puedes enviar:
                 # if NOTION_PROP_FECHA_SOLICITUD: common_properties[NOTION_PROP_FECHA_SOLICITUD] = {"date": None}
                 pass # Si la propiedad es opcional en Notion o el frontend valida, no hacer nada es suficiente.

        # Especificaciones adicionales (Opcional, Rich Text)
        especificaciones_val = data.get("especificaciones_adicionales", "")
        if especificaciones_val:
             common_properties[NOTION_PROP_ESPECIFICACIONES] = {"rich_text": [{"type": "text", "text": {"content": especificaciones_val}}]}

        items_to_process_list = []
        if is_torni_mode:
             torni_items_list_from_data = data.get('torni_items', [])
             if not isinstance(torni_items_list_from_data, list):
                  logger.error(f"{user_log_prefix}: Se esperaba una lista para 'torni_items', pero se recibió {type(torni_items_list_from_data)}. No se procesarán items Torni.")
                  # Podrías considerar esto un error fatal si no hay items esperados
                  # return {"error": "Datos de productos Torni inválidos recibidos. Se esperaba una lista."}, 400 # Bad Request
                  pass # Continuar para reportar 0 items procesados si no hay lista válida

             # Validar mínimamente cada item Torni
             valid_torni_items = []
             for idx, item in enumerate(torni_items_list_from_data):
                  # Requisitos mínimos: quantity (num), id (str/num). Description puede ser opcional.
                  quantity = item.get("quantity")
                  item_id = item.get("id")

                  # Check quantity is number > 0 (assuming >0 is required for a valid item)
                  is_quantity_valid = isinstance(quantity, (int, float)) and quantity > 0 # Validar > 0
                  is_id_valid = item_id is not None and str(item_id).strip() != ""

                  if not is_quantity_valid or not is_id_valid:
                       # Loggea un warning por item inválido en la lista
                       logger.warning(f"{user_log_prefix}: Item Torni inválido/incompleto en índice {idx}. Datos: {item}. Requisitos mínimos: quantity (num > 0), id (non-empty). Omitiendo este item.")
                       continue # Saltar este item inválido

                  valid_torni_items.append(item) # Añadir solo items válidos

             items_to_process_list = valid_torni_items

        else: # Proveedor estándar
             # En modo estándar, solo hay UN item principal.
             # Verificamos si hay suficientes datos para considerar que hay un item estándar válido.
             # Criterio: ¿Tiene una cantidad *válida* O un nombre/tipo de material? (Puede ser 0 cantidad a veces).
             cantidad_estandar = data.get('cantidad_solicitada')
             tiene_cantidad_valida_o_cero = isinstance(cantidad_estandar, (int, float)) and cantidad_estandar >= 0
             tiene_material_identificado = data.get('nombre_material') is not None and str(data.get('nombre_material')).strip() != ""
             tiene_tipo_material = data.get('tipo_material') is not None and str(data.get('tipo_material')).strip() != ""

             # Consideramos que hay un item si tiene una cantidad numérica VÁLIDA (incluso 0)
             # O si tiene al menos el nombre o el tipo de material especificado.
             # El frontend debería asegurar los campos obligatorios, esto es un fallback de validación aquí.
             if tiene_cantidad_valida_o_cero or tiene_material_identificado or tiene_tipo_material:
                items_to_process_list = [data] # Procesar el diccionario 'data' principal como el único item
             else:
                 logger.warning(f"{user_log_prefix}: Diccionario 'data' estándar sin campos de item principal (cantidad numérica válida, nombre material, o tipo material). No se procesará ningún item estándar.")


        if not items_to_process_list:
             logger.warning(f"{user_log_prefix}: Después de validación, no hay items válidos para procesar.")
             # Si no hay items que procesar (ni Torni válidos ni Standard detectado), es un error 400 del usuario.
             return {"error": "No se encontraron items de material válidos para procesar en la solicitud. Asegúrate de llenar la información del material correctamente.", "folio_solicitud": folio_solicitud}, 400 # Bad Request


        logger.info(f"{user_log_prefix}: Items finales a procesar ({'Torni' if is_torni_mode else 'Estándar'}): {len(items_to_process_list)}")

        # Contadores para el resumen final
        items_processed_count = 0
        items_failed_count = 0
        # URLs para mostrar en la respuesta (la primera página creada con éxito en cada DB)
        first_page_total_success_url1 = None
        first_page_total_success_url2 = None


        # 7. Iterar sobre la lista FINAL de items y crear una página en cada DB de Notion por cada item
        for index, item_data in enumerate(items_to_process_list):
            # Prefix para logs específicos de este item
            item_log_prefix = f"{user_log_prefix} [Item {index + 1}]"
            logger.info(f"{item_log_prefix}: --- Procesando item ---")

            # Copiar propiedades comunes (Folio, Relation Proyecto, Urgente, Solicitante, etc.)
            # Cada página de item comienza con estas propiedades generales de la solicitud.
            item_properties_payload = common_properties.copy();

            # --- 8. Construir Propiedades ESPECÍFICAS para este item ---
            # Extraer los valores relevantes del item_data (depende si es modo Torni o estándar)
            if is_torni_mode:
                 # Propiedades específicas de Torni items
                 item_quantity_val = item_data.get('quantity')
                 item_id_torni = item_data.get("id", "")
                 item_desc_torni = item_data.get("description", "")

                 # Cantidad (Number)
                 cantidad_num_val = None
                 if item_quantity_val is not None and str(item_quantity_val).strip() != "":
                      try: cantidad_num_val = float(str(item_quantity_val).strip())
                      except (ValueError, TypeError):
                           logger.warning(f"{item_log_prefix}: Cantidad '{item_quantity_val}' no es numérica válida. Se enviará null a Notion.")
                           cantidad_num_val = None
                 if cantidad_num_val is not None:
                      item_properties_payload[NOTION_PROP_CANTIDAD] = {"number": cantidad_num_val}

                 # ID y Descripción de Torni (Rich Text)
                 if item_id_torni:
                      item_properties_payload[NOTION_PROP_TORNI_ID] = {"rich_text": [{"type": "text", "text": {"content": str(item_id_torni).strip()}}]}
                 if item_desc_torni:
                      item_properties_payload[NOTION_PROP_TORNI_DESCRIPTION] = {"rich_text": [{"type": "text", "text": {"content": str(item_desc_torni).strip()}}]}

                 # Propiedades estándar que no aplican a Torni o vienen de forma diferente se omiten aquí.
                 # NOTA: Asegúrate de que las propiedades Torni (ID, Descripción) existan en ambas DBs de Materiales (DB1 y DB2)
                 # si estás creando páginas para cada item en ambas, o ajusta la lógica si solo van a una DB.
                 # El código actual las incluye en el payload para AMBAS DBs.


            else: # Modo Estándar (single item, properties from main data dict)
                 # Propiedades específicas del item estándar
                 item_quantity_val = item_data.get("cantidad_solicitada")
                 tipo_material = item_data.get("tipo_material", "")
                 nombre_material = item_data.get("nombre_material", "")
                 unidad_medida = item_data.get("unidad_medida", "")
                 largo = item_data.get("largo")
                 ancho = item_data.get("ancho")
                 alto = item_data.get("alto")
                 diametro = item_data.get("diametro")

                 # Cantidad (Number)
                 cantidad_num_val = None
                 if item_quantity_val is not None and str(item_quantity_val).strip() != "":
                      try: cantidad_num_val = float(str(item_quantity_val).strip())
                      except (ValueError, TypeError):
                           logger.warning(f"{item_log_prefix}: Cantidad '{item_quantity_val}' no es numérica válida. Se enviará null a Notion.")
                           cantidad_num_val = None
                 if cantidad_num_val is not None:
                      item_properties_payload[NOTION_PROP_CANTIDAD] = {"number": cantidad_num_val}

                 # Tipo de material, Nombre de material, Unidad de medida (ASUMIDO SELECT)
                 if tipo_material: item_properties_payload[NOTION_PROP_TIPO_MATERIAL] = {"select": {"name": tipo_material}}
                 if nombre_material: item_properties_payload[NOTION_PROP_NOMBRE_MATERIAL] = {"select": {"name": nombre_material}}
                 if unidad_medida: item_properties_payload[NOTION_PROP_UNIDAD_MEDIDA] = {"select": {"name": unidad_medida}}

                 # Dimensiones (ASUMIDO RICH TEXT)
                 if largo is not None and str(largo).strip() != "":
                      item_properties_payload[NOTION_PROP_LARGO] = {"rich_text": [{"type": "text", "text": {"content": str(largo).strip()}}]}
                 if ancho is not None and str(ancho).strip() != "":
                      item_properties_payload[NOTION_PROP_ANCHO] = {"rich_text": [{"type": "text", "text": {"content": str(ancho).strip()}}]}
                 if alto is not None and str(alto).strip() != "":
                      item_properties_payload[NOTION_PROP_ALTO] = {"rich_text": [{"type": "text", "text": {"content": str(alto).strip()}}]}
                 if diametro is not None and str(diametro).strip() != "":
                      item_properties_payload[NOTION_PROP_DIAMETRO] = {"rich_text": [{"type": "text", "text": {"content": str(diametro).strip()}}]}

            # 9. Crear página en DB 1 (Materiales)
            page1_created = False; page1_url_current = None; error1_info = {}
            try:
                logger.info(f"{item_log_prefix}: Intentando crear página en DB 1 Materiales ({database_id_db1})...")
                # La creación de página requiere un parent con database_id y las properties
                response1 = notion_client.pages.create(parent={"database_id": database_id_db1}, properties=item_properties_payload)
                page1_url_current = response1.get("url")
                # Guarda la URL del primer item creado con ÉXITO en DB1 para la respuesta final
                if first_page_total_success_url1 is None and page1_url_current:
                     first_page_total_success_url1 = page1_url_current

                logger.info(f"{item_log_prefix}: Página creada con éxito en DB 1: {page1_url_current}")
                page1_created = True
            except APIResponseError as e1:
                 # Captura errores específicos de la API de Notion
                 api_error_msg = e1.message if hasattr(e1, 'message') else str(e1)
                 notion_response_body = getattr(e1, 'response', None)
                 notion_error_details = None
                 if notion_response_body is not None and hasattr(notion_response_body, 'json'):
                      try: notion_error_details = notion_response_body.json()
                      except Exception: pass # No fallar si no se puede parsear el JSON del error API

                 logger.error(f"{item_log_prefix}: ERROR API en DB 1 Materiales: Código={e1.code if hasattr(e1, 'code') else 'N/A'} Mensaje={api_error_msg} Estado HTTP={e1.status if hasattr(e1, 'status') else 'N/A'}", exc_info=True)
                 if notion_error_details: logger.error(f"{item_log_prefix}: Detalles adicionales del error de Notion (DB 1): {json.dumps(notion_error_details, ensure_ascii=False)}")
                 error1_info = {"code": e1.code if hasattr(e1, 'code') else 'N/A', "message": api_error_msg, "http_status": e1.status if hasattr(e1, 'status') else 'N/A', "notion_error_details": notion_error_details}
            except Exception as e1:
                 # Captura otros errores inesperados durante la creación en DB1
                 logger.error(f"{item_log_prefix}: ERROR inesperado en DB 1 Materiales: {e1}", exc_info=True)
                 error1_info = {"message": str(e1)}


            # 10. Crear página en DB 2 (Materiales) - Proceso similar a DB1
            page2_created = False; page2_url_current = None; error2_info = {}
            try:
                logger.info(f"{item_log_prefix}: Intentando crear página en DB 2 Materiales ({database_id_db2})...")
                response2 = notion_client.pages.create(parent={"database_id": database_id_db2}, properties=item_properties_payload)
                page2_url_current = response2.get("url")
                # Guarda la URL del primer item creado con ÉXITO en DB2
                if first_page_total_success_url2 is None and page2_url_current:
                     first_page_total_success_url2 = page2_url_current

                logger.info(f"{item_log_prefix}: Página creada con éxito en DB 2: {page2_url_current}")
                page2_created = True
            except APIResponseError as e2:
                 api_error_msg = e2.message if hasattr(e2, 'message') else str(e2)
                 notion_response_body = getattr(e2, 'response', None)
                 notion_error_details = None
                 if notion_response_body is not None and hasattr(notion_response_body, 'json'):
                      try: notion_error_details = notion_response_body.json()
                      except Exception: pass

                 logger.error(f"{item_log_prefix}: ERROR API en DB 2 Materiales: Código={e2.code if hasattr(e2, 'code') else 'N/A'} Mensaje={api_error_msg} Estado HTTP={e2.status if hasattr(e2, 'status') else 'N/A'}", exc_info=True)
                 if notion_error_details: logger.error(f"{item_log_prefix}: Detalles adicionales del error de Notion (DB 2): {json.dumps(notion_error_details, ensure_ascii=False)}")
                 error2_info = {"code": e2.code if hasattr(e2, 'code') else 'N/A', "message": api_error_msg, "http_status": e2.status if hasattr(e2, 'status') else 'N/A', "notion_error_details": notion_error_details}

            except Exception as e2:
                 logger.error(f"{item_log_prefix}: ERROR inesperado en DB 2 Materiales: {e2}", exc_info=True)
                 error2_info = {"message": str(e2)}


            # 11. Contar items procesados con éxito (en ambas DBs) y fallidos
            if page1_created and page2_created:
                items_processed_count += 1
                logger.info(f"{item_log_prefix} procesado con éxito en AMBAS DBs.")
            else:
                 items_failed_count += 1
                 # Registrar detalles resumidos del fallo
                 error_details_summary = {
                     "item_index": index + 1,
                     "item_identifier": item_data.get('id', item_data.get('nombre_material', 'Desconocido Item')), # Identificador del item
                     "db1_success": page1_created, "db1_error": error1_info,
                     "db2_success": page2_created, "db2_error": error2_info,
                     # Puedes añadir más info del item aquí si es útil para depurar
                     # "proveedor": selected_proveedor, "cantidad": item_quantity_val, "es_urgente": is_urgent_bool
                 }
                 logger.error(f"{item_log_prefix} falló al procesar en una o ambas DBs. Resumen de errores: {json.dumps(error_details_summary, ensure_ascii=False)}")
                 # Opcional: Loggear el payload completo que causó el fallo (muy verbose)
                 # logger.debug(f"{item_log_prefix}: Payload que causó el fallo: {json.dumps(item_properties_payload, ensure_ascii=False, indent=2)}")


        # --- Fin del bucle for sobre items ---

        # 12. Construir Respuesta Final
        final_response = {"folio_solicitud": folio_solicitud}
        status_code_return = 200 # Default: Éxito
        total_items_intended = len(items_to_process_list)

        # Incluir las URLs del primer item que se creó exitosamente (si alguno lo hizo)
        if first_page_total_success_url1:
             final_response["notion_url_db1"] = first_page_total_success_url1
        if first_page_total_success_url2:
             final_response["notion_url_db2"] = first_page_total_success_url2


        if items_processed_count == total_items_intended:
             # Todos los items se procesaron correctamente en ambas DBs
             final_response["message"] = f"Solicitud Folio '{folio_solicitud}' ({items_processed_count}/{total_items_intended} item(s)) registrada con éxito en ambas Bases de Datos de Notion."
             status_code_return = 200

        elif items_processed_count > 0 and items_failed_count > 0:
             # Algunos items tuvieron éxito, otros fallaron
             final_response["warning"] = f"Folio '{folio_solicitud}' procesado parcialmente: {items_processed_count}/{total_items_intended} item(s) registrados OK, {items_failed_count} fallaron."
             final_response["message"] = "Algunos items fueron registrados con éxito. Consulta los logs del servidor para identificar los fallidos." # Mensaje más claro para el usuario
             final_response["failed_count"] = items_failed_count
             final_response["processed_count"] = items_processed_count
             status_code_return = 207 # Partial Content (Multi-Status)

        else: # items_processed_count == 0 (Ningún item se creó con éxito en ambas DBs)
             final_response["error"] = f"Error al procesar Folio '{folio_solicitud}'. Ningún item registrado con éxito en ambas Bases de Datos."
             final_response["message"] = "No se pudo registrar ningún item. Revisa los logs del servidor para detalles sobre los fallos."
             final_response["failed_count"] = items_failed_count
             final_response["processed_count"] = items_processed_count # Esto será 0 aquí
             # Si había items que intentar procesar (total_items_intended > 0) pero todos fallaron
             status_code_return = 500 # Error interno (el backend falló al comunicarse con Notion para todos los items)


        logger.info(f"{user_log_prefix}: Procesamiento de Materiales completado. Resultado general: Status {status_code_return}, Items procesados: {items_processed_count}, Fallidos: {items_failed_count}")
        return final_response, status_code_return


    except Exception as e:
        # Captura cualquier error inesperado no manejado por los bloques try/except internos
        error_message = f"Error inesperado de servidor al procesar la solicitud de Materiales para el Folio '{folio_solicitud}': {str(e)}"
        full_trace = traceback.format_exc() # Captura el traceback completo
        # Intenta incluir el prefijo de log si ya se ha definido
        current_log_prefix = user_log_prefix if 'user_log_prefix' in locals() else f"[User ID: {user_id or 'N/A'}] Folio: N/A (Antes de definir Folio)"
        logger.error(f"--- {current_log_prefix} ERROR FATAL INESPERADO en submit_request_for_material_logic --- Exception: {e}\n{full_trace}")
        # Intenta obtener el folio para la respuesta, incluso si la variable local fallo
        folio_para_respuesta = data.get('folio_solicitud', "No asignado (Error Fatal)") if 'data' in locals() and isinstance(data, dict) else "No asignado (Error Fatal)"

        return {
            "error": error_message,
            "folio_solicitud": folio_para_respuesta,
            "status_code": 500, # Internal Server Error
            # Opcional: incluir traceback en la respuesta si es para depuración interna
            # "trace": full_trace
        }, 500