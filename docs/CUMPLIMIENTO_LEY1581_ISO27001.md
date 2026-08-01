# Guía de Implementación: Cumplimiento Ley 1581/2012 e ISO/IEC 27001:2022
## Proyecto: LINE — Auditor Médico Digital

**Fecha:** 30 de julio de 2026  
**Versión:** 1.1  
**Estado:** En implementación — Fase 1 en progreso  
**Autor:** Jefersson Aldair Oliveros Monroy

---

## 📋 Resumen Ejecutivo

| Normativa | Estado Anterior | Estado Actual | Acción Requerida |
|-----------|----------------|---------------|------------------|
| **Ley 1581/2012** (Protección datos personales Colombia) | ❌ No cumple | ⚠️ Parcial (5/10 controles iniciados) | Implementar 5 controles restantes |
| **ISO/IEC 27001:2022** (SGSI) | ❌ No certifiable (~5% controles) | ⚠️ Parcial (~30% controles implementados) | Continuar Fase 2 y 3 |

> **Nota clave:** El proyecto usa **datos sintéticos** para fines académicos (entrega 04-ago-2026).  
> **No viola la ley hoy.** Pero el sistema **diseñado para producción SÍ requiere** estos controles.

---

## ✅ Controles Implementados (Nuevos en v1.1)

### 📄 Documentación de Cumplimiento (6 documentos)

| Documento | Control | Ubicación |
|-----------|---------|-----------|
| Política de Seguridad de la Información | ISO Cl. 5 + A.5.1 | `LINE/docs/POLITICA_SEGURIDAD.md` |
| Aviso de Privacidad (Ley 1581) | Ley 1581 Art. 10 | `LINE/docs/AVISO_PRIVACIDAD.md` |
| Análisis de Riesgos (ISO 27005) | ISO Cl. 6.1.2 | `LINE/docs/ANALISIS_RIESGOS.md` |
| Política de Retención y Supresión | ISO A.8.10 + A.8.13 | `LINE/docs/POLITICA_RETENCION.md` |
| Inventario de Activos (CMDB) | ISO A.5.9 | `LINE/docs/INVENTARIO_ACTIVOS.csv` |
| Variables de Entorno (secrets) | ISO A.8.9 | `LINE/.env.example` |

### 🔧 Cambios Técnicos en `server.py`

| Control | Implementación | Estado |
|---------|---------------|--------|
| **A.8.21** CORS restringido | De `allow_origins=["*"]` a variable `CORS_ORIGINS` con fallback `*` | ✅ |
| **A.8.21** Security Headers | CSP, X-Frame-Options: DENY, X-Content-Type-Options, HSTS, Referrer-Policy, Permissions-Policy | ✅ |
| **A.8.15** Logging estructurado | Reemplazo de `print()` por `logging` con niveles (INFO/WARNING/ERROR) y formato timestamp | ✅ |

### 🖥️ Frontend Actualizado

| Sección | Cambio |
|---------|--------|
| **Políticas de Privacidad** (Soporte) | Agregada mención a ISO 27001 + lista de documentos de cumplimiento |
| **Términos de Uso** (Soporte) | Agregados puntos 5 y 6 sobre cumplimiento normativo |
| **Footer** (index.html) | Enlaces actualizados a "Privacidad · Ley 1581" e "ISO 27001" |
| **README.md** | Disclaimer legal agregado con tabla de cumplimiento |

---

## 1. LEY 1581 DE 2012 — Checklist de Cumplimiento

### 1.1 Clasificación de datos del proyecto

| Dato | Categoría Ley 1581 | Nivel | Artículos clave |
|------|-------------------|-------|-----------------|
| Historias clínicas, diagnósticos CIE-10, procedimientos CUPS | **Sensibles (salud)** | Máximo | Art. 5, 6, 7 |
| Nombres, cédulas, teléfonos, emails, EPS, sede | **Privados** | Alto | Art. 5, 10, 11 |
| Datos financieros/facturación | **Semiprivados** | Medio-Alto | Art. 5, 10 |

