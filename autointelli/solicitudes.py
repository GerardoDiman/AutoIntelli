# autointelli/solicitudes.py

from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_required, current_user # Necesitas current_user
from .notion.solicitudes import submit_request_for_material_logic
from .notion.utils import list_available_properties
from .decorators import role_required

import logging

# Configurar logger para este módulo
logger = logging.getLogger(__name__)

# Crear el Blueprint. Prefijo /solicitudes para todas las rutas definidas aquí.
solicitudes_bp = Blueprint('solicitudes', __name__, url_prefix='/solicitudes')

@solicitudes_bp.route('/')
@login_required # Asegura que solo usuarios logueados pueden acceder
@role_required(['logistica', 'admin']) # Asegura que solo usuarios con estos roles pueden acceder
def standard_material_request_page():
    """
    Renderiza la página del formulario estándar de solicitud de materiales.
    Pasa el nombre completo del usuario logueado a la plantilla.
    """
    # El user_loader de Flask-Login carga el objeto User y lo asigna a current_user
    # Asumiendo que tu modelo User tiene la propiedad 'full_name'
    # Verifica que el usuario está autenticado antes de intentar acceder a full_name
    # (login_required ya hace esto, pero es una buena práctica defensive coding)
    current_user_full_name = ""
    if current_user.is_authenticated and hasattr(current_user, 'full_name'):
        current_user_full_name = current_user.full_name
    # else: current_user_full_name seguirá siendo "" si current_user no está autenticado o no tiene full_name

    logger.info(f"[{current_user.username if current_user.is_authenticated else 'Unauthenticated'}] Solicitud GET recibida en /solicitudes/ (Formulario Estándar). Pasando nombre: '{current_user_full_name}'")

    # Renderiza la plantilla HTML del formulario estándar.
    # Pasa la variable con el nombre completo del usuario a la plantilla.
    return render_template('solicitudes/standard_request_form.html',
                           current_user_full_name=current_user_full_name) # <<<< Pasando la variable a la plantilla


