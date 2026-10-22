#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de Exportación y Administración de Hablantes.
Genera TXT, SRT, DOCX y JSON estructurado.
Permite renombrar hablantes en < 1 segundo sin reprocesar audio.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.config import formatear_tiempo, formatear_tiempo_srt


def aplicar_mapeo_hablante(speaker_raw: str, speaker_mapping: Optional[Dict[str, str]]) -> str:
    """Aplica el nombre personalizado a la etiqueta de hablante (capa de presentación)."""
    if not speaker_mapping:
        return speaker_raw
    return speaker_mapping.get(speaker_raw, speaker_raw)


def generar_txt(segments: List[Dict[str, Any]], output_path: Path, speaker_mapping: Optional[Dict[str, str]] = None) -> Path:
    """Genera archivo TXT limpio con timestamp + hablante + texto."""
    with open(output_path, "w", encoding="utf-8") as f:
        for seg in segments:
            ts = formatear_tiempo(seg["start"])
            raw_speaker = seg.get("speaker", "SPEAKER 01")
            display_speaker = aplicar_mapeo_hablante(raw_speaker, speaker_mapping)
            text = seg.get("text", "").strip()
            f.write(f"[{ts}] {display_speaker}:\n{text}\n\n")
    return output_path


def generar_srt(segments: List[Dict[str, Any]], output_path: Path, speaker_mapping: Optional[Dict[str, str]] = None) -> Path:
    """Genera archivo SRT estándar de subtítulos con timestamps exactos."""
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start_ts = formatear_tiempo_srt(seg["start"])
            end_ts = formatear_tiempo_srt(seg["end"])
            raw_speaker = seg.get("speaker", "SPEAKER 01")
            display_speaker = aplicar_mapeo_hablante(raw_speaker, speaker_mapping)
            text = seg.get("text", "").strip()
            
            f.write(f"{i}\n")
            f.write(f"{start_ts} --> {end_ts}\n")
            f.write(f"[{display_speaker}] {text}\n\n")
    return output_path


def generar_docx(segments: List[Dict[str, Any]], output_path: Path, titulo: str = "Transcripción", speaker_mapping: Optional[Dict[str, str]] = None) -> Path:
    """Genera documento DOCX profesional con estilos legibles, tabla estadística y metadatos."""
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.oxml import parse_xml
        from docx.oxml.ns import nsdecls
    except ImportError:
        return output_path

    doc = Document()
    
    # Configurar márgenes limpios
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Título principal
    h = doc.add_heading(titulo, level=1)
    h.paragraph_format.space_after = Pt(2)

    # Subtítulo institucional
    p_sub = doc.add_paragraph()
    r_sub = p_sub.add_run("Transcriptor Local · Tu Tiendita IA (tutiendita-ia.store)")
    r_sub.font.size = Pt(9.5)
    r_sub.font.color.rgb = RGBColor(120, 130, 150)
    p_sub.paragraph_format.space_after = Pt(12)

    # Calcular estadísticas de participación por hablante
    stats: Dict[str, Dict[str, Any]] = {}
    total_tiempo_habla = 0.0

    for seg in segments:
        spk_raw = seg.get("speaker", "SPEAKER 01")
        spk_name = aplicar_mapeo_hablante(spk_raw, speaker_mapping)
        dur = max(0.0, float(seg.get("end", 0.0)) - float(seg.get("start", 0.0)))
        if spk_name not in stats:
            stats[spk_name] = {"duracion": 0.0, "intervenciones": 0}
        stats[spk_name]["duracion"] += dur
        stats[spk_name]["intervenciones"] += 1
        total_tiempo_habla += dur

    # Tabla resumen si hay datos válidos
    if stats and total_tiempo_habla > 0:
        h_stats = doc.add_heading("Distribución de Habla por Participante", level=2)
        h_stats.paragraph_format.space_before = Pt(8)
        h_stats.paragraph_format.space_after = Pt(6)

        table = doc.add_table(rows=1, cols=4)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False

        headers = ["Participante", "Tiempo Total", "Participación (%)", "Intervenciones"]
        col_widths = [Inches(2.5), Inches(1.3), Inches(1.4), Inches(1.3)]

        hdr_row = table.rows[0]
        for idx, name in enumerate(headers):
            cell = hdr_row.cells[idx]
            cell.width = col_widths[idx]
            cell._tc.get_or_add_tcPr().append(parse_xml(r'<w:shd {} w:fill="1E3C96"/>'.format(nsdecls('w'))))
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if idx > 0 else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(name)
            r.bold = True
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor(255, 255, 255)

        sorted_speakers = sorted(stats.items(), key=lambda x: x[1]["duracion"], reverse=True)
        for spk_name, info in sorted_speakers:
            row_cells = table.add_row().cells
            for idx in range(4):
                row_cells[idx].width = col_widths[idx]
                row_cells[idx]._tc.get_or_add_tcPr().append(parse_xml(r'<w:shd {} w:fill="F4F6FB"/>'.format(nsdecls('w'))))

            # Participante
            p0 = row_cells[0].paragraphs[0]
            r0 = p0.add_run(spk_name)
            r0.bold = True
            r0.font.size = Pt(9.5)
            r0.font.color.rgb = RGBColor(22, 32, 90)

            # Tiempo Total
            p1 = row_cells[1].paragraphs[0]
            p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r1 = p1.add_run(formatear_tiempo(info["duracion"]))
            r1.font.size = Pt(9.5)

            # Porcentaje
            porc = (info["duracion"] / total_tiempo_habla) * 100
            p2 = row_cells[2].paragraphs[0]
            p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r2 = p2.add_run(f"{porc:.1f}%")
            r2.font.size = Pt(9.5)

            # Intervenciones
            p3 = row_cells[3].paragraphs[0]
            p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r3 = p3.add_run(str(info["intervenciones"]))
            r3.font.size = Pt(9.5)

        p_space = doc.add_paragraph()
        p_space.paragraph_format.space_before = Pt(10)
        p_space.paragraph_format.space_after = Pt(2)

        h_trans = doc.add_heading("Transcripción Completa", level=2)
        h_trans.paragraph_format.space_after = Pt(8)

    # Paleta de colores para los hablantes (estilo Tu Tiendita IA)
    colores_hablantes = [
        RGBColor(30, 60, 150),   # Azul Birome
        RGBColor(190, 50, 75),   # Malvón
        RGBColor(170, 115, 20),  # Yema tostado
        RGBColor(40, 120, 120),  # Petróleo
    ]
    speaker_color_map: Dict[str, RGBColor] = {}
    next_color_idx = 0

    current_speaker = None
    first_ts = "00:00:00"
    accumulated_texts = []

    def flush_paragraph():
        nonlocal current_speaker, first_ts, accumulated_texts, next_color_idx
        if current_speaker is not None and accumulated_texts:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.line_spacing = 1.15
            
            # Nombre de hablante + timestamp en color temático asignado
            display_speaker = aplicar_mapeo_hablante(current_speaker, speaker_mapping)
            if display_speaker not in speaker_color_map:
                speaker_color_map[display_speaker] = colores_hablantes[next_color_idx % len(colores_hablantes)]
                next_color_idx += 1
            spk_color = speaker_color_map[display_speaker]

            run_header = p.add_run(f"[{first_ts}] {display_speaker}:\n")
            run_header.bold = True
            run_header.font.size = Pt(11)
            run_header.font.color.rgb = spk_color
            
            # Contenido de la intervención
            run_body = p.add_run(" ".join(accumulated_texts))
            run_body.font.size = Pt(11)
            run_body.font.color.rgb = RGBColor(30, 30, 30)

    for seg in segments:
        speaker = seg.get("speaker", "SPEAKER 01")
        ts = formatear_tiempo(seg["start"])
        text = seg.get("text", "").strip()
        
        if speaker != current_speaker:
            flush_paragraph()
            current_speaker = speaker
            first_ts = ts
            accumulated_texts = [text]
        else:
            accumulated_texts.append(text)

    flush_paragraph()
    doc.save(str(output_path))
    return output_path


