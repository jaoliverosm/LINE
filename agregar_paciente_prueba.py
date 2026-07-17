import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Leer dataset actual
df = pd.read_csv('D:/PROYECTOS/LINE/data/dataset_maestro.csv')

# Obtener el último ID para generar nuevos IDs
last_cruce = df['id_cruce'].iloc[-1] if len(df) > 0 else 'CRZ-0000000'
last_atencion = df['id_atencion'].iloc[-1] if len(df) > 0 else 'ATN-0000000'
last_prefactura = df['id_prefactura'].iloc[-1] if len(df) > 0 else 'PF-0000000'
last_detalle = df['id_detalle_hc'].iloc[-1] if len(df) > 0 else 'DET-0000000'

# Manejar valores NaN
if pd.isna(last_detalle):
    last_detalle = 'DET-0000000'

# Generar nuevos IDs
new_cruce_num = int(str(last_cruce).split('-')[1]) + 1
new_atencion_num = int(str(last_atencion).split('-')[1]) + 1
new_prefactura_num = int(str(last_prefactura).split('-')[1]) + 1
new_detalle_num = int(str(last_detalle).split('-')[1]) + 1

# Datos del paciente de prueba
paciente_id = '1005711681'
paciente_nombre = 'Jefersson aldair Oliveros monroy'
tipo_documento = 'CC'
eps_paciente = 'Salud Total EPS'
eps_atencion = 'Salud Total EPS'
tipo_afiliacion = 'Contributivo'
edad = 35
sexo = 'M'
ciudad = 'Bogota'

# Crear una fila de prueba consistente
fecha_atencion = datetime.now().strftime('%Y-%m-%d')
fecha_facturacion = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
fecha_registro = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

nueva_fila = {
    'id_cruce': f'CRZ-{new_cruce_num:07d}',
    'id_atencion': f'ATN-{new_atencion_num:07d}',
    'id_prefactura': f'PF-{new_prefactura_num:07d}',
    'id_detalle_hc': f'DET-{new_detalle_num:07d}',
    'resultado': 'CONSISTENTE',
    'tipo_alerta': 'CONSISTENTE',
    'severidad': 'NINGUNA',
    'descripcion_alerta': 'Coincide cantidad, codigo y soporte clinico',
    'tipo_item': 'consulta',
    'codigo_cups': '890201',
    'cantidad_realizada': 1.0,
    'fecha_registro': fecha_registro,
    'soporte_clinico': 'SI',
    'profesional_responsable': 'MED-001',
    'codigo_cups_facturado': '890201',
    'descripcion_servicio_facturado': 'Consulta de primera vez medicina general',
    'cantidad_facturada': 1.0,
    'valor_unitario': 50000.0,
    'valor_total': 50000.0,
    'fecha_facturacion': fecha_facturacion,
    'id_paciente': paciente_id,
    'fecha_atencion': fecha_atencion,
    'tipo_atencion': 'Ambulatorio',
    'diagnostico_principal_cie10': 'Z000',
    'descripcion_diagnostico': 'Examen general de rutina',
    'medico_tratante': 'MED-001',
    'sede': 'Sede Principal',
    'eps_atencion': eps_atencion,
    'tipo_documento': tipo_documento,
    'edad': edad,
    'sexo': sexo,
    'eps_paciente': eps_paciente,
    'tipo_afiliacion': tipo_afiliacion,
    'ciudad': ciudad,
    'codigo_facturado_tiene_soporte_en_atencion': 1,
    'codigo_hc_fue_facturado_en_atencion': 1,
    'total_cups_hc': 1.0,
    'total_cups_pf': 1.0,
    'cups_con_soporte_count': 1.0,
    'cups_sin_soporte_count': 0.0,
    'cups_no_facturados_count': 0.0,
    'proporcion_cups_con_soporte': 1.0,
    'proporcion_cups_sin_soporte': 0.0,
    'es_ambulatorio': 1,
    'es_hospitalario': 0,
    'es_urgencia': 0,
    'valor_total_atencion': 50000.0,
    'servicio_alto_valor_ambulatorio': 0,
    'tratamiento_complejo_hospitalario': 0,
    'dias_atencion_a_facturacion': 3.0,
    'facturacion_tardia': 0,
    'target': 0,
    'mes_atencion': datetime.now().month,
    'grupo_etario': 'Adulto',
    'eps_coincide_paciente': 1.0
}

# Agregar la nueva fila
df_nuevo = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)

# Guardar el dataset actualizado
df_nuevo.to_csv('D:/PROYECTOS/LINE/data/dataset_maestro.csv', index=False)

print(f'Paciente {paciente_nombre} (CC {paciente_id}) agregado exitosamente')
print(f'ID cruce: {nueva_fila["id_cruce"]}')
print(f'ID atención: {nueva_fila["id_atencion"]}')
print(f'Total filas: {len(df_nuevo)}')
