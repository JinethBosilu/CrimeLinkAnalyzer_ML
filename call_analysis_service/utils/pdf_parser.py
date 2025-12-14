import PyPDF2
import re
from datetime import datetime

def parse_call_records(pdf_path):
    """
    Parse call records from PDF file
    Expected format: Each line contains call details like:
    "2024-01-15 10:30:45 | +94771234567 | Outgoing | 00:05:23"
    
    Returns list of call records with direction detection:
    [
        {
            'timestamp': '2024-01-15T10:30:45',
            'phone_number': '+94771234567',
            'call_type': 'Outgoing',  # 'Incoming' or 'Outgoing'
            'direction': 'outgoing',   # Normalized direction
            'duration': '00:05:23',
            'main_number': '+94713268081'  # MSISON/subscriber number
        },
        ...
    ]
    """
    call_records = []
    main_number = None
    skipped_lines = 0
    full_text = ""
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text() or ""
                full_text += text + "\n"
                lines = text.split('\n')
                
                for line in lines:
                    try:
                        # Try multiple patterns to extract call data
                        record = extract_call_data(line)
                        if record:
                            # Normalize phone number
                            record['phone_number'] = normalize_phone_number(record['phone_number'])
                            
                            # Detect and normalize direction
                            record['direction'] = detect_call_direction(record.get('call_type', ''))
                            
                            # Store main number if found
                            if record.get('main_number'):
                                record['main_number'] = normalize_phone_number(record['main_number'])
                                if not main_number:
                                    main_number = record['main_number']
                                    print(f"DEBUG: Found main number (MSISON): {main_number}")
                            
                            call_records.append(record)
                        else:
                            # Check if line might contain call data but didn't match
                            if any(keyword in line.lower() for keyword in ['incoming', 'outgoing', 'missed']) and any(c.isdigit() for c in line):
                                skipped_lines += 1
                    except Exception as e:
                        print(f"DEBUG: Error parsing line: {str(e)[:100]}")
                        continue
    
    except Exception as e:
        print(f"Error parsing PDF: {str(e)}")
        raise
    
    # Set main_number for all records if we found one
    if main_number:
        for record in call_records:
            if 'main_number' not in record or not record['main_number']:
                record['main_number'] = main_number

    #  ADD THIS BLOCK RIGHT HERE (before print/return)
    has_location = any(r.get("location") for r in call_records)
    if not has_location:
        cell_rows = extract_cell_table_rows(full_text)
        call_records = attach_locations_by_row_index(call_records, cell_rows)
    
    print(f"DEBUG: Parsed {len(call_records)} records, skipped {skipped_lines} potential lines, main number: {main_number}")
    
    return call_records

