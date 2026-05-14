# Archive File Extractor Service

This is a small Flask app that accepts an archive upload, searches for matching files, including files inside nested archives, and stores the results.

## What it supports

- `POST /extractions`
- `GET /extractions/<job_id>`
- `GET /extractions/<job_id>/results`
- `GET /health`

## Run locally

```bash
pip install -r requirements.txt
python app.py

## To run with Docker 

docker build -t file-extractor .
docker run --rm -p 5000:5000 file-extractor

## Test locally with command below

# Create extraction job

curl -X POST http://127.0.0.1:5000/extractions ^
  -F "archive=@sample.zip" ^
  -F "pattern=*.json"

# Get job status
curl http://127.0.0.1:5000/extractions/<job_id>

# Get Results 

curl http://127.0.0.1:5000/extractions/<job_id>/results

# Health check 

curl http://127.0.0.1:5000/health

