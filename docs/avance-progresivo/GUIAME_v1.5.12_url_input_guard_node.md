# GUIAME v1.5.12 — url_input_guard_node

**Fecha:** 2026-06-20  
**Estado:** Implementado y confirmado en producción  
**Tipo de mejora:** Seguridad / Validación de entrada

## Objetivo

Implementar un control de seguridad para validar URLs antes de enviarlas al análisis del agente, evitando esquemas peligrosos y destinos internos/no públicos.

## Problema corregido

El formulario de análisis permitía ingresar URLs sin validación suficiente, lo que podía aceptar entradas peligrosas como:

- `javascript:alert(1)`
- `data:text/html,<script>alert(1)</script>`
- `file:///etc/passwd`
- `http://localhost`
- `http://127.0.0.1`
- `http://192.168.x.x`
- `http://10.x.x.x`

Este comportamiento estaba señalado en la revisión de seguridad como riesgo alto.

## Cambios aplicados

### Frontend

Archivo modificado:

- `html/index.html`

Se agregó validación antes de enviar el análisis cuando `inputType === 'url'`.

El frontend ahora:

- Solo permite URLs con protocolo `http://` o `https://`.
- Bloquea `javascript:`, `data:` y otros esquemas peligrosos.
- Bloquea hosts internos como `localhost`, `127.0.0.1`, `0.0.0.0` y `::1`.
- Bloquea rangos privados como `10.x.x.x`, `192.168.x.x` y `172.16.x.x` a `172.31.x.x`.
- Limita la longitud de la URL a 2048 caracteres.

### Backend

Archivo modificado:

- `backend/routers/analyze.py`

Se agregó validación real en el endpoint `/api/analyze`.

El backend ahora:

- Valida URLs antes de consumir cuota diaria.
- Bloquea esquemas no permitidos.
- Bloquea localhost, loopback, redes privadas, link-local, multicast, reserved y unspecified.
- Resuelve DNS con `socket.getaddrinfo`.
- Rechaza dominios que apunten a IPs internas o no públicas.
- Devuelve HTTP 400 con mensaje genérico cuando la URL no está permitida.

## Pruebas realizadas

### URLs bloqueadas correctamente

- `javascript:alert(1)`
- `data:text/html,<script>alert(1)</script>`
- `file:///etc/passwd`
- `http://localhost:8000/admin`
- `http://127.0.0.1:8000/admin`
- `http://192.168.1.1`
- `http://10.0.0.1`

### URLs permitidas correctamente

- `https://guiame.pro`
- `https://www.google.com`

## Resultado

El punto de seguridad “URLs sin validar antes del análisis” queda cerrado con protección en frontend y backend.

## Estado final

**GUIAME v1.5.12 — url_input_guard_node** queda implementado, probado y listo para continuar con el siguiente control de seguridad.
