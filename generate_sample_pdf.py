"""
Sample Call Records PDF Generator
Creates a test PDF file with call records in supported formats
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from datetime import datetime, timedelta
import random

def generate_sample_call_records_pdf(filename="sample_call_records.pdf"):
    """
    Generate a sample PDF with call records for testing
    """
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph("<b>Call Records Report</b>", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    
    # Metadata
    info = f"""
    <b>Report Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>
    <b>Date Range:</b> 2024-01-01 to 2024-01-31<br/>
    <b>Suspect ID:</b> S12345<br/>
    <b>Primary Number:</b> +94771234567<br/>
    """
    story.append(Paragraph(info, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Generate sample call records
    phone_numbers = [
        "+94771234567",  # Primary number (suspect)
        "+94772345678",
        "+94773456789",
        "+94774567890",
        "+94775678901",
        "+94776789012",
        "+94777890123",
        "+94778901234",
    ]
    
    call_types = ["Incoming", "Outgoing", "Missed"]
    
    # Generate 50 random call records
    call_records = []
    start_date = datetime(2024, 1, 1)
    
    for i in range(50):
        # Random date in January 2024
        days_offset = random.randint(0, 30)
        hours = random.randint(0, 23)
        minutes = random.randint(0, 59)
        seconds = random.randint(0, 59)
        
        call_date = start_date + timedelta(days=days_offset, hours=hours, minutes=minutes, seconds=seconds)
        
        # Random phone number (weighted towards primary number)
        if random.random() < 0.3:
            phone = phone_numbers[0]  # Primary number appears more
        else:
            phone = random.choice(phone_numbers[1:])
        
        call_type = random.choice(call_types)
        
        # Random duration (1-15 minutes)
        duration_seconds = random.randint(60, 900)
        duration_minutes = duration_seconds // 60
        duration_secs = duration_seconds % 60
        duration = f"00:{duration_minutes:02d}:{duration_secs:02d}"
        
        call_records.append([
            call_date.strftime('%Y-%m-%d %H:%M:%S'),
            phone,
            call_type,
            duration
        ])
    
    # Sort by date
    call_records.sort(key=lambda x: x[0])
    
    # Add header
    story.append(Paragraph("<b>Call Records:</b>", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    # Create table
    table_data = [['Date & Time', 'Phone Number', 'Type', 'Duration']] + call_records
    
    table = Table(table_data, colWidths=[120, 100, 70, 70])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    
    story.append(table)
    
    # Build PDF
    doc.build(story)
    print(f"✓ Generated sample PDF: {filename}")
    print(f"✓ Contains {len(call_records)} call records")
    print(f"✓ Phone numbers: {len(set([r[1] for r in call_records]))} unique")
    
    # Also create a text version
    create_text_version(call_records, filename.replace('.pdf', '.txt'))

def create_text_version(call_records, filename="sample_call_records.txt"):
    """
    Create a text version of the call records for manual testing
    """
    with open(filename, 'w') as f:
        f.write("Call Records Report\n")
        f.write("=" * 80 + "\n\n")
        f.write("Date Range: 2024-01-01 to 2024-01-31\n")
        f.write("Suspect ID: S12345\n")
        f.write("Primary Number: +94771234567\n\n")
        f.write("Call Records:\n")
        f.write("-" * 80 + "\n")
        
        for record in call_records:
            f.write(f"{record[0]} | {record[1]} | {record[2]} | {record[3]}\n")
    
    print(f"✓ Generated text version: {filename}")

if __name__ == "__main__":
    # Install required package first:
    # pip install reportlab
    
    try:
        generate_sample_call_records_pdf()
        print("\n✓ Files generated successfully!")
        print("\nYou can now:")
        print("1. Upload sample_call_records.pdf to the Call Analysis feature")
        print("2. View sample_call_records.txt for reference")
    except ImportError:
        print("Error: reportlab package not installed")
        print("Please run: pip install reportlab")
