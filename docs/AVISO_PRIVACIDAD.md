# Aviso de Privacidad — LINE | Health & Life IPS SAS

**Última actualización:** 30 de julio de 2026  
**Fundamento legal:** Ley 1581 de 2012, Decreto 1377 de 2013, Decreto 1074 de 2015

---

## 1. Identidad del Responsable

| Información | Dato |
|-------------|------|
| **Razón Social** | Health & Life IPS SAS |
| **Producto** | LINE — Auditor Médico Digital |
| **Correo DPO** | protecciondatos@hlsite.com.co |
| **Teléfono** | +57 (1) 234 5678 |
| **Dirección** | Bogotá D.C., Colombia |

## 2. Datos Personales Recopilados

| Categoría | Datos | Finalidad |
|-----------|-------|-----------|
| **Identificación** | Nombres, apellidos, tipo y número de documento, EPS, régimen | Verificación de afiliación en BDUA-ADRES, cruce con historia clínica |
| **Datos sensibles (salud)** | Diagnósticos CIE-10, procedimientos CUPS, historias clínicas, soportes clínicos | Auditoría médica de prefacturas, detección de inconsistencias |
| **Facturación** | Códigos de factura, valores, cantidades, fechas | Validación de facturación vs servicios prestados |

## 3. Finalidades del Tratamiento

1. **Verificar** la identidad y afiliación del paciente ante ADRES (BDUA)
2. **Auditar** prefacturas contra historias clínicas para detectar inconsistencias
3. **Identificar** fugas de ingreso (servicios realizados no facturados)
4. **Rechazar** facturación sin soporte clínico (Código CUPS sin registro en HC)
5. **Generar** reportes de auditoría para la IPS
6. **Entrenar y mejorar** modelos de IA (CNN, XGBoost) con datos anonimizados

## 4. Derechos del Titular (ARCO)

El titular puede ejercer sus derechos de **Acceder, Rectificar, Cancelar y Oponerse** al tratamiento de sus datos:

| Derecho | Descripción | Canal |
|---------|-------------|-------|
| **Acceder** | Conocer qué datos tenemos y cómo se usan | protecciondatos@hlsite.com.co |
| **Rectificar** | Actualizar datos incorrectos o desactualizados | protecciondatos@hlsite.com.co |
| **Cancelar** | Solicitar la eliminación de datos no necesarios | protecciondatos@hlsite.com.co |
| **Oponerse** | Limitar el tratamiento para fines específicos | protecciondatos@hlsite.com.co |

**Plazo de respuesta:** 15 días hábiles (Art. 15 Ley 1581)

## 5. Transferencia de Datos

| Destinatario | Finalidad | País |
|-------------|-----------|------|
| **ADRES (BDUA)** | Consulta de afiliación | Colombia |
| **NVIDIA (Nemotron)** | Análisis LLM de prefacturas (datos anonimizados) | Estados Unidos |
| **Entes de control (SIC)** | Requerimientos legales | Colombia |

## 6. Seguridad de la Información

Implementamos controles basados en ISO/IEC 27001:2022:
- Cifrado en tránsito (TLS 1.2+)
- Acceso restringido por roles (RBAC pendiente)
- Logs de acceso con retención mínima de 1 año
- Modelos de IA entrenados con datos sintéticos para fines académicos

## 7. Política de Retención

| Tipo de Dato | Período de Retención |
|--------------|---------------------|
| Datos de pacientes (identificación, EPS) | 5 años desde última atención |
| Historias clínicas | 20 años (Ley 2015 de 2020) |
| Logs de acceso | 1 año |
| Modelos de IA entrenados | 5 años desde última versión |

## 8. Contacto

Para ejercer sus derechos ARCO o cualquier consulta sobre protección de datos:
- **Correo:** protecciondatos@hlsite.com.co
- **Teléfono:** +57 (1) 234 5678
- **Dirección:** Bogotá D.C., Colombia

---

*Documento controlado v1.0 — Health & Life IPS SAS*
