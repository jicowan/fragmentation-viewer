#!/bin/bash

# Quick start script for VPC IP Fragmentation Viewer

echo "🚀 Starting VPC IP Fragmentation Viewer..."
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✅ Created .env file. Please configure AWS credentials if needed."
    echo ""
fi

# Check if user wants to use Docker or local setup
echo "Choose how to run the application:"
echo "1) Docker Compose (recommended - starts everything)"
echo "2) Local development (manual - requires Python & Node.js)"
echo ""
read -p "Enter your choice (1 or 2): " choice

if [ "$choice" = "1" ]; then
    echo ""
    echo "🐳 Starting with Docker Compose..."
    echo ""

    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Error: Docker is not running. Please start Docker and try again."
        exit 1
    fi

    # Start services
    docker-compose up --build

elif [ "$choice" = "2" ]; then
    echo ""
    echo "🛠️  Starting local development servers..."
    echo ""

    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        echo "Setting up Python virtual environment..."
        python3 -m venv venv
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
    else
        source venv/bin/activate
    fi

    # Start Flask backend in background
    echo "Starting Flask backend on http://localhost:5000..."
    python app.py &
    BACKEND_PID=$!

    # Wait a moment for backend to start
    sleep 2

    # Start React frontend
    echo "Starting React frontend on http://localhost:3000..."
    cd frontend

    # Install npm dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo "Installing npm dependencies..."
        npm install
    fi

    # Start React dev server
    npm start

    # Cleanup on exit
    trap "kill $BACKEND_PID" EXIT

else
    echo "Invalid choice. Exiting."
    exit 1
fi
