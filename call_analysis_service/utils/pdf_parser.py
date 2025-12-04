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
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page in pdf_reader.pages:
                text = page.extract_text()
                lines = text.split('\n')
                
                for line in lines:
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
                        
                        call_records.append(record)
    
    except Exception as e:
        print(f"Error parsing PDF: {str(e)}")
        raise
    
    # Set main_number for all records if we found one
    if main_number:
        for record in call_records:
            if 'main_number' not in record or not record['main_number']:
                record['main_number'] = main_number
    
    return call_records

def extract_call_data(line):
    """
    Extract call data from a line of text
    Supports multiple formats including Sri Lankan telecom format
    """
    # Pattern 1: "2024-01-15 10:30:45 | +94771234567 | Outgoing | 00:05:23"
    pattern1 = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|\s*(\+?\d+)\s*\|\s*(Incoming|Outgoing|Missed)\s*\|\s*(\d{2}:\d{2}:\d{2})'
    
    # Pattern 2: "15/01/2024 10:30 +94771234567 OUT 5m 23s"
    pattern2 = r'(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\s+(\+?\d+)\s+(IN|OUT|MISSED)\s+(\d+)m\s+(\d+)s'
    
    # Pattern 3: Phone number with date and duration
    pattern3 = r'(\d{2}-\d{2}-\d{4})\s+(\d{2}:\d{2})\s*[,\s]+(\+?\d{10,15})\s*[,\s]+(Incoming|Outgoing|Missed)\s*[,\s]+(\d+:\d+:\d+)'
    
    # Pattern 4: Sri Lankan format "0713268081 0715689865 0713268081 Incoming 2024-09-20 08:43:14 15"
    # Format: a_number b_number msison event_type date time duration
    pattern4 = r'(\d{10})\s+(\d{10})\s+(\d{10})\s+(Incoming|Outgoing|Missed)\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(\d+)'
    
    match = re.search(pattern1, line)
    if match:
        return {
            'timestamp': match.group(1).replace(' ', 'T'),
            'phone_number': match.group(2),
            'call_type': match.group(3),
            'duration': match.group(4)
        }
    
    match = re.search(pattern2, line)
    if match:
        # Convert date format from DD/MM/YYYY to YYYY-MM-DD
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
    
    match = re.search(pattern3, line)
    if match:
        # Convert date format from DD-MM-YYYY to YYYY-MM-DD
        date_parts = match.group(1).split('-')
        date_str = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
        timestamp = f"{date_str}T{match.group(2)}:00"
        
        return {
            'timestamp': timestamp,
            'phone_number': match.group(3),
            'call_type': match.group(4),
            'duration': match.group(5)
        }
    
    # Pattern 4: Sri Lankan telecom format
    match = re.search(pattern4, line)
    if match:
        a_number = match.group(1)  # Calling party
        b_number = match.group(2)  # Called party
        msison = match.group(3)     # Main subscriber number
        event_type = match.group(4) # Incoming/Outgoing
        date = match.group(5)
        time = match.group(6)
        duration_seconds = int(match.group(7))
        
        # Convert duration from seconds to HH:MM:SS
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        timestamp = f"{date}T{time}"
        
        # Determine the other party number based on event type
        # For Incoming: a_number is the caller (other party)
        # For Outgoing: b_number is the person being called (other party)
        if event_type == 'Incoming':
            other_party = a_number if a_number != msison else b_number
        else:  # Outgoing
            other_party = b_number if b_number != msison else a_number
        
        return {
            'timestamp': timestamp,
            'phone_number': other_party,
            'call_type': event_type,
            'duration': duration,
            'main_number': msison
        }
    
    return None

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
