# Análisis de Riesgos — LINE | Auditor Médico Digital

**Versión:** 1.0 · **Fecha:** 30-jul-2026  
**Autor:** Jefersson Aldair Oliveros Monroy  
**Metodología:** ISO 27005 simplificado (cualitativo)  
**Clasificación:** Alto (3), Medio (2), Bajo (1)

---

## 1. Identificación de Activos Críticos

| # | Activo | Tipo | Clasificación |
|---|--------|------|---------------|
| A1 | Base de datos `linea.db` (pacientes, HC, cruces) | Datos | Sensible |
| A2 | CSV `historia_clinica_detalle` | Datos |  Sensible |
| A3 | API Backend `server.py` | Software |  Interno |
| A4 | Modelos IA (`CNN.keras`, `XGBoost.pkl`) | Software |  Interno |
| A5 | API Key NVIDIA Nemotron | Secreto |  Crítico |
| A6 | `adres_scraper.py` (scraping BDUA) | Software |  Interno |
| A7 | Frontend web | Software |  Público |
| A8 | Documentación del proyecto | Datos |  Público |
| A9 | Logs de acceso | Datos |  Interno |
| A10 | Código fuente (GitHub) | Software |  Interno |

---

## 2. Matriz de Riesgos

### Convención
- **Probabilidad:** Alta (3) / Media (2) / Baja (1)
- **Impacto:** Crítico (3) / Significativo (2) / Menor (1)
- **Nivel:** Crítico (7-9) / Alto (5-6) / Medio (3-4) / Bajo (1-2)

### Riesgos Identificados

| # | Activo | Amenaza | Prob. | Impacto | Nivel |
|---|--------|---------|-------|---------|-------|
| R1 | A5 (API Key) | Exposición de API key en código/repositorio | 3 | 3 | ** 9** |
| R2 | A1 (BD) | Fuga de datos sensibles de pacientes | 2 | 3 | ** 6** |
| R3 | A1 (BD) | Pérdida de datos por falta de backups | 2 | 3 | ** 6** |
| R4 | A1, A2 (Datos) | Acceso no autorizado a datos de salud | 2 | 3 | ** 6** |
| R5 | A6 (Scraper) | Bloqueo del scraper ADRES por cambios en BDUA | 3 | 2 |  5 |
| R6 | A4 (Modelos) | Envenenamiento del modelo (adversarial) | 1 | 3 |  4 |
| R7 | A3 (API) | Ataque DoS al endpoint de análisis | 2 | 2 | 🟠 4 |
| R8 | A1 (BD) | Inyección SQL en consultas | 2 | 2 |  4 |
| R9 | A7 (Frontend) | XSS o manipulación del DOM | 2 | 1 |  3 |
| R10 | A10 (Código) | Exposición de secretos en Git | 2 | 2 |  4 |
| R11 | A4 (Modelos) | Modelo desactualizado (data drift) | 2 | 1 |  3 |
| R12 | A9 (Logs) | Logs sin rotación ni retención | 2 | 1 |  3 |

---

## 3. Plan de Tratamiento

| # | Riesgo | Control Aplicado | Control ISO | Responsable | Estado |
|---|--------|------------------|-------------|-------------|--------|
| R1 | API key expuesta | Variables de entorno (`.env` excluido en `.gitignore`) | A.8.9 | Líder Técnico |  Parcial |
| R2 | Fuga datos pacientes | CORS restringido + security headers en server.py | A.8.21 | Líder Técnico |  Parcial |
| R3 | Pérdida de datos | Backup manual de `linea.db` planificado | A.8.13 | Líder Técnico |  Pendiente |
| R4 | Acceso no autorizado | Autenticación JWT (pendiente), CORS restringido | A.8.2, A.8.5 | Backend |  Pendiente |
| R5 | Bloqueo scraper ADRES | Fallback a modo contingencia (datos formulario) | A.5.29 | Backend |  Implementado |
| R6 | Envenenamiento modelo | Modelos entrenados con datos controlados | A.8.25 | Líder Técnico |  Parcial |
| R7 | Ataque DoS | Rate limiting pendiente | A.8.21 | Backend | Pendiente |
| R8 | Inyección SQL | Uso de parámetros seguros en `_query()` | A.8.21 | Backend |  Implementado |
| R9 | XSS Frontend | Content-Security-Policy en security headers | A.8.21 | Backend |  Implementado |
| R10 | Secretos en Git | `.gitignore` con `.env`, secrets scanning pendiente | A.8.9 | DevOps |  Parcial |
| R11 | Data drift | Monitoreo manual de métricas del modelo | A.8.29 | Líder Técnico |  Pendiente |
| R12 | Logs sin retención | Logging estructurado implementado | A.8.15 | Backend |  Implementado |

---

## 4. Riesgos Residuales

| Riesgo | Nivel Residual | Aceptado | Justificación |
|--------|---------------|----------|---------------|
| API key expuesta |  3 (Medio) | Sí | `.env` en `.gitignore`, solo en local |
| Bloqueo scraper |  3 (Medio) | Sí | Modo contingencia implementado |
| Data drift | 3 (Medio) | Sí | Monitoreo manual aceptable para MVP |
| DoS |  4 (Alto) | No | Requiere rate limiting antes de producción |

---

## 5. Seguimiento

| KPI | Meta | Frecuencia |
|-----|------|------------|
| Controles implementados | 100% Fase 1 | Mensual |
| Vulnerabilidades críticas | 0 | Semanal |
| Secretos en código | 0 | Por commit |
| Backups verificados | 1/mes | Mensual |

---

*Documento controlado v1.0 — Próxima revisión: Semana del 4 de agosto de 2026*