def generar_json(segments: List[Dict[str, Any]], output_path: Path, metadata: Optional[Dict[str, Any]] = None, speaker_mapping: Optional[Dict[str, str]] = None) -> Path:
    """Genera archivo JSON estructurado con toda la metadata para visualización y edición."""
    data = {
        "metadata": metadata or {},
        "speaker_mapping": speaker_mapping or {},
        "segments": segments,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return output_path


def exportar_todo(segments: List[Dict[str, Any]], output_dir: Path, base_name: str, speaker_mapping: Optional[Dict[str, str]] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Path]:
    """Genera simultáneamente todos los formatos (TXT, SRT, DOCX, JSON)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    txt_path = output_dir / f"{base_name}.txt"
    srt_path = output_dir / f"{base_name}.srt"
    docx_path = output_dir / f"{base_name}.docx"
    json_path = output_dir / f"{base_name}_completo.json"
    
    generar_txt(segments, txt_path, speaker_mapping)
    generar_srt(segments, srt_path, speaker_mapping)
    generar_docx(segments, docx_path, titulo=f"Transcripción: {base_name}", speaker_mapping=speaker_mapping)
    generar_json(segments, json_path, metadata=metadata, speaker_mapping=speaker_mapping)
    
    return {
        "txt": txt_path,
        "srt": srt_path,
        "docx": docx_path,
        "json": json_path,
    }


def reexportar_desde_json(json_path: Path, nuevo_mapping: Dict[str, str], output_dir: Optional[Path] = None) -> Dict[str, Path]:
    """
    Carga un archivo JSON de transcripción previa, actualiza los nombres de los hablantes
    y reexporta TXT, SRT, DOCX y JSON en menos de 1 segundo sin tocar Whisper ni pyannote.
    """
    json_path = Path(json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    segments = data.get("segments") or data.get("segmentos") or []
    metadata = data.get("metadata", {})
    base_name = json_path.stem.replace("_completo", "")
    target_dir = Path(output_dir) if output_dir else json_path.parent
    
    return exportar_todo(
        segments=segments,
        output_dir=target_dir,
        base_name=base_name,
        speaker_mapping=nuevo_mapping,
        metadata=metadata,
    )
