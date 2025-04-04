#!/usr/bin/env python3
"""
PDF Splitter - Divide grandes archivos PDF en páginas A4/Legal con guías de empalme
y márgenes blancos personalizables.
"""

import fitz  # PyMuPDF
import argparse
from typing import Tuple, Dict
import os

# Constantes
MM_TO_POINTS = 2.83465  # Factor de conversión de milímetros a puntos
GUIDE_FONT_SIZE = 8
CENTER_FONT_SIZE = 9
EMPTY_BOX = "□"  # Carácter para posiciones fuera de rango
GUIDE_FONT = "Helvetica"  # Fuente para los textos guía
MARGIN_LINE_WIDTH = 0.25 * MM_TO_POINTS  # Ancho de línea del rectángulo de margen (0.5mm)
GRAY_COLOR = (0.5, 0.5, 0.5)  # Color gris intermedio (RGB)

def get_page_size(paper_size: str) -> Tuple[int, int]:
    """
    Obtiene las dimensiones en puntos para un tamaño de papel dado.
    
    Args:
        paper_size: Tamaño de papel ('A4' o 'Legal')
    
    Returns:
        Tuple con el ancho y alto en puntos
    """
    sizes: Dict[str, Tuple[int, int]] = {
        "A4": (595, 842),         # 210 x 297 mm
        "LEGAL": (612, 1008),     # 8.5 x 14 in
    }
    return sizes.get(paper_size.upper(), sizes["A4"])

def create_clip_rect(col: int, row: int, page_width: int, page_height: int, 
                    orig_width: float, orig_height: float) -> fitz.Rect:
    """
    Crea el rectángulo de recorte para una sección específica del PDF.
    """
    return fitz.Rect(
        col * page_width,
        row * page_height,
        min((col + 1) * page_width, orig_width),
        min((row + 1) * page_height, orig_height)
    )

def create_content_rect(page_width: int, page_height: int, margen_pts: float) -> fitz.Rect:
    """
    Crea el rectángulo de contenido con márgenes.
    """
    return fitz.Rect(
        margen_pts,
        margen_pts,
        page_width - margen_pts,
        page_height - margen_pts
    )

def draw_margin_rectangle(page: fitz.Page, page_width: int, page_height: int, margen_pts: float) -> None:
    """
    Dibuja un rectángulo fino en el límite del margen.
    
    Args:
        page: Página del PDF donde dibujar
        page_width: Ancho de la página
        page_height: Alto de la página
        margen_pts: Margen en puntos
    """
    # Crear el rectángulo de margen
    margin_rect = fitz.Rect(
        margen_pts,
        margen_pts,
        page_width - margen_pts,
        page_height - margen_pts
    )
    
    # Dibujar el rectángulo con línea fina
    page.draw_rect(margin_rect, width=MARGIN_LINE_WIDTH)

def format_position(row: int, col: int, max_rows: int, max_cols: int) -> str:
    """
    Formatea la posición (fila, columna) o retorna un carácter de caja vacía
    si está fuera de rango.
    
    Args:
        row: Número de fila
        col: Número de columna
        max_rows: Número máximo de filas
        max_cols: Número máximo de columnas
        
    Returns:
        String formateado con la posición o carácter de caja vacía
    """
    if row < 0 or col < 0 or row >= max_rows or col >= max_cols:
        return EMPTY_BOX
    return f"({row + 1}, {col + 1})"

def add_guide_texts(page: fitz.Page, row: int, col: int, 
                   page_width: int, page_height: int, margen_pts: float,
                   max_rows: int, max_cols: int, input_name: str) -> None:
    """
    Agrega el texto guía a una página mostrando solo la posición actual.
    
    Args:
        page: Página del PDF a modificar
        row: Fila actual
        col: Columna actual
        page_width: Ancho de la página
        page_height: Alto de la página
        margen_pts: Margen en puntos
        max_rows: Número total de filas
        max_cols: Número total de columnas
        input_name: Nombre del archivo de entrada
    """
    # Calcular el número de página actual
    current_page = (row * max_cols) + col + 1
    
    # Formatear el texto completo
    text = f"{input_name} {format_position(row, col, max_rows, max_cols)} [ {current_page} ]"
    
    # Posicionar texto en esquina inferior derecha pegado al margen
    text_width = len(text) * CENTER_FONT_SIZE
    x = page_width - margen_pts - text_width
    y = page_height - margen_pts - CENTER_FONT_SIZE
    
    # Insertar texto con color gris
    page.insert_text(
        (x, y),
        text,
        fontsize=CENTER_FONT_SIZE,
        color=GRAY_COLOR
    )

