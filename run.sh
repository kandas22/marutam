#!/bin/bash

# ITBP RTC Grain Shop Management - Run Script

echo "🌾 Starting ITBP RTC Grain Shop Management System"
echo "=================================================="

# Activate virtual environment
source venv/bin/activate

# Check if running both or specific service
if [ "$1" == "api" ]; then
    echo "🚀 Starting Flask API on port 5001..."
    cd api && python app.py
elif [ "$1" == "frontend" ]; then
    echo "🎨 Starting Streamlit Frontend..."
    streamlit run frontend/app.py --server.port 8501
else
    echo "Usage: ./run.sh [api|frontend]"
    echo ""
    echo "Options:"
    echo "  api       - Start Flask API server"
    echo "  frontend  - Start Streamlit frontend"
    echo ""
    echo "Run both in separate terminals:"
    echo "  Terminal 1: ./run.sh api"
    echo "  Terminal 2: ./run.sh frontend"
fi