@solicitudes_bp.route('/submit_standard', methods=['POST'])
@login_required # Requiere que el usuario esté logueado para enviar el formulario
@role_required(['logistica', 'admin']) # Requiere roles específicos para enviar
def submit_standard_request():
    """
    Maneja la solicitud POST del formulario estándar de solicitud de materiales.
    Recibe los datos del frontend, valida, busca proyecto en Notion (si aplica),
    y llama a la lógica principal para crear registros en las DBs de Materiales en Notion.
    """
    logger.info(f"[{current_user.username if current_user.is_authenticated else 'Unauthenticated'}] Recibiendo solicitud de Materiales Estándar en /solicitudes/submit_standard")

    # Obtener el cliente Notion y los IDs de DB desde la configuración de Flask
    # Estos IDs DEBEN estar configurados en tu app.config (ej. en config.py)
    notion_client = current_app.notion_client
    database_id_db1 = current_app.config.get('DATABASE_ID_MATERIALES_DB1')
    database_id_db2 = current_app.config.get('DATABASE_ID_MATERIALES_DB2')
    # Obtener ID de la BD de Partidas de la configuración
    database_id_partidas = current_app.config.get('DATABASE_ID_PARTIDAS')
    database_id_proyectos = current_app.config.get('DATABASE_ID_PROYECTOS') # Obtener ID de la BD de Proyectos


    # *** VALIDACIÓN DE IDs DE BASE DE DATOS Y CLIENTE NOTION ***
    # Si alguno de los IDs de bases de datos necesarios o el cliente Notion no está configurado,
    # no podemos procesar la solicitud relacionada con Notion.
    if notion_client is None or not database_id_db1 or not database_id_db2 or not database_id_partidas: # <<<< Incluye database_id_partidas en la verificación
        error_msg = "La integración con Notion para Solicitudes o Partidas no está configurada correctamente (IDs de bases de datos o cliente Notion faltantes)."
        logger.error(f"[{current_user.username if current_user.is_authenticated else 'Unauthenticated'}] {error_msg}. IDs: DB1='{database_id_db1}', DB2='{database_id_db2}', Partidas='{database_id_partidas}'")
        # Devolver un error 503 (Service Unavailable) indica un problema del servidor/configuración
        return jsonify({"error": error_msg}), 503


    # Obtener los datos JSON enviados en el cuerpo de la solicitud POST
    data = request.get_json()

    # --- DEBUG: Log de los datos JSON recibidos en la ruta Flask ---
    current_app.logger.debug(f"[{current_user.username if current_user.is_authenticated else 'Unauthenticated'}] Datos JSON recibidos para solicitud estándar en ruta Flask: {data}")
    # --- Fin Debugging ---


    # Validar que se recibieron datos JSON en absoluto
    if not data:
        logger.warning(f"[{current_user.username if current_user.is_authenticated else 'Unauthenticated'}] No se recibieron datos JSON en submit_standard_request (body vacío o no JSON).")
        return jsonify({"error": "No se recibieron datos en el formato esperado."}), 400 # Bad Request


    # --- Validaciones backend mínimas de campos requeridos ---
    # Hacemos una validación básica de campos esenciales aquí,
    # pero la validación detallada de dimensiones, conflictos y existencia del proyecto
    # se realiza dentro de la lógica principal en notion_utils.py.
    # La validación frontend con JavaScript ya proporciona retroalimentación visual al usuario,
    # pero la validación backend es una capa de seguridad crucial.
    # 'proveedor', 'departamento_area' vienen de campos ocultos definidos en HTML y JS, asumidos presentes.
    # 'fecha_solicitud' es un campo readonly llenado por JS, asumido presente.
    # 'tipo_material' es llenado por JS basándose en el material, asumido presente si nombre_material no está vacío.
    # 'proyecto' se valida la existencia en Notion dentro de submit_request_for_material_logic.
    # 'especificaciones_adicionales' es opcional.
    # Campos que esperamos recibir y no deberían estar completamente vacíos/nulos del frontend
    required_fields_basic = ['nombre_solicitante', 'cantidad_solicitada', 'nombre_material', 'unidad_medida', 'partida'] # Incluimos partida aquí para asegurar que al menos se envió algo

    missing_fields_basic = []

    for field in required_fields_basic:
        value = data.get(field)
        # Check for None or empty string after strip.
        # Note: Para campos numéricos o Selects que deberían tener un valor, value podría ser None o 0/""
        if value is None or (isinstance(value, str) and not value.strip()):
             missing_fields_basic.append(field)

    # Validación específica para cantidad solicitada: debe ser un número mayor que 0 si está presente.
    # get() devuelve None si la clave no existe, o el valor. CollectFormData en JS envía float o null.
    cantidad = data.get('cantidad_solicitada')
    if cantidad is not None and (not isinstance(cantidad, (int, float)) or cantidad <= 0):
        # Si cantidad ya se marcó como faltante, removemos ese mensaje y añadimos el específico.
        if 'cantidad_solicitada' in missing_fields_basic:
            missing_fields_basic.remove('cantidad_solicitada')
            missing_fields_basic.append('cantidad_solicitada (debe ser un número > 0)')


    if missing_fields_basic:
        error_msg = f"Faltan campos obligatorios o son inválidos: {', '.join(missing_fields_basic)}".replace('proyecto', 'partida') # Reemplaza 'proyecto' por 'partida' en el mensaje de error
        # --- LÍNEA MODIFICADA PARA MAYOR ROBUSTEZ EN EL LOG ---
        log_message = f"[{current_user.username if current_user.is_authenticated else 'Unauthenticated'}] {error_msg}. "
        log_message += "Datos recibidos: " + json.dumps(data, ensure_ascii=False)
        logger.warning(log_message)
        # --- FIN LÍNEA MODIFICADA ---
        return jsonify({"error": error_msg}), 400 # Bad Request


    # La validación de dimensiones (conjunto completo, conflicto) y la validación más detallada del proyecto (existencia en Notion)
    # se manejan dentro de submit_request_for_material_logic (ahora con 'partida').


    # Asegúrate de que el diccionario data NO incluye 'torni_items' si el proveedor no es Torni.
    # Esto es una medida de limpieza. submit_request_for_material_logic ya maneja esto,
    # pero puede prevenir problemas si el frontend por error enviara datos Torni en modo estándar.
    is_torni_mode = data.get("proveedor") == 'Torni'
    if not is_torni_mode and 'torni_items' in data:
         del data['torni_items']
         logger.warning(f"[{current_user.username if current_user.is_authenticated else 'Unauthenticated'}] Campo 'torni_items' encontrado en modo no Torni. Eliminado antes de pasar a lógica principal.")


    # --- DEBUG: Imprimir los datos *finales* que se pasarán a la lógica principal en notion_utils ---
    current_app.logger.debug(f"[{current_user.username if current_user.is_authenticated else 'Unauthenticated'}] Pasando datos procesados y validados a submit_request_for_material_logic: {data}")
    # --- Fin Debugging ---


    # Llamar a la lógica principal de procesamiento en notion_utils, pasándole todos los IDs necesarios
    # submit_request_for_material_logic maneja la creación de páginas en Notion,
    # la validación de dimensiones/proyecto en Notion, y la construcción de la respuesta final.
    response_data, status_code = submit_request_for_material_logic(
        notion_client,
        database_id_db1,
        database_id_db2,
        database_id_partidas,
        database_id_proyectos,  # Obtener y pasar el ID de la BD de Proyectos
        data=data, # Pasar el diccionario data completo (con todos los campos recolectados del frontend) como argumento con nombre
        user_id=current_user.id if current_user.is_authenticated else None # Pasar el ID del usuario logueado
    )

    # La respuesta y el código de estado HTTP devueltos por esta ruta son los que genera
    # la función submit_request_for_material_logic en notion_utils.py.

    return jsonify(response_data), status_code


