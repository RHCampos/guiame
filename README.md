# GUIAME - Agente Inteligente de Ciberseguridad para Usuarios No Expertos

GUIAME es un prototipo académico desarrollado como parte del Trabajo Final de Grado. Su objetivo es asistir a usuarios no expertos en la identificación temprana de situaciones digitales potencialmente riesgosas, tales como mensajes sospechosos, enlaces dudosos, archivos permitidos para análisis preliminar o solicitudes que podrían estar vinculadas con phishing, estafas digitales o suplantación de identidad.

El sistema brinda una evaluación orientativa del nivel de riesgo, explica las señales detectadas en lenguaje claro y ofrece recomendaciones preventivas para favorecer una toma de decisiones digitales más segura.

## Decisiones técnicas principales

Durante el desarrollo se priorizó una arquitectura simple, modular y defendible para un prototipo académico. Se separó el frontend del backend, se utilizó FastAPI para exponer los servicios principales, PostgreSQL para registrar usuarios y análisis, Docker para organizar el entorno de despliegue y Nginx como servidor web.
El flujo interno del agente se estructuró mediante LangGraph para dividir el análisis en etapas diferenciadas, como validación de entrada, análisis heurístico, recuperación de contexto, apoyo de un modelo de lenguaje y generación de la respuesta final. Además, se incorporaron controles de seguridad para reducir riesgos asociados a URLs no públicas, archivos peligrosos, abuso del sistema y exposición de información sensible.

## Objetivo del prototipo

Permitir a un usuario no experto ingresar mensajes, enlaces, archivos o situaciones digitales sospechosas, con el fin de obtener una evaluación preliminar del nivel de riesgo, una explicación comprensible de las señales detectadas y recomendaciones preventivas orientadas a la toma de decisiones digitales más seguras.

## Alcance

El prototipo tiene carácter académico, preventivo y orientativo. No reemplaza el análisis profesional de un especialista en ciberseguridad ni garantiza la detección definitiva de todas las amenazas posibles.

La versión actual permite:

- Registro e inicio de sesión de usuarios.
- Inicio de sesión mediante Google.
- Validación de cuenta por correo electrónico.
- Recuperación de acceso.
- Análisis de mensajes sospechosos.
- Análisis de enlaces/URLs.
- Carga controlada de archivos permitidos.
- Validación de extensiones y tamaño máximo de archivo.
- Clasificación orientativa del riesgo.
- Explicación en lenguaje claro.
- Recomendaciones preventivas.
- Modo Rescate.
- Historial de análisis por usuario.
- Límite diario de análisis por usuario.
- Registro de fecha de último acceso.

## Tecnologías utilizadas

El prototipo fue desarrollado utilizando una arquitectura web con frontend, backend, base de datos y servicios complementarios.

Componentes principales:

- Frontend: HTML, CSS y JavaScript.
- Backend: Python con FastAPI.
- Base de datos: PostgreSQL.
- Contenedores: Docker y Docker Compose.
- Servidor web: Nginx.
- Orquestación del flujo del agente: LangGraph.
- Recuperación de contexto: RAG con embeddings.
- OCR para archivos compatibles: procesamiento de imágenes/documentos permitidos.
- Modelo de lenguaje externo: generación de explicaciones y recomendaciones en lenguaje claro.

## Funcionamiento general

El flujo principal del prototipo puede resumirse de la siguiente manera:

Inicio de sesión o registro -> Dashboard principal -> Nueva consulta de seguridad -> Selección del canal -> Selección del tipo de entrada -> Carga de mensaje, enlace o archivo -> Análisis preliminar -> Resultado de riesgo -> Explicación comprensible -> Recomendación preventiva -> Modo Rescate o retroalimentación -> Nueva consulta o cierre del proceso.

## Lógica de análisis

GUIAME utiliza una lógica híbrida de análisis. En primer lugar, aplica reglas heurísticas para detectar señales observables de riesgo, como urgencia artificial, enlaces sospechosos, solicitudes de contraseñas, códigos de verificación, datos bancarios o posibles intentos de suplantación.

Luego, el sistema puede recuperar contexto mediante RAG y utilizar una capa de inteligencia artificial para generar una explicación comprensible y recomendaciones preventivas. El resultado final se presenta como una clasificación orientativa de riesgo bajo, medio o alto.

## Aclaración académica