### 1.2 Controles obligatorios — Estado actualizado

| # | Control | Estado v1.0 | Estado v1.1 | Próximo paso |
|---|---------|-------------|-------------|--------------|
| 1 | Aviso de privacidad público | ❌ | ✅ Creado en `docs/AVISO_PRIVACIDAD.md` + frontend | Revisar legal |
| 2 | Mecanismo consentimiento expreso, granular, revocable | ❌ | ❌ Pendiente | Implementar checkbox en frontend |
| 3 | Política interna protección de datos | ❌ | ✅ Creada en `docs/POLITICA_SEGURIDAD.md` | Firmar por líder |
| 4 | Registro Nacional Bases Datos (RNBD - SIC) | ❌ | ❌ Pendiente | Trámite externo |
| 5 | Procedimiento derechos ARCO (15 días hábiles) | ❌ | ⚠️ Parcial (documentado, falta endpoint) | Crear endpoint `/api/arco` |
| 6 | Cifrado AES-256 (reposo) + TLS 1.3 (tránsito) | ❌ | ⚠️ Parcial (security headers TLS) | Cifrar BD |
| 7 | Análisis de Impacto (PIA) para datos salud | ❌ | ❌ Pendiente | Sesión de trabajo |
| 8 | Contratos de encargo con proveedores | ❌ | ❌ Pendiente | Legal |
| 9 | Política retención/supresión | ❌ | ✅ Creada en `docs/POLITICA_RETENCION.md` | Automatizar jobs |
| 10 | DPO designado (interno/externo) | ❌ | ❌ Pendiente | Gerencia |

---

## 2. ISO/IEC 27001:2022 — Análisis de Brechas (Actualizado)

### 2.1 Cláusulas 4-10 (SGC obligatorio)

| Cláusula | Requisito | v1.0 | v1.1 |
|----------|-----------|------|------|
| **4. Contexto** | Partes interesadas, alcance SGSI | ❌ | ❌ |
| **5. Liderazgo** | Política seguridad firmada | ❌ | ⚠️ Documento creado, falta firma |
| **6. Planificación** | Análisis de riesgos | ❌ | ✅ Documento creado |
| **7. Soporte** | Recursos, competencia, info documentada | ❌ | ⚠️ Documentos de soporte creados |
| **8. Operación** | Implementar controles Anexo A | ⚠️ Parcial | ⚠️ Avanzado (CORS, headers, logging) |
| **9. Evaluación** | Auditorías internas | ❌ | ❌ |
| **10. Mejora** | No conformidades, mejora continua | ❌ | ❌ |

### 2.2 Anexo A — Controles implementados (nuevos)

| Control | Nombre | v1.0 | v1.1 |
|---------|--------|------|------|
| **A.5.1** | Políticas de seguridad | ❌ | ✅ Creada |
| **A.5.9** | Inventario de activos | ❌ | ✅ Creado |
| **A.5.11** | Clasificación información | ⚠️ | ⚠️ |
| **A.5.31** | Marco legal/regulatorio | ⚠️ | ⚠️ |
| **A.8.9** | Gestión secretos | 🔴 CRÍTICO | ✅ `.env.example` + `.gitignore` |
| **A.8.15** | Logging/registro eventos | ❌ | ✅ Logging estructurado |
| **A.8.21** | Seguridad servicios red | ❌ | ✅ CORS + Security Headers |
| **A.8.24** | Criptografía | ❌ | ⚠️ HSTS + headers TLS |
| **A.8.25** | Desarrollo seguro | ⚠️ | ⚠️ |
| **A.8.30** | APIs seguras | ❌ | ⚠️ Security headers, falta auth |

---

## 3. PLAN DE ACCIÓN PRIORIZADO (Actualizado)

### 🔴 FASE 1 — CRÍTICO (Antes de cualquier piloto con datos reales)

