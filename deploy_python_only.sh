#!/bin/bash

# Deployment Strategy for Python-Only Environment
# Use this if the server only has Python 3 (no Node.js)

echo "🚀 Deploying AIssociate to Python-Only Environment"
echo "================================================"
echo ""

# Step 1: Build frontend locally (on your Mac)
echo "Step 1: Building frontend locally..."
cd frontend
npm install
npm run build
cd ..

# Step 2: Create deployment package
echo "Step 2: Creating deployment package..."

# Create a clean directory structure
mkdir -p deploy_package
mkdir -p deploy_package/backend
mkdir -p deploy_package/frontend_dist

# Copy backend files
cp -r backend/* deploy_package/backend/
cp requirements.txt deploy_package/
cp .env deploy_package/  # Make sure to update DATABASE_URL for production!

# Copy built frontend
cp -r frontend/dist/* deploy_package/frontend_dist/

# Copy deployment scripts
cat > deploy_package/start_backend.sh << 'EOF'
#!/bin/bash
# Start FastAPI backend
source venv/bin/activate
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
EOF

cat > deploy_package/start_frontend.sh << 'EOF'
#!/bin/bash
# Start frontend with Python HTTP server
cd frontend_dist
python3 -m http.server 3000
EOF

chmod +x deploy_package/start_backend.sh
chmod +x deploy_package/start_frontend.sh

# Create setup script for server
cat > deploy_package/setup_on_server.sh << 'EOF'
#!/bin/bash
# Run this script on the server after uploading

echo "Setting up AIssociate on server..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Update .env file with production DATABASE_URL"
echo "2. Start backend: ./start_backend.sh"
echo "3. Start frontend: ./start_frontend.sh"
EOF

chmod +x deploy_package/setup_on_server.sh

# Create tarball
echo "Step 3: Creating tarball..."
tar -czf aissociate_deploy.tar.gz deploy_package/

echo ""
echo "✅ Deployment package created: aissociate_deploy.tar.gz"
echo ""
echo "Next steps:"
echo "1. Upload to server: scp aissociate_deploy.tar.gz app-admin@10.20.10.130:~/"
echo "2. SSH to server: ssh app-admin@10.20.10.130"
echo "3. Extract: tar -xzf aissociate_deploy.tar.gz"
echo "4. Run setup: cd deploy_package && ./setup_on_server.sh"
echo "5. Update .env with production database credentials"
echo "6. Start services: ./start_backend.sh and ./start_frontend.sh"
echo ""
echo "⚠️  Remember to configure PostgreSQL database before starting!"