def process_page(output: fitz.Document, pdf: fitz.Document, input_name: str,
                row: int, col: int, dims: Dict, max_rows: int, max_cols: int) -> None:
    """
    Procesa una página individual del PDF dividido.
    
    Args:
        output: Documento PDF de salida
        pdf: Documento PDF original
        input_name: Nombre del archivo de entrada
        row: Número de fila actual
        col: Número de columna actual
        dims: Diccionario con dimensiones y márgenes
        max_rows: Número total de filas
        max_cols: Número total de columnas
    """
    clip = create_clip_rect(
        col, row, 
        dims['page_width'], dims['page_height'],
        dims['orig_width'], dims['orig_height']
    )
    
    new_page = output.new_page(width=dims['page_width'], height=dims['page_height'])
    content_rect = create_content_rect(dims['page_width'], dims['page_height'], dims['margen_pts'])
    
    new_page.show_pdf_page(content_rect, pdf, 0, clip=clip)
    
    # Dibujar el rectángulo de margen
    draw_margin_rectangle(new_page, dims['page_width'], dims['page_height'], dims['margen_pts'])
    
    add_guide_texts(new_page, row, col, dims['page_width'], dims['page_height'], 
                   dims['margen_pts'], max_rows, max_cols, input_name)

def create_map_pdf(input_pdf_path: str, output_pdf_path: str, paper_size: str = "A4", margen: float = 10) -> None:
    """
    Crea un mapa del PDF original con líneas de cuadrícula y contadores.
    
    Args:
        input_pdf_path: Ruta al archivo PDF de entrada
        output_pdf_path: Ruta donde guardar el PDF resultante
        paper_size: Tamaño de papel destino ('A4' o 'Legal')
        margen: Margen en milímetros para el contenido
    """
    page_width, page_height = get_page_size(paper_size)
    margen_pts = float(margen) * MM_TO_POINTS
    input_name = os.path.splitext(os.path.basename(input_pdf_path))[0]

    # Abrir PDF original y obtener dimensiones
    pdf = fitz.open(input_pdf_path)
    page = pdf[0]
    orig_width = page.rect.width
    orig_height = page.rect.height
    
    # Crear documento de salida con tamaño del original
    output = fitz.open()
    new_page = output.new_page(width=orig_width, height=orig_height)
    
    # Copiar contenido original
    new_page.show_pdf_page(new_page.rect, pdf, 0)
    
    # Calcular dimensiones efectivas para la cuadrícula
    grid_width = page_width - (2 * margen_pts)
    grid_height = page_height - (2 * margen_pts)
    
    # Calcular número de líneas necesarias
    cols = int(orig_width // grid_width) + 1
    rows = int(orig_height // grid_height) + 1
    
    # Dibujar líneas verticales
    counter = 1
    for col in range(cols):
        x = col * grid_width
        new_page.draw_line(
            (x, 0),
            (x, orig_height),
            color=GRAY_COLOR,
            width=MARGIN_LINE_WIDTH
        )
        
        # Dibujar números en intersecciones
        for row in range(rows):
            y = row * grid_height
            text = str(counter)
            counter += 1
            
            # Calcular posición del texto (centrado en la intersección)
            text_width = len(text) * CENTER_FONT_SIZE / 2
            text_x = x - text_width / 2
            text_y = y - CENTER_FONT_SIZE / 2
            
            new_page.insert_text(
                (text_x, text_y),
                text,
                fontsize=CENTER_FONT_SIZE,
                color=GRAY_COLOR
            )
    
    # Dibujar última línea vertical
    new_page.draw_line(
        (cols * grid_width, 0),
        (cols * grid_width, orig_height),
        color=GRAY_COLOR,
        width=MARGIN_LINE_WIDTH
    )
    
    # Dibujar líneas horizontales
    for row in range(rows):
        y = row * grid_height
        new_page.draw_line(
            (0, y),
            (orig_width, y),
            color=GRAY_COLOR,
            width=MARGIN_LINE_WIDTH
        )
    
    # Dibujar última línea horizontal
    new_page.draw_line(
        (0, rows * grid_height),
        (orig_width, rows * grid_height),
        color=GRAY_COLOR,
        width=MARGIN_LINE_WIDTH
    )
    
    # Agregar texto guía
    text = f"{input_name} [{cols}x{rows} grid]"
    text_width = len(text) * CENTER_FONT_SIZE
    x = orig_width - margen_pts - text_width
    y = orig_height - margen_pts - CENTER_FONT_SIZE
    new_page.insert_text((x, y), text, fontsize=CENTER_FONT_SIZE, color=GRAY_COLOR)
    
    # Guardar resultado
    output.save(output_pdf_path)
    print(f"✅ PDF mapa guardado en: {output_pdf_path}")

def dividir_pdf_con_guia(input_pdf_path: str, output_pdf_path: str, 
                        paper_size: str = "A4", margen: float = 10) -> None:
    """
    Divide un PDF grande en páginas más pequeñas con guías de empalme y márgenes.
    
    Args:
        input_pdf_path: Ruta al archivo PDF de entrada
        output_pdf_path: Ruta donde guardar el PDF resultante
        paper_size: Tamaño de papel destino ('A4' o 'Legal')
        margen: Margen en milímetros para el contenido
    """
    page_width, page_height = get_page_size(paper_size)
    margen_pts = float(margen) * MM_TO_POINTS
    input_name = os.path.splitext(os.path.basename(input_pdf_path))[0]

    pdf = fitz.open(input_pdf_path)
    page = pdf[0]
    
    # Dimensiones del PDF original
    orig_width = page.rect.width
    orig_height = page.rect.height
    
    # Calcular número de filas y columnas necesarias
    cols = int(orig_width // page_width) + 1
    rows = int(orig_height // page_height) + 1
    
    # Crear documento de salida
    output = fitz.open()
    
    # Dimensiones y márgenes para el procesamiento
    dims = {
        'page_width': page_width,
        'page_height': page_height,
        'orig_width': orig_width,
        'orig_height': orig_height,
        'margen_pts': margen_pts
    }
    
    # Procesar cada página
    for row in range(rows):
        for col in range(cols):
            process_page(output, pdf, input_name, row, col, dims, rows, cols)
    
    output.save(output_pdf_path)
    print(f"✅ PDF dividido y guardado en: {output_pdf_path}")

def parse_arguments() -> argparse.Namespace:
    """
    Configura y procesa los argumentos de línea de comandos.
    """
    parser = argparse.ArgumentParser(
        description="Divide uno o más PDFs grandes en páginas A4 o Legal con guías de empalme y márgenes blancos de 10mm por defecto."
    )
    parser.add_argument("--input", nargs='+', help="Rutas a los PDFs originales")
    parser.add_argument("--output-dir", help="Directorio para los PDFs de salida (opcional, por defecto: directorio actual)")
    parser.add_argument("--size", default="A4", help="Tamaño de hoja: A4 o Legal (por defecto: A4)")
    parser.add_argument("--margen", type=float, default=10, help="Margen en milímetros para el contenido del PDF (default: 10)")
    
    return parser.parse_args()

def get_pdf_files() -> list:
    """
    Obtiene la lista de archivos PDF en el directorio actual,
    excluyendo los archivos de salida (*.output.pdf)
    """
    import os
    pdf_files = []
    for file in os.listdir('.'):
        if file.lower().endswith('.pdf') and not file.endswith('.output.pdf'):
            pdf_files.append(file)
    return pdf_files

def confirm_process(prompt: str) -> bool:
    """
    Solicita confirmación al usuario. Por defecto es no,
    solo retorna True si explícitamente escribe 'y' o 'yes'.
    
    Args:
        prompt: Mensaje a mostrar
        
    Returns:
        bool: True solo si el usuario escribe 'y' o 'yes'
    """
    response = input(f"{prompt} (y/N): ").lower().strip()
    return response in ['y', 'yes']

def main():
    """
    Función principal que maneja la lógica de ejecución del script.
    """
    args = parse_arguments()
    
    import os
    output_dir = args.output_dir if args.output_dir else '.'
    os.makedirs(output_dir, exist_ok=True)
    
    # Si no se proporcionan archivos de entrada, buscar PDFs en el directorio actual
    input_files = args.input if args.input else get_pdf_files()
    
    if not input_files:
        print("❌ No se encontraron archivos PDF para procesar")
        return
        
    # Si no se proporcionaron archivos específicos, preguntar por cada uno
    if not args.input:
        selected_files = []
        for file in input_files:
            if confirm_process(f"¿Procesar {file}?"):
                selected_files.append(file)
        input_files = selected_files
        
        if not input_files:
            print("\n❌ No se seleccionaron archivos para procesar")
            return
    
    # Procesar archivos seleccionados
    for input_path in input_files:
        input_filename = os.path.basename(input_path)
        output_filename = f"{os.path.splitext(input_filename)[0]}.output.pdf"
        output_path = os.path.join(output_dir, output_filename)
        
        print(f"\n📄 Procesando: {input_path}")
        
        # Generar PDF dividido
        dividir_pdf_con_guia(
            input_pdf_path=input_path,
            output_pdf_path=output_path,
            paper_size=args.size,
            margen=args.margen
        )
        
        # Generar PDF mapa
        map_output_filename = f"{os.path.splitext(input_filename)[0]}.map.output.pdf"
        map_output_path = os.path.join(output_dir, map_output_filename)
        create_map_pdf(
            input_pdf_path=input_path,
            output_pdf_path=map_output_path,
            paper_size=args.size,
            margen=args.margen
        )
    
    print(f"\n✨ Procesamiento completado - {len(input_files)} archivo(s) procesado(s)")

if __name__ == "__main__":
    main()
