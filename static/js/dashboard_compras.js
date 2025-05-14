// static/js/dashboard_compras.js

document.addEventListener('DOMContentLoaded', function() {
    // --- Referencias a elementos DOM ---
    const solicitudesTable = document.getElementById('solicitudes-table-compras'); // La tabla de solicitudes de Compras
    // Referencia al div donde mostraremos los mensajes de feedback de AJAX
    const updateFeedbackDiv = document.getElementById('compras-update-feedback');


    // --- Event Listeners ---

    // Añadir listener a la tabla para delegar eventos de los selects de estatus
    if (solicitudesTable) {
        solicitudesTable.addEventListener('change', function(event) {
            const target = event.target;

            // Verificar si el elemento que disparó el evento es un select con clase 'update-estatus-select'
            if (target.classList.contains('update-estatus-select')) {
                const selectElement = target;
                const newStatus = selectElement.value; // Obtener el nuevo estatus seleccionado
                const row = selectElement.closest('tr'); // Obtener la fila (tr) a la que pertenece este select
                const pageId = row ? row.getAttribute('data-page-id') : null; // Obtener el page-id del atributo data-page-id de la fila

                // --- Nuevo: Obtener el Folio de la solicitud de la primera celda (asumiendo que es la primera) ---
                // Necesitamos encontrar la celda del Folio dentro de la misma fila
                const folioCell = row ? row.querySelector('td:first-child') : null; // Asume que el Folio está en la primera celda
                const folioText = folioCell ? folioCell.textContent.trim() : 'Desconocido'; // Obtener el texto del Folio


                // Verificar que tenemos un page ID y un estatus seleccionado válido
                if (pageId && newStatus) {
                    console.log(`Intentando actualizar estatus para solicitud con Folio ${folioText} (Page ID: ${pageId}) a \"${newStatus}\"`);
                    // Llamar a la función para enviar la solicitud de actualización, pasando el folio también
                    updateSolicitudStatus(pageId, newStatus, row, folioText); // Pasar folioText
                } else if (!newStatus) {
                    console.log("Select de estatus cambiado, pero el valor es vacío o inválido.");
                    // El usuario seleccionó la opción disabled/empty
                    // Opcional: mostrar un mensaje al usuario en el div de feedback si es necesario
                    if (updateFeedbackDiv) {
                         updateFeedbackDiv.textContent = "Por favor, selecciona un estatus válido.";
                         updateFeedbackDiv.className = ''; // Limpiar clases anteriores
                         updateFeedbackDiv.classList.add('feedback-message', 'info'); // Clase info para mensajes informativos
                         hideFeedbackMessage(); // Ocultar después de un tiempo
                     }

                } else {
                    console.warn("No se pudo obtener page ID para actualizar estatus.");
                    // Mostrar un mensaje de error en el div de feedback
                    if (updateFeedbackDiv) {
                        updateFeedbackDiv.textContent = "Error interno: No se pudo identificar la solicitud.";
                        updateFeedbackDiv.className = ''; // Limpiar clases anteriores
                        updateFeedbackDiv.classList.add('feedback-message', 'error'); // Clase error
                        hideFeedbackMessage(); // Ocultar después de un tiempo
                    }
                }
            }
        });
    } else {
        console.error("Tabla de solicitudes #solicitudes-table-compras no encontrada.");
         // Mostrar un mensaje de error si la tabla no se encuentra
         if (updateFeedbackDiv) {
             updateFeedbackDiv.textContent = "Error: No se encontró la tabla de solicitudes.";
             updateFeedbackDiv.className = ''; // Limpiar clases anteriores
             updateFeedbackDiv.classList.add('feedback-message', 'error'); // Clase error
         }
    }


    // --- Funciones ---

    // Función para enviar la solicitud de actualización de estatus via AJAX al backend
    // Ahora recibe el folioText como argumento
    function updateSolicitudStatus(pageId, newStatus, rowElement, folioText) {
        const updateUrl = `/compras/update_solicitud_status/${pageId}`;

        const propertiesToUpdate = {
            // Asegúrate de que "Estatus" coincide con el nombre de la propiedad en tu DB Notion
            // Si tu propiedad de estatus es tipo Status: {"Status": {"name": newStatus}}
            "Estatus": {"select": {"name": newStatus}}
        };

        const requestBody = {
            properties: propertiesToUpdate
        };

        // --- Mostrar indicador visual de carga y mensaje "Actualizando..." ---
        if (rowElement) {
             rowElement.classList.add('updating'); // Añadir clase CSS
             const selectElement = rowElement.querySelector('.update-estatus-select');
             if(selectElement) selectElement.disabled = true; // Deshabilitar el select
             // Si ocultaste el texto de estatus antes, puedes mostrar algo como un spinner aquí
 }
        // Mostrar mensaje en el div de feedback
        if(updateFeedbackDiv) {
            updateFeedbackDiv.textContent = `Actualizando estatus para solicitud con Folio ${folioText}...`;
            updateFeedbackDiv.className = ''; // Limpiar clases anteriores
            updateFeedbackDiv.classList.add('feedback-message', 'processing'); // Clase processing para estilos de carga
        }


        fetch(updateUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        })
        .then(response => {
            // --- Ocultar indicador visual de carga y limpiar mensaje "Actualizando..." ---
            if (rowElement) rowElement.classList.remove('updating');
             // El select se re-habilita más abajo o en el catch si hay error

            if (!response.ok) {
                // Si la respuesta no es OK, lanzar error
                return response.json().then(errData => {
                     let msg = errData.error || `Error: ${response.status}`;
                     if(errData.details) msg += `: ${errData.details}`;
                     if(errData.notion_message) msg += ` (Notion: ${errData.notion_message})`;
                     throw new Error(msg);
                }).catch(() => {
                    throw new Error(`Error ${response.status}: ${response.statusText}`);
                });
            }
            // Si la respuesta es OK, procesar éxito
            return response.json();
        })
        .then(data => {
            console.log('Actualización exitosa:', data);
            // Actualizar la UI de la fila en el frontend
            if (rowElement) {
                const statusCell = rowElement.querySelector('.solicitud-estatus-celda');
                if (statusCell) {
                    const statusTextSpan = statusCell.querySelector('.current-estatus-text');
                    if(statusTextSpan) {
                        statusTextSpan.textContent = newStatus; // Actualizar el texto del estatus
                        // --- Opcional: Actualizar clases CSS en el span para reflejar el nuevo estatus ---
                        // Esto requiere que tengas clases CSS definidas como .status-pendiente, .status-en-proceso, etc.
                        const currentStatusClass = statusTextSpan.className.split(' ').find(cls => cls.startsWith('status-'));
                        if (currentStatusClass) {
                            statusTextSpan.classList.remove(currentStatusClass);
                        }
                         const newStatusClass = `status-${newStatus.toLowerCase().replace(/\s+/g, '-').replace('/', '-')}`;
                         statusTextSpan.classList.add(newStatusClass);
                     }
                }
                 // Re-habilitar el select y resetear su valor
                const selectElement = rowElement.querySelector('.update-estatus-select');
                if(selectElement) {
                    selectElement.value = ""; // Resetear al valor por defecto "Cambiar Estatus"
                    selectElement.disabled = false; // Re-habilitar
                }
            }

            // --- Mostrar mensaje de éxito en el div de feedback ---
            if(updateFeedbackDiv) {
                // data.message podría venir del backend con un mensaje más específico
                const successMessage = data.message || `Estatus actualizado a \"${newStatus}\"`;
                updateFeedbackDiv.textContent = `Solicitud con Folio ${folioText}: ${successMessage}`;
                updateFeedbackDiv.className = ''; // Limpiar clases anteriores
                updateFeedbackDiv.classList.add('feedback-message', 'success'); // Clase success
                hideFeedbackMessage(); // Ocultar después de un tiempo
            }

        })
        .catch(error => {
            console.error('Error al actualizar estatus via AJAX:', error);
            // --- Ocultar indicador visual de carga y mostrar mensaje de error ---
            if (rowElement) rowElement.classList.remove('updating');
             // Re-habilitar el select en caso de error
             const selectElement = rowElement ? rowElement.querySelector('.update-estatus-select') : null;
             if(selectElement) selectElement.disabled = false;


            // Mostrar mensaje de error en el div de feedback
            if(updateFeedbackDiv) {
                const errorMessage = error.message || 'Error desconocido al actualizar estatus.';
                updateFeedbackDiv.textContent = `Error al actualizar estatus para solicitud con Folio ${folioText}: ${errorMessage}`;
                updateFeedbackDiv.className = ''; // Limpiar clases anteriores
                updateFeedbackDiv.classList.add('feedback-message', 'error'); // Clase error
                hideFeedbackMessage(); // Ocultar después de un tiempo
            }
        });
    }

    // --- Nueva función para ocultar el mensaje de feedback ---
    let feedbackTimer;
    function hideFeedbackMessage() {
        // Limpiar cualquier temporizador anterior
        clearTimeout(feedbackTimer);
        // Establecer un nuevo temporizador para limpiar el texto después de 5 segundos (5000 ms)
        feedbackTimer = setTimeout(() => {
            if (updateFeedbackDiv) {
                updateFeedbackDiv.textContent = ''; // Limpiar el texto
                updateFeedbackDiv.className = ''; // Limpiar las clases
            }
        }, 5000); // Tiempo en milisegundos (5 segundos)
    }


}); // Fin DOMContentLoaded
