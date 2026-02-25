# -*- coding: utf-8 -*-
"""Genera helpdesk_ticket_category_data.xml desde la estructura del Excel (categoría y subcategorías)."""
import re
import xml.sax.saxutils

def slug(s):
    """Identificador único para xml id: sin espacios, sin acentos (aprox)."""
    s = s.upper().strip()
    s = re.sub(r'[^A-Z0-9]+', '_', s)
    return s or 'CAT'

def escape(s):
    return xml.sax.saxutils.escape(s or "")

# Estructura del Excel: (nombre, [hijos]) donde hijo es str o (nombre, [hijos])
TREE = [
    ("ACCESORIOS", [
        ("CABLE", ["USB", "HDMI", "VGA", "RED", "AUDIO", "VIDEO"]),
        "ADAPTADOR", "CONECTOR", "AURICULAR", "MICROFONO", "PARLANTE", "BATERIA", "CARGADOR",
        "ESTUCHE", "BASE REFRIGERANTE", "CONVERSOR", "DISPOSITIVO DE ALMACENAMIENTO", "LECTOR",
        "HUB", "WEBCAM", "SOFTWARE", "ANTENA", "LICENCIA",
    ]),
    ("IMPRESORA", [
        "LASER", "TINTA", "MULTIFUNCIONAL", "ETIQUETAS", "POS",
        ("ACCESORIOS IMPRESORA", ["CINTAS", "TONER", "CARTUCHO", "TINTA ORIGINAL", "FILAMENTO"]),
    ]),
    ("MONITOR", ["LED", "LCD"]),
    ("REDES", ["CABLE UTP", "SWITCH", "ROUTER", "AP", "TARJETA DE RED", "ANTENA"]),
    ("SOFTWARE", ["OFFICE", "SISTEMA OPERATIVO", "ANTIVIRUS", "EDI"]),
    ("SERVIDOR", ["RACK", "TORRE", "ACCESORIOS SERVIDOR"]),
    ("COMPUTADOR", [
        "ESCRITORIO", "PORTATIL", "TODO EN UNO",
        ("ACCESORIOS COMPUTADOR", [
            "DISCO DURO", "SSD", "MEMORIA RAM", "PROCESADOR", "TARJETA DE VIDEO",
            "TARJETA MADRE", "FUENTE DE PODER", "TECLADO", "MOUSE", "WEBCAM",
        ]),
    ]),
    ("TELEFONIA", ["CELULAR", "FIJO", "ACCESORIOS TELEFONIA"]),
    ("PAPELERIA", [
        "RESMAS", "BOLIGRAFOS", "LAPICES", "CUADERNOS", "ARCHIVADORES", "MARCADORES",
        "BORRADORES", "CINTAS", "SOBRES", "POST-IT", "PERFORADORAS", "GRAPADORAS",
        "TIJERAS", "PEGANTES", "CORRECTORES", "PLUMAS", "REGLAS", "CALCULADORAS",
        "CALENDARIOS", "AGENDAS", "MATERIAL DE ESCRITORIO",
    ]),
]

def collect_nodes(nodes, parent_xmlid=None, level=1):
    """Convierte TREE en lista (xmlid, name, parent_xmlid, level)."""
    out = []
    for i, node in enumerate(nodes):
        if isinstance(node, tuple):
            name, children = node
        else:
            name, children = node, []
        base = slug(name)
        xmlid = base
        k = 0
        while xmlid in [x[0] for x in out]:
            k += 1
            xmlid = "%s_%d" % (base, k)
        out.append((xmlid, name, parent_xmlid, level))
        for child in children:
            if isinstance(child, tuple):
                out.extend(collect_nodes([child], xmlid, level + 1))
            else:
                b = slug(child)
                xid = b
                k = 0
                while xid in [x[0] for x in out]:
                    k += 1
                    xid = "%s_%d" % (b, k)
                out.append((xid, child, xmlid, level + 1))
    return out

def main():
    rows = []
    for node in TREE:
        rows.extend(collect_nodes([node], None, 1))
    out = ['<?xml version="1.0" encoding="utf-8"?>', '<odoo>', '    <data noupdate="0">']
    for xmlid, name, parent_xmlid, level in rows:
        out.append('        <record id="cat_%s" model="helpdesk.ticket.category">' % xmlid)
        out.append('            <field name="name">%s</field>' % escape(name))
        if parent_xmlid:
            out.append('            <field name="parent_id" ref="cat_%s"/>' % parent_xmlid)
        out.append('            <field name="level">%s</field>' % level)
        out.append('        </record>')
    out.append('    </data>')
    out.append('</odoo>')
    return "\n".join(out)

if __name__ == "__main__":
    p = r"c:\Users\yhernandez.SUPPLIESDC\Music\Modulos Odoo\mesa_ayuda_inventario\data\helpdesk_ticket_category_data.xml"
    with open(p, "w", encoding="utf-8") as f:
        f.write(main())
    print("Written:", p)
