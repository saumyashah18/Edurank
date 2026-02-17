#!/bin/bash
# Quick Frontend Update Script
# Use this when you only changed frontend React code

echo "🎨 Quick Frontend Update"
echo "========================"
echo ""

cd /Users/apple/Edurank

echo "Building frontend..."
cd frontend
npm run build

if [ $? -eq 0 ]; then
    cd ..
    echo ""
    echo "✅ Frontend built successfully!"
    echo ""
    echo "Creating package..."
    tar -czf frontend_update.tar.gz frontend/dist
    
    echo "Uploading to server..."
    scp frontend_update.tar.gz app-admin@10.20.10.130:~/
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Upload complete!"
        echo ""
        echo "Next steps (on server):"
        echo "1. SSH: ssh app-admin@10.20.10.130"
        echo "2. Extract: tar -xzf frontend_update.tar.gz"
        echo "3. Update: cd deploy_package && cp -r ../frontend/dist/* frontend_dist/"
        echo "4. Restart: pkill -f http.server && ./start_frontend.sh"
    else
        echo "❌ Upload failed. Check SSH connection."
    fi
else
    echo "❌ Build failed. Check for errors above."
fi
