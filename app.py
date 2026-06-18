import os
import tarfile
import zipfile
import uuid
import fnmatch
import re
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify

from db import db
from models.extracted_file import ExtractedFile
from models.extraction_job import ExtractionJob
import re
MAX_NESTING_DEPTH = 100  # Define a maximum nesting depth to prevent infinite recursion
# ARCHIVE_EXTENSIONS = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")

app = Flask(__name__)
if os.getenv("DATABASE_URL"):
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///extraction_jobs.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9797, debug=True)

def Identify_archive_type(file_path):
    if zipfile.is_zipfile(file_path):
        return "zip"
    elif tarfile.is_tarfile(file_path):
        return "tar"
    else:
        return None

def extract_archive(file_path, request_id, pattern, max_nesting, nesting_depth, logical_root=""):
    if nesting_depth > max_nesting:
        return jsonify({"message": "Maximum nesting depth reached"}), 200
    try:
        if Identify_archive_type(file_path) == "zip":
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for file in zip_ref.namelist():

                    normalized_file = file.replace("\\", "/")
                    logical_member_path = f"{logical_root}/{normalized_file}" if logical_root else normalized_file

                    zip_ref.extract(file, os.path.dirname(file_path))
                    complete_file_path = os.path.join(os.path.dirname(file_path), file)
                    if Identify_archive_type(complete_file_path):
                        print(f"nested archive file: {complete_file_path}")
                        nested_result = extract_archive(complete_file_path, request_id, pattern, max_nesting, nesting_depth + 1, logical_member_path)
                        if nested_result is not None:
                            return nested_result
                    else:
                        match_path = Path(logical_member_path)
                        if match_path.match(pattern):
                            print(f"matched file: {logical_member_path}")
                            extracted_file_record = ExtractedFile(
                                job_id = request_id,
                                full_path = logical_member_path,
                                file_name = os.path.basename(file),
                                file_size = zip_ref.getinfo(file).file_size,
                                nesting_depth = nesting_depth,
                                source_archive_name = os.path.basename(file_path)
                            )
                            # update the count of total matches in ExtractionJob
                            db.session.add(extracted_file_record)
                            extraction_job = ExtractionJob.query.get(request_id)
                            extraction_job.total_matches += 1
                            extraction_job.status = "running"
                            db.session.add(extraction_job)
                            db.session.commit()
        elif Identify_archive_type(file_path) == "tar":
                with tarfile.open(file_path, 'r') as tar_ref:
                    for member in tar_ref.getmembers():
                        normalized_member_name = member.name.replace("\\", "/")
                        logical_member_path = f"{logical_root}/{normalized_member_name}" if logical_root else normalized_member_name
                        tar_ref.extract(member, os.path.dirname(file_path))
                        complete_file_path = os.path.join(os.path.dirname(file_path), member.name)
                        if Identify_archive_type(complete_file_path):
                            print(f"nested archive file: {complete_file_path}")
                            nested_result = extract_archive(complete_file_path, request_id, pattern, max_nesting, nesting_depth + 1, logical_member_path)
                            if nested_result is not None:
                                return nested_result
                        else:
                            match_path = Path(logical_member_path)
                            if match_path.match(pattern):
                                print(f"matched file: {logical_member_path}")
                                extracted_file_record = ExtractedFile(
                                    job_id = request_id,
                                    full_path = logical_member_path,
                                    file_name = os.path.basename(member.name),
                                    file_size = member.size,
                                    nesting_depth = nesting_depth,
                                    source_archive_name = os.path.basename(file_path)
                                )

                                db.session.add(extracted_file_record)
                                extraction_job = ExtractionJob.query.get(request_id)
                                extraction_job.total_matches += 1
                                extraction_job.status = "running"
                                db.session.add(extraction_job)
                                db.session.commit()
        else:
            extraction_job = ExtractionJob.query.get(request_id)
            extraction_job.status = "failed"
            db.session.add(extraction_job)
            db.session.commit()
            return jsonify({"error": "Unsupported archive format"}), 400
    except zipfile.BadZipFile:
        print(f"Error: {file_path} is not a valid zip file.")
        extraction_job = ExtractionJob.query.get(request_id)
        extraction_job.status = "failed"
        db.session.add(extraction_job)
        db.session.commit()
        return jsonify({"error": f"{file_path} is not a valid zip file."}), 400
    except Exception as e:
        print(f"An error occurred while extracting {file_path}: {e}")
        extraction_job = ExtractionJob.query.get(request_id)
        extraction_job.status = "failed"
        db.session.add(extraction_job)
        db.session.commit()
        return jsonify({"error": "Extraction failed"}), 500
    
    # set status to completed if no errors occurred
    extraction_job = ExtractionJob.query.get(request_id)
    if extraction_job.status != "failed":
        extraction_job.status = "completed"
        extraction_job.completed_at = datetime.utcnow()
        db.session.add(extraction_job)
        db.session.commit()
    return None


