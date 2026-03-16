#!/bin/bash

# ITBP RTC Grain Shop Management - Setup Script

echo "🌾 ITBP RTC Grain Shop Management System - Setup"
echo "=================================================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env file with your Supabase credentials"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Configure your .env file with Supabase credentials"
echo "2. Run the database schema in Supabase SQL Editor"
echo "3. Start the API: python api/app.py"
echo "4. Start the Frontend: streamlit run frontend/app.py"
echo ""
echo "Default login: admin@itbp.gov.in / admin123"
