# -*- coding: utf-8 -*-
"""
Migración pre-upgrade para convertir internal_ref de Char a Many2one.
Este script se ejecuta antes de que Odoo intente convertir el campo.
"""

def migrate(cr, version):
    """Migrar datos de internal_ref de Char a Many2one."""
    import logging
    _logger = logging.getLogger(__name__)
    
    _logger.info("Iniciando migración de internal_ref...")
    
    # Verificar si la tabla quant_editor_wizard existe
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'quant_editor_wizard'
        )
    """)
    table_exists = cr.fetchone()[0]
    
    if not table_exists:
        _logger.info("La tabla quant_editor_wizard no existe, no hay datos que migrar.")
        return
    
    # Verificar si el campo internal_ref existe y es de tipo char
    cr.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'quant_editor_wizard' 
        AND column_name = 'internal_ref'
    """)
    column_info = cr.fetchone()
    
    if not column_info:
        _logger.info("El campo internal_ref no existe, no hay datos que migrar.")
        return
    
    column_type = column_info[1]
    
    if column_type != 'character varying' and column_type != 'text':
        _logger.info("El campo internal_ref ya no es de tipo texto, migración no necesaria.")
        return
    
    # Crear tabla internal_reference si no existe
    cr.execute("""
        CREATE TABLE IF NOT EXISTS internal_reference (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL UNIQUE,
            create_uid INTEGER,
            create_date TIMESTAMP,
            write_uid INTEGER,
            write_date TIMESTAMP
        )
    """)
    
    # Obtener todos los valores únicos de internal_ref que no sean NULL ni vacíos
    cr.execute("""
        SELECT DISTINCT internal_ref 
        FROM quant_editor_wizard 
        WHERE internal_ref IS NOT NULL 
        AND internal_ref != ''
    """)
    
    unique_refs = cr.fetchall()
    _logger.info("Encontrados %d referencias internas únicas para migrar", len(unique_refs))
    
    # Crear registros en internal_reference para cada valor único
    ref_mapping = {}  # Mapeo de texto a ID
    for (ref_text,) in unique_refs:
        if ref_text and ref_text.strip():
            # Buscar si ya existe
            cr.execute("""
                SELECT id FROM internal_reference WHERE name = %s
            """, (ref_text.strip(),))
            existing = cr.fetchone()
            
            if existing:
                ref_id = existing[0]
            else:
                # Crear nuevo registro
                cr.execute("""
                    INSERT INTO internal_reference (name, create_date, write_date)
                    VALUES (%s, NOW(), NOW())
                    RETURNING id
                """, (ref_text.strip(),))
                ref_id = cr.fetchone()[0]
                _logger.info("Creada referencia interna: %s (ID: %s)", ref_text.strip(), ref_id)
            
            ref_mapping[ref_text.strip()] = ref_id
    
    # Ahora actualizar quant_editor_wizard para usar los IDs
    # Primero, agregar la columna temporal para el ID
    cr.execute("""
        ALTER TABLE quant_editor_wizard 
        ADD COLUMN IF NOT EXISTS internal_ref_id INTEGER
    """)
    
    # Actualizar los valores
    for ref_text, ref_id in ref_mapping.items():
        cr.execute("""
            UPDATE quant_editor_wizard 
            SET internal_ref_id = %s 
            WHERE internal_ref = %s
        """, (ref_id, ref_text))
    
    _logger.info("Migración completada: %d registros actualizados", len(ref_mapping))
    
    # Eliminar la columna antigua
    cr.execute("""
        ALTER TABLE quant_editor_wizard 
        DROP COLUMN IF EXISTS internal_ref
    """)
    
    # Renombrar la columna nueva
    cr.execute("""
        ALTER TABLE quant_editor_wizard 
        RENAME COLUMN internal_ref_id TO internal_ref
    """)
    
    _logger.info("Migración de internal_ref completada exitosamente")

