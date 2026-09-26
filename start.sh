#!/bin/bash

# 1. Start the FastAPI backend in the background on port 8000
echo "Starting FastAPI backend..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &

# Wait a moment to ensure backend starts
sleep 3

# 2. Start the Streamlit frontend on port 7860 (which Hugging Face exposes publicly)
echo "Starting Streamlit frontend..."
cd frontend
streamlit run app.py --server.port 7860 --server.address 0.0.0.0
