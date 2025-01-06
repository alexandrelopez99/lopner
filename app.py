import json
import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
from dotenv import load_dotenv
from supabase import create_client, Client

# Load secret .env data
load_dotenv() 

# Supabase setup
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
bucket_name = "uploads"

# Load date_ideas from JSON file
def load_date_ideas():
    file_name = "date_ideas.json"
    response = supabase.storage.from_(bucket_name).download(file_name).decode('utf-8')
    return json.loads(response)
date_ideas = load_date_ideas()

# Update JSON file with date_ideas
def save_date_ideas():
    json_data = json.dumps(date_ideas, indent=4).encode("utf-8")
    response = supabase.storage.from_(bucket_name).update(
            path="date_ideas.json",
            file=json_data
            )

# Initialise app
app = Flask(__name__)

# App authentication
app.secret_key = os.getenv("APP_SECRET_KEY")

# Login page
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        entered_passcode = request.form["passcode"]
        if entered_passcode == os.getenv("PASSCODE"):
            session["authenticated"] = True
            return redirect(url_for("index"))
        else:
            flash("Incorrect passcode. Please try again.", "danger")
    return render_template("login.html")

# Logout route
@app.route("/logout")
def logout():
    session.pop("authenticated", None)  # Remove authentication from session
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# Protect routes
@app.route("/")
@login_required
def index():
    return render_template("index.html", date_ideas=date_ideas)

# Date picker
@app.route("/pick_date", methods=["POST"])
def pick_date():
    selected_dates = request.form.getlist("date")
    if not selected_dates:
        return redirect(url_for("index"))
    chosen_date = random.choice(selected_dates)
    return redirect(url_for("date_page", date_id=chosen_date))

# Date viewer
@app.route("/<date_id>")
def date_page(date_id):
    date_info = date_ideas.get(date_id)
    if date_info == None:
        return redirect("/")
    return render_template("date.html", date_id=date_id, date_info=date_info)

# Date editor
@app.route("/<date_id>/edit")
def edit_date(date_id):
    date_info = date_ideas.get(date_id)

    return render_template(
        "date_edit.html",
        date_info=date_info,
        date_id=date_id
    )

# Save date edits
@app.route("/<date_id>/save", methods=["POST"])
def save_date(date_id):

    # Request form data
    new_title = request.form["title"]
    new_description = request.form["description"]
    new_logbook = request.form["logbook"]
    new_photo = request.files["photo"]

    # Handle file upload
    if new_photo and new_photo.filename:

        # Rename photo
        extension = new_photo.filename.rsplit('.', 1)[1]
        photo_filename = f"date{date_id}.{extension}"

        # Update the date idea
        date_ideas[date_id]["photo"] = photo_filename

        # Upload photo
        response = supabase.storage.from_(bucket_name).upload(
            path=photo_filename,
            file=new_photo.read(),
            file_options={"content-type": new_photo.mimetype, "upsert": "true"}
            )
        
    # Update the date idea
    date_ideas[date_id]["title"] = new_title
    date_ideas[date_id]["description"] = new_description
    date_ideas[date_id]["logbook"] = new_logbook
    save_date_ideas()

    # View date page when done
    return redirect(url_for("date_page", date_id=date_id))

# Delete date
@app.route("/<date_id>/delete", methods=["POST"])
def delete_date(date_id):
    del date_ideas[date_id]
    save_date_ideas()
    return redirect(url_for("index"))

# Add new date
@app.route("/add_date", methods=["POST","GET"])
def add_date():

    # Create date with unique id
    new_id = str(max(int(id) for id in date_ideas.keys()) + 1)
    date_ideas[new_id] = {
        "title": "New Date",
    }
    save_date_ideas() 

    # Redirect editing newly created date
    return redirect(url_for("edit_date", date_id=new_id))

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    response = supabase.storage.from_(bucket_name).create_signed_url(
        path=filename,
        expires_in=3600
    )
    return redirect(response['signedURL'])

# Main function
if __name__ == "__main__":
    app.run(debug=True)
