from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import joblib
from datetime import datetime
import os

# --- Initialization ---
app = Flask("complaint-classifier")
app.config['SECRET_KEY'] = os.urandom(24) # Necessary for session management and flash messages
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///complaints.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirect to /login if user is not authenticated

# --- Models ---
# Hugging Face and Label Encoder
HF_MODEL_ID = "Jomsky/brgy-complaint-classifier"
LOCAL_LABEL_ENCODER = "ml_model/saved_model/label_encoder.pkl"

# Check if model files exist before loading
try:
    model = AutoModelForSequenceClassification.from_pretrained(HF_MODEL_ID)
    tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_ID)
    label_encoder = joblib.load(LOCAL_LABEL_ENCODER)
    model.eval() # Set model to evaluation mode
except Exception as e:
    print(f"Error loading ML model: {e}")
    model = None # Set model to None if loading fails

# --- Database Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Pending') # New status field
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# --- Flask-Login Configuration ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ML Classification Function ---
def classify_complaint(text):
    """Classifies the complaint text using the loaded model."""
    if not model:
        return "Classification Unavailable"
        
    inputs = tokenizer(
        text,
        truncation=True,
        padding=True,
        return_tensors="pt"
    ).to(model.device)

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        predicted_class_id = torch.argmax(logits, dim=-1).item()

    predicted_label = label_encoder.inverse_transform([predicted_class_id])[0]
    return predicted_label

# --- Routes ---
@app.route("/")
def index():
    return redirect(url_for('complaint'))

@app.route("/complaint", methods=["GET", "POST"])
def complaint():
    prediction = None
    text_input = ""
    if request.method == "POST":
        text_input = request.form.get("complaint", "")
        
        # Requirement 1: Validate word count
        if len(text_input.split()) < 5:
            flash("Please enter a complaint with at least 5 words.", "error")
        else:
            prediction = classify_complaint(text_input)
            new_entry = Complaint(text=text_input, category=prediction)
            db.session.add(new_entry)
            db.session.commit()
            flash(f"Your complaint has been submitted! Category: {prediction}", "success")
            return redirect(url_for('complaint')) # Redirect to clear the form

    return render_template('complaint.html', prediction=prediction, text=text_input)

@app.route("/records")
@login_required # Requirement 2: Protect this route
def records():
    all_complaints = Complaint.query.order_by(Complaint.timestamp.desc()).all()
    return render_template("complaint_db.html", complaints=all_complaints)

@app.route("/update_status/<int:complaint_id>", methods=["POST"])
@login_required # Requirement 3: Route to update status
def update_status(complaint_id):
    complaint_to_update = Complaint.query.get_or_404(complaint_id)
    new_status = request.form.get("status")
    if new_status in ['Pending', 'In Progress', 'Resolved']:
        complaint_to_update.status = new_status
        db.session.commit()
        flash(f"Complaint #{complaint_id} status updated to '{new_status}'.", "info")
    else:
        flash("Invalid status selected.", "error")
    return redirect(url_for('records'))

# --- Authentication Routes ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('records')) # Redirect if already logged in
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('records'))
        else:
            flash("Invalid username or password.", "error")
            
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- API and Test Routes ---
@app.route("/predict", methods=["POST"])
def predict():
    data = request.json
    text = data.get("complaint", "")
    if not text:
        return jsonify({"error": "Missing 'complaint' text"}), 400
    prediction = classify_complaint(text)
    return jsonify({"category": prediction})

@app.route("/ping", methods=["GET"])
def ping():
    return "pong"

# --- Main Execution ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all() # Ensure tables are created
    app.run(debug=True, host="0.0.0.0", port=9696)
