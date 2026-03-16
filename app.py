import os
import bcrypt
import PyPDF2
from datetime import datetime
from bson.objectid import ObjectId
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file,
    abort
)
from flask_mail import Mail, Message
from pymongo import MongoClient
from config import Config
from services.ml_service import evaluate_resume


# =====================================
# APP INITIALIZATION
# =====================================
app = Flask(__name__)
app.config.from_object(Config)

# MongoDB Setup
client = MongoClient(app.config["MONGO_URI"])
db = client[app.config["DATABASE_NAME"]]

users = db["users"]
jobs = db["jobs"]
applications = db["applications"]

# Mail Setup
mail = Mail(app)

# Ensure uploads folder exists
if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])


# =====================================
# AUTH DECORATOR
# =====================================
def login_required(role=None):
    def wrapper(func):
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))

            if role and session.get("role") != role:
                return "Access Denied"

            return func(*args, **kwargs)

        decorated.__name__ = func.__name__
        return decorated
    return wrapper


# =====================================
# HOME
# =====================================
@app.route("/")
def home():
    return redirect(url_for("login"))


# =====================================
# REGISTER
# =====================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        existing_user = users.find_one({"username": request.form["username"]})
        if existing_user:
            return "Username already exists"

        hashed_pw = bcrypt.hashpw(
            request.form["password"].encode("utf-8"),
            bcrypt.gensalt()
        )

        user = {
            "username": request.form["username"],
            "email": request.form["email"],
            "password": hashed_pw,
            "role": request.form["role"],
            "created_at": datetime.utcnow()
        }

        users.insert_one(user)
        return redirect(url_for("login"))

    return render_template("register.html")


# =====================================
# LOGIN
# =====================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        user = users.find_one({"username": request.form["username"]})

        if user and bcrypt.checkpw(
            request.form["password"].encode("utf-8"),
            user["password"]
        ):
            session["user_id"] = str(user["_id"])
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("view_jobs"))

        return "Invalid Credentials"

    return render_template("login.html")


# =====================================
# LOGOUT
# =====================================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =====================================
# ADMIN DASHBOARD
# =====================================
@app.route("/admin_dashboard")
@login_required(role="admin")
def admin_dashboard():

    all_jobs = list(jobs.find())
    all_applications = list(applications.find())

    total_jobs = len(all_jobs)
    total_applications = len(all_applications)
    total_shortlisted = len(
        [a for a in all_applications if a.get("status") == "Shortlisted"]
    )

    return render_template(
        "admin_dashboard.html",
        jobs=all_jobs,
        applications=all_applications,
        total_jobs=total_jobs,
        total_applications=total_applications,
        total_shortlisted=total_shortlisted
    )


# =====================================
# POST JOB
# =====================================
@app.route("/post_job", methods=["POST"])
@login_required(role="admin")
def post_job():

    job = {
        "title": request.form["title"],
        "description": request.form["description"],
        "keywords": request.form["keywords"],
        "posted_by": session["user_id"],
        "created_at": datetime.utcnow()
    }

    jobs.insert_one(job)
    return redirect(url_for("admin_dashboard"))


# =====================================
# DELETE JOB
# =====================================
@app.route("/delete_job/<job_id>", methods=["POST"])
@login_required(role="admin")
def delete_job(job_id):

    # Delete job
    jobs.delete_one({"_id": ObjectId(job_id)})

    # Delete all applications for that job
    applications.delete_many({"job_id": job_id})

    return redirect(url_for("admin_dashboard"))


# =====================================
# VIEW APPLICANTS FOR JOB
# =====================================

@app.route("/view_applicants/<job_id>")
@login_required(role="admin")
def view_applicants(job_id):

    job = jobs.find_one({"_id": ObjectId(job_id)})

    job_applications = list(applications.find({"job_id": str(job_id)}))

    # 🔥 Sort by score descending
    job_applications.sort(key=lambda x: x.get("score", 0), reverse=True)

    enriched_apps = []

    for index, app in enumerate(job_applications):
        user = users.find_one({"_id": ObjectId(app["user_id"])})

        enriched_apps.append({
            "rank": index + 1,
            "name": user["username"],
            "email": user["email"],
            "score": app.get("score", 0),
            "status": app.get("status"),
            "top10": True if index < 10 else False,
            "resume_id": app["_id"]
        })

    return render_template(
        "view_applicants.html",
        job=job,
        applications=enriched_apps
    )


# =====================================
# DOWNLOAD RESUME
# =====================================
@app.route("/download_resume/<app_id>")
@login_required(role="admin")
def download_resume(app_id):

    application = applications.find_one({"_id": ObjectId(app_id)})

    if not application:
        abort(404)

    return send_file(application["resume_path"], as_attachment=True)


# =====================================
# SHORTLISTED CANDIDATES
# =====================================
@app.route("/shortlisted")
@login_required(role="admin")
def shortlisted():

    shortlisted_apps = list(applications.find({"status": "Shortlisted"}))

    enriched_apps = []

    for app in shortlisted_apps:

        user = users.find_one({"_id": ObjectId(app["user_id"])}) if app.get("user_id") else None
        job = jobs.find_one({"_id": ObjectId(app["job_id"])}) if app.get("job_id") else None

        enriched_apps.append({
            "name": user["username"] if user else "Unknown",
            "email": user["email"] if user else "Unknown",
            "job_title": job["title"] if job else "Unknown",
            "score": app.get("score", 0),
            "resume_id": app["_id"]
        })

    return render_template(
        "shortlisted.html",
        applications=enriched_apps
    )


