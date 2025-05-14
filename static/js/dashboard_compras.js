// static/js/dashboard_compras.js

document.addEventListener('DOMContentLoaded', function() {

    // --- Funcionalidad de Actualización de Estatus ---

    // Seleccionar todos los elementos select con la clase 'update-estatus-select'
    const statusSelects = document.querySelectorAll('.update-estatus-select');

    statusSelects.forEach(selectElement => {
        selectElement.addEventListener('change', function() {
            // 'this' se refiere al elemento select que disparó el evento
            const select = this;
            // Obtener el page_id de la fila padre (<tr>)
            const row = select.closest('tr');
            const pageId = row.dataset.pageId; // Obtener el page_id del atributo data-page-id
            const newStatus = select.value; // Obtener el nuevo valor seleccionado

            console.log(`Intentando actualizar estatus para Page ID: ${pageId} a ${newStatus}`);

            // Deshabilitar el select temporalmente y quizás mostrar un indicador de carga
            select.disabled = true;
            select.style.cursor = 'wait'; // Cambiar cursor a espera

            // Opcional: Encontrar la celda del estatus actual para mostrar un mensaje temporal
            const currentStatusCell = row.querySelector('.solicitud-estatus-celda');
             if (currentStatusCell) {
                 // Guardar el contenido original para restaurar después
                 const originalContent = currentStatusCell.innerHTML;
                 currentStatusCell.innerHTML = '<span class="processing-text">Actualizando...</span>'; // Mostrar mensaje de "Actualizando..."
                 // Usar un atributo para guardar el contenido original si quieres ser más robusto
                 currentStatusCell.dataset.originalContent = originalContent;
                 // Limpiar las clases de estado previas si existen
                 currentStatusCell.querySelector('.current-estatus-text')?.classList.forEach(className => {
                     if (className.startsWith('status-')) {
                         currentStatusCell.querySelector('.current-estatus-text').classList.remove(className);
                     }
                 });
            }


            // Preparar los datos para enviar
            // Nota: El endpoint del backend espera un JSON con la estructura { "properties": { "Estatus": { "select": { "name": "Nuevo Estatus" } } } }
            const data = {
                properties: {
                    "Estatus": { // Asegúrate de que "Estatus" coincide exactamente con el nombre de la propiedad en Notion
                        "select": {
                            "name": newStatus
                        }
                    }
                }
            };

            // Realizar la solicitud AJAX (fetch API)
            fetch(`/compras/update_solicitud_status/${pageId}`, { // Asegúrate de que la URL coincide con tu ruta Flask
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            })
            .then(response => {
                // Verificar si la respuesta HTTP fue exitosa (status 2xx)
                if (!response.ok) {
                     // Si no es exitosa, lanzar un error con el estado y el mensaje de respuesta
                     return response.json().then(errorData => {
                         const errorMessage = errorData.error || `Error de servidor (Status: ${response.status})`;
                         const notionErrorDetails = errorData.notion_error_details ? ` Detalles: ${JSON.stringify(errorData.notion_error_details)}` : '';
                         throw new Error(`${errorMessage}${notionErrorDetails}`);
                     }).catch(() => {
                         // Si no se puede parsear el JSON de error, usar un mensaje genérico
                          throw new Error(`Error de servidor (Status: ${response.status}). No se pudo obtener el detalle del error.`);
                     });
                }
                // Si es exitosa, parsear el JSON de la respuesta
                return response.json();
            })
            .then(data => {
                // Manejar la respuesta exitosa del backend
                console.log('Actualización exitosa:', data);
                // Mostrar mensaje de éxito al usuario (opcional, en un div dedicado o como flash message)
                // alert('Estatus actualizado correctamente!'); // Usa algo mejor que alert en producción
                const feedbackDiv = document.getElementById('compras-update-feedback');
                 if (feedbackDiv) {
                     feedbackDiv.textContent = data.message || 'Actualización exitosa.';
                     feedbackDiv.style.color = 'green';
                     // Limpiar mensaje después de unos segundos
                     setTimeout(() => { feedbackDiv.textContent = ''; }, 5000);
                 }

                // Actualizar la visualización del estatus actual en la tabla
                 if (currentStatusCell) {
                    // Restaurar el contenido original si lo guardaste o crear el nuevo badge
                    // Una forma más robusta es actualizar el contenido basado en el nuevo estatus seleccionado:
                    const newStatusText = newStatus; // El texto a mostrar es el nuevo estatus seleccionado
                    const newStatusClass = newStatusText.toLowerCase().replace(' ', '-').replace('/', '-');
                    currentStatusCell.innerHTML = `<span class="current-estatus-text status-badge status-${newStatusClass}">${newStatusText}</span>`;
                 }

                // Opcional: Deshabilitar el select o restablecerlo a la opción por defecto "Cambiar Estatus"
                select.disabled = false; // Habilitar select
                select.style.cursor = 'pointer'; // Restaurar cursor
                select.value = ""; // Restablecer a la opción "Cambiar Estatus"

            })
            .catch(error => {
                // Manejar errores de la solicitud o del backend
                console.error('Error en la actualización:', error);
                // Mostrar mensaje de error al usuario
                 const feedbackDiv = document.getElementById('compras-update-feedback');
                 if (feedbackDiv) {
                     feedbackDiv.textContent = `Error al actualizar: ${error.message || 'Error desconocido.'}`;
                     feedbackDiv.style.color = 'red';
                      // Limpiar mensaje después de unos segundos
                     setTimeout(() => { feedbackDiv.textContent = ''; }, 10000); // Dejar mensaje de error más tiempo
                 }


                // Restaurar el select y la celda de estatus si es necesario
                select.disabled = false; // Habilitar select
                select.style.cursor = 'pointer'; // Restaurar cursor
                 if (currentStatusCell && currentStatusCell.dataset.originalContent) {
                    // Restaurar el contenido original que guardaste
                    currentStatusCell.innerHTML = currentStatusCell.dataset.originalContent;
                    // Limpiar el atributo dataset
                    delete currentStatusCell.dataset.originalContent;
                 } else if (currentStatusCell) {
                     // Si no se pudo restaurar el contenido original, al menos mostrar un indicador de error
                     currentStatusCell.innerHTML = '<span class="error-text">Error</span>';
                 }

                 // Opcional: Restablecer el select a su valor original antes del intento de actualización
                 // Esto requeriría almacenar el valor original antes del cambio, lo cual añade complejidad.
                 // Por ahora, simplemente se habilita el select.
            });
        });
    });

    // --- Funcionalidad Adicional (si la hay) ---
    // Puedes añadir aquí más listeners de eventos o lógica de JavaScript que necesites para el dashboard de compras.

}); // Fin de DOMContentLoaded
