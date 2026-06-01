"""
PDF heat sheet generation using ReportLab.
Produces professional, printable heat sheets from seeded events.
"""
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from src.models.schemas import HeatSheet, Entry, RelayEntry


def generate_heat_sheet_pdf(
    heat_sheet: HeatSheet,
    output_path: str,
    meet_title: str = "Swimming Meet",
    meet_date: str = None,
    page_size=letter
) -> Path:
    """
    Generate a PDF heat sheet and save to disk using ReportLab.
    
    Args:
        heat_sheet: HeatSheet object with seeded assignments
        output_path: Path where PDF will be saved
        meet_title: Title of the meet
        meet_date: Date of the meet (optional)
        page_size: ReportLab page size (letter or A4)
    
    Returns:
        Path to the generated PDF file
    """
    if meet_date is None:
        meet_date = datetime.now().strftime("%m/%d/%Y")
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create PDF document
    doc = SimpleDocTemplate(str(output_file), pagesize=page_size)
    styles = getSampleStyleSheet()
    elements = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#333333'),
        spaceAfter=6,
        alignment=1  # Center
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#666666'),
        spaceAfter=12,
        alignment=1  # Center
    )
    
    event_style = ParagraphStyle(
        'EventTitle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#333333'),
        spaceAfter=8,
        alignment=1  # Center
    )
    
    # Header
    elements.append(Paragraph(meet_title, title_style))
    elements.append(Paragraph(f"Date: {meet_date}", subtitle_style))
    elements.append(Spacer(1 * inch, 0.2 * inch))
    
    event = heat_sheet.event
    elements.append(Paragraph(
        f"Event {event.number}: {event.gender} {event.distance} Yard {event.stroke}",
        event_style
    ))
    elements.append(Spacer(1 * inch, 0.15 * inch))
    
    # Group assignments by heat
    heats_by_num = {}
    for assignment in heat_sheet.assignments:
        heat_num = assignment.heat
        if heat_num not in heats_by_num:
            heats_by_num[heat_num] = []
        heats_by_num[heat_num].append(assignment)
    
    # Generate heat tables
    for heat_num in sorted(heats_by_num.keys()):
        assignments = heats_by_num[heat_num]
        
        # Heat header
        heat_style = ParagraphStyle(
            'HeatHeader',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.white,
            backColor=colors.HexColor('#333333'),
            spaceAfter=3
        )
        
        # Build table data
        table_data = [
            ['Lane', 'Name / Team', 'Team Code', 'Seed Time', 'Place']
        ]
        
        for assignment in sorted(assignments, key=lambda a: a.lane):
            entry = assignment.entry
            lane = assignment.lane
            
            if isinstance(entry, Entry):
                swimmer = entry.swimmer
                name = f"{swimmer.name}"
                if swimmer.age:
                    name += f" (Age {swimmer.age})"
                team_code = swimmer.team_code
                seed_time = entry.seed_time
                place = str(entry.place)
            else:  # RelayEntry
                name = entry.team_name
                team_code = "RELAY"
                seed_time = entry.seed_time
                place = str(entry.place)
            
            table_data.append([
                str(lane),
                name,
                team_code,
                seed_time,
                place
            ])
        
        # Create table
        table = Table(table_data, colWidths=[0.6*inch, 2.5*inch, 1.2*inch, 1.0*inch, 0.6*inch])
        
        # Apply table styling
        table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            
            # Data rows
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Lane column
            ('ALIGN', (2, 1), (-1, -1), 'CENTER'),  # Team, time, place columns
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            
            # Borders
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            
            # Lane column highlight
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#e8f4f8')),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ]))
        
        elements.append(Paragraph(f"Heat {heat_num}", heat_style))
        elements.append(table)
        elements.append(Spacer(1 * inch, 0.15 * inch))
    
    # Summary footer
    summary_style = ParagraphStyle(
        'Summary',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        spaceAfter=3
    )
    
    elements.append(Spacer(1 * inch, 0.1 * inch))
    elements.append(Paragraph(
        f"<b>Summary:</b> {len(heat_sheet.assignments)} entries in {heat_sheet.heats} heat(s) | {heat_sheet.lanes} lanes",
        summary_style
    ))
    
    # Build PDF
    doc.build(elements)
    
    return output_file


