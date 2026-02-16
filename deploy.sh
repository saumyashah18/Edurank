#!/bin/bash

# Edurank Deployment Script
# This script helps deploy/redeploy the Edurank application on a server

set -e  # Exit on any error

echo "🚀 Edurank Deployment Script"
echo "=============================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "requirements.txt" ] || [ ! -d "frontend" ]; then
    print_error "This script must be run from the Edurank project root directory"
    exit 1
fi

print_info "Current directory: $(pwd)"
echo ""

# Menu
echo "What would you like to do?"
echo "1) First-time deployment (full setup)"
echo "2) Redeploy after code changes"
echo "3) Restart services only"
echo "4) View running processes"
echo ""
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        print_info "Starting first-time deployment..."
        echo ""
        
        # Backend setup
        print_info "Setting up Python backend..."
        
        if [ ! -d ".venv" ]; then
            print_info "Creating virtual environment..."
            python3 -m venv .venv
        else
            print_info "Virtual environment already exists"
        fi
        
        print_info "Activating virtual environment..."
        source .venv/bin/activate
        
        print_info "Installing Python dependencies..."
        pip install -r requirements.txt
        
        # Check for .env file
        if [ ! -f ".env" ]; then
            print_warning ".env file not found!"
            echo "Please create a .env file with your configuration."
            echo "Example:"
            echo "OPENROUTER_API_KEY=your_key_here"
            echo "LLM_MODEL=anthropic/claude-opus-4.6"
            echo "DATABASE_URL=postgresql://username:password@localhost:5432/edurank"
            echo "HF_TOKEN=your_token_here"
            echo ""
            read -p "Press Enter after creating .env file..."
        fi
        
        # Check PostgreSQL connection
        print_info "Checking PostgreSQL connection..."
        if command -v psql &> /dev/null; then
            print_info "PostgreSQL client found. Make sure your database is set up!"
            echo "You can test connection with: psql -U your_username -d edurank"
        else
            print_warning "PostgreSQL client (psql) not found on this system"
            print_warning "Make sure you have access to a PostgreSQL database"
        fi
        echo ""
        
        # Frontend setup
        print_info "Setting up frontend..."
        cd frontend
        
        if [ ! -d "node_modules" ]; then
            print_info "Installing npm dependencies..."
            npm install
        else
            print_info "npm dependencies already installed"
        fi
        
        print_info "Building frontend for production..."
        npm run build
        
        cd ..
        
        print_info "✅ First-time deployment complete!"
        echo ""
        print_info "Next steps:"
        echo "1. Start backend: uvicorn backend.api.main:app --host 0.0.0.0 --port 8000"
        echo "2. Start frontend: cd frontend/dist && python3 -m http.server 3000"
        echo ""
        print_info "Or use screen/pm2 for persistent processes (see deployment_guide.md)"
        ;;
        
    2)
        print_info "Starting redeployment..."
        echo ""
        
        # Pull latest changes
        print_info "Pulling latest code from Git..."
        git pull origin main || print_warning "Git pull failed or no changes"
        
        # Backend updates
        print_info "Updating backend..."
        source .venv/bin/activate
        
        print_info "Installing/updating Python dependencies..."
        pip install -r requirements.txt
        
        # Frontend updates
        print_info "Updating frontend..."
        cd frontend
        
        print_info "Installing/updating npm dependencies..."
        npm install
        
        print_info "Rebuilding frontend..."
        npm run build
        
        cd ..
        
        print_info "✅ Redeployment complete!"
        echo ""
        print_warning "Remember to restart your backend and frontend services!"
        echo ""
        print_info "Quick restart commands:"
        echo "- Kill processes: pkill -f uvicorn && pkill -f 'http.server'"
        echo "- Restart backend: uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 &"
        echo "- Restart frontend: cd frontend/dist && python3 -m http.server 3000 &"
        ;;
        
    3)
        print_info "Restarting services..."
        echo ""
        
        # Kill existing processes
        print_info "Stopping existing processes..."
        pkill -f uvicorn || print_warning "No uvicorn process found"
        pkill -f "http.server" || print_warning "No http.server process found"
        
        sleep 2
        
        # Start backend
        print_info "Starting backend..."
        source .venv/bin/activate
        nohup uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
        BACKEND_PID=$!
        print_info "Backend started with PID: $BACKEND_PID"
        
        # Start frontend
        print_info "Starting frontend..."
        cd frontend/dist
        nohup python3 -m http.server 3000 > ../../frontend.log 2>&1 &
        FRONTEND_PID=$!
        print_info "Frontend started with PID: $FRONTEND_PID"
        cd ../..
        
        sleep 2
        
        print_info "✅ Services restarted!"
        echo ""
        print_info "View logs:"
        echo "- Backend: tail -f backend.log"
        echo "- Frontend: tail -f frontend.log"
        ;;
        
    4)
        print_info "Checking running processes..."
        echo ""
        
        echo "Backend processes (uvicorn):"
        ps aux | grep uvicorn | grep -v grep || echo "No backend process found"
        echo ""
        
        echo "Frontend processes (http.server):"
        ps aux | grep "http.server" | grep -v grep || echo "No frontend process found"
        echo ""
        
        echo "Screen sessions:"
        screen -ls || echo "No screen sessions found"
        echo ""
        
        if command -v pm2 &> /dev/null; then
            echo "PM2 processes:"
            pm2 status
        fi
        ;;
        
    *)
        print_error "Invalid choice"
        exit 1
        ;;
esac

echo ""
print_info "Done! 🎉"