""" 
Accepts the archive as multipart/form-data upload or a URL/path reference — 
your choice, justify in the README 
● Body parameters: pattern (glob, required) 
● Response: 202 Accepted with a job_id 
"""
@app.post("/extractions")
def create_extraction_job():

    #  get the file and pattern from the request
    file = request.files.get('archive')
    if not file:
        return jsonify({"error": "No file uploaded"}), 400
    pattern = request.form.get('pattern')
    if not pattern:
        return jsonify({"error": "Pattern is required"}), 400


    # calculate nesting depth based on pattern
    if "**" in pattern:
        max_nesting = MAX_NESTING_DEPTH  # Set to a predefined maximum depth
    else:
        pattern_parts = Path(pattern).parts
        max_nesting = max(0,len(pattern_parts) - 1) # Calculate depth based on pattern parts
    

    #  save the uploaded file to a temporary location
    filename = file.filename
    request_id = str(uuid.uuid4())
    request_temp_dir = os.path.join("temp", request_id)
    os.makedirs(request_temp_dir, exist_ok=True)
    file_path = os.path.join(request_temp_dir, filename)
    file.save(file_path)

    # create entry in ExtractionJob
    extraction_job = ExtractionJob(
        id = request_id,
        status = "pending",
        total_matches = 0,
        submitted_at = datetime.utcnow(),
        completed_at = None
    )
    db.session.add(extraction_job)
    db.session.commit()

    archive_type = Identify_archive_type(file_path)
    if not archive_type:
        return jsonify({"error": "Unsupported archive format"}), 400
    else:
        nesting_depth = 0
        extraction_result = extract_archive(file_path, request_id, pattern, max_nesting, nesting_depth)
        if extraction_result is not None:
            return extraction_result
    return jsonify(
        {
            "job_id": request_id,
            "message": {
                "status": ExtractionJob.query.get(request_id).status,
                "pattern": pattern,
                "nesting_depth": nesting_depth,
                "archive_type": archive_type,
                "total_matches": ExtractionJob.query.get(request_id).total_matches,
                "completed_at": ExtractionJob.query.get(request_id).completed_at.isoformat() if ExtractionJob.query.get(request_id).completed_at else None
            }
        }
    ), 202

@app.get("/extractions/<job_id>")
def get_extraction_job(job_id):
    try:
        extraction_job = ExtractionJob.query.get(job_id)
        if not extraction_job:
            return jsonify({"error": "Job not found"}), 404

        extracted_files = ExtractedFile.query.filter_by(job_id=job_id).all()
        extracted_files_list = [file.to_dict() for file in extracted_files]
    except Exception as e:
        return jsonify({"error": "Failed to retrieve job"}), 500

    return jsonify(
        {
            "job_id": extraction_job.id,
            "status": extraction_job.status,
            "total_matches": extraction_job.total_matches,
            "submitted_at": extraction_job.submitted_at.isoformat() if extraction_job.submitted_at else None,
            "completed_at": extraction_job.completed_at.isoformat() if extraction_job.completed_at else None,
            "extracted_files": extracted_files_list
        }
    ), 200

@app.get("/extractions/<job_id>/results")
def get_extraction_results(job_id):
    #  list the matched files with pagination
    try:
        extraction_job = ExtractionJob.query.get(job_id)
        if not extraction_job:
            return jsonify({"error": "Job not found"}), 404

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        extracted_files_query = ExtractedFile.query.filter_by(job_id=job_id)
        extracted_files_paginated = extracted_files_query.paginate(page=page, per_page=per_page, error_out=False)
        extracted_files_list = [file.to_dict() for file in extracted_files_paginated.items]
    except Exception as e:
        return jsonify({"error": "Failed to retrieve results"}), 500
    return jsonify(
        {
            "extracted_files": extracted_files_list,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_pages": extracted_files_paginated.pages,
                "total_items": extracted_files_paginated.total
            }
        }
    ), 200


@app.get("/health")
def health_check():
    return jsonify({"status": "ok"}), 200

