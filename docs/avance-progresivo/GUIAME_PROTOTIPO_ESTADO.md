## Actualización del prototipo — GuIAme v1.5.7 / v1.5.8

Fecha: 14/06/2026  
Ubicación del proyecto en VPS: `/opt/guiame`  
Frontend activo: `html/index.html`  
Backend: `backend/`  
Repositorio GitHub: `RHCampos/guiame`

### v1.5.7 — Modo Rescate en pantalla Resultado

Se incorporó la funcionalidad **Modo Rescate** en la pantalla **Resultado**, ubicada debajo de la sección **¿Qué hacer ahora?**.

El objetivo de esta funcionalidad es asistir al usuario no experto después de detectar una posible amenaza, permitiéndole indicar si ya interactuó con el mensaje, enlace o archivo analizado.

Opciones disponibles:

- No hice clic.
- Hice clic en el enlace.
- Ingresé una contraseña.
- Ingresé datos bancarios.
- Compartí un código.
- Descargué o abrí un archivo.

Según la opción seleccionada, GuIAme muestra un plan personalizado de respuesta, con acciones preventivas, urgentes o críticas.

Esta funcionalidad fortalece el valor del prototipo porque GuIAme no solo informa el riesgo detectado, sino que también acompaña al usuario en la toma de decisiones posteriores a una posible interacción con la amenaza.

### Estado de Git de v1.5.7

La versión visual del Modo Rescate fue confirmada y subida correctamente a GitHub.

Datos registrados:

- Commit: `f7bda5f`
- Mensaje: `feat(frontend): add rescue mode to result page`
- Rama: `main`
- Tag: `v1.5.7`
- Archivo modificado: `html/index.html`
- Cambios: 254 inserciones

Estado confirmado:

`HEAD -> main, tag: v1.5.7, origin/main`

---

## Fase 2A — Persistencia del Modo Rescate

Después de validar que el Modo Rescate funcionaba correctamente en frontend, se avanzó con la persistencia de la opción seleccionada por el usuario.

### Cambios implementados

Se modificaron los siguientes archivos:

- `backend/db/database.py`
- `backend/models/schemas.py`
- `backend/routers/analyze.py`
- `html/index.html`

### Cambios en base de datos

Se agregaron nuevos campos a la tabla `analyses`:

- `rescue_case`
- `rescue_level`
- `rescue_used_at`

Estos campos permiten guardar:

- qué opción seleccionó el usuario en el Modo Rescate;
- el nivel asociado al caso;
- la fecha y hora en que se activó el Modo Rescate.

### Nuevo endpoint backend

Se agregó el endpoint:

`POST /api/rescue`

Este endpoint recibe el `analysis_id` y el `rescue_case`, y guarda la selección correspondiente en la base de datos.

### Casos contemplados

- `no_click` → preventivo.
- `clicked_link` → atención.
- `entered_password` → urgente.
- `bank_data` → crítico.
- `shared_code` → crítico.
- `opened_file` → urgente.

### Corrección aplicada

Durante la implementación inicial, el backend quedó reiniciando por el siguiente error:

`NameError: name 'RescueRequest' is not defined`

La causa fue que el nuevo endpoint `/rescue` usaba el schema `RescueRequest`, pero este no había quedado correctamente definido/importado.

Se corrigió agregando y asegurando:

- `class RescueRequest(BaseModel)` en `backend/models/schemas.py`;
- importación de `RescueRequest` en `backend/routers/analyze.py`.

Después de la corrección, el backend volvió a iniciar correctamente y la funcionalidad fue probada con éxito.

### Estado actual

La Fase 2A quedó funcionando correctamente:

- El Modo Rescate se muestra en frontend.
- El usuario puede seleccionar una opción.
- El frontend envía la opción al backend.
- El backend guarda la selección en la base de datos.
- El análisis mantiene asociado el caso de rescate elegido.

---

## Próximo paso recomendado — Fase 2B

La próxima mejora sugerida es mostrar en el Dashboard una etiqueta dentro del historial cuando un análisis tenga Modo Rescate activado.

Ejemplo visual esperado:

`🛟 Modo Rescate: Ingresé una contraseña`

Esto permitirá que el historial no solo muestre si un análisis fue seguro, sospechoso o peligroso, sino también si el usuario activó el Modo Rescate y qué tipo de situación declaró.
