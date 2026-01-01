from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
from datetime import datetime
from utils.pdf_parser import parse_call_records
from utils.network_analyzer import analyze_call_network

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# In-memory storage for analysis results (use Redis in production)
analysis_results = {}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'call_analysis_service',
        'timestamp': datetime.utcnow().isoformat()
    }), 200

@app.route('/analyze', methods=['POST'])
def analyze_call_records():
    """
    Analyze call records from uploaded PDF file
    Expected: multipart/form-data with 'file' field
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are supported'}), 400
        
        # Generate unique analysis ID
        analysis_id = str(uuid.uuid4())
        
        # Save uploaded file
        file_path = os.path.join(UPLOAD_FOLDER, f"{analysis_id}.pdf")
        file.save(file_path)
        
        # Parse call records from PDF
        call_records = parse_call_records(file_path)
        
        if not call_records:
            return jsonify({
                'error': 'No call records found in PDF',
                'analysis_id': analysis_id
            }), 400
        
        # Analyze call network
        analysis = analyze_call_network(call_records)
        
        # Prepare result - just visualization data, no database lookups
        result = {
            'analysis_id': analysis_id,
            'status': 'completed',
            'timestamp': datetime.utcnow().isoformat(),
            'file_name': file.filename,
            'main_number': analysis['main_number'],
            'total_calls': analysis['total_calls'],
            'total_incoming': analysis['total_incoming'],
            'total_outgoing': analysis['total_outgoing'],
            'unique_numbers': analysis['unique_numbers'],
            'call_frequency': analysis['call_frequency'],
            'time_pattern': analysis['time_pattern'],
            'common_contacts': analysis['common_contacts'],
            'incoming_graph': analysis['incoming_graph'],
            'outgoing_graph': analysis['outgoing_graph'],
            'risk_score': calculate_risk_score(analysis)
        }
        
        # Store result in memory for retrieval
        analysis_results[analysis_id] = result
        
        return jsonify({
            'analysis_id': analysis_id,
            'status': 'completed',
            'message': 'Analysis completed successfully'
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'failed'
        }), 500

@app.route('/results/<analysis_id>', methods=['GET'])
def get_analysis_results(analysis_id):
    """
    Get analysis results by ID
    """
    if analysis_id not in analysis_results:
        return jsonify({'error': 'Analysis not found'}), 404
    
    return jsonify(analysis_results[analysis_id]), 200

@app.route('/results', methods=['GET'])
def list_all_results():
    """
    List all analysis results (for testing)
    """
    return jsonify({
        'total': len(analysis_results),
        'results': [
            {
                'analysis_id': aid,
                'timestamp': result['timestamp'],
                'file_name': result['file_name'],
                'status': result['status']
            }
            for aid, result in analysis_results.items()
        ]
    }), 200

def calculate_risk_score(analysis):
    """
    Calculate risk score based on call patterns only
    """
    score = 0
    
    # High number of calls increases risk
    if analysis['total_calls'] > 100:
        score += 40
    elif analysis['total_calls'] > 50:
        score += 25
    
    # Many unique contacts increase risk
    if len(analysis['unique_numbers']) > 50:
        score += 30
    elif len(analysis['unique_numbers']) > 30:
        score += 20
    
    # Unusual time patterns (late night calls)
    late_night_calls = sum(
        count for hour, count in analysis['time_pattern'].items()
        if int(hour) >= 22 or int(hour) <= 5
    )
    if late_night_calls > analysis['total_calls'] * 0.3:
        score += 20
    
    # High frequency to specific numbers
    max_frequency = max(analysis['call_frequency'].values()) if analysis['call_frequency'] else 0
    if max_frequency > 20:
        score += 10
    
    return min(score, 100)  # Cap at 100

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
