// static/js/standard_request.js

// Este script maneja la lógica del formulario de solicitud estándar (para el rol Logística).
// Asume que la variable global STANDARD_DIMENSIONS_URL se define en la plantilla HTML
// antes de que este script se cargue, usando url_for.

// --- Variables Globales (Constantes que NO dependen del DOM o init en DOMContentLoaded) ---
// Estas pueden estar fuera del DOMContentLoaded
const materialesPorProveedor = { "Mipsa": ["D2", "Cobre", "Aluminio"], "LBO": ["H13", "1018", "4140T"], "Grupo Collado": ["D2", "4140T", "H13", "1018", "Acetal"], "Cameisa": ["Aluminio", "Cobre", "Acetal", "Nylamid"], "Surcosa": ["1018", "Nylamid", "Acetal", "D2"], "Diace": ["D2", "H13", "Aluminio", "4140T", "Cobre", "1018"], "Por definir": ["D2", "Cobre", "Aluminio", "H13", "1018", "4140T", "Acetal", "Nylamid"] };
const tipoPorMaterial = { "D2": "Metal", "Aluminio": "Metal", "Cobre": "Metal", "4140T": "Metal", "H13": "Metal", "1018": "Metal", "Acetal": "Plastico", "Nylamid": "Plastico" };


// --- Funciones PURAS (No dependen del DOM o variables dentro de DOMContentLoaded) ---
// Estas funciones pueden estar fuera del DOMContentLoaded y ser llamadas desde dentro si es necesario.
function generateFolio() {
    const timestamp = Date.now();
    const randomPart = Math.random().toString(36).substring(2, 8).toUpperCase();
    return `MAT-${timestamp}-${randomPart}`;
}


