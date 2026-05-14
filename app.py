import fnmatch
import os
import shutil
import tarfile
import tempfile
import threading
import zipfile
from datetime import datetime

from flask import Flask, request

from db import db, DATABASE_URL
from models import ExtractionJob, ExtractedFile


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

MAX_NESTED_DEPTH = 5


def is_archive_file(file_name):
    lower_name = file_name.lower()
    return (
        lower_name.endswith(".zip")
        or lower_name.endswith(".tar")
        or lower_name.endswith(".tar.gz")
        or lower_name.endswith(".tgz")
    )


def file_matches_pattern(file_path, pattern):
    clean_path = file_path.replace("\\", "/")
    file_name = clean_path.split("/")[-1]

    return fnmatch.fnmatch(clean_path, pattern) or fnmatch.fnmatch(file_name, pattern)


def save_temp_file(source_file, temp_dir):
    with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir) as temp_file:
        shutil.copyfileobj(source_file, temp_file)
        return temp_file.name


def save_match(job_id, full_path, file_size, nesting_depth, source_archive_name):
    result = ExtractedFile(
        job_id=job_id,
        full_path=full_path.replace("\\", "/"),
        file_name=full_path.replace("\\", "/").split("/")[-1],
        file_size=file_size,
        nesting_depth=nesting_depth,
        source_archive_name=source_archive_name,
    )
    db.session.add(result)


def scan_zip_file(file_path, pattern, job_id, chain_path, depth, root_archive_name, temp_dir):
    match_count = 0

    with zipfile.ZipFile(file_path, "r") as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue

            item_name = item.filename.replace("\\", "/").strip("/")
            current_path = f"{chain_path}/{item_name}"

            if file_matches_pattern(current_path, pattern):
                save_match(
                    job_id=job_id,
                    full_path=current_path,
                    file_size=item.file_size,
                    nesting_depth=depth,
                    source_archive_name=root_archive_name,
                )
                match_count += 1

            if is_archive_file(item_name):
                if depth + 1 > MAX_NESTED_DEPTH:
                    raise ValueError("Archive nesting is too deep")

                with archive.open(item) as source_file:
                    nested_temp_path = save_temp_file(source_file, temp_dir)

                try:
                    match_count += scan_archive(
                        nested_temp_path,
                        pattern,
                        job_id,
                        current_path,
                        depth + 1,
                        root_archive_name,
                        temp_dir,
                    )
                finally:
                    if os.path.exists(nested_temp_path):
                        os.remove(nested_temp_path)

    return match_count


def scan_tar_file(file_path, pattern, job_id, chain_path, depth, root_archive_name, temp_dir):
    match_count = 0

    with tarfile.open(file_path, "r:*") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue

            item_name = member.name.replace("\\", "/").strip("/")
            current_path = f"{chain_path}/{item_name}"

            if file_matches_pattern(current_path, pattern):
                save_match(
                    job_id=job_id,
                    full_path=current_path,
                    file_size=member.size,
                    nesting_depth=depth,
                    source_archive_name=root_archive_name,
                )
                match_count += 1

            if is_archive_file(item_name):
                if depth + 1 > MAX_NESTED_DEPTH:
                    raise ValueError("Archive nesting is too deep")

                source_file = archive.extractfile(member)
                if source_file is None:
                    continue

                with source_file:
                    nested_temp_path = save_temp_file(source_file, temp_dir)

                try:
                    match_count += scan_archive(
                        nested_temp_path,
                        pattern,
                        job_id,
                        current_path,
                        depth + 1,
                        root_archive_name,
                        temp_dir,
                    )
                finally:
                    if os.path.exists(nested_temp_path):
                        os.remove(nested_temp_path)

    return match_count


def scan_archive(file_path, pattern, job_id, chain_path, depth, root_archive_name, temp_dir):
    if zipfile.is_zipfile(file_path):
        return scan_zip_file(
            file_path,
            pattern,
            job_id,
            chain_path,
            depth,
            root_archive_name,
            temp_dir,
        )

    if tarfile.is_tarfile(file_path):
        return scan_tar_file(
            file_path,
            pattern,
            job_id,
            chain_path,
            depth,
            root_archive_name,
            temp_dir,
        )

    raise ValueError("Unsupported archive format")


def run_extraction_job(job_id, archive_path, archive_name, pattern, temp_dir):
    with app.app_context():
        job = db.session.get(ExtractionJob, job_id)
        if job is None:
            return

        try:
            job.status = "running"
            db.session.commit()

            total_matches = scan_archive(
                file_path=archive_path,
                pattern=pattern,
                job_id=job_id,
                chain_path=archive_name,
                depth=0,
                root_archive_name=archive_name,
                temp_dir=temp_dir,
            )

            job.total_matches = total_matches
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            db.session.commit()

        except Exception as error:
            db.session.rollback()

            job = db.session.get(ExtractionJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(error)
                job.completed_at = datetime.utcnow()
                db.session.commit()

        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

# POST /extractions Submit a new extraction job. 
# •	Accepts the archive as multipart/form-data upload or a URL/path reference — your choice, justify in the README 
# •	Body parameters: pattern (glob, required) 
# •	Response: 202 Accepted with a job_id 


@app.route("/extractions", methods=["POST"])
def create_extraction():
    uploaded_file = request.files.get("archive")
    pattern = request.form.get("pattern", "").strip()

    if uploaded_file is None or uploaded_file.filename == "":
        return {"error": "archive file is required"}, 400

    if pattern == "":
        return {"error": "pattern is required"}, 400

    temp_dir = tempfile.mkdtemp(prefix="extract_")
    archive_name = os.path.basename(uploaded_file.filename)

    if archive_name == "":
        archive_name = "uploaded_archive.zip"

    archive_path = os.path.join(temp_dir, archive_name)
    uploaded_file.save(archive_path)

    job = ExtractionJob(
        status="pending"
    )
    db.session.add(job)
    db.session.commit()

    worker = threading.Thread(
        target=run_extraction_job,
        args=(job.id, archive_path, archive_name, pattern, temp_dir),
        daemon=True,
    )
    worker.start()

    return {
        "job_id": job.id,
        "status": job.status,
        "message": "job started",
    }, 202

# GET /extractions/{job_id} Get job status (pending / running / completed / failed) and summary (number of matches, error if any). 


@app.route("/extractions/<job_id>", methods=["GET"])
def get_extraction(job_id):
    job = db.session.get(ExtractionJob, job_id)

    if job is None:
        return {"error": "job not found"}, 404

    return job.to_dict(), 200

# GET /extractions/{job_id}/results List matched files for a job, with pagination.  

@app.route("/extractions/<job_id>/results", methods=["GET"])
def get_results(job_id):
    job = db.session.get(ExtractionJob, job_id)

    if job is None:
        return {"error": "job not found"}, 404

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    if page < 1 or per_page < 1:
        return {"error": "page and per_page must be positive"}, 400

    query = ExtractedFile.query.filter_by(job_id=job_id).order_by(ExtractedFile.id)
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "job_id": job_id,
        "status": job.status,
        "page": page,
        "per_page": per_page,
        "total": total,
        "results": [item.to_dict() for item in items],
    }, 200

# GET /health Liveness/readiness endpoint. 

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)