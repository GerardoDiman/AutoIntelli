# autointelli/compras.py

from flask import Blueprint, render_template, current_app, request, jsonify, flash
from flask_login import login_required, current_user
from .models import db, AuditLog
from .decorators import role_required
# Importar funciones para consultar/actualizar Notion
from .notion.utils import get_pages_with_filter_util, update_notion_page_properties, build_filter_from_properties_util

import logging
from collections import defaultdict # Importar defaultdict para facilitar la agrupación

logger = logging.getLogger(__name__)

compras_bp = Blueprint('compras', __name__, url_prefix='/compras')

@compras_bp.route('/')
@login_required
@role_required(['compras', 'admin'])
def compras_dashboard():
    logger.info(f"[{current_user.username}] Solicitud GET recibida en /compras/ (Compras Dashboard)")

    notion_client = current_app.notion_client
    database_id_solicitudes_compras = current_app.config.get('DATABASE_ID_MATERIALES_DB1') # O la DB relevante para Compras
    database_id_partidas = current_app.config.get('DATABASE_ID_PARTIDAS') # Obtener el ID de la base de datos de Partidas
    database_id_proyectos = current_app.config.get('DATABASE_ID_PROYECTOS') # Obtener el ID de la base de datos de Proyectos


    solicitudes = []
    error_msg = None
    # Usar defaultdict para agrupar solicitudes por proyecto más fácilmente
    grouped_solicitudes = defaultdict(list)

    if not notion_client:
        error_msg = "Cliente Notion no inicializado."
        logger.error(f"[{current_user.username}] {error_msg}")
        flash(error_msg, "danger")
    elif not database_id_solicitudes_compras:
         error_msg = "DATABASE_ID_MATERIALES_DB1 no está configurado."
         logger.error(f"[{current_user.username}] {error_msg}")
         flash(error_msg, "danger")
    elif not database_id_partidas:
         error_msg = "DATABASE_ID_PARTIDAS no está configurado."
         logger.error(f"[{current_user.username}] {error_msg}")
         flash(error_msg, "danger")
    elif not database_id_proyectos: # Verificar también el ID de la base de datos de Proyectos
         error_msg = "DATABASE_ID_PROYECTOS no está configurado."
         logger.error(f"[{current_user.username}] {error_msg}")
         flash(error_msg, "danger")
    else:
         try:
              # Define los filtros relevantes para Compras (ej: ver todas, o filtrar por estatus)
              filters_for_compras = [] # Ejemplo: Obtener todas las solicitudes (sin filtros)

              logger.info(f"[{current_user.username}] Compras: Filters built: {filters_for_compras if filters_for_compras else 'Ninguno'}")

              solicitudes = get_pages_with_filter_util(notion_client, database_id_solicitudes_compras, filters_for_compras)
              logger.info(f"[{current_user.username}] Compras: Obtenidas {len(solicitudes)} solicitudes de Notion.")
              if not solicitudes:
                  logger.warning(f"[{current_user.username}] Compras: No se obtuvieron solicitudes de Notion.")


              # --- Lógica para obtener detalles de las Partidas y Proyectos relacionados ---
              for solicitud in solicitudes:
                  logger.debug(f"[{current_user.username}] Procesando solicitud ID: {solicitud.get('id')}")
                  # Lógica para Partidas (existente)
                  partida_details_list = []
                  partida_prop = solicitud.get('properties', {}).get('Partida')
                  if partida_prop and partida_prop.get('type') == 'relation' and partida_prop.get('relation'):
                      relation_ids = [rel.get('id') for rel in partida_prop.get('relation')]
                      logger.debug(f"[{current_user.username}] Solicitud {solicitud.get('id')}: Encontradas {len(relation_ids)} relaciones de Partida: {relation_ids}")
                      for related_page_id in relation_ids:
                          try:
                              related_page = notion_client.pages.retrieve(related_page_id)
                              partida_id_prop = related_page.get('properties', {}).get('ID de partida')
                              if partida_id_prop and (partida_id_prop.get('type') == 'rich_text' or partida_id_prop.get('type') == 'title'):
                                  partida_code = "".join([text_part.get('text', {}).get('content', '') for text_part in partida_id_prop.get(partida_id_prop.get('type'), [])])
                                  partida_details_list.append({'id': related_page_id, 'title': partida_code})
                                  logger.debug(f"[{current_user.username}] Solicitud {solicitud.get('id')}: Partida '{partida_code}' obtenida.")
                              else:
                                  logger.warning(f"[{current_user.username}] Partida relacionada con ID {related_page_id} no tiene una propiedad 'ID de partida' válida o es de un tipo inesperado.")
                                  partida_details_list.append({'id': related_page_id, 'title': 'Título no disponible'})
                          except Exception as e:
                              logger.error(f"[{current_user.username}] Error al obtener detalles de Partida relacionada con ID {related_page_id}: {e}", exc_info=True)
                              partida_details_list.append({'id': related_page_id, 'title': 'Error al cargar detalles'})
                  solicitud['partida_details'] = partida_details_list


                  # --- Lógica para obtener detalles del Proyecto relacionado ---
                  project_name = "Sin Proyecto" # Valor por defecto si no hay proyecto relacionado
                  project_prop = solicitud.get('properties', {}).get('Proyecto') # Acceder a la propiedad "Proyecto"

                  logger.debug(f"[{current_user.username}] Solicitud {solicitud.get('id')}: Propiedad 'Proyecto': {project_prop}")

                  if project_prop and project_prop.get('type') == 'relation' and project_prop.get('relation'):
                       # Asumimos que solo hay UNA relación de proyecto principal para la agrupación
                       related_project_id = project_prop.get('relation')[0].get('id') # Tomar el primer ID relacionado
                       logger.debug(f"[{current_user.username}] Solicitud {solicitud.get('id')}: Encontrada relación de Proyecto con ID: {related_project_id}")

                       try:
                           # Obtener los detalles de la página de Proyecto relacionada
                           related_project_page = notion_client.pages.retrieve(related_project_id)
                           logger.debug(f"[{current_user.username}] Solicitud {solicitud.get('id')}: Detalles de página de Proyecto {related_project_id} obtenidos.")
                           # Extraer la propiedad 'ID del proyecto' de la página relacionada
                           project_id_prop = related_project_page.get('properties', {}).get('ID del proyecto') # ¡Corregido el nombre!

                           logger.debug(f"[{current_user.username}] Solicitud {solicitud.get('id')}: Propiedad 'ID del proyecto' en Proyecto: {project_id_prop}")

                           if project_id_prop and (project_id_prop.get('type') == 'rich_text' or project_id_prop.get('type') == 'title'):
                               # Concatenar el texto de las partes de rich_text/title para obtener el código/nombre
                               project_code = "".join([text_part.get('text', {}).get('content', '') for text_part in project_id_prop.get(project_id_prop.get('type'), [])])
                               project_name = project_code # Usar el código del proyecto como nombre de grupo
                               logger.debug(f"[{current_user.username}] Solicitud {solicitud.get('id')}: Código de Proyecto '{project_name}' extraído.")
                           else:
                               logger.warning(f"[{current_user.username}] Proyecto relacionado con ID {related_project_id} no tiene una propiedad 'ID del proyecto' válida o es de un tipo inesperado.")
                               pass # Mantiene "Sin Proyecto" por defecto

                       except Exception as e:
                           logger.error(f"[{current_user.username}] Error al obtener detalles de Proyecto relacionado con ID {related_project_id}: {e}", exc_info=True)
                           pass # Mantiene "Sin Proyecto" por defecto

                  # Adjuntar el nombre del proyecto (obtenido o por defecto) a la solicitud
                  solicitud['project_name'] = project_name
                  # Añadir la solicitud al grupo correspondiente
                  grouped_solicitudes[project_name].append(solicitud)
                  logger.debug(f"[{current_user.username}] Solicitud {solicitud.get('id')} añadida al grupo '{project_name}'.")


              # --- Fin de la lógica para obtener detalles de Proyectos ---

              logger.info(f"[{current_user.username}] Compras: Proceso de agrupación completado. Grupos creados: {list(grouped_solicitudes.keys())}")
              for project_name, solicitudes_list in grouped_solicitudes.items():
                  logger.info(f"[{current_user.username}] Compras: Grupo '{project_name}' tiene {len(solicitudes_list)} solicitudes.")


         except Exception as e:
              error_msg = f"Error al cargar solicitudes de Notion para Compras: {e}"
              logger.error(f"[{current_user.username}] {error_msg}", exc_info=True)
              flash(error_msg, "danger")

    # Pasar los datos agrupados al template
    return render_template('compras/dashboard_compras.html', grouped_solicitudes=grouped_solicitudes, error_msg=error_msg)