# Puedes añadir aquí otras rutas relacionadas con las solicitudes si las tienes
# Ejemplo:
# @solicitudes_bp.route('/view_request/<folio>')
# @login_required
# def view_request(folio):
#     # Lógica para mostrar una solicitud específica
#     pass

# Ejemplo de ruta para listar propiedades si tu UI lo requiere (ej. para un selector de filtros en el frontend)
# Asegúrate de que list_available_properties está implementada en notion_utils.py
@solicitudes_bp.route('/list_properties/<string:db_id_key>')
@login_required
@role_required(['admin']) # Solo administradores pueden listar propiedades? Ajusta según tus necesidades
def list_notion_properties(db_id_key):
    """Endpoint para listar propiedades disponibles de una base de datos de Notion por su clave de configuración."""
    logger.info(f"[{current_user.username}] Solicitud GET para listar propiedades de DB: {db_id_key}")

    notion_client = current_app.notion_client
    # Mapear la clave de la URL a la clave en app.config
    db_id = current_app.config.get(f'DATABASE_ID_{db_id_key.upper()}') # Ejemplo asumiendo claves como 'MATERIALES_DB1', 'PROYECTOS'

    if notion_client is None or not db_id:
         error_msg = f"Base de datos con clave '{db_id_key}' no encontrada o Cliente Notion no inicializado."
         logger.error(f"[{current_user.username}] {error_msg}")
         return jsonify({"error": error_msg}), 404 # Not Found o 503

    try:
         properties_list = list_available_properties(notion_client, db_id)
         return jsonify(properties_list), 200
    except Exception as e:
         logger.error(f"[{current_user.username}] Error al listar propiedades para DB '{db_id_key}': {e}", exc_info=True)
         return jsonify({"error": "Error al obtener propiedades de Notion."}), 500 # Internal Server Error