def generate_full_meet_pdf(
    heat_sheets: list[HeatSheet],
    output_path: str,
    meet_title: str = "Swimming Meet",
    meet_date: str = None,
    page_size=letter
) -> Path:
    """
    Generate a complete meet PDF with multiple events.
    
    Args:
        heat_sheets: List of HeatSheet objects
        output_path: Path where PDF will be saved
        meet_title: Title of the meet
        meet_date: Date of the meet
        page_size: ReportLab page size
    
    Returns:
        Path to the generated PDF file
    """
    if meet_date is None:
        meet_date = datetime.now().strftime("%m/%d/%Y")
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create PDF document
    doc = SimpleDocTemplate(str(output_file), pagesize=page_size)
    styles = getSampleStyleSheet()
    elements = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#333333'),
        spaceAfter=12,
        alignment=1  # Center
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#666666'),
        spaceAfter=6,
        alignment=1  # Center
    )
    
    cover_style = ParagraphStyle(
        'CoverStyle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#999999'),
        spaceAfter=36,
        alignment=1  # Center
    )
    
    event_style = ParagraphStyle(
        'EventTitle',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        spaceAfter=6,
        alignment=1  # Center
    )
    
    # Cover page
    elements.append(Spacer(1 * inch, 1.2 * inch))
    elements.append(Paragraph(meet_title, title_style))
    elements.append(Paragraph("Heat Sheets", subtitle_style))
    elements.append(Paragraph(f"Date: {meet_date}", subtitle_style))
    elements.append(Paragraph(f"Total Events: {len(heat_sheets)}", cover_style))
    elements.append(PageBreak())
    
    # Add each event
    for event_idx, heat_sheet in enumerate(heat_sheets):
        event = heat_sheet.event
        
        # Event header
        elements.append(Paragraph(meet_title, ParagraphStyle(
            'EventHeader',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            spaceAfter=3,
            alignment=1
        )))
        
        elements.append(Paragraph(
            f"Event {event.number}: {event.gender} {event.distance} Yard {event.stroke}",
            event_style
        ))
        elements.append(Spacer(1 * inch, 0.1 * inch))
        
        # Group assignments by heat
        heats_by_num = {}
        for assignment in heat_sheet.assignments:
            heat_num = assignment.heat
            if heat_num not in heats_by_num:
                heats_by_num[heat_num] = []
            heats_by_num[heat_num].append(assignment)
        
        # Generate heat tables
        for heat_num in sorted(heats_by_num.keys()):
            assignments = heats_by_num[heat_num]
            
            # Build table data
            table_data = [
                ['Lane', 'Name / Team', 'Team', 'Time', '#']
            ]
            
            for assignment in sorted(assignments, key=lambda a: a.lane):
                entry = assignment.entry
                
                if isinstance(entry, Entry):
                    swimmer = entry.swimmer
                    name = swimmer.name
                    team_code = swimmer.team_code
                    seed_time = entry.seed_time
                    place = str(entry.place)
                else:  # RelayEntry
                    name = entry.team_name
                    team_code = "RELAY"
                    seed_time = entry.seed_time
                    place = str(entry.place)
                
                table_data.append([
                    str(assignment.lane),
                    name,
                    team_code,
                    seed_time,
                    place
                ])
            
            # Create compact table for full meet
            table = Table(table_data, colWidths=[0.5*inch, 2.2*inch, 1.0*inch, 0.9*inch, 0.5*inch])
            
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 7.5),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
                
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                
                ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#e8f4f8')),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ]))
            
            heat_label = ParagraphStyle(
                'HeatLabel',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor('#333333'),
                spaceAfter=2
            )
            elements.append(Paragraph(f"Heat {heat_num}", heat_label))
            elements.append(table)
            elements.append(Spacer(1 * inch, 0.08 * inch))
        
        # Page break between events (except last)
        if event_idx < len(heat_sheets) - 1:
            elements.append(PageBreak())
    
    # Build PDF
    doc.build(elements)
    
    return output_file
