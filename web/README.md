# VeriAgent Web Interface

Professional web interface for demonstrating VeriAgent's ML-powered behavioral verification system.

## Features

- 🎯 **Interactive Verification** - Test actions with real-time verification
- 📊 **Live Statistics** - Model performance metrics and system status
- 🎨 **Professional Design** - Clean, modern UI with custom styling
- 🚀 **Example Scenarios** - Pre-configured normal and attack scenarios
- 🔍 **Detailed Results** - Comprehensive breakdown of decisions and confidence scores
- 📱 **Responsive** - Works on desktop, tablet, and mobile

## Local Development

### Prerequisites

- Python 3.10+
- Trained ML models in `../experiments/outputs/phase5_models/`

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

The app will be available at `http://localhost:5000`

## Deployment

### Vercel (Frontend + Serverless Functions)

1. Install Vercel CLI:
```bash
npm install -g vercel
```

2. Deploy:
```bash
vercel
```

### Render (Full Python Backend)

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Set build command: `pip install -r web/requirements.txt`
4. Set start command: `cd web && python app.py`
5. Deploy

## API Endpoints

### `POST /api/verify`
Verify a proposed action.

**Request:**
```json
{
  "action": "get_customer",
  "user_role": "AGENT",
  "parameters": {"customer_id": 123},
  "behavioral_context": {
    "tool_sensitivity": "LOW",
    "has_amount": false,
    ...
  }
}
```

**Response:**
```json
{
  "decision": "ALLOW",
  "reasons": ["All checks passed"],
  "checks": {
    "permission": true,
    "ml_consulted": true,
    "ml_safe_probability": 0.98
  },
  "verifier_used": "hybrid"
}
```

### `GET /api/examples`
Get predefined example scenarios.

### `GET /api/stats`
Get system statistics and model performance.

### `GET /api/health`
Health check endpoint.

## Architecture

```
web/
├── app.py              # Flask application
├── requirements.txt    # Python dependencies
├── static/
│   ├── style.css      # Custom professional styling
│   └── script.js      # Interactive JavaScript
└── templates/
    └── index.html     # Main page template
```

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: Vanilla JavaScript (no frameworks)
- **Styling**: Custom CSS with modern design system
- **ML**: Scikit-learn Random Forest
- **Verification**: Hybrid rules + ML system

## Design Philosophy

- **No AI-generated look**: Custom-designed, hand-crafted UI
- **Professional**: Clean, modern design inspired by enterprise applications
- **Accessible**: Semantic HTML, clear contrast, keyboard navigation
- **Fast**: No heavy frameworks, optimized assets
- **Responsive**: Mobile-first design approach

## License

Part of VeriAgent project.