# =====================================
# CANDIDATE VIEW JOBS
# =====================================

# @app.route("/view_jobs")
# @login_required(role="candidate")
# def view_jobs():

#     search_query = request.args.get("search", "").lower()
#     skill_filter = request.args.get("skill", "").lower()

#     all_jobs = list(jobs.find())

#     enriched_jobs = []

#     for job in all_jobs:

#         job_id = str(job["_id"])

#         # Check if already applied
#         application = applications.find_one({
#             "user_id": session["user_id"],
#             "job_id": job_id
#         })

#         already_applied = True if application else False
#         score = application.get("score") if application else None

#         # Search filter
#         if search_query and search_query not in job["title"].lower():
#             continue

#         # Skill filter
#         if skill_filter and skill_filter not in job["keywords"].lower():
#             continue

#         enriched_jobs.append({
#             "id": job_id,
#             "title": job["title"],
#             "description": job["description"],
#             "keywords": job["keywords"],
#             "already_applied": already_applied,
#             "score": score
#         })

#         all_jobs = list(jobs.find({}))  # explicitly empty filter

#     return render_template("view_jobs.html", jobs=all_jobs)


@app.route("/view_jobs")
@login_required(role="candidate")
def view_jobs():

    search_query = request.args.get("search", "").lower()
    skill_filter = request.args.get("skill", "").lower()

    all_jobs = list(jobs.find())

    filtered_jobs = []

    for job in all_jobs:

        title = job.get("title", "").lower()
        keywords = job.get("keywords", "").lower()

        if search_query and search_query not in title:
            continue

        if skill_filter and skill_filter not in keywords:
            continue

        # check if already applied
        existing = applications.find_one({
            "user_id": session["user_id"],
            "job_id": job["_id"]
        })

        job["already_applied"] = True if existing else False

        filtered_jobs.append(job)

    return render_template("view_jobs.html", jobs=filtered_jobs)

# =====================================
# PDF TEXT EXTRACTION
# =====================================
def extract_text_from_pdf(path):
    text = ""
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                if page.extract_text():
                    text += page.extract_text()
    except Exception as e:
        print("PDF Extraction Error:", e)
    return text


# =====================================
# APPLY FOR JOB + AI EVALUATION
# =====================================
@app.route("/apply/<job_id>", methods=["POST"])
@login_required(role="candidate")

def apply(job_id):

    existing = applications.find_one({
        "user_id": session["user_id"],
        "job_id": ObjectId(job_id)
    })

    if existing:
        return redirect(url_for("view_jobs"))

    file = request.files["resume"]

    if not file:
        return redirect(url_for("view_jobs"))

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    job = jobs.find_one({"_id": ObjectId(job_id)})
    resume_text = extract_text_from_pdf(filepath)

    job_text = job["description"] + " " + job["keywords"]

    ai_result = evaluate_resume(job_text, resume_text)

    score = ai_result["score"]
    matched_skills = ai_result["matched_skills"]
    missing_skills = ai_result["missing_skills"]

    threshold = 40
    status = "Shortlisted" if score >= threshold else "Rejected"

    application = {
        "user_id": session["user_id"],
        "job_id": ObjectId(job_id),
        "resume_path": filepath,
        "score": score,
        "status": status,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "applied_at": datetime.utcnow()
    }

    applications.insert_one(application)

    # ✅ Send Mail
    user = users.find_one({"_id": ObjectId(session["user_id"])})

    if status == "Shortlisted":
        send_shortlist_email(user["email"], user["username"], score)
    else:
        send_rejection_email(user["email"], user["username"], score)

    return redirect(url_for("my_applications"))




# =====================================
# MY APPLICATIONS (CANDIDATE)
# =====================================
@app.route("/my_applications")
@login_required(role="candidate")
def my_applications():

    my_apps = list(applications.find({"user_id": session["user_id"]}))
    final_apps = []

    for app in my_apps:

        job_id = app.get("job_id")

        # Handle both string and ObjectId types
        try:
            if isinstance(job_id, str):
                job = jobs.find_one({"_id": ObjectId(job_id)})
            else:
                job = jobs.find_one({"_id": job_id})
        except:
            job = None

        if job:
            final_apps.append({
                "title": job.get("title", "Unknown Job"),
                "status": app.get("status", "Under Review"),
                "applied_at": app.get("applied_at")
            })

    return render_template("my_applications.html", applications=final_apps)



# =====================================
# EMAIL FUNCTIONS
# =====================================
def send_shortlist_email(candidate_email, candidate_name, score):
    msg = Message(
        subject="🎉 Congratulations! You Are Shortlisted",
        recipients=[candidate_email]
    )

    msg.body = f"""
Dear {candidate_name},

Congratulations!

Your resume scored {score}% and you have been shortlisted.

Our HR team will contact you soon.

Best Regards,
Recruitment Team
"""

    mail.send(msg)


def send_rejection_email(candidate_email, candidate_name, score):
    msg = Message(
        subject="Application Update",
        recipients=[candidate_email]
    )

    msg.body = f"""
Dear {candidate_name},

Thank you for applying.

After reviewing your profile, we will not proceed further at this time.

Best Regards,
Recruitment Team
"""

    mail.send(msg)
    
# =====================================
# RUN SERVER
# =====================================
if __name__ == "__main__":
    app.run(debug=True)