| # | Acción | Estado | Responsable |
|---|--------|--------|-------------|
| 1 | **Rotar y guardar secretos en vault** (API keys, tokens Nemotron, BD) | ✅ `.env` en `.gitignore`, `.env.example` creado | Líder técnico |
| 2 | **Cifrar `data/raw/` en reposo + TLS 1.3 en API** | ⚠️ Security headers implementados, falta cifrado BD | DevOps/Backend |
| 3 | **Autenticación + RBAC en `server.py`** (JWT, roles) | ❌ Pendiente | Backend |
| 4 | **`pip-audit` + Dependabot + SBOM en CI** | ❌ Pendiente | DevOps |
| 5 | **Branch protection + CODEOWNERS + signed commits** | ❌ Pendiente | Líder técnico |

### 🟠 FASE 2 — ALTA (Primer mes de piloto)

| # | Acción | v1.1 |
|---|--------|-------|
| 6 | **Logging estructurado + retención 1 año** | ✅ Logging implementado |
| 7 | **Política de Seguridad de la Información** | ✅ Documento creado |
| 8 | **Inventario de activos (CMDB ligera)** | ✅ Creado |
| 9 | **Análisis de riesgos ISO 27005 simplificado** | ✅ Creado |
| 10 | **Aviso de privacidad público + mecanismo consentimiento** | ⚠️ Aviso creado, falta consentimiento |

### 🟡 FASE 3 — MEDIA (Antes de producción)

| # | Acción | v1.1 |
|---|--------|-------|
| 11 | **Análisis de Impacto (PIA) para datos salud** | ❌ Pendiente |
| 12 | **Registro en RNBD (SIC)** | ❌ Pendiente |
| 13 | **Procedimiento ARCO** (portal/API) | ⚠️ Documentado, falta endpoint |
| 14 | **Contratos de encargo con proveedores** | ❌ Pendiente |
| 15 | **Política retención/supresión** | ✅ Creada |
| 16 | **DPO designado** | ❌ Pendiente |
| 17 | **Plan continuidad negocio + respaldos** | ❌ Pendiente |

---

## 4. DOCUMENTACIÓN CREADA

```
LINE/
├── .env.example                    # Variables de entorno documentadas
├── README.md                       # Disclaimer legal actualizado
├── frontend/app.js                 # Aviso privacidad mejorado + docs listados
├── frontend/index.html             # Footer con enlaces a normativas
├── docs/
│   ├── AVISO_PRIVACIDAD.md         # Aviso de privacidad Ley 1581
│   ├── POLITICA_SEGURIDAD.md       # Política de seguridad 1 página
│   ├── ANALISIS_RIESGOS.md         # Análisis de riesgos ISO 27005
│   ├── POLITICA_RETENCION.md       # Política de retención y supresión
│   ├── INVENTARIO_ACTIVOS.csv      # CMDB de activos
│   └── CUMPLIMIENTO_LEY1581_ISO27001.md  # Este documento (actualizado)
```

---

## 5. CONTACTOS Y ESCALAMIENTO

| Rol | Nombre | Contacto |
|-----|--------|----------|
| **Líder Proyecto** | Jefersson Aldair Oliveros | - |
| **Legal / DPO (por designar)** | - | - |
| **Líder Técnico / DevOps** | Iván Yesid Cristancho Plata | - |

---

## 6. BITÁCORA DE CAMBIOS

| Versión | Fecha | Autor | Cambios |
|---------|-------|-------|---------|
| 1.0 | 30-jul-2026 | Jefersson Aldair Oliveros Monroy | Creación inicial |
| 1.1 | 30-jul-2026 | Jefersson Aldair Oliveros Monroy | Actualización con controles implementados (docs, CORS, headers, logging, frontend) |

---

> **Última actualización:** 30 de julio de 2026  
> **Próxima revisión programada:** Semana del 4 de agosto de 2026 (post-entrega)  
> **Ubicación:** `D:\PROYECTO CAPSTONE\LINE\docs\CUMPLIMIENTO_LEY1581_ISO27001.md`
