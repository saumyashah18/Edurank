#!/bin/bash
# Quick Backend Update Script
# Use this when you only changed backend Python code

echo "🔄 Quick Backend Update"
echo "======================="
echo ""

cd /Users/apple/Edurank

echo "Building deployment package..."
./deploy_python_only.sh

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Package built successfully!"
    echo ""
    echo "Uploading to server..."
    scp edurank_deploy.tar.gz app-admin@10.20.10.130:~/
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Upload complete!"
        echo ""
        echo "Next steps (on server):"
        echo "1. SSH: ssh app-admin@10.20.10.130"
        echo "2. Extract: cd deploy_package && tar -xzf ../edurank_deploy.tar.gz --strip-components=1"
        echo "3. Restart backend: pkill -f uvicorn && ./start_backend.sh"
    else
        echo "❌ Upload failed. Check SSH connection."
    fi
else
    echo "❌ Build failed. Check for errors above."
fi