// --- CÓDIGO QUE SE EJECUTA AL CARGAR LA PÁGINA (DENTRO DE DOMContentLoaded) ---
// Todo el código que interactúa con el DOM o depende de variables definidas aquí va dentro de este listener.
document.addEventListener('DOMContentLoaded', function() {
    // --- Referencias a elementos DOM (>>> OBTENER TODAS AQUÍ AL PRINCIPIO <<<) ---
    // OBTÉN TODAS LAS REFERENCIAS QUE NECESITAS AQUÍ
    const materialForm = document.getElementById('standard-material-form');
    const responseMessageDiv = document.getElementById('response-message');

    // Referencias a campos visibles
    const materialSelect = document.getElementById('nombre_material'); // Referencia al Select de Material
    const tipoMaterialInput = document.getElementById('tipo_material'); // Referencia al Input de Tipo Material
    const fechaInput = document.getElementById('fecha_solicitud'); // Input text readonly para fecha
    const cantidadSolicitadaInput = document.getElementById('cantidad_solicitada');
    const unidadMedidaSelect = document.getElementById('unidad_medida'); // Referencia al Select de Unidad
    const dimensionDatalist = document.getElementById('dimensionList');
    const largoInput = document.getElementById('largo');
    const anchoInput = document.getElementById('ancho');
    const altoInput = document.getElementById('alto');
    const diametroInput = document.getElementById('diametro');
    const dimensionesContainer = document.getElementById('dimensiones-container'); // Contenedor de dimensiones

    const nombreSolicitanteInput = document.getElementById('nombre_solicitante');
    // const departamentoAreaSelect = document.getElementById('departamento_area'); // Este select visible fue eliminado
    const proyectoInput = document.getElementById('proyecto'); // Usar 'proyecto' en minúsculas aquí
    const especificacionesAdicionalesTextarea = document.getElementById('especificaciones_adicionales');

    // Referencias a elementos de Folio
    const folioDisplayValue = document.getElementById('folio-display-value');
    const folioInputHidden = document.getElementById('folio_solicitud');

    // Referencias a inputs ocultos (para obtener sus valores)
    const proveedorInputHidden = document.querySelector('#standard-material-form input[name="proveedor"]');
    const departamentoAreaInputHidden = document.querySelector('#standard-material-form input[name="departamento_area"]');


    // --- Variables Globales del Script (dentro de DOMContentLoaded) ---
    // Declara las variables que se usarán dentro de este scope o en funciones definidas aquí.
    let allStandardDimensions = {}; // Se asignará en el .then() del fetch
    let currentFolio = null;
    let submitBtn = null; // Declare submitBtn here to make it accessible

    // Obtener el proveedor por defecto de logística (del input oculto si existe, o un default)
    // Aquí el proveedor es fijo a "Por definir" según tu HTML, pero mantenemos la variable para claridad.
    const DEFAULT_PROVEVEDOR_LOGISTICA = proveedorInputHidden ? proveedorInputHidden.value : 'Por definir';


    // --- Funciones que DEPENDEN de Elementos del DOM o Variables Definidas AQUÍ (>>> DEFINIR AQUÍ <<<) ---
    // Estas funciones usan las referencias DOM y variables declaradas justo arriba en este mismo scope.

    // Funciones de Folio (dependen de referencias DOM)
    function updateFolioDisplay(folio) {
        if (folioDisplayValue) folioDisplayValue.textContent = folio;
        if (folioInputHidden) folioInputHidden.value = folio;
    }


    // Funciones de Datalist (dependen de referencias DOM y allStandardDimensions)
    function populateDimensionDatalist(dimensionsArray) {
        console.log("Inside populateDimensionDatalist with array:", dimensionsArray); // Log para depuración
        if (!dimensionDatalist) {
             console.error("populateDimensionDatalist aborted: Datalist element not found!"); // Log para depuración
            return;
        }
         // Asegurarse de que es un array válido
        if (!dimensionsArray || !Array.isArray(dimensionsArray) || dimensionsArray.length === 0) {
             // --- ** CAMBIO AQUÍ: console.warn a console.log (ya hecho, mantenido) ** ---
             console.log("populateDimensionDatalist called with invalid or empty array. Cleaning datalist."); // Log informativo
             // --- FIN CAMBIO ---
             dimensionDatalist.innerHTML = ''; // Limpiar si no hay datos o el formato es incorrecto
             return;
        }

        dimensionDatalist.innerHTML = ''; // Limpiar opciones anteriores
        dimensionsArray.forEach(dim => {
            const option = document.createElement('option');
            option.value = String(dim); // Asegurarse de que es string para la opción
            dimensionDatalist.appendChild(option);
        });
        console.log(`Datalist poblado con ${dimensionsArray.length} opciones.`); // Log existente
    }

    function updateDatalistForUnit() {
        console.log("Inside updateDatalistForUnit function."); // Log para depuración
        // allStandardDimensions debe haber sido poblado por el fetch antes de llamar a esta función de forma efectiva.
        // Como ahora habilitamos el select *antes* de las llamadas iniciales a enforceDimensionDependency,
        // esta condición !unidadMedidaSelect.disabled será true si los datos se cargaron con éxito.
        // Mantenemos la comprobación de datos cargados por robustez.
        if (!unidadMedidaSelect || !allStandardDimensions || Object.keys(allStandardDimensions).length === 0) {
             // Este log ya estaba en warn, lo mantenemos así porque *esto* sí sería un problema si ocurre con el select habilitado.
             console.warn("updateDatalistForUnit aborted: Missing select element or dimensions data.", { unidadMedidaSelect, allStandardDimensions }); // Log para depuración
            populateDimensionDatalist([]);
            return;
        }
        const selectedUnit = unidadMedidaSelect.value;
        console.log("Selected Unit:", selectedUnit); // Log para depuración

        // Obtener las dimensiones para la unidad seleccionada. Si la unidad no existe en allStandardDimensions, será []
        // Si el select está en la opción deshabilitada `value=""`, selectedUnit será "". allStandardDimensions[""] será `undefined`.
        const dimensionsForUnit = allStandardDimensions[selectedUnit] || [];
         console.log("Dimensions found for unit:", dimensionsForUnit); // Log para depuración

        // Solo poblar la datalist si la unidad seleccionada no es la opción vacía por defecto
        if (selectedUnit !== "") {
            populateDimensionDatalist(dimensionsForUnit); // Llama a otra función definida aquí
        } else {
             populateDimensionDatalist([]); // Limpiar la datalist si la unidad es la opción por defecto
        }
    }

    // Lógica Dropdowns Dependientes (dependen de referencias DOM y constantes/variables)
    function actualizarMateriales() {
        if (!materialSelect || !tipoMaterialInput) return; // Usa referencias DOM
        const selectedProveedor = DEFAULT_PROVEVEDOR_LOGISTICA;

        materialSelect.innerHTML = '<option value="" disabled selected>Seleccionar material:</option>'; // Usa referencia DOM
        tipoMaterialInput.value = ""; // Usa referencia DOM
        tipoMaterialInput.disabled = true; // Usa referencia DOM

        if (selectedProveedor && materialesPorProveedor[selectedProveedor]) { // usa constante materialesPorProveedor
            const materialesDisponibles = materialesPorProveedor[selectedProveedor];
            materialesDisponibles.forEach(material => {
                const option = document.createElement('option');
                option.value = material;
                option.textContent = material;
                materialSelect.appendChild(option); // usa materialSelect
            });
            // Habilitar el select de material una vez poblado
            materialSelect.disabled = false; // usa materialSelect
             // No llamamos a actualizarTipoMaterial() aquí; se disparará por el evento 'change' cuando el usuario seleccione.
        } else {
            // Si el proveedor por defecto no tiene materiales definidos, deshabilitar select de materiales
            materialSelect.disabled = true; // usa materialSelect
            console.warn(`Proveedor por defecto "${selectedProveedor}" no encontrado en materialesPorProveedor.`);
        }
    }

    function actualizarTipoMaterial() {
        if (!materialSelect || !tipoMaterialInput) return; // Usa referencias DOM
        const selectedMaterial = materialSelect.value; // Usa referencia DOM
        console.log("Selected Material (for Tipo):", selectedMaterial); // Log para depuración

        // If the selected value is the default empty option, clear the type field
        if (selectedMaterial === "" || !selectedMaterial) {
             tipoMaterialInput.value = ""; // Usa referencia DOM
             console.log("Material vacío o no seleccionado. Tipo Material vaciado."); // Log para depuración
             return; // Exit function
        }

        // If a material is selected, find its type
        if(tipoPorMaterial[selectedMaterial]) { // usa constante tipoPorMaterial
            const tipo = tipoPorMaterial[selectedMaterial];
            tipoMaterialInput.value = tipo; // Usa referencia DOM
            console.log("Tipo Material actualizado a:", tipo); // Log para depuración
        } else {
            tipoMaterialInput.value = "Desconocido"; // Or empty "" if you prefer
             console.warn(`Tipo de material desconocido para "${selectedMaterial}". Establecido a "Desconocido".`); // Log para depuración
        }
    }

    // --- Función para aplicar la lógica de dependencia de dimensiones ---
    function enforceDimensionDependency(changedInput) {
        // --- ** LOG DE ESTADO DEL SELECTOR DE UNIDAD AL PRINCIPIO DE LA FUNCIÓN ** ---
        console.log(`--- enforceDimensionDependency called. Changed input: ${changedInput ? changedInput.id : 'none'}. Unidad Select Disabled: ${unidadMedidaSelect ? unidadMedidaSelect.disabled : 'N/A'}`);
        // --- FIN LOG ---

        // Get trimmed values from all dimension inputs
        // Note: We use raw values from the DOM elements here to check their current state
        // before any logic potentially changes them to 'N/A'. collectFormData will process 'N/A' later.
        const largoVal = largoInput ? largoInput.value.trim() : '';
        const anchoVal = anchoInput ? anchoInput.value.trim() : '';
        const altoVal = altoInput ? altoInput.value.trim() : '';
        const diametroVal = diametroInput ? diametroInput.value.trim() : '';

        // Declare linearInputs here for use throughout the function
        const linearInputs = [largoInput, anchoInput, altoInput].filter(input => input); // Filter out null references just in case


        // Check if any linear dimension *other than Largo* has a non-empty value that isn't "N/A"
        const otherLinearInputs = [anchoInput, altoInput].filter(input => input); // Filter out null if elements not found
        const otherLinearHasRealValue = otherLinearInputs.some(input => {
            const val = input.value.trim();
             return val !== '' && val.toUpperCase() !== 'N/A';
        });

         // Check if Largo has a non-empty value that isn't "N/A"
        const largoHasRealValue = largoInput ? (largoVal !== '' && largoVal.toUpperCase() !== 'N/A') : false;

        // Check if diameter has a non-empty value that isn't "N/A"
        const diameterHasRealValue = diametroInput ? (diametroVal !== '' && diametroVal.toUpperCase() !== 'N/A') : false;


        // Helper function to apply the 'N/A' state to an input
        function applyNaState(inputElement) {
            if (!inputElement) return;
            // Only change value and state if it's not already N/A state
             // Check if current value is 'N/A' AND if it's already readonly
             const isAlreadyNaState = inputElement.readOnly && inputElement.value.trim().toUpperCase() === 'N/A';
             if (!isAlreadyNaState) {
                 inputElement.value = 'N/A';
                 inputElement.readOnly = true;
                 inputElement.classList.add('na-field');
                 // Remove the datalist attribute
                 inputElement.removeAttribute('list');
                 console.log(`Applied N/A state to ${inputElement.id}`); // Log change
            }
        }

        // Helper function to clear the 'N/A' state and make editable
        function clearNaState(inputElement) {
             if (!inputElement) return;
            // Only clear value and state if it IS N/A state or if it's readonly
             const isNaState = inputElement.readOnly && inputElement.value.trim().toUpperCase() === 'N/A';
             const isJustReadonly = inputElement.readOnly && inputElement.value.trim().toUpperCase() !== 'N/A'; // Case if it was made readonly without N/A? (shouldn't happen with our logic)
             if (isNaState || isJustReadonly) {
                if (inputElement.value.trim().toUpperCase() === 'N/A') {
                     inputElement.value = ''; // Clear the N/A text
                     console.log(`Cleared N/A value from ${inputElement.id}`); // Log change
                 }
                inputElement.readOnly = false;
                inputElement.classList.remove('na-field');
                 // Re-add the datalist attribute
                 inputElement.setAttribute('list', 'dimensionList');
                 console.log(`Cleared N/A state and made ${inputElement.id} editable.`); // Log change
             } else if (!inputElement.readOnly) {
                 // If it's already editable and not N/A state, just ensure class and list are correct
                  inputElement.classList.remove('na-field'); // Make sure class is off
                  inputElement.setAttribute('list', 'dimensionList'); // Make sure list is on
             }
        }

        // --- Apply Logic based on the new rules ---

        // Check if the *just changed* input created a conflict. This should happen BEFORE applying the general rules.
         let needsReevaluationAfterConflictClear = false;

         if (changedInput && changedInput.id === diametroInput?.id && otherLinearHasRealValue) {
             // Conflict: User typed in Diameter, but Ancho or Alto already has a value. Clear Diameter.
              console.warn("Conflict detected: Typed in Diameter but Ancho or Alto already have value. Clearing Diameter.");
              if (diametroInput) diametroInput.value = ''; // Clear the input
              // Re-evaluate the state based on current (now possibly empty) values.
             needsReevaluationAfterConflictClear = true;

         } else if (changedInput && otherLinearInputs.includes(changedInput) && diameterHasRealValue) {
             // Conflict: User typed in Ancho or Alto, but Diameter already has a value. Clear Ancho/Alto that was typed into.
             console.warn(`Conflict detected: Typed in ${changedInput.id} but Diameter already has value. Clearing ${changedInput.id}.`);
             changedInput.value = ''; // Clear the invalid input
             // Re-evaluate the state based on current (now possibly empty) values.
             needsReevaluationAfterConflictClear = true;
         }

         // If a conflict was just cleared, re-run this function with the new values and stop the current execution path.
         if (needsReevaluationAfterConflictClear) {
              enforceDimensionDependency(); // Recursive call to apply rules based on corrected values
              return;
         }


        // Now apply the general rules based on the CURRENT (and possibly corrected) values:

        // Rule 1: If Diameter has a value, Ancho and Alto become N/A. Largo remains editable.
        if (diameterHasRealValue) {
            console.log("Diameter has a real value. Setting Ancho and Alto to N/A.");
            otherLinearInputs.forEach(input => applyNaState(input)); // Ancho, Alto = N/A
            // Ensure Largo and Diameter are editable and not N/A state
             if (largoInput) clearNaState(largoInput);
             if (diametroInput) clearNaState(diametroInput); // Should already be clear state if it has value, but ensure
        }
        // Rule 2: If Ancho OR Alto has a value, Diameter becomes N/A. Largo remains editable.
        else if (otherLinearHasRealValue) { // Only check this if Rule 1 condition is false (Diameter is empty)
            console.log("Ancho OR Alto have real values. Setting Diameter to N/A.");
             // Ensure Ancho/Alto and Largo are editable
            otherLinearInputs.forEach(input => clearNaState(input)); // Ancho, Alto = editable
            if (largoInput) clearNaState(largoInput); // Largo = editable
            if (diametroInput) applyNaState(diametroInput); // Diameter = N/A
        }
        // Rule 3: If neither Diameter nor Ancho/Alto have values (This includes the case where ONLY Largo has a value).
        else {
             console.log("Neither Diameter, Ancho, nor Alto have real values. All dimension fields are editable.");
            // Ensure all dimension fields are editable and clear N/A state.
            // This covers the initial state, reset state, and state where only Largo has a value.
            linearInputs.forEach(input => clearNaState(input)); // Largo, Ancho, Alto = editable
            if (diametroInput) clearNaState(diametroInput); // Diameter = editable
        }

        // --- End Apply Logic ---


         // After enforcing the state, update the datalist based on the current unit.
         // We only update datalist IF the unit select is enabled (i.e., data is loaded).
         if (unidadMedidaSelect && !unidadMedidaSelect.disabled) {
             updateDatalistForUnit(); // This will call populateDatalist([]) and trigger the console.log (was warn)
         } else {
              // This log should only appear if the unit select wasn't found OR if it's somehow disabled after data load (an error state)
              // We'll leave a warning here for actual unexpected states, but the primary load-time warning is gone.
             if (!unidadMedidaSelect) {
                 console.warn("Datalist not updated: Unidad de Medida select element not found.");
             } else {
                 console.warn("Datalist not updated: Unidad de Medida select is unexpectedly disabled.", { selectState: unidadMedidaSelect.disabled });
             }
             populateDimensionDatalist([]); // Ensure datalist is cleared in these error states.
         }
    }

    // Helper function for clearing dimension fields *completely* (useful on form reset)
    function clearDimensionFields() {
        console.log("Clearing dimension fields completely.");
         // Use direct references here
         if (largoInput) { largoInput.value = ''; largoInput.classList.remove('error-field'); } // Also clear validation styles
         if (anchoInput) { anchoInput.value = ''; anchoInput.classList.remove('error-field'); }
         if (altoInput) { altoInput.value = ''; altoInput.classList.remove('error-field'); }
         if (diametroInput) { diametroInput.value = ''; diametroInput.classList.remove('error-field'); }

         // After clearing, apply the dependency logic (which will make them all editable and remove N/A)
         // Calling enforceDimensionDependency here without a changedInput makes it evaluate based on empty values.
         enforceDimensionDependency(); // This will potentially call updateDatalistForUnit if select is enabled
     }


    // Lógica de UI basada en Proveedor (Simplificada para este formulario)
     function handleProveedorChange() {
        console.log("handleProveedorChange ejecutado en formulario Estándar.");

        actualizarMateriales(); // Updates material select

        // Clear dimension fields and apply dependency logic
        clearDimensionFields(); // <-- Call the helper function. This also calls enforceDimensionDependency

         // Ensure quantity is 1 if needed
        if (cantidadSolicitadaInput && !cantidadSolicitadaInput.value) {
             cantidadSolicitadaInput.value = '1';
        }
     }


    // Función para Recolectar Datos del Formulario Estándar
    function collectFormData() {
        const data = {};
        const form = materialForm;

        form.querySelectorAll('input[name], select[name], textarea[name]').forEach(input => {
              // Skip disabled fields completely
              if (input.disabled) {
                   return; // Skip to next iteration
              }

              const name = input.name;
              const value = input.value; // Use raw value before trim for specific checks like "N/A"
              const trimmedValue = value.trim();


              if (input.type === 'hidden') {
                  data[name] = value; // Collect hidden fields regardless of value
              } else if (input.readOnly && input.id === 'fecha_solicitud') {
                   data[name] = value; // Collect readonly date field value
              } else if (input.type === 'number') {
                   // Collect number, convert to float. Use null if empty string or not a valid number.
                    data[name] = trimmedValue !== '' ? parseFloat(trimmedValue) : null;
                    if (isNaN(data[name])) data[name] = null;

              } else if (input.type === 'checkbox') {
                 data[name] = input.checked;

              } else if (['largo', 'ancho', 'alto', 'diametro'].includes(name)) {
                  // Specific handling for dimension fields with "N/A" logic
                  if (input.readOnly && trimmedValue.toUpperCase() === 'N/A') {
                      // If it's readonly AND its value is "N/A", send null to the backend.
                      data[name] = null;
                  } else if (trimmedValue === '') {
                      // If it's an editable dimension field but is empty, send an empty string.
                      // We'll treat empty strings from dimension fields as "not filled" in validation
                      data[name] = '';
                  } else {
                     // If it's an editable dimension field with a value, send the trimmed value
                      data[name] = trimmedValue;
                  }

              } else {
                  // Default case for other text, select, textarea fields
                  // Collect the trimmed value. If empty, sends empty string.
                  data[name] = trimmedValue;
              }
         });

          // Ensure type_material is included even if disabled/readonly
          // Its value is set by JS based on material selection.
         if (tipoMaterialInput && tipoMaterialInput.name) {
             // Collect the trimmed value, send empty string if empty
              data[tipoMaterialInput.name] = tipoMaterialInput.value.trim();
         }


         console.log('Datos recolectados para JSON (Estándar):', data);
         return data;
     }


    // Función para Configurar Submit (depende de referencias DOM y otras funciones definidas aquí)
    function setupFormSubmitListener() {
        if (!materialForm) { console.error("Formulario #standard-material-form no encontrado."); return; } // Usa referencia DOM

       materialForm.addEventListener('submit', function(event) { // Usa referencia DOM
           event.preventDefault(); // PREVENT default browser form submission and validation

           const form = event.target; // Obtiene referencia al formulario

           // 1. Recolectar datos y validar ítems (Llama a collectFormData)
           const datosSolicitud = collectFormData(); // Llama a la función definida aquí

           // 2. Validación General Frontend
           // Limpiar errores visuales y mensajes anteriores
            form.querySelectorAll('.error-field').forEach(el => el.classList.remove('error-field')); // Usa referencia DOM
            if (responseMessageDiv) { // Usa referencia DOM
                 responseMessageDiv.textContent = '';
                 // --- ** CORRECCIÓN AQUÍ: Usar responseMessageDiv ** ---
                 responseMessageDiv.classList.remove('processing', 'success', 'error', 'warning'); // Limpiar también warnings
                 // --- FIN CORRECCIÓN ---
            }

           let isValid = true;
           const errores = [];

           // Validar campos comunes requeridos (que ahora NO tienen el atributo 'required' en HTML)
           // 'proveedor', 'departamento_area', 'fecha_solicitud' are hidden/readonly and set by JS, assumed present.
           // Adding 'tipo_material' here as it's also effectively required once a material is selected
           const camposComunesReq = ['nombre_solicitante', 'proyecto', 'cantidad_solicitada', 'nombre_material', 'unidad_medida', 'tipo_material'];
           camposComunesReq.forEach(name => { // Itera sobre nombres (keys)
               const value = datosSolicitud[name]; // Obtener valor del objeto recolectado

               // Check for null, undefined, or empty string (after trim in collectFormData)
               if (value === null || value === undefined || value === "") {
                   isValid = false;
                   // Find the field to mark (tipo_material is an input, others are inputs/selects)
                   const campo = form.querySelector(`[name="${name}"]`);
                   if(campo) campo.classList.add('error-field');

                   let fieldName = name.charAt(0).toUpperCase() + name.slice(1).replace(/_/g, ' ');
                   // Improve field names for messages
                   if (name === 'unidad_medida' || name === 'nombre_material') {
                        const label = form.querySelector(`label[for="${campo?.id}"]`);
                        fieldName = label ? label.textContent.replace(':', '').trim() : fieldName; // Use label text if available
                   } else if (name === 'cantidad_solicitada') {
                         fieldName = 'Cantidad solicitada';
                   } else if (name === 'tipo_material') {
                         fieldName = 'Tipo de material'; // Explicitly name the type field
                   }
                    errores.push(`"${fieldName}" es obligatorio.`);
               } else if (name === 'cantidad_solicitada' && typeof value === 'number' && value <= 0) {
                     // Specific check for quantity value if it was somehow 0 or less after parsing (although HTML min="1" helps)
                     isValid = false;
                     const campo = form.querySelector(`[name="${name}"]`);
                     if(campo) campo.classList.add('error-field');
                      errores.push(`"Cantidad solicitada" debe ser un número mayor que 0.`);
               }
               // Note: 'especificaciones_adicionales' is NOT in camposComunesReq, so it won't be checked here if empty.
           });


            // --- ** VALIDACIÓN REVISADA PARA EL GRUPO DE DIMENSIONES ** ---
            // Se considera válido si UN CONJUNTO COMPLETO está lleno Y no hay conflictos.
            // Estos son los valores recolectados (null if N/A, "" if empty input)
            const largoVal = datosSolicitud['largo'];
            const anchoVal = datosSolicitud['ancho'];
            const altoVal = datosSolicitud['alto'];
            const diametroVal = datosSolicitud['diametro'];

             // Check for complete rectangular set (L, A, H filled - i.e., not null/empty)
             const isRectangularSetComplete = (largoVal !== null && largoVal !== "") &&
                                              (anchoVal !== null && anchoVal !== "") &&
                                              (altoVal !== null && altoVal !== "");

             // Check for complete cylindrical set (Dia, L filled - i.e., not null/empty)
             const isCylindricalSetComplete = (diametroVal !== null && diametroVal !== "") &&
                                               (largoVal !== null && largoVal !== "");


             // --- VALIDACIÓN DE CONFLICTO DE DIMENSIONES (Diámetro vs Ancho/Alto) ---
             // Esta validación ocurre PRIMERO. Si hay conflicto, el formulario es inválido.
             const collectedOtherLinearHasValue = (anchoVal !== null && anchoVal !== "") || (altoVal !== null && altoVal !== "");
             const collectedDiameterHasValue = (diametroVal !== null && diametroVal !== "");

             if (collectedDiameterHasValue && collectedOtherLinearHasValue) {
                 isValid = false; // Form is invalid due to conflict
                 console.log("Frontend Validation Error: Conflict between Diameter and Ancho/Alto values.");
                 // Mark conflicting fields visually (use DOM values before collection's null conversion for visual marker)
                 if(anchoInput && (anchoInput.value.trim() !== '' && anchoInput.value.trim().toUpperCase() !== 'N/A')) anchoInput.classList.add('error-field');
                 if(altoInput && (altoInput.value.trim() !== '' && altoInput.value.trim().toUpperCase() !== 'N/A')) altoInput.classList.add('error-field');
                 if(diametroInput && (diametroInput.value.trim() !== '' && diametroInput.value.trim().toUpperCase() !== 'N/A')) diametroInput.classList.add('error-field');
                 errores.push("No puedes especificar Diámetro si has especificado Ancho o Alto. Por favor, corrige las dimensiones.");
             } else {
                 // --- VALIDACIÓN DE CONJUNTO COMPLETO (SOLO SI NO HAY CONFLICTO) ---
                 // Si no hay conflicto, verificar si se proporcionó un conjunto completo de dimensiones.
                 if (!isRectangularSetComplete && !isCylindricalSetComplete) {
                      isValid = false; // Form is invalid because no complete set was provided
                      console.log("Frontend Validation Error: Missing a complete set of dimensions (No conflict detected).");
                      // Mark all dimension inputs to highlight the area needing input
                      if(largoInput) largoInput.classList.add('error-field');
                      if(anchoInput) anchoInput.classList.add('error-field');
                      if(altoInput) altoInput.classList.add('error-field');
                      if(diametroInput) diametroInput.classList.add('error-field');

                       // Specific error message indicating which sets are valid options
                       // Construct the message using collected values to be more specific? No, just list the required sets.
                       let specificDimError = "Se debe especificar un conjunto completo de dimensiones:<br>";
                       specificDimError += "<ul><li>Rectangular (Largo, Ancho, Alto)</li><li>Cilíndrica (Diámetro, Largo)</li></ul>";
                       errores.push(specificDimError);

                 }
                 // Optional additional validation: If cylindrical set is complete, ensure Ancho/Alto are N/A (should be enforced by JS logic and checked by conflict validation, but good to double-check if needed)
                 // if (isCylindricalSetComplete && collectedOtherLinearHasValue) { ... This case is already handled by the primary conflict check ... }
             }
            // --- ** FIN VALIDACIÓN REVISADA DIMENSIONES ** ---


           // Si hay errores de validación, mostrar y detener
           if (!isValid) {
                console.log("Validación fallida en frontend:", errores); // Log de depuración
                const uniqueErrors = [...new Set(errores)]; // Eliminar duplicados
               if (responseMessageDiv) { // Usa referencia DOM
                   // Mostrar errores en lista con formato HTML para saltos de línea y lista
                   // Use innerHTML as the message contains HTML tags for list items
                   responseMessageDiv.innerHTML = "Por favor, corrige los siguientes errores:<br><ul>" + uniqueErrors.map(err => `<li>${err}</li>`).join('') + "</ul>";
                   responseMessageDiv.classList.add('error'); // Añadir clase 'error' para el estilo
               }
                // Intenta enfocar el primer campo de error visible y no deshabilitado
                 const primerErrorField = form.querySelector('.error-field:not(:disabled):not([type="hidden"]):not([readonly])'); // Enfocar solo campos interactivos
                 if(primerErrorField) primerErrorField.focus();
                return; // Detener el submit
           }
           // --- Fin Validación General Frontend ---


           // 3. Si la validación general fue exitosa, proceder con el fetch
           console.log('Validación general exitosa. Datos del formulario a enviar:', datosSolicitud); // Log de depuración

           if (responseMessageDiv) { // Usa referencia DOM
                responseMessageDiv.textContent = 'Enviando solicitud...';
                responseMessageDiv.classList.remove('error', 'success', 'warning'); // Limpiar clases previas
                responseMessageDiv.classList.add('processing'); // Añadir clase 'processing'
            }

           if (submitBtn) submitBtn.disabled = true; // Disable button on submit start

           fetch(form.action, { // Usa form.action
               method: form.method, // Usa form.method (POST)
               headers: {
                   'Content-Type': 'application/json', // Enviamos JSON
               },
               body: JSON.stringify(datosSolicitud) // Convertir a string JSON
           })
           .then(response => {
               console.log("Respuesta fetch del backend:", response); // Log de depuración

                if (responseMessageDiv) responseMessageDiv.classList.remove('processing'); // Quitar clase 'processing'
                if (submitBtn) submitBtn.disabled = false; // Re-enable button on response

                if (!response.ok) {
                     // Attempt to parse error body as JSON
                     return response.json().then(errData => {
                          console.error("Error response body (JSON):", errData); // Log de depuración
                          let msg = errData.error || `Error: ${response.status}`;
                          if(errData.details) msg += `: ${errData.details}`;
                           // Do not show internal Notion details unless it's for advanced debugging
                          // if(errData.notion_error) msg += ` (Notion: ${errData.notion_error.message})`;
                          throw new Error(msg);
                     }).catch(() => {
                          // If JSON parsing fails, read as text or use just status text
                          return response.text().then(text => {
                                console.error("Error response body (Text):", text); // Log de depuración
                                // Avoid exposing too much server info
                                const errorTextPreview = text.substring(0, 150) + (text.length > 150 ? '...' : '');
                                throw new Error(`Error ${response.status}: ${response.statusText} - ${errorTextPreview}`); // Include part of the text
                          }).catch(() => {
                               // If everything fails
                                throw new Error(`Error ${response.status}: ${response.statusText}`);
                          });
                     });
                }
                 // If response is OK, parse the body as JSON
                return response.json();
           })
           .then(data => {
               console.log('Respuesta backend exitosa:', data); // Log de depuración
               if (submitBtn) submitBtn.disabled = false; // Re-enable button on success

               let feedbackMessage = "";
               let isSuccess = false; // True if the request was processed (message or warning), false if error
               let firstUrl = null;

               // Determine message and success status based on backend response structure
               if (data.message) { feedbackMessage = data.message; isSuccess = true; firstUrl = data.notion_url || data.notion_url_db2; }
               else if (data.warning) { feedbackMessage = data.warning; isSuccess = true; firstUrl = data.notion_url || data.notion_url_db2; }
               else if (data.error) { feedbackMessage = data.error; isSuccess = false; } // An error response means it was NOT successful
               else { feedbackMessage = "Respuesta inesperada del servidor."; isSuccess = false; }


               if (responseMessageDiv) { // Usa referencia DOM
                   // If success (message or warning), show the message and link if exists
                   if (isSuccess) {
                       responseMessageDiv.innerHTML = feedbackMessage + (firstUrl ? ` <a href="${firstUrl}" target="_blank" rel="noopener noreferrer" style="color: red;">Ver Registro</a>` : '');
                       responseMessageDiv.className = ''; // Clear previous classes
                       // Use success or warning class based on actual data structure
                       responseMessageDiv.classList.add(data.message ? 'success' : 'warning'); // Assume 'warning' if message field wasn't 'message' but 'warning'
                   } else { // If error, only show the message
                       responseMessageDiv.innerHTML = feedbackMessage || 'Error desconocido.'; // Fallback message
                       responseMessageDiv.className = ''; // Clear previous classes
                       responseMessageDiv.classList.add('error');
                   }
               }

               // Reset form and UI only if successful (based on isSuccess flag)
               if (isSuccess) {
                   form.reset();
                   console.log("Formulario reseteado."); // Log de depuración

                   currentFolio = generateFolio(); // Call pure function
                   updateFolioDisplay(currentFolio); // Call function defined above
                    console.log("Folio actualizado:", currentFolio); // Log de depuración

                   // Re-initialize dependent logic after reset
                   // handleProveedorChange() calls actualizarMateriales and clearDimensionFields.
                   // clearDimensionFields calls enforceDimensionDependency, which now runs *after* unit select is re-enabled (if data loaded)
                   handleProveedorChange();

                    // Restore default date
                    if(fechaInput) {
                         const today = new Date();
                         const year = today.getFullYear();
                         const month = ('0' + (today.getMonth() + 1)).slice(-2);
                         const day = ('0' + today.getDate()).slice(-2);
                         fechaInput.value = `${year}-${month}-${day}`;
                    }
                    console.log("Fecha restablecida in input readonly after reset.");

               }
           })
           .catch(error => {
               console.error('Error inesperado in fetch or processing:', error); // Log de depuración
                if (submitBtn) submitBtn.disabled = false; // Re-enable button on error

                if (responseMessageDiv) { // Usa referencia DOM
                    responseMessageDiv.classList.remove('processing');
                     // Use innerHTML to allow basic formatting or links if added later
                    responseMessageDiv.innerHTML = `Error de red o del servidor: ${error.message || 'Ver logs de consola.'}`;
                    responseMessageDiv.classList.add('error');
                    console.error("Error message shown in #response-message."); // Log de depuración
                }
               // Do not reset the form on error
               // Keep unit select disabled if initial dimension data load failed
                if (unidadMedidaSelect && (!allStandardDimensions || Object.keys(allStandardDimensions).length === 0)) {
                     unidadMedidaSelect.disabled = true; // Ensure it remains disabled if data wasn't loaded
                     console.warn("Unidad de medida disabled due to initial data load error.");
                 }
           });
       });
   }


    // --- ** CÓDIGO QUE SE EJECUTA INMEDIATAMENTE DENTRO DE DOMContentLoaded ** ---
    // Este código se ejecuta DESPUÉS de que todas las referencias DOM y funciones de este scope han sido definidas.

    // Generar y Mostrar Folio Inicial
    currentFolio = generateFolio(); // Pure function
    updateFolioDisplay(currentFolio); // <<< Call function defined ABOVE
    console.log("Initial folio generated:", currentFolio);

    // Deshabilitar el select de Unidad de medida hasta que los datos de dimensiones se carguen
    if (unidadMedidaSelect) {
        unidadMedidaSelect.disabled = true;
        console.log("Unidad de Medida select disabled initially.");
         unidadMedidaSelect.selectedIndex = 0; // Select the first disabled option
    } else {
        console.error("Unidad de Medida select #unidad_medida not found.");
         if(responseMessageDiv) { responseMessageDiv.textContent = "Error interno: Elemento de Unidad de Medida no encontrado."; responseMessageDiv.classList.add('error'); }
    }

     // Deshabilitar el select de Material hasta que se determine el proveedor y los materiales se pueblen (in this case, it's fixed)
     // Disable it here, and actualizarMateriales will enable it after populating.
    if (materialSelect) {
        materialSelect.disabled = true;
        console.log("Material select disabled initially.");
         materialSelect.selectedIndex = 0; // Select the first disabled option
    } else {
        console.error("Material select #nombre_material not found.");
        if(responseMessageDiv) { responseMessageDiv.textContent = "Error interno: Elemento de Material no encontrado."; responseMessageDiv.classList.add('error'); }
    }


    // Deshabilitar el botón de submit initially until data is loaded
    if(materialForm) {
        submitBtn = materialForm.querySelector('button[type="submit"]'); // Assign to the variable declared earlier
        if (submitBtn) {
            submitBtn.disabled = true;
            console.log("Submit button disabled initially.");
        } else {
            console.error("Submit button not found in the form.");
            if(responseMessageDiv) { responseMessageDiv.textContent = "Error interno: Botón de submit no encontrado."; responseMessageDiv.classList.add('error'); }
        }
    }


    // Load Data (Standard dimensions JSON)
    if (typeof STANDARD_DIMENSIONS_URL !== 'undefined' && STANDARD_DIMENSIONS_URL) {
        fetch(STANDARD_DIMENSIONS_URL)
        .then(res => {
            console.log("Fetch dimensions response received.");
            if (!res.ok) {
                 throw new Error(`HTTP error! status: ${res.status} when fetching dimensions.`);
            }
             return res.json();
        })
        .then(dimensionsData => {
            console.log("Initial data loaded successfully (Dimensions).", dimensionsData);
            allStandardDimensions = dimensionsData;

            console.log("Dimensions data loaded. Initializing dependent UI.");

            // Habilitar el select de Unidad de Medida AHORA que los datos están cargados
             if (unidadMedidaSelect) {
                 unidadMedidaSelect.disabled = false;
                 console.log("Unidad de Medida select enabled after data load."); // Log actualizado

                 // Explicitly update datalist right after enabling the select
                 // This handles the initial population for the default selected option ("").
                 updateDatalistForUnit(); // This will call populateDatalist([]) and trigger the console.log (was warn)
             }

            // Now call handleProveedorChange.
            // handleProveedorChange calls actualizarMateriales (enables material select)
            // handleProveedorChange calls clearDimensionFields, which calls enforceDimensionDependency.
            handleProveedorChange();


             if(materialForm) {
                 // Use the submitBtn variable from the DOMContentLoaded scope
                 if (submitBtn) submitBtn.disabled = false;
                 console.log("Submit button enabled after data load.");
             }

        })
        .catch(error => {
            console.error("General error loading initial JSON data or parsing:", error);
            if(responseMessageDiv){
                 responseMessageDiv.textContent = `Error al cargar datos iniciales: ${error.message || 'Ver logs de consola.'} Funcionalidad de dimensiones y unidad puede estar limitada.`;
                 responseMessageDiv.classList.add('error');
                 console.error("Error message shown in #response-message.");
            }
             // If dimension load fails, associated functionality is limited.
             // Unit and material selects remain disabled if not found/loaded.
             // Submit button remains enabled assuming form can be submitted without dimension list suggestions.
             if (unidadMedidaSelect) unidadMedidaSelect.disabled = true; // Ensure it remains disabled if data wasn't loaded
             if (materialSelect) materialSelect.disabled = true; // Also ensure material select remains disabled
             console.warn("Initial data load failed. Unit and Material selects disabled.");
        });
    } else {
         console.error("URLs for initial data (static JSON) are not defined or empty (Dimensions).");
         if(responseMessageDiv){
              responseMessageDiv.textContent = `Error: URLs de datos iniciales no configuradas en la plantilla HTML. Funcionalidad de dimensiones no disponible.`;
              responseMessageDiv.classList.add('error');
         }
         if (unidadMedidaSelect) unidadMedidaSelect.disabled = true;
         if (materialSelect) materialSelect.disabled = true; // Disable material select if data URL is missing
         console.warn("Carga de datos iniciales omitida due to missing URL. Unit and Material selects disabled.");
    }


    // --- Event Listeners (Inside DOMContentLoaded) ---

    // Listeners for dimension fields (Input events)
    // Each time a dimension field is typed into, enforce the dependency logic.
    // The datalist update is handled *inside* enforceDimensionDependency after state changes.
    if(largoInput) largoInput.addEventListener('input', function(event){ enforceDimensionDependency(event.target); });
    if(anchoInput) anchoInput.addEventListener('input', function(event){ enforceDimensionDependency(event.target); });
    if(altoInput) altoInput.addEventListener('input', function(event){ enforceDimensionDependency(event.target); });
    if(diametroInput) diametroInput.addEventListener('input', function(event){ enforceDimensionDependency(event.target); });


    // Listener for Unit select (Change event)
    if (unidadMedidaSelect) {
        unidadMedidaSelect.addEventListener('change', function() {
             console.log("unidadMedidaSelect change event fired. Calling updateDatalistForUnit."); // Log para depuración
             updateDatalistForUnit(); // Update datalist based on the new unit selection
             // No need to call enforceDimensionDependency here, as changing unit doesn't change values in dimension inputs,
             // only affects the datalist suggestions when user starts typing again.
         });
     }

    // Listener for Material select (Change event)
    if (materialSelect) {
        materialSelect.addEventListener('change', function() {
            console.log("Material Select change event fired. Calling actualizarTipoMaterial.");
            actualizarTipoMaterial();
        });
    } else {
        console.error("Material select #nombre_material not found when trying to add listener.");
    }

    // Configure the form submit listener
    setupFormSubmitListener();

}); // End DOMContentLoaded