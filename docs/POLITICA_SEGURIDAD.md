# Política de Seguridad de la Información
## LINE — Auditor Médico Digital · Health & Life IPS SAS

| Versión | Fecha | Estado | 
|---------|-------|--------|
| 1.0 | 30-jul-2026 | Aprobada |

---

### 1. Propósito

Establecer el compromiso de **Health & Life IPS SAS** con la protección de la información de pacientes, datos clínicos y activos tecnológicos del sistema **LINE — Auditor Médico Digital**, asegurando confidencialidad, integridad y disponibilidad.

### 2. Alcance

Esta política aplica a todo el personal, contratistas y sistemas que interactúan con LINE, incluyendo:
- Datos de pacientes (identificación, historia clínica, afiliación)
- Modelos de IA (CNN, XGBoost, Nemotron)
- Infraestructura tecnológica (servidores, bases de datos, APIs)
- Proveedores externos (NVIDIA, ADRES)

### 3. Principios

| Principio | Descripción |
|-----------|-------------|
| **Confidencialidad** | Los datos de pacientes solo se acceden por personal autorizado para fines de auditoría médica |
| **Integridad** | Los registros de auditoría no pueden modificarse sin dejar trazabilidad |
| **Disponibilidad** | El sistema debe estar operativo en horarios definidos con respaldos verificados |
| **Cumplimiento** | Nos regimos por la Ley 1581/2012, ISO/IEC 27001:2022 y normativa SGSSS |

### 4. Roles y Responsabilidades

| Rol | Responsabilidad |
|-----|----------------|
| **Líder de Proyecto** | Aprobación de políticas, decisiones de seguridad, priorización de controles |
| **Líder Técnico** | Implementación de controles ISO A.8, CI/CD, gestión de secretos, parches |
| **Equipo Desarrollo** | Seguridad en código, validación de entradas, revisión de dependencias |
| **Proveedores (NVIDIA, etc.)** | Cumplimiento de cláusulas de seguridad contractuales |

### 5. Controles Esenciales

1. **Gestión de secretos**: Las API keys se almacenan en variables de entorno (`.env`), nunca en el código fuente
2. **Control de acceso**: Autenticación requerida para endpoints de producción (JWT pendiente)
3. **Cifrado**: TLS 1.2+ en tránsito, cifrado en reposo planificado para Fase 1
4. **Logs**: Registro de eventos con retención mínima de 1 año
5. **Actualizaciones**: Dependencias auditadas semanalmente (`pip-audit`, Dependabot)

### 6. Revisión

Esta política se revisa anualmente o ante cambios significativos en el sistema o normativa.

---

**Aprobado por:** *[Nombre del Líder de Proyecto]*  
**Fecha de aprobación:** 30 de julio de 2026  
**Próxima revisión:** Julio 2027

---
*Documento controlado — Prohibida su reproducción sin autorización*
