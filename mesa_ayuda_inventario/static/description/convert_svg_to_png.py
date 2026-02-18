#!/usr/bin/env python3
"""
Script para convertir icon.svg a icon.png
Requisitos: pip install cairosvg pillow
"""

try:
    import cairosvg
    print("Convirtiendo SVG a PNG...")
    cairosvg.svg2png(url='icon.svg', write_to='icon.png', output_width=128, output_height=128)
    print("✅ Conversión exitosa! icon.png creado.")
except ImportError:
    print("❌ Error: cairosvg no está instalado.")
    print("Instala con: pip install cairosvg")
    print("\nAlternativa: Usa un convertidor online:")
    print("1. Ve a https://convertio.co/es/svg-png/")
    print("2. Sube el archivo icon.svg")
    print("3. Descarga como PNG 128x128")
    print("4. Renombra a icon.png y colócalo en esta carpeta")
except Exception as e:
    print(f"❌ Error durante la conversión: {e}")
    print("\nAlternativa: Usa un convertidor online:")
    print("1. Ve a https://convertio.co/es/svg-png/")
    print("2. Sube el archivo icon.svg")
    print("3. Descarga como PNG 128x128")
    print("4. Renombra a icon.png y colócalo en esta carpeta")

