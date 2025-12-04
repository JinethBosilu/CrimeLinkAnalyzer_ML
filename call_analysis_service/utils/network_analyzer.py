import networkx as nx
from collections import Counter, defaultdict
from datetime import datetime

def analyze_call_network(call_records):
    """
    Analyze call patterns and build separate incoming/outgoing network graphs
    
    Returns:
    {
        'main_number': str,
        'total_calls': int,
        'total_incoming': int,
        'total_outgoing': int,
        'unique_numbers': list,
        'incoming_graph': {nodes: [...], edges: [...]},
        'outgoing_graph': {nodes: [...], edges: [...]},
        'call_frequency': dict,
        'time_pattern': dict,
        'common_contacts': list
    }
    """
    if not call_records:
        return {
            'main_number': None,
            'total_calls': 0,
            'total_incoming': 0,
            'total_outgoing': 0,
            'unique_numbers': [],
            'incoming_graph': {'nodes': [], 'edges': []},
            'outgoing_graph': {'nodes': [], 'edges': []},
            'call_frequency': {},
            'time_pattern': {},
            'common_contacts': []
        }
    
    # Get main number (MSISON/subscriber)
    main_number = call_records[0].get('main_number')
    if not main_number:
        # Fallback: use most frequent number
        phone_counts = Counter([r['phone_number'] for r in call_records])
        main_number = phone_counts.most_common(1)[0][0] if phone_counts else None
    
    # Separate incoming and outgoing calls
    incoming_calls = [r for r in call_records if r.get('direction') == 'incoming']
    outgoing_calls = [r for r in call_records if r.get('direction') == 'outgoing']
    
    # Count total calls
    total_calls = len(call_records)
    total_incoming = len(incoming_calls)
    total_outgoing = len(outgoing_calls)
    
    # Extract unique phone numbers (excluding main number)
    phone_numbers = [record['phone_number'] for record in call_records 
                    if record['phone_number'] != main_number]
    unique_numbers = list(set(phone_numbers))
    
    # Calculate call frequency per number
    call_frequency = dict(Counter(phone_numbers))
    
    # Analyze time patterns (calls by hour)
    time_pattern = defaultdict(int)
    for record in call_records:
        try:
            timestamp = datetime.fromisoformat(record['timestamp'])
            hour = timestamp.hour
            time_pattern[str(hour)] = time_pattern[str(hour)] + 1
        except:
            continue
    
    # Get most common contacts (top 10)
    most_common = Counter(phone_numbers).most_common(10)
    common_contacts = [
        {'phone': phone, 'count': count}
        for phone, count in most_common
    ]
    
    # Build separate incoming and outgoing graphs
    incoming_graph = build_directional_graph(incoming_calls, main_number, 'incoming')
    outgoing_graph = build_directional_graph(outgoing_calls, main_number, 'outgoing')
    
    return {
        'main_number': main_number,
        'total_calls': total_calls,
        'total_incoming': total_incoming,
        'total_outgoing': total_outgoing,
        'unique_numbers': unique_numbers,
        'incoming_graph': incoming_graph,
        'outgoing_graph': outgoing_graph,
        'call_frequency': call_frequency,
        'time_pattern': dict(time_pattern),
        'common_contacts': common_contacts
    }

def build_directional_graph(call_records, main_number, direction):
    """
    Build network graph for a specific direction (incoming or outgoing)
    
    Args:
        call_records: List of call records filtered by direction
        main_number: The main subscriber number (center node)
        direction: 'incoming' or 'outgoing'
    
    Returns:
        {
            'nodes': [{id, label, type, size, color, call_count}],
            'edges': [{source, target, call_count, label}],
            'total_nodes': int,
            'total_edges': int,
            'total_calls': int
        }
    """
    if not call_records or not main_number:
        return {
            'nodes': [],
            'edges': [],
            'total_nodes': 0,
            'total_edges': 0,
            'total_calls': 0
        }
    
    # Count calls per contact
    contact_counts = defaultdict(int)
    for record in call_records:
        phone = record['phone_number']
        if phone != main_number:
            contact_counts[phone] += 1
    
    # Build nodes
    nodes = []
    edges = []
    
    # Color scheme based on direction
    if direction == 'incoming':
        main_color = '#3b82f6'  # Blue for main
        contact_color = '#10b981'  # Green for incoming contacts
        edge_color = '#10b981'
    else:  # outgoing
        main_color = '#3b82f6'  # Blue for main
        contact_color = '#ef4444'  # Red for outgoing contacts
        edge_color = '#ef4444'
    
    # Add main number as center node
    nodes.append({
        'id': main_number,
        'label': main_number,
        'type': 'main',
        'size': 50,
        'color': main_color,
        'borderWidth': 3
    })
    
    # Add contact nodes and edges
    for phone, call_count in contact_counts.items():
        # Node size based on call frequency (min 20, max 45)
        node_size = min(20 + (call_count * 2), 45)
        
        nodes.append({
            'id': phone,
            'label': phone,
            'type': 'contact',
            'size': node_size,
            'color': contact_color,
            'call_count': call_count
        })
        
        # Create edge with call count label
        if direction == 'incoming':
            # Arrow points FROM contact TO main number
            edges.append({
                'source': phone,
                'target': main_number,
                'call_count': call_count,
                'label': str(call_count),
                'color': edge_color,
                'width': min(1 + (call_count * 0.5), 10)
            })
        else:  # outgoing
            # Arrow points FROM main number TO contact
            edges.append({
                'source': main_number,
                'target': phone,
                'call_count': call_count,
                'label': str(call_count),
                'color': edge_color,
                'width': min(1 + (call_count * 0.5), 10)
            })
    
    return {
        'nodes': nodes,
        'edges': edges,
        'total_nodes': len(nodes),
        'total_edges': len(edges),
        'total_calls': len(call_records)
    }


