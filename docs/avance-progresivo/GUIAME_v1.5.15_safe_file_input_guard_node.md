# GUIAME v1.5.15 — safe_file_input_guard_node

**Fecha:** 2026-06-20  
**Estado:** Implementado y confirmado en producción  
**Tipo de mejora:** Seguridad / Validación segura de archivos

## Objetivo

Reforzar el manejo seguro de archivos en GUIAME, evitando que archivos no permitidos o potencialmente peligrosos sean leídos, enviados o procesados por el backend.

## Problema corregido

La revisión de seguridad indicó que el flujo de archivos validaba principalmente el tamaño, pero no aplicaba una validación completa de extensión, tipo y seguridad.

El flujo existente usaba `FileReader` en frontend, enviaba `content`, `filename` e `input_type` al backend, y luego procesaba el contenido mediante `extract_text_from_file`.

## Cambios aplicados

### Frontend

Archivo modificado:

- `html/index.html`

Cambios realizados:

- Se agregó atributo `accept` al input de archivos.
- Se agregó lista de extensiones permitidas.
- Se agregó lista de extensiones bloqueadas.
- Se agregó validación de tamaño máximo de 10 MB.
- Se agregó validación de MIME cuando el navegador lo informa.
- Se bloquean archivos sin extensión.
- Se bloquean extensiones peligrosas o activas.

Extensiones permitidas:

- `.txt`
- `.csv`
- `.json`
- `.md`
- `.log`
- `.eml`
- `.pdf`
- `.docx`
- `.png`
- `.jpg`
- `.jpeg`
- `.webp`
- `.bmp`
- `.tif`
- `.tiff`

Extensiones bloqueadas por seguridad:

- `.exe`
- `.bat`
- `.cmd`
- `.com`
- `.msi`
- `.scr`
- `.pif`
- `.dll`
- `.sys`
- `.jar`
- `.ps1`
- `.vbs`
- `.vbe`
- `.js`
- `.jse`
- `.wsf`
- `.wsh`
- `.html`
- `.htm`
- `.svg`
- `.php`
- `.asp`
- `.aspx`
- `.jsp`
- `.docm`
- `.xlsm`
- `.pptm`
- `.lnk`
- `.iso`
- `.apk`

### Backend

Archivo modificado:

- `backend/routers/analyze.py`

Cambios realizados:

- Se agregó validación de `input_type`.
- Se agregó validación de archivos antes de consumir cuota diaria.
- Se agregó sanitización del nombre del archivo.
- Se agregó validación de extensión permitida.
- Se agregó bloqueo de extensiones peligrosas.
- Se agregó estimación de tamaño del payload recibido.
- Se evita que archivos no permitidos lleguen al extractor.

### Extractor de archivos

Archivo modificado:

- `backend/agent/file_extractor.py`

Cambios realizados:

- Se quitaron `html` y `htm` de los tipos de texto permitidos.
- Se reemplazaron errores técnicos con mensajes seguros.
- Se eliminó el fallback permisivo que analizaba contenido de extensiones desconocidas.
- Si llega una extensión no soportada, se responde con un mensaje defensivo.

## Pruebas realizadas

### Archivos permitidos

- `archivo.txt`
- `captura.png`
- `documento.pdf`
- `documento.docx`

### Archivos bloqueados

- `prueba.exe`
- `factura_urgente.scr`
- `comprobante.bat`
- `foto.jpg.exe`
- `pagina.html`
- `script.js`
- `macro.docm`

## Resultado

GUIAME ahora bloquea archivos ejecutables, scripts, macros y formatos activos o potencialmente peligrosos antes de procesarlos.

El análisis de archivos queda limitado a formatos compatibles con el prototipo: texto, PDF, DOCX e imágenes para OCR.

## Estado final

**GUIAME v1.5.15 — safe_file_input_guard_node** queda implementado, probado y listo para continuar con el siguiente control de seguridad.
