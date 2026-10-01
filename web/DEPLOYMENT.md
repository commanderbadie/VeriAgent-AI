# VeriAgent Web Deployment Guide

Complete guide for deploying VeriAgent web interface to production.

## 🚀 Quick Deploy Options

### Option 1: Render (Recommended for Python Apps)

**Pros:**
- Native Python support
- Easy ML model deployment
- Free tier available
- Auto-deploy from Git

**Steps:**

1. **Push to GitHub**
```bash
git add -A
git commit -m "feat: add web interface"
git push origin main
```

2. **Create Render Account**
- Go to [render.com](https://render.com)
- Sign up with GitHub

3. **Create New Web Service**
- Click "New +" → "Web Service"
- Connect your GitHub repository
- Select the VeriAgent repo

4. **Configure Service**
```
Name: veriagent
Environment: Python 3
Region: Choose nearest
Branch: main
Build Command: pip install -r web/requirements.txt
Start Command: cd web && gunicorn --bind 0.0.0.0:$PORT app:app
```

5. **Add Environment Variables** (if needed)
```
PYTHON_VERSION=3.11.0
```

6. **Deploy!**
- Click "Create Web Service"
- Wait 2-3 minutes for build
- Your app will be live at `https://veriagent.onrender.com`

---

### Option 2: Railway

**Pros:**
- Extremely simple
- Great free tier
- Fast deployments

**Steps:**

1. **Install Railway CLI**
```bash
npm install -g @railway/cli
```

2. **Login and Deploy**
```bash
cd web
railway login
railway init
railway up
```

3. **Configure**
```bash
railway add
railway variables set PYTHON_VERSION=3.11
```

4. **Open**
```bash
railway open
```

---

### Option 3: Fly.io

**Pros:**
- Global edge deployment
- Great performance
- Free tier

**Steps:**

1. **Install Fly CLI**
```bash
curl -L https://fly.io/install.sh | sh
```

2. **Create fly.toml in web/ directory**
```toml
app = "veriagent"

[build]
  builder = "paketobuildpacks/builder:base"

[[services]]
  http_checks = []
  internal_port = 5000
  protocol = "tcp"

  [[services.ports]]
    force_https = true
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443
```

3. **Deploy**
```bash
cd web
fly launch
fly deploy
```

---

## 📦 Manual Deployment (Any VPS)

### Prerequisites
- Ubuntu 20.04+ server
- Python 3.10+
- Nginx
- Domain name (optional)

### Steps

1. **SSH into Server**
```bash
ssh user@your-server-ip
```

2. **Install Dependencies**
```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx
```

3. **Clone Repository**
```bash
git clone https://github.com/yourusername/veriagent-ai.git
cd veriagent-ai/web
```

4. **Setup Virtual Environment**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

5. **Test Application**
```bash
gunicorn --bind 0.0.0.0:8000 app:app
```

6. **Create Systemd Service**
```bash
sudo nano /etc/systemd/system/veriagent.service
```

Add:
```ini
[Unit]
Description=VeriAgent Web Service
After=network.target

[Service]
User=youruser
WorkingDirectory=/home/youruser/veriagent-ai/web
Environment="PATH=/home/youruser/veriagent-ai/web/venv/bin"
ExecStart=/home/youruser/veriagent-ai/web/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:8000 app:app

[Install]
WantedBy=multi-user.target
```

7. **Start Service**
```bash
sudo systemctl start veriagent
sudo systemctl enable veriagent
sudo systemctl status veriagent
```

8. **Configure Nginx**
```bash
sudo nano /etc/nginx/sites-available/veriagent
```

Add:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static {
        alias /home/youruser/veriagent-ai/web/static;
    }
}
```

9. **Enable Site**
```bash
sudo ln -s /etc/nginx/sites-available/veriagent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

10. **Setup SSL (Optional but Recommended)**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 🔧 Environment Configuration

### Required Files

Make sure these files exist before deploying:
- `experiments/outputs/phase5_models/random_forest.pkl`
- `experiments/outputs/phase5_models/preprocessor.json`
- `data/veriagent.db`

### Environment Variables

```bash
# Optional
FLASK_ENV=production
PYTHON_VERSION=3.11.0
```

---

## ✅ Post-Deployment Checklist

- [ ] App loads successfully
- [ ] API endpoints respond (`/api/health`, `/api/stats`)
- [ ] Example scenarios load
- [ ] Verification works for both normal and attack scenarios
- [ ] ML confidence scores display correctly
- [ ] Responsive design works on mobile
- [ ] SSL certificate installed (if using custom domain)

---

## 🔍 Troubleshooting

### Issue: ML Model Not Loading

**Solution:**
Ensure model files are present:
```bash
ls experiments/outputs/phase5_models/
# Should show: random_forest.pkl, preprocessor.json
```

### Issue: Static Files Not Loading

**Solution:**
Check Flask static folder configuration and Nginx rules.

### Issue: Port Already in Use

**Solution:**
```bash
# Find process using port
sudo lsof -i :5000
# Kill it
sudo kill -9 <PID>
```

### Issue: Gunicorn Workers Crashing

**Solution:**
Check logs:
```bash
journalctl -u veriagent -f
```

Reduce workers if low memory:
```bash
gunicorn --workers 1 --bind 0.0.0.0:8000 app:app
```

---

## 📊 Monitoring

### Health Check
```bash
curl https://your-domain.com/api/health
```

### View Logs (Render)
- Go to Render Dashboard → Your Service → Logs

### View Logs (Systemd)
```bash
sudo journalctl -u veriagent -f
```

---

## 🔐 Security Considerations

1. **Never expose `.env` files** with secrets
2. **Use HTTPS** in production (Render/Railway do this automatically)
3. **Rate limit API endpoints** if expecting high traffic
4. **Keep dependencies updated**
```bash
pip list --outdated
```

5. **Regular backups** of model files

---

## 🎯 Performance Optimization

### For Production

1. **Enable Gunicorn Workers**
```bash
gunicorn --workers 4 --threads 2 --bind 0.0.0.0:$PORT app:app
```

2. **Add Caching**
Install Flask-Caching for stats endpoint

3. **Compress Static Assets**
Enable gzip in Nginx

4. **CDN for Static Files**
Use Cloudflare or similar for CSS/JS

---

## 📝 Custom Domain Setup

### Render
1. Go to Settings → Custom Domains
2. Add your domain
3. Update DNS with provided CNAME

### Railway
1. Settings → Domains
2. Add custom domain
3. Update DNS records

---

## 🆘 Support

If deployment fails:
1. Check logs first
2. Verify Python version (3.10+)
3. Ensure all dependencies installed
4. Test locally with `python app.py`

---

**Your VeriAgent web interface should now be live! 🎉**

Visit your deployment URL and test with the example scenarios.
