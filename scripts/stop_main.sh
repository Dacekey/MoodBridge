#!/usr/bin/env bash

echo "Stopping MoodBridge backend + frontend..."

pkill -f "uvicorn app.main:app" || true
pkill -f "vite" || true
pkill -f "npm run dev" || true
pkill -f "node.*vite" || true

echo "Stopped."