GUIAME fue desarrollado como prototipo académico de asistencia preventiva. Sus resultados tienen carácter orientativo y no constituyen un diagnóstico definitivo de ciberseguridad. El sistema busca ayudar al usuario a reconocer señales de alerta y tomar decisiones más prudentes, pero no reemplaza herramientas profesionales de seguridad ni la intervención de un especialista.

## Seguridad implementada

El prototipo incorpora medidas de seguridad orientadas a proteger el acceso, el uso del sistema y la información procesada:

- Contraseñas con mínimo 12 caracteres y máximo 64.
- Requisito de mayúscula, minúscula, número y carácter especial.
- Hashing de contraseñas.
- Validación de cuenta por correo electrónico.
- Recuperación de acceso mediante token.
- Bloqueo por intentos fallidos de inicio de sesión.
- Registro de último acceso.
- Límite diario de 10 análisis por usuario autenticado.
- Validación de URLs.
- Bloqueo de localhost, rangos privados y direcciones no públicas.
- Validación de archivos antes del análisis.
- Tamaño máximo de archivo: 10 MB.
- Bloqueo de extensiones potencialmente peligrosas.
- Mensajes de error controlados.

## Archivos permitidos y bloqueados

Extensiones permitidas:

.txt, .csv, .json, .md, .log, .eml, .pdf, .docx, .png, .jpg, .jpeg, .webp, .bmp, .tif, .tiff

Extensiones bloqueadas:

.exe, .bat, .cmd, .com, .msi, .scr, .pif, .dll, .sys, .jar, .ps1, .vbs, .vbe, .js, .jse, .wsf, .wsh, .html, .htm, .svg, .php, .asp, .aspx, .jsp, .docm, .xlsm, .pptm, .lnk, .iso, .apk

Los archivos bloqueados son rechazados antes de consumir cuota de análisis o ejecutar el flujo interno del agente.

## Estructura general del proyecto
```text
guiame/
├── backend/
│   ├── agent/
│   ├── db/
│   ├── routers/
│   └── main.py
├── html/
│   └── index.html
├── nginx/
├── docs/
│   └── avance-progresivo/
├── docker-compose.yml
└── README.md
```
## Ejecución en entorno controlado

El prototipo fue desplegado en un VPS mediante contenedores Docker, con frontend web, backend, base de datos PostgreSQL y servidor Nginx.

Para una ejecución local o en entorno controlado, se requiere configurar previamente las variables de entorno necesarias, especialmente aquellas vinculadas con base de datos, autenticación, correo electrónico y servicios externos.

Ejemplo general de ejecución:

docker compose up -d --build

Luego, la aplicación puede accederse desde el dominio o puerto configurado para el frontend.

## Variables de entorno

Por seguridad, las claves reales, tokens y credenciales productivas no se incluyen en el repositorio. Para ejecutar el proyecto se debe crear un archivo de variables de entorno según la configuración requerida por el backend.

Ejemplos de variables necesarias:
```text
DATABASE_URL=
SECRET_KEY=
ANTHROPIC_API_KEY=
VOYAGE_API_KEY=
RESEND_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
FRONTEND_URL=
```
## Demo funcional

La demo funcional del prototipo GUIAME se encuentra disponible en un entorno productivo controlado, desplegado en un VPS para su evaluación académica y validación técnica.

Demo funcional:

https://guiame.pro

Repositorio del proyecto:

https://github.com/RHCampos/guiame

## Validación del prototipo

La validación preliminar se realizó mediante casos simulados representativos de situaciones digitales frecuentes, tales como phishing, enlaces dudosos, suplantación de identidad, solicitudes de datos sensibles, archivos permitidos y consultas de bajo riesgo.

Los casos simulados permiten comparar resultados esperados y resultados obtenidos, observando la coherencia de la clasificación, la claridad de las explicaciones y la pertinencia de las recomendaciones preventivas.

## Mejoras futuras

Entre las posibles mejoras futuras se contemplan:

- Integración con VirusTotal API para consulta de reputación de archivos o hashes.
- Análisis de archivos de mayor riesgo mediante contenedores Docker efímeros.
- Incorporación de un modelo local mediante Ollama u otra alternativa similar.
- Mayor monitoreo operativo.
- Panel administrativo ampliado.
- Reportes avanzados.
- Mejora continua de reglas heurísticas y validación con más casos.

## Autor

Rubén H. Campos

Trabajo Final de Grado
Agente Inteligente de Ciberseguridad para Usuarios No Expertos
