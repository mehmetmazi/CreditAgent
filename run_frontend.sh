#!/bin/bash

# Quick start script for Credit Analysis Platform

echo "======================================================================"
echo "Credit Analysis Platform - Frontend"
echo "======================================================================"
echo ""

# Check for FMP_API_KEY
if [ -z "$FMP_API_KEY" ]; then
    echo "⚠️  Warning: FMP_API_KEY is not set!"
    echo "   Please set it with: export FMP_API_KEY='your_key_here'"
    echo ""
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✓ FMP_API_KEY is set"
fi

# Check for OPENAI_API_KEY (optional)
if [ -z "$OPENAI_API_KEY" ]; then
    echo "ℹ️  Note: OPENAI_API_KEY is not set (AI memos will be disabled)"
else
    echo "✓ OPENAI_API_KEY is set"
fi

echo ""
echo "Starting Flask server..."
echo "Navigate to: http://127.0.0.1:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo "======================================================================"
echo ""

# Run the Flask app
python app.py