def extract_call_data(line):
    """
    Extract call data from a line of text
    Supports multiple formats including Sri Lankan telecom format
    """
    # Pattern 1
    pattern1 = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|\s*(\+?\d+)\s*\|\s*(Incoming|Outgoing|Missed)\s*\|\s*(\d{2}:\d{2}:\d{2})'

    # Pattern 2
    pattern2 = r'(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\s+(\+?\d+)\s+(IN|OUT|MISSED)\s+(\d+)m\s+(\d+)s'

    # Pattern 3
    pattern3 = r'(\d{2}-\d{2}-\d{4})\s+(\d{2}:\d{2})\s*[,\s]+(\+?\d{10,15})\s*[,\s]+(Incoming|Outgoing|Missed)\s*[,\s]+(\d+:\d+:\d+)'

    # Pattern 4 (table with |)
    pattern4_table = r'\|\s*(\d{9,15})\s*\|\s*(\d{9,15})\s*\|\s*(\d{9,15})\s*\|\s*(Incoming|Outgoing|Missed|incoming|outgoing|missed|INCOMING|OUTGOING|MISSED)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d{2}:\d{2}:\d{2})\s*\|\s*(\d+)'

    # Pattern 6 (FULL row with Cell ID + Call Name) — MUST RUN BEFORE pattern5
    # msison a_number b_number event_type date time duration cell_id call_name
    pattern6_full = (
        r'(\+?\d{9,15})[\s\t]+(\+?\d{9,15})[\s\t]+(\+?\d{9,15})[\s\t]+'
        r'(Incoming|Outgoing|Missed|incoming|outgoing|missed|INCOMING|OUTGOING|MISSED)[\s\t]+'
        r'(\d{4}-\d{2}-\d{2})[\s\t]+(\d{2}:\d{2}:\d{2})[\s\t]+'
        r'(\d+)[\s\t]+(\d+)[\s\t]+([^\s]+)'
    )

    # Pattern 5 (tabs/spaces)
    pattern5_tabs = r'(\d{9,15})[\s\t]+(\d{9,15})[\s\t]+(\d{9,15})[\s\t]+(Incoming|Outgoing|Missed|incoming|outgoing|missed|INCOMING|OUTGOING|MISSED)[\s\t]+(\d{4}-\d{2}-\d{2})[\s\t]+(\d{2}:\d{2}:\d{2})[\s\t]+(\d+)'

    #  Pattern 1 
    match = re.search(pattern1, line)
    if match:
        return {
            'timestamp': match.group(1).replace(' ', 'T'),
            'phone_number': match.group(2),
            'call_type': match.group(3),
            'duration': match.group(4)
        }

    #  Pattern 2 
    match = re.search(pattern2, line)
    if match:
        date_parts = match.group(1).split('/')
        date_str = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
        timestamp = f"{date_str}T{match.group(2)}:00"

        call_type_map = {'IN': 'Incoming', 'OUT': 'Outgoing', 'MISSED': 'Missed'}
        duration = f"00:{match.group(5).zfill(2)}:{match.group(6).zfill(2)}"

        return {
            'timestamp': timestamp,
            'phone_number': match.group(3),
            'call_type': call_type_map.get(match.group(4), 'Unknown'),
            'duration': duration
        }

    #  Pattern 3
    match = re.search(pattern3, line)
    if match:
        date_parts = match.group(1).split('-')
        date_str = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
        timestamp = f"{date_str}T{match.group(2)}:00"

        return {
            'timestamp': timestamp,
            'phone_number': match.group(3),
            'call_type': match.group(4),
            'duration': match.group(5)
        }

    #  Pattern 4 
    match = re.search(pattern4_table, line)
    if match:
        msison = match.group(1)
        a_number = match.group(2)
        b_number = match.group(3)
        event_type = match.group(4)
        date = match.group(5)
        time = match.group(6)
        duration_seconds = int(match.group(7))

        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        timestamp = f"{date}T{time}"

        other_party = a_number if event_type.lower() == 'incoming' else b_number

        return {
            'timestamp': timestamp,
            'phone_number': other_party,
            'call_type': event_type,
            'duration': duration,
            'main_number': msison
        }

    # Pattern 6 (FULL) 
    match = re.search(pattern6_full, line)
    if match:
        msison = match.group(1)
        a_number = match.group(2)
        b_number = match.group(3)
        event_type = match.group(4)
        date = match.group(5)
        time = match.group(6)
        duration_seconds = int(match.group(7))
        cell_id = match.group(8)
        call_name = match.group(9)  # location

        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        timestamp = f"{date}T{time}"

        other_party = a_number if event_type.lower() == "incoming" else b_number

        return {
            "timestamp": timestamp,
            "phone_number": other_party,
            "call_type": event_type,
            "duration": duration,
            "main_number": msison,
            "cell_id": cell_id,
            "location": call_name,  # IMPORTANT
        }

    # Pattern 5 
    match = re.search(pattern5_tabs, line)
    if match:
        msison = match.group(1)
        a_number = match.group(2)
        b_number = match.group(3)
        event_type = match.group(4)
        date = match.group(5)
        time = match.group(6)
        duration_seconds = int(match.group(7))

        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        timestamp = f"{date}T{time}"
        other_party = a_number if event_type.lower() == 'incoming' else b_number

        return {
            'timestamp': timestamp,
            'phone_number': other_party,
            'call_type': event_type,
            'duration': duration,
            'main_number': msison
        }

    return None

def extract_cell_table_rows(full_text: str):
    """
    Extracts: Cell ID  Call Name  IMEI  IMSI
    Example line: 46066 Urubokka2 324633636720 43772005848
    """
    rows = []
    for raw in full_text.splitlines():
        line = raw.strip()
        m = re.match(r'^(\d{4,6})\s+([A-Za-z0-9_\-]+)\s+\d+\s+\d+\s*$', line)
        if m:
            rows.append({"cell_id": m.group(1), "location": m.group(2)})
    return rows


def attach_locations_by_row_index(call_records: list, cell_rows: list):
    """
    If the PDF keeps call rows on page1 and cell table rows on page2,
    and both counts match, attach location to each call row by index.
    """
    if not call_records or not cell_rows:
        return call_records

    # only attach if counts match
    if len(call_records) != len(cell_rows):
        return call_records

    for i in range(len(call_records)):
        call_records[i]["cell_id"] = cell_rows[i]["cell_id"]
        call_records[i]["location"] = cell_rows[i]["location"]

    return call_records


def normalize_phone_number(phone):
    """
    Normalize phone numbers to consistent format
    Handles Sri Lankan numbers: +94, 0, or 94 prefixes
    """
    if not phone:
        return phone
        
    # Remove all non-digit characters except +
    phone = re.sub(r'[^\d+]', '', phone)
    
    # Handle Sri Lankan phone numbers
    if phone.startswith('0') and len(phone) == 10:
        # Local format: 0771234567 -> +94771234567
        phone = '+94' + phone[1:]
    elif phone.startswith('94') and not phone.startswith('+'):
        # Missing + prefix: 94771234567 -> +94771234567
        phone = '+' + phone
    elif not phone.startswith('+') and len(phone) >= 9:
        # International format without +
        phone = '+' + phone
    
    return phone


def detect_call_direction(call_type):
    """
    Detect and normalize call direction
    
    Args:
        call_type: String indicating call type (Incoming, Outgoing, IN, OUT, etc.)
        
    Returns:
        'incoming' or 'outgoing' (lowercase normalized)
    """
    if not call_type:
        return 'unknown'
    
    call_type_lower = call_type.lower().strip()
    
    # Map various formats to normalized direction
    if call_type_lower in ['incoming', 'in', 'received', 'inbound']:
        return 'incoming'
    elif call_type_lower in ['outgoing', 'out', 'dialed', 'outbound', 'called']:
        return 'outgoing'
    elif call_type_lower in ['missed', 'miss']:
        return 'missed'
    else:
        return 'unknown'
