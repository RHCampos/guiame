# GUIAME v1.5.14 — security_headers_csp_node

**Fecha:** 2026-06-20  
**Estado:** Implementado y confirmado en producción  
**Tipo de mejora:** Seguridad / Headers HTTP / CSP inicial

## Objetivo

Agregar headers de seguridad HTTP en el frontend de GUIAME para reducir riesgos de clickjacking, MIME sniffing, exposición innecesaria de referrers, abuso de permisos del navegador y ejecución de contenido embebido no deseado.

## Problema corregido

La revisión de seguridad indicó que GUIAME no tenía configurada una Content Security Policy ni headers HTTP de seguridad en el servidor web.

## Cambios aplicados

Se creó una configuración propia de Nginx:

- `nginx/default.conf`

Se actualizó el montaje en:

- `docker-compose.yml`

El contenedor `guiame-web` ahora monta:

- `./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro`

## Headers agregados

```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()" always;
add_header Content-Security-Policy "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests" always;
