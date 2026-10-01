// VeriAgent Web Interface - Professional JavaScript

// State
let currentScenario = null;
let exampleScenarios = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadExamples();
    setupEventListeners();
});

// Load statistics
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        // Update stat cards
        document.getElementById('test-accuracy').textContent = 
            stats.model_performance.test_accuracy ? 
            (stats.model_performance.test_accuracy * 100).toFixed(0) + '%' : 
            'N/A';
            
        document.getElementById('adversarial-accuracy').textContent = 
            stats.model_performance.adversarial_accuracy ? 
            (stats.model_performance.adversarial_accuracy * 100).toFixed(0) + '%' : 
            'N/A';
            
        document.getElementById('model-type').textContent = 
            stats.model_performance.model_type || 'Rules Only';
            
        document.getElementById('training-scenarios').textContent = 
            stats.total_scenarios_trained || '0';
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

// Load example scenarios
async function loadExamples() {
    try {
        const response = await fetch('/api/examples');
        exampleScenarios = await response.json();
        
        const scenarioList = document.getElementById('scenario-list');
        scenarioList.innerHTML = '';
        
        for (const [key, scenario] of Object.entries(exampleScenarios)) {
            const card = createScenarioCard(key, scenario);
            scenarioList.appendChild(card);
        }
    } catch (error) {
        console.error('Failed to load examples:', error);
    }
}

// Create scenario card element
function createScenarioCard(key, scenario) {
    const card = document.createElement('div');
    card.className = `scenario-card scenario-${scenario.expected === 'BLOCK' ? 'attack' : 'normal'}`;
    card.onclick = () => loadScenario(key);
    
    card.innerHTML = `
        <span class="scenario-name">${scenario.name}</span>
        <span class="scenario-expected expected-${scenario.expected.toLowerCase()}">
            ${scenario.expected}
        </span>
    `;
    
    return card;
}

// Load scenario into form
function loadScenario(key) {
    const scenario = exampleScenarios[key];
    if (!scenario) return;
    
    currentScenario = scenario;
    
    // Fill form
    document.getElementById('action').value = scenario.action;
    document.getElementById('user_role').value = scenario.user_role;
    document.getElementById('parameters').value = JSON.stringify(scenario.parameters, null, 2);
    
    // Scroll to form
    document.getElementById('verify-form').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Setup event listeners
function setupEventListeners() {
    // Form submission
    document.getElementById('verify-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await verifyAction();
    });
    
    // Clear button
    document.getElementById('clear-btn').addEventListener('click', () => {
        document.getElementById('verify-form').reset();
        currentScenario = null;
    });
    
    // Close results
    document.getElementById('close-results').addEventListener('click', () => {
        document.getElementById('results-panel').style.display = 'none';
    });
}

