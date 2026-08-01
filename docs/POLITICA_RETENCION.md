# Política de Retención y Supresión de Datos
## LINE — Auditor Médico Digital · Health & Life IPS SAS

**Versión:** 1.0 · **Fecha:** 30-jul-2026  
**Fundamento legal:** Ley 1581/2012 Art. 11, Ley 2015/2020, ISO 27001:2022 A.8.10, A.8.13

---

## 1. Objetivo

Definir los plazos de retención y los mecanismos de supresión segura de los datos personales y clínicos tratados por el sistema LINE, cumpliendo con la normativa colombiana de protección de datos y la Ley de Historia Clínica.

## 2. Tabla de Retención

| Categoría | Datos | Plazo de Retención | Fundamento Legal | Acción al Vencimiento |
|-----------|-------|-------------------|------------------|----------------------|
| **Identificación del paciente** | Nombres, cédula, EPS, régimen, tipo de afiliación | 5 años desde la última atención | Ley 1581 Art. 11 (finalidad del tratamiento) | Anonimización irreversible |
| **Historia Clínica** | Diagnósticos CIE-10, procedimientos CUPS, soportes clínicos, notas médicas | 20 años desde la última atención | Ley 2015 de 2020 Art. 5 | Archivado cifrado + eliminación física |
| **Prefacturas** | Códigos CUPS facturados, cantidades, valores, fechas | 5 años desde la fecha de facturación | Estatuto Tributario (facturación electrónica) | Eliminación segura |
| **Cruces HC vs PF** | Resultados de auditoría, alertas, recomendaciones | 5 años desde la auditoría | Finalidad del sistema | Anonimización |
| **Logs de acceso** | IP, endpoint, timestamp, usuario | 1 año | ISO 27001 A.8.15 | Rotación y eliminación |
| **Modelos de IA entrenados** | Pesos del modelo (CNN, XGBoost) | 5 años desde última versión | Propiedad intelectual | Archivado o eliminación |
| **Resultados de ADRES (BDUA)** | Nombre, documento, EPS, régimen, estado | Solo durante la sesión de auditoría | No almacenar permanentemente | Eliminación inmediata post-análisis |
| **Archivos subidos (CSV/PDF)** | Prefacturas cargadas por el usuario | 30 días o hasta fin de sesión | Seguridad | Eliminación automática |

## 3. Mecanismos de Supresión

| Método | Aplica a | Descripción |
|--------|----------|-------------|
| **Anonimización** | Datos de identificación, cruces HC-PF | Reemplazo de identificadores con hash irreversible, eliminación de nombres y cédulas |
| **Eliminación segura** | Archivos CSV/PDF subidos, logs | Borrado físico del archivo + sobreescritura del sector |
| **Archivado cifrado** | Historias clínicas vencidas | Compresión + cifrado AES-256, almacenamiento fuera de línea |

## 4. Procedimiento ARCO (Acceso, Rectificación, Cancelación, Oposición)

El titular puede solicitar:

1. **Acceso:** Enviar correo a protecciondatos@hlsite.com.co con el asunto "ARCO - Acceso". Se responderá en 15 días hábiles con los datos tratados.
2. **Rectificación:** Si los datos son incorrectos, se actualizarán en la base de datos local y en próximas consultas a ADRES.
3. **Cancelación (Supresión):** Se eliminarán los datos personales del paciente de la BD local, conservando solo registros anonimizados para auditoría.
4. **Oposición:** Se limitará el tratamiento a fines exclusivamente legales o contractuales.

## 5. Automatización

Actualmente la supresión es **manual** (requiere intervención del administrador). Para producción se planifica:
- Jobs automáticos de limpieza (cron mensual)
- Endpoint `/api/arco` para solicitudes automatizadas
- Anonimización automática post-período de retención

## 6. Excepciones

Los siguientes datos **no están sujetos a supresión**:
- Registros anonimizados usados para entrenamiento de modelos de IA
- Logs de acceso a la API (retención mínima 1 año por seguridad)
- Documentos requeridos por autoridades de control (SIC, Supersalud)

---

## 7. Bitácora de Cambios

| Versión | Fecha | Cambio | Autor |
|---------|-------|--------|-------|
| 1.0 | 30-jul-2026 | Creación inicial | Jefersson Aldair Oliveros Monroy |

---

*Documento controlado — Próxima revisión: Julio 2027*
