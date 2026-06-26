# GUIAME v1.5.11 — admin_metrics_node

**Fecha de implementación:** 18 de junio de 2026  
**Estado:** Implementado y probado en producción  
**Proyecto:** GUIAME — Agente inteligente de ciberseguridad para usuarios no expertos

---

## 1. Resumen de la mejora

En la versión **GUIAME v1.5.11** se incorporó el componente **admin_metrics_node**, orientado a generar métricas administrativas a partir de la información real almacenada en la base de datos.

Este nodo utiliza principalmente la tabla **audit_logs**, incorporada en la versión anterior, y también consulta tablas existentes como **users** y **analyses**.

---

## 2. Objetivo

El objetivo de esta mejora es preparar a GUIAME para contar con un futuro panel administrativo basado en datos reales del sistema.

El nodo permite consultar:

- cantidad total de usuarios;
- cantidad total de análisis;
- análisis realizados en el día;
- casos de Modo Rescate;
- eventos de auditoría;
- advertencias de las últimas 24 horas;
- errores de las últimas 24 horas;
- eventos agrupados por tipo;
- eventos agrupados por severidad;
- actividad por día;
- endpoints más utilizados;
- eventos recientes.

---

## 3. Componentes incorporados

Se agregó el archivo:

```text
backend/admin_metrics_node.py
