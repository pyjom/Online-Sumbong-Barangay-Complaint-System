
from flask import Flask, request, jsonify, render_template_string, render_template
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import joblib
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


# Initialize Flask
app = Flask("complaint-classifier")

# Initialize DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///complaints.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# Load model and tokenizer
model = AutoModelForSequenceClassification.from_pretrained("saved_model")
tokenizer = AutoTokenizer.from_pretrained("saved_model")
label_encoder = joblib.load("saved_model/label_encoder.pkl")

# Make sure model is in evaluation mode
model.eval()

# Function to classify text
def classify_complaint(text):
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

# Prediction endpoint
@app.route("/predict", methods=["POST"])
def predict():
    data = request.json
    text = data.get("complaint", "")

    if not text:
        return jsonify({"error": "Missing 'complaint' text"}), 400

    prediction = classify_complaint(text)
    return jsonify({"category": prediction})

# Ping test
@app.route("/ping", methods=["GET"])
def ping():
    return "pongpong"


 
@app.route("/complaint", methods=["GET", "POST"])
def complaint():
    if request.method == "POST":
        text = request.form["complaint"]
        prediction = classify_complaint(text)

        # Save to DB
        new_entry = Complaint(text=text, category=prediction)
        db.session.add(new_entry)
        db.session.commit()
        return render_template('complaint.html', prediction = prediction, text=text)

    return render_template('complaint.html', prediction=None, text="")

@app.route("/records", methods=["GET"])

def records():
    all_complaints = Complaint.query.order_by(Complaint.timestamp.desc()).all()
    return render_template("complaint_db.html", complaints=all_complaints)



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=9696)