def build_network_graph(call_records):
    """
    DEPRECATED: Legacy function for backward compatibility
    Use build_directional_graph instead for separate incoming/outgoing graphs
    """
    if not call_records:
        return {
            'nodes': [],
            'edges': [],
            'total_nodes': 0,
            'total_edges': 0,
            'density': 0,
            'main_number': None
        }
    
    # Get main number (MSISON) from first record if available
    main_number = call_records[0].get('main_number')
    if not main_number:
        # Fallback: use most frequent number
        phone_counts = Counter([r['phone_number'] for r in call_records])
        main_number = phone_counts.most_common(1)[0][0] if phone_counts else None
    
    if not main_number:
        return {
            'nodes': [],
            'edges': [],
            'total_nodes': 0,
            'total_edges': 0,
            'density': 0,
            'main_number': None
        }
    
    # Separate incoming and outgoing calls
    incoming_calls = defaultdict(int)
    outgoing_calls = defaultdict(int)
    
    for record in call_records:
        phone = record['phone_number']
        if phone == main_number:
            continue
            
        if record['call_type'] == 'Incoming':
            incoming_calls[phone] += 1
        elif record['call_type'] == 'Outgoing':
            outgoing_calls[phone] += 1
    
    # Build nodes
    nodes = []
    edges = []
    
    # Add main number as center node
    nodes.append({
        'id': main_number,
        'label': main_number,
        'type': 'main',
        'size': 40,
        'color': '#3b82f6',  # Blue for main
        'borderWidth': 3,
        'centrality': 1.0
    })
    
    # Add other numbers with different colors for incoming/outgoing
    all_phones = set(incoming_calls.keys()) | set(outgoing_calls.keys())
    
    for phone in all_phones:
        incoming_count = incoming_calls.get(phone, 0)
        outgoing_count = outgoing_calls.get(phone, 0)
        total_count = incoming_count + outgoing_count
        
        # Determine node color based on call type dominance
        if incoming_count > outgoing_count:
            node_color = '#10b981'  # Green for mostly incoming
            node_type = 'incoming'
        elif outgoing_count > incoming_count:
            node_color = '#ef4444'  # Red for mostly outgoing
            node_type = 'outgoing'
        else:
            node_color = '#8b5cf6'  # Purple for balanced
            node_type = 'both'
        
        nodes.append({
            'id': phone,
            'label': phone,
            'type': node_type,
            'size': 15 + min(total_count * 2, 25),
            'color': node_color,
            'incoming_count': incoming_count,
            'outgoing_count': outgoing_count,
            'centrality': total_count / max(len(call_records), 1)
        })
        
        # Create edges for incoming calls (arrow TO main number)
        if incoming_count > 0:
            edges.append({
                'source': phone,
                'target': main_number,
                'weight': incoming_count,
                'type': 'incoming',
                'color': '#10b981',
                'label': f"{incoming_count} incoming",
                'arrows': 'to'
            })
        
        # Create edges for outgoing calls (arrow FROM main number)
        if outgoing_count > 0:
            edges.append({
                'source': main_number,
                'target': phone,
                'weight': outgoing_count,
                'type': 'outgoing',
                'color': '#ef4444',
                'label': f"{outgoing_count} outgoing",
                'arrows': 'to'
            })
    
    # Calculate density
    total_possible_edges = len(nodes) * (len(nodes) - 1)
    density = len(edges) / total_possible_edges if total_possible_edges > 0 else 0
    
    return {
        'nodes': nodes,
        'edges': edges,
        'total_nodes': len(nodes),
        'total_edges': len(edges),
        'main_number': main_number,
        'density': density
    }
