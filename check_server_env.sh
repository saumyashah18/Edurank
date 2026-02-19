#!/bin/bash

# Server Environment Check Script
# Run this script AFTER connecting to the server via SSH

echo "🔍 AIssociate Server Environment Check"
echo "====================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
    else
        echo -e "${RED}✗${NC} $1"
    fi
}

# Check Python
echo "Checking Python..."
python3 --version 2>/dev/null
print_check "Python 3 installed"
echo ""

# Check Node.js
echo "Checking Node.js..."
node --version 2>/dev/null
print_check "Node.js installed"
npm --version 2>/dev/null
print_check "npm installed"
echo ""

# Check Git
echo "Checking Git..."
git --version 2>/dev/null
print_check "Git installed"
echo ""

# Check PostgreSQL
echo "Checking PostgreSQL..."
psql --version 2>/dev/null
print_check "PostgreSQL client installed"

# Try to check if PostgreSQL server is running
if command -v systemctl &> /dev/null; then
    sudo systemctl status postgresql 2>/dev/null | grep -q "active (running)"
    print_check "PostgreSQL server running"
elif command -v service &> /dev/null; then
    sudo service postgresql status 2>/dev/null | grep -q "running"
    print_check "PostgreSQL server running"
else
    echo -e "${YELLOW}⚠${NC} Cannot determine PostgreSQL server status (no systemctl/service)"
fi
echo ""

# Check process managers
echo "Checking process managers..."
which screen &>/dev/null
print_check "screen available"

which tmux &>/dev/null
print_check "tmux available"

which pm2 &>/dev/null
print_check "pm2 available"
echo ""

# Check available ports
echo "Checking if ports 8000 and 3000 are available..."
if command -v lsof &> /dev/null; then
    lsof -i :8000 &>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${YELLOW}⚠${NC} Port 8000 is in use"
    else
        echo -e "${GREEN}✓${NC} Port 8000 is available"
    fi
    
    lsof -i :3000 &>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${YELLOW}⚠${NC} Port 3000 is in use"
    else
        echo -e "${GREEN}✓${NC} Port 3000 is available"
    fi
elif command -v netstat &> /dev/null; then
    netstat -tuln | grep -q ":8000 "
    if [ $? -eq 0 ]; then
        echo -e "${YELLOW}⚠${NC} Port 8000 is in use"
    else
        echo -e "${GREEN}✓${NC} Port 8000 is available"
    fi
    
    netstat -tuln | grep -q ":3000 "
    if [ $? -eq 0 ]; then
        echo -e "${YELLOW}⚠${NC} Port 3000 is in use"
    else
        echo -e "${GREEN}✓${NC} Port 3000 is available"
    fi
else
    echo -e "${YELLOW}⚠${NC} Cannot check port availability (no lsof/netstat)"
fi
echo ""

# Check disk space
echo "Checking disk space..."
df -h . | tail -1
echo ""

# Check home directory
echo "Current directory: $(pwd)"
echo "Home directory: $HOME"
echo ""

echo "====================================="
echo "Environment check complete!"
echo ""
echo "Next steps:"
echo "1. If PostgreSQL is not available, contact IT or use a cloud service"
echo "2. Clone your repository: git clone <your-repo-url>"
echo "3. Run the deployment script: ./deploy.sh"
