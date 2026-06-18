import pytest
from app import app
from db import db
from pathlib import Path
import time
from models.extraction_job import ExtractionJob
from models.extracted_file import ExtractedFile

#  make a function to push archive 
def push_archive():
    file_path = Path(__file__).parent / "testarchives" / "archive1.zip"
    with app.test_client() as client:
        response = client.post(
            "/extractions",
            data={
                "file": (open(file_path, "rb"), file_path.name),
                "pattern": "**/*.txt"
            },
            content_type="multipart/form-data"
        )
    return response

#  function to just wait for the async job to complete and return the payload
def wait_for_job_completion(job_id, timeout=5):
    deadline = time.time() + timeout
    with app.test_client() as client:
        while time.time() < deadline:
            response = client.get(f"/extractions/{job_id}")
            payload = response.get_json()
            if payload["status"] in {"completed", "failed"}:
                return payload
            time.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not complete within {timeout} seconds.")

# function to truncate tables after test
def clear_database():
    with app.app_context():
        db.session.query(ExtractedFile).delete()
        db.session.query(ExtractionJob).delete()
        db.session.commit()

#  Testcase for uploading the archive present in tests/testarchives/archive1.zip with pattern **/*.txt
# Expected an output with job_id

def test_create_extraction_job():
    with app.test_client() as client:
        response = push_archive()
        assert response.status_code == 202
        assert "job_id" in response.get_json()
        wait_for_job_completion(response.get_json()["job_id"])
    clear_database()

#  after the first testcase runs check for file match in extractedfile table, there should be 1 match
def test_extracted_file_entry():
    with app.app_context():
        response = push_archive()
        wait_for_job_completion(response.get_json()["job_id"])
        extraction_job = ExtractionJob.query.first()
        assert extraction_job is not None, "No extraction job found in the database."
        extracted_files = ExtractedFile.query.filter_by(job_id=extraction_job.id).all()
        assert len(extracted_files) == 1, f"Expected 1 extracted file, found {len(extracted_files)}."
        wait_for_job_completion(response.get_json()["job_id"])
    clear_database()

#  testcase to test the /extractions/<job_id> endpoint, it should return the status of the job and other details
def test_get_extraction_job_status():
    with app.test_client() as client:
        response = push_archive()
        job_id = response.get_json()["job_id"]
        payload = wait_for_job_completion(job_id)
        assert payload["job_id"] == job_id
        assert payload["status"] == "completed"
        assert payload["total_matches"] == 1
        assert payload["completed_at"] is not None
    clear_database()


#  testcase for /extractions/<job_id>/results
def test_get_extraction_job_results():
    with app.test_client() as client:
        response = push_archive()
        job_id = response.get_json()["job_id"]
        wait_for_job_completion(job_id)
        results_response = client.get(f"/extractions/{job_id}/results")

        assert results_response.status_code == 200
        results_payload = results_response.get_json()
        assert len(results_payload["extracted_files"]) == 1
        extracted_file = results_payload["extracted_files"][0]
    clear_database()