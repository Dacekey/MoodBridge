# 🎭 MoodBridge

### 🐉 Real-Time Emotion-Aware Conversational AI System

<p align="center">
  <img src="https://img.shields.io/badge/Ubuntu-24.04-E95420?logo=ubuntu&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-WebSocket-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-Frontend-61DAFB?logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?logo=opencv&logoColor=white" />
  <img src="https://img.shields.io/badge/YOLO-Emotion%20Detection-111111" />
  <img src="https://img.shields.io/badge/WebSocket-Realtime-2C3E50" />
  <img src="https://img.shields.io/badge/Vite-Build%20Tool-646CFF?logo=vite&logoColor=white" />
  <img src="https://img.shields.io/badge/Whisper-Speech%20to%20Text-412991" />
  <img src="https://img.shields.io/badge/Edge--TTS-Text%20to%20Speech-0078D4" />
  <img src="https://img.shields.io/badge/Llama%203-Local%20LLM-8E44AD" />
  <img src="https://img.shields.io/badge/Node.js-18-339933?logo=nodedotjs&logoColor=white" />
  <img src="https://img.shields.io/badge/Conda-Environment-44A833?logo=anaconda&logoColor=white" />
  <img src="https://img.shields.io/badge/Architecture-State%20Machine-blue" />
  <img src="https://img.shields.io/badge/Runtime-Realtime-orange" />
  <img src="https://img.shields.io/badge/Status-Stable-brightgreen" />
</p>

------------------------------------------------------------------------

## 🦈 Overview

**MoodBridge** is a real-time multimodal conversational AI system that
integrates:

-   facial emotion detection\
-   realtime speech interaction\
-   large language model reasoning\
-   text-to-speech synthesis

into a unified browser-based conversational experience.

The system is built around a backend-orchestrated runtime with a
deterministic state machine controlling the full conversation lifecycle.

------------------------------------------------------------------------

## 🦅 Vision

MoodBridge represents an early step toward building intelligent systems
capable of understanding human emotional signals through perception and
interaction.

The long-term vision is to develop systems that can:

-   perceive emotional context\
-   interpret user intent\
-   respond naturally in real time\
-   adapt behavior dynamically

Ultimately, the goal is to gradually reduce the boundary between humans
and machines and enable more natural human-computer interaction.

------------------------------------------------------------------------

## 🐅 Frontend UI

<p align="center">
  <img src="images/moodbridge_i1.png" width="100%">
</p>

------------------------------------------------------------------------

## 🐂 ORB Effects

<p align="center">
  
  <img src="images/s2_listening.png" width="30%">
  <img src="images/s1_thinking.png" width="30%">
  <img src="images/s3_waiting.png" width="30%">

</p>

------------------------------------------------------------------------

## 🐎 Project Structure

    moodbridge/
    │
    ├── backend/
    ├── frontend/
    ├── services/
    ├── models/
    ├── demos/
    ├── scripts/
    ├── env/
    ├── docs/
    ├── images/
    └── tools/

------------------------------------------------------------------------

## 🦋 System Requirements

### Hardware

CPU: 4 cores\
RAM: 8 GB\
Microphone: required\
Camera: required\
GPU: optional

### Software

Ubuntu 22.04 / 24.04\
Python 3.10\
Node.js 18+\
Conda\
Git

------------------------------------------------------------------------

## 🐝 Quick Start (Recommended)

This project is designed to be launched using shell scripts for
reproducibility.

### 1. Clone Repository

``` bash
git clone https://github.com/<your-username>/moodbridge.git
cd moodbridge
```

### 2. Create Environment

``` bash
conda env create -f environment.yml
conda activate mood_bridge
```

### 3. Load Environment Variables

``` bash
source env/llm.sh
```

### 4. Run the System

``` bash
./scripts/run_main.sh
```

This script will:

-   start backend runtime\
-   start frontend interface\
-   initialize services

### Stop the System

``` bash
./scripts/stop_main.sh
```

------------------------------------------------------------------------

## Demo Mode

``` bash
./scripts/run_subs.sh
```

------------------------------------------------------------------------

## 🐙 Manual Startup (Advanced)

### Backend

``` bash
cd backend

uvicorn app.main:app \
  --reload \
  --ws-ping-interval 60 \
  --ws-ping-timeout 60 \
  --timeout-keep-alive 120
```

### Frontend

``` bash
cd frontend

npm install
npm run dev
```

------------------------------------------------------------------------

## 🐬 Fully Details

``` bash
docs/MoodBridge_Technical_Report.pdf
```

------------------------------------------------------------------------

## 🦉 Current System Status

System State: Stable\
Interaction Mode: Realtime\
Architecture: Backend-Orchestrated

------------------------------------------------------------------------

## 🐕 Author

**Dacekey**\
AI-Robotics Engineering\
Faculty of Artificial Intelligence | FPT University