// Verify action
async function verifyAction() {
    const form = document.getElementById('verify-form');
    const submitBtn = form.querySelector('button[type="submit"]');
    
    // Get form data
    const action = document.getElementById('action').value;
    const user_role = document.getElementById('user_role').value;
    const parametersText = document.getElementById('parameters').value;
    
    // Parse parameters
    let parameters = {};
    if (parametersText.trim()) {
        try {
            parameters = JSON.parse(parametersText);
        } catch (error) {
            alert('Invalid JSON in parameters field');
            return;
        }
    }
    
    // Build request
    const requestData = {
        action,
        user_role,
        parameters
    };
    
    // Add behavioral context if from example
    if (currentScenario && currentScenario.behavioral_context) {
        requestData.behavioral_context = currentScenario.behavioral_context;
    }
    
    // Show loading
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="loading"></span> Verifying...';
    
    try {
        const response = await fetch('/api/verify', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        const result = await response.json();
        
        // Display result
        displayResult(result);
        
    } catch (error) {
        alert('Verification failed: ' + error.message);
    } finally {
        // Reset button
        submitBtn.disabled = false;
        submitBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="9 11 12 14 22 4"></polyline>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
            </svg>
            Verify Action
        `;
    }
}

// Display verification result
function displayResult(result) {
    const resultsPanel = document.getElementById('results-panel');
    const resultsContent = document.getElementById('results-content');
    
    const decision = result.decision || 'UNKNOWN';
    const decisionClass = decision.toLowerCase();
    
    // Icon based on decision
    let icon = '';
    if (decision === 'ALLOW') {
        icon = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
        `;
    } else if (decision === 'BLOCK') {
        icon = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="15" y1="9" x2="9" y2="15"></line>
                <line x1="9" y1="9" x2="15" y2="15"></line>
            </svg>
        `;
    } else {
        icon = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
        `;
    }
    
    resultsContent.innerHTML = `
        <div class="result-header decision-${decisionClass}">
            <div class="result-icon decision-${decisionClass}">
                ${icon}
            </div>
            <div>
                <div class="result-title">${decision}</div>
                <div style="font-size: 0.875rem; opacity: 0.8; margin-top: 4px;">
                    Verified by: ${result.verifier_used === 'hybrid' ? 'Hybrid (Rules + ML)' : 'Rules Only'}
                </div>
            </div>
        </div>
        
        <div class="result-section">
            <h3>Reasons</h3>
            <div class="reasons-list">
                ${result.reasons.map(reason => `
                    <div class="reason-item">${escapeHtml(reason)}</div>
                `).join('')}
            </div>
        </div>
        
        <div class="result-section">
            <h3>Verification Checks</h3>
            <div class="checks-grid">
                ${Object.entries(result.checks).map(([key, value]) => {
                    const valueClass = typeof value === 'boolean' ? (value ? 'check-true' : 'check-false') : '';
                    const displayValue = formatCheckValue(value);
                    return `
                        <div class="check-item">
                            <span class="check-name">${formatCheckName(key)}</span>
                            <span class="check-value ${valueClass}">${displayValue}</span>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
        
        ${result.verifier_used === 'hybrid' && result.checks.ml_safe_probability !== undefined ? `
            <div class="result-section">
                <h3>ML Confidence</h3>
                <div style="background: var(--color-bg); padding: 1rem; border-radius: var(--radius-md);">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                        <span style="font-size: 0.875rem; font-weight: 500;">SAFE</span>
                        <span style="font-size: 0.875rem; font-weight: 700; color: var(--color-success);">
                            ${(result.checks.ml_safe_probability * 100).toFixed(1)}%
                        </span>
                    </div>
                    <div style="height: 8px; background: var(--color-border); border-radius: 4px; overflow: hidden;">
                        <div style="height: 100%; width: ${result.checks.ml_safe_probability * 100}%; background: var(--color-success); transition: width 0.3s ease;"></div>
                    </div>
                    
                    <div style="display: flex; justify-content: space-between; margin-top: 1rem; margin-bottom: 0.5rem;">
                        <span style="font-size: 0.875rem; font-weight: 500;">UNSAFE</span>
                        <span style="font-size: 0.875rem; font-weight: 700; color: var(--color-danger);">
                            ${(result.checks.ml_unsafe_probability * 100).toFixed(1)}%
                        </span>
                    </div>
                    <div style="height: 8px; background: var(--color-border); border-radius: 4px; overflow: hidden;">
                        <div style="height: 100%; width: ${result.checks.ml_unsafe_probability * 100}%; background: var(--color-danger); transition: width 0.3s ease;"></div>
                    </div>
                </div>
            </div>
        ` : ''}
    `;
    
    // Show results panel
    resultsPanel.style.display = 'block';
    resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Helper functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatCheckName(key) {
    return key
        .replace(/_/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
}

function formatCheckValue(value) {
    if (typeof value === 'boolean') {
        return value ? '✓' : '✗';
    }
    if (typeof value === 'number') {
        return value < 1 ? (value * 100).toFixed(1) + '%' : value.toFixed(2);
    }
    return String(value);
}
