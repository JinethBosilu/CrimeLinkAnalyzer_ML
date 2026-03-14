import psycopg
import os

# Database configuration (read from environment variables)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'junction.proxy.rlwy.net'),
    'port': os.getenv('DB_PORT', '37073'),
    'dbname': os.getenv('DB_NAME', 'railway'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}


def get_db_connection():
    """Create database connection"""
    try:
        conn = psycopg.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        return None


def get_criminal_info(phone_number):
    """
    Check if phone number belongs to a known criminal
    Returns criminal information if found, None otherwise
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        # Query to find criminal by phone number
        query = """
            SELECT c.id, c.name, c.nic, c.contact_number, 
                   COALESCE(
                       json_agg(
                           json_build_object(
                               'crime_type', cr.crime_type,
                               'date', cr.crime_date,
                               'status', cr.status
                           )
                       ) FILTER (WHERE cr.id IS NOT NULL),
                       '[]'
                   ) as crimes
            FROM criminals c
            LEFT JOIN crime_records cr ON c.id = cr.criminal_id
            WHERE c.contact_number = %s OR c.secondary_contact = %s
            GROUP BY c.id, c.name, c.nic, c.contact_number
        """
        
        cursor.execute(query, (phone_number, phone_number))
        result = cursor.fetchone()
        
        if result:
            return {
                'id': result[0],
                'name': result[1],
                'nic': result[2],
                'phone': result[3],
                'crimes': result[4] if isinstance(result[4], list) else []
            }
        
        return None
        
    except Exception as e:
        print(f"Error querying criminal database: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()
