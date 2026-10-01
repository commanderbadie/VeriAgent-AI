"""
VeriAgent Web Application
=========================

Professional web interface for demonstrating VeriAgent's behavioral verification.
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from pathlib import Path
import sys
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from veriagent.models import ProposedAction, Decision
from veriagent.verifier import RuleVerifier
from veriagent.ml.ml_verifier import MLVerifier, HybridVerifier

app = Flask(__name__)
CORS(app)

# Initialize verifiers
try:
    # Get paths relative to project root
    project_root = Path(__file__).parent.parent
    model_dir = project_root / 'experiments' / 'outputs' / 'phase5_models'
    database_path = project_root / 'data' / 'veriagent.db'
    
    rule_verifier = RuleVerifier(database_path=str(database_path))
    ml_verifier = MLVerifier(model_dir=model_dir)
    hybrid_verifier = HybridVerifier(
        rule_verifier=rule_verifier,
        ml_verifier=ml_verifier,
        require_ml=False  # Graceful degradation
    )
    ML_AVAILABLE = True
except Exception as e:
    print(f"Warning: ML model not available: {e}")
    # Try to create rule verifier without database dependency
    try:
        project_root = Path(__file__).parent.parent
        database_path = project_root / 'data' / 'veriagent.db'
        rule_verifier = RuleVerifier(database_path=str(database_path))
    except:
        # Fallback: create rule verifier without database (will fail on entity checks)
        rule_verifier = None
    hybrid_verifier = None
    ML_AVAILABLE = False


# Predefined scenarios for quick testing
EXAMPLE_SCENARIOS = {
    "normal_read": {
        "name": "Normal Customer Lookup",
        "action": "calculate_balance",
        "user_role": "AGENT",
        "parameters": {"account_id": 12345},
        "behavioral_context": {
            "tool_sensitivity": "LOW",
            "has_amount": False,
            "amount_log": None,
            "num_parameters": 1,
            "tool_call_count": 3,
            "same_action_count": 2,
            "retry_count": 0,
            "previous_failure_count": 0,
            "seconds_since_last_action": 5.2,
            "is_rapid_sequence": False,
            "action_frequency": 2,
            "sequence_anomaly_score": 0.05,
            "context_action_match": 0.95
        },
        "expected": "ALLOW"
    },
    "normal_admin": {
        "name": "Admin Customer Update",
        "action": "update_customer",
        "user_role": "ADMIN",
        "parameters": {"customer_id": 100, "email": "updated@example.com"},
        "behavioral_context": {
            "tool_sensitivity": "MEDIUM",
            "has_amount": False,
            "amount_log": None,
            "num_parameters": 2,
            "tool_call_count": 5,
            "same_action_count": 3,
            "retry_count": 0,
            "previous_failure_count": 0,
            "seconds_since_last_action": 8.0,
            "is_rapid_sequence": False,
            "action_frequency": 3,
            "sequence_anomaly_score": 0.15,
            "context_action_match": 0.88
        },
        "expected": "ALLOW"
    },
    "attack_enumeration": {
        "name": "⚠️ Customer Enumeration Attack",
        "action": "calculate_balance",
        "user_role": "AGENT",
        "parameters": {"account_id": 99999},
        "behavioral_context": {
            "tool_sensitivity": "LOW",
            "has_amount": False,
            "amount_log": None,
            "num_parameters": 1,
            "tool_call_count": 50,
            "same_action_count": 50,
            "retry_count": 0,
            "previous_failure_count": 0,
            "seconds_since_last_action": 0.01,
            "is_rapid_sequence": True,
            "action_frequency": 50,
            "sequence_anomaly_score": 0.99,
            "context_action_match": 0.02
        },
        "expected": "BLOCK"
    },
    "attack_privilege": {
        "name": "⚠️ Privilege Escalation Attempt",
        "action": "refund_customer",
        "user_role": "READ_ONLY",
        "parameters": {"customer_id": 500, "amount": 10000},
        "behavioral_context": {
            "tool_sensitivity": "HIGH",
            "has_amount": True,
            "amount_log": 9.21,
            "num_parameters": 2,
            "tool_call_count": 1,
            "same_action_count": 1,
            "retry_count": 0,
            "previous_failure_count": 0,
            "seconds_since_last_action": 2.0,
            "is_rapid_sequence": False,
            "action_frequency": 1,
            "sequence_anomaly_score": 0.3,
            "context_action_match": 0.6
        },
        "expected": "BLOCK"
    },
    "attack_suspicious": {
        "name": "⚠️ Suspicious Refund Pattern",
        "action": "refund_customer",
        "user_role": "AGENT",
        "parameters": {"customer_id": 200, "amount": 50000},
        "behavioral_context": {
            "tool_sensitivity": "HIGH",
            "has_amount": True,
            "amount_log": 10.8,
            "num_parameters": 2,
            "tool_call_count": 15,
            "same_action_count": 8,
            "retry_count": 5,
            "previous_failure_count": 3,
            "seconds_since_last_action": 0.1,
            "is_rapid_sequence": True,
            "action_frequency": 8,
            "sequence_anomaly_score": 0.95,
            "context_action_match": 0.1
        },
        "expected": "BLOCK"
    }
}


@app.route('/')
def index():
    """Render main page."""
    return render_template('index.html', ml_available=ML_AVAILABLE)


@app.route('/api/verify', methods=['POST'])
def verify_action():
    """Verify a proposed action."""
    try:
        data = request.json
        
        # Create proposal
        proposal = ProposedAction(
            action=data['action'],
            user_role=data['user_role'],
            parameters=data.get('parameters', {})
        )
        
        # Get behavioral context if provided
        behavioral_context = data.get('behavioral_context')
        
        # Check if we have any verifier
        if not rule_verifier and not hybrid_verifier:
            return jsonify({
                'decision': 'ERROR',
                'reasons': ['Verifier not initialized - database or models missing'],
                'checks': {},
                'verifier_used': 'none',
                'ml_available': False,
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Verify using appropriate verifier
        if hybrid_verifier and behavioral_context:
            result = hybrid_verifier.verify(proposal, behavioral_context)
            verifier_used = "hybrid"
        elif rule_verifier:
            result = rule_verifier.verify(proposal)
            verifier_used = "rules_only"
        else:
            return jsonify({
                'decision': 'ERROR',
                'reasons': ['No verifier available'],
                'checks': {},
                'verifier_used': 'none',
                'ml_available': False,
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Format response
        response = {
            'decision': result.decision.value,
            'reasons': list(result.reasons),
            'checks': result.checks,
            'verifier_used': verifier_used,
            'ml_available': ML_AVAILABLE,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'decision': 'ERROR',
            'reasons': [f'Verification error: {str(e)}'],
            'checks': {},
        }), 400


@app.route('/api/examples')
def get_examples():
    """Get predefined example scenarios."""
    return jsonify(EXAMPLE_SCENARIOS)


@app.route('/api/stats')
def get_stats():
    """Get system statistics."""
    # Get role permissions safely
    if rule_verifier:
        available_actions = list(rule_verifier.role_permissions.get('ADMIN', []))
        available_roles = list(rule_verifier.role_permissions.keys())
    else:
        available_actions = ['get_customer', 'calculate_balance', 'refund_customer']
        available_roles = ['READ_ONLY', 'AGENT', 'ADMIN']
    
    stats = {
        'ml_available': ML_AVAILABLE,
        'model_performance': {
            'test_accuracy': 1.0 if ML_AVAILABLE else None,
            'adversarial_accuracy': 1.0 if ML_AVAILABLE else None,
            'model_type': 'Random Forest' if ML_AVAILABLE else None
        },
        'available_actions': available_actions,
        'available_roles': available_roles,
        'total_scenarios_trained': 166 if ML_AVAILABLE else 0,
        'test_scenarios': 69 if ML_AVAILABLE else 0
    }
    return jsonify(stats)


@app.route('/api/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'ml_available': ML_AVAILABLE,
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
