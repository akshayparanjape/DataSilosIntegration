# 🧠 Improved ETL Agent

This project contains a privacy-aware, Dockerized ETL (Extract, Transform, Load) pipeline designed for preprocessing industrial datasets like SECOM. It supports outlier removal, imputation, normalization, and optional PII detection using Gemini + Presidio.

---

## 📆 Features

* 📊 Cleans and imputes missing sensor data
* 🔍 Optional PII detection using Microsoft Presidio
* 🔐 Gemini API integration for text redaction
* 🐳 Dockerized for consistency and easy deployment
* ✅ Works with SECOM and other tabular time-series datasets

---

## ⚛️ Step-by-Step Setup

### ♻️ 1. Clone the Repository

```bash
git clone https://github.com/akshayparanjape/DataSilosIntegration.git
cd DataSilosIntegration
```

---

### 📁 2. Add Your Data Files

Place your CSV files in the following directory:

```bash
DataSilosIntegration/deploy/data/
```

Example:

```bash
cp /path/to/secom_data.csv ./deploy/data/
cp /path/to/secom_labels.csv ./deploy/data/
```

---

### 🔑 3. Add Your Gemini API Key

1. Copy the sample `.env` file:

```bash
cp deploy/.env.example deploy/.env
```

2. Edit the `.env` file and add your Gemini API key:

```env
GOOGLE_API_KEY=your_api_key_here
```

---

### 🐳 4. Install Docker & Docker Compose

If you don’t have them installed:

* [Install Docker](https://docs.docker.com/get-docker/)
* [Install Docker Compose](https://docs.docker.com/compose/install/)

---

### ⚡ 5. Run the Setup Script

```bash
cd deploy
sudo ./deploy.sh
```

This script will:

* Create required folders (`data/`, `output/`, `logs/`)
* Ensure `.env` is in place
* Pull the latest Docker image

---

### ▶️ 6. Launch the ETL Agent

Run the agent:

```bash
sudo docker-compose up etl-agent-interactive
```

Once inside the container:


Cleaned output will be saved to:

```
deploy/output/
```

---

## 📁 Folder Structure

```bash
DataSilosIntegration/
├── improved_etl.py          # Main ETL logic
├── Dockerfile               # Container build file
├── requirements.txt         # Python dependencies
├── deploy/
│   ├── deploy.sh            # Bootstrap script
│   ├── docker-compose.yml   # Compose setup
│   ├── .env.example         # Gemini key template
│   ├── data/                # Place CSV input files here
│   ├── output/              # Output will be saved here
│   └── logs/                # Optional logging
```

---

## 🧰 Optional: Run with Docker Only

You can skip Docker Compose and run the agent directly:


## 📋 Requirements

* Docker
* Docker Compose
* Gemini API Key: [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)

---

## 🧠 Credits

Built with 🍺 by [iampruh887](https://github.com/iampruh887)