# --- RUTA POST para actualizar el estatus de una solicitud ---
# Esta ruta recibirá el page_id y el nuevo estatus (u otras propiedades) del frontend via AJAX
@compras_bp.route('/update_solicitud_status/<string:page_id>', methods=['POST'])
@login_required
@role_required(['compras', 'admin']) # Solo roles 'compras' y 'admin' pueden actualizar
def update_solicitud_status(page_id):
    logger.info(f"[{current_user.username}] Recibiendo solicitud para actualizar solicitud {page_id} (Compras)")

    # Obtener los datos a actualizar del request.get_json() enviado por el frontend AJAX
    data = request.get_json()
    if not data:
        logger.warning(f"[{current_user.username}] Solicitud de actualización para {page_id} sin datos recibidos.")
        return jsonify({"error": "Datos inválidos: no se recibieron datos."}), 400 # Bad Request

    # Validar que los datos recibidos tienen la estructura esperada para la actualización
    # Por ejemplo, si solo esperas un nuevo estatus:\
    # if \'status\' not in data or not isinstance(data[\'status\'], str):\
    #     logger.warning(f\"[{current_user.username}] Solicitud de actualización para {page_id} sin campo \'status\' o tipo incorrecto.\")
    #     return jsonify({\"error\": \"Datos inválidos: se esperaba un campo \'status\' (string).\"}), 400

    # Si esperas un diccionario de propiedades a actualizar (más flexible):
    properties_to_update = data.get('properties', {}) # Asume que el frontend envía {"properties": {...}}
    if not isinstance(properties_to_update, dict) or not properties_to_update:
        logger.warning(f"[{current_user.username}] Solicitud de actualización para {page_id} sin diccionario 'properties' o está vacío.")
        return jsonify({"error": "Datos inválidos: se esperaba un diccionario no vacío en el campo 'properties'."}), 400


    # Obtener el cliente Notion desde la configuración central
    notion_client = current_app.notion_client
    if notion_client is None:
        error_msg = "Cliente Notion no inicializado."
        logger.error(f"[{current_user.username}] {error_msg}")
        return jsonify({"error": error_msg}), 503 # Service Unavailable


    try:
        # Llamar a la nueva función para actualizar propiedades generales
        # Le pasamos el diccionario properties_to_update directamente
        status_code, response_data = update_notion_page_properties(notion_client, page_id, properties_to_update)

        if 200 <= status_code < 300:
            # Registrar auditoría si la actualización fue exitosa
            from .models import db, AuditLog
            try:
                # Detalles del log: Incluir las propiedades actualizadas
                details_log = f'Solicitud ID Notion: {page_id}, Propiedades: {properties_to_update}'
                audit_log = AuditLog(user_id=current_user.id, action=f'Actualizar solicitud', details=details_log[:500]) # Limitar a 500 chars
                db.session.add(audit_log)
                db.session.commit()
                logger.info(f"[{current_user.username}] Registro de auditoría creado para actualización de solicitud {page_id}.")
            except Exception as audit_e:
                 db.session.rollback()
                 logger.error(f"[{current_user.username}] ERROR al crear registro de auditoría para actualización de solicitud: {audit_e}", exc_info=True)


            # Devolver un mensaje de éxito, quizás incluyendo los datos de la respuesta de Notion si son útiles
            return jsonify({"message": "Solicitud actualizada con éxito!", "notion_response": response_data}), 200

        else:
            # Si update_notion_page_properties devolvió un error (API de Notion u otro)
            logger.error(f"[{current_user.username}] Error al actualizar solicitud {page_id}: {response_data}")
            # Devolver el mensaje de error que viene de update_notion_page_properties
            return jsonify({"error": response_data.get('error', 'Error desconocido al actualizar solicitud.')}), status_code

    except Exception as e:
        # Capturar cualquier excepción inesperada durante el proceso de backend
        logger.error(f"[{current_user.username}] Error inesperado en update_solicitud_status para {page_id}: {e}", exc_info=True)
        return jsonify({"error": "Error interno del servidor al actualizar estatus."}), 500
