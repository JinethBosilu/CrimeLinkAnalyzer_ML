import psycopg
import os
import json
from datetime import datetime

# Database configuration (read from environment variables)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'junction.proxy.rlwy.net'),
    'port': os.getenv('DB_PORT', '37073'),
    'dbname': os.getenv('DB_NAME', 'railway'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'tqHFBHxFqajlAKFYaxCzfwYvNzeLPXXM')
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

def store_analysis_result(analysis_id, result_data):
    """
    Store analysis results in database for future reference
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_analysis_results (
                id VARCHAR(255) PRIMARY KEY,
                file_name VARCHAR(500),
                analysis_data JSONB,
                risk_score INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert analysis result
        query = """
            INSERT INTO call_analysis_results (id, file_name, analysis_data, risk_score, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE 
            SET analysis_data = EXCLUDED.analysis_data,
                risk_score = EXCLUDED.risk_score
        """
        
        cursor.execute(query, (
            analysis_id,
            result_data['file_name'],
            json.dumps(result_data),
            result_data['risk_score'],
            datetime.utcnow()
        ))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error storing analysis result: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def get_stored_analysis(analysis_id):
    """
    Retrieve stored analysis result from database
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        
        query = """
            SELECT id, file_name, analysis_data, risk_score, created_at
            FROM call_analysis_results
            WHERE id = %s
        """
        
        cursor.execute(query, (analysis_id,))
        result = cursor.fetchone()
        
        if result:
            return {
                'analysis_id': result[0],
                'file_name': result[1],
                'analysis_data': result[2],
                'risk_score': result[3],
                'created_at': result[4].isoformat()
            }
        
        return None
        
    except Exception as e:
        print(f"Error retrieving analysis: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()
