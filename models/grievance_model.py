"""Demonstration ML classifier. Replace demo examples with anonymized labeled data."""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

TRAINING = [
    ("teacher did not upload internal marks and attendance", "Academic"),
    ("class timetable has a clash and course registration issue", "Academic"),
    ("need clarification about assignment and lecture material", "Academic"),
    ("exam hall ticket not generated and exam schedule issue", "Examination"),
    ("wrong marks in semester result and revaluation request", "Examination"),
    ("exam fee payment not reflected in portal", "Examination"),
    ("hostel room has no water and bathroom is dirty", "Hostel"),
    ("mess food quality is poor and hostel maintenance needed", "Hostel"),
    ("hostel room allocation and warden complaint", "Hostel"),
    ("classroom projector is broken and lights are not working", "Infrastructure"),
    ("college road is damaged and drinking water facility missing", "Infrastructure"),
    ("library chairs and building maintenance problem", "Infrastructure"),
    ("student portal login fails and website server is down", "Technical"),
    ("wifi internet is not working in campus", "Technical"),
    ("computer lab system crashes and software installation issue", "Technical"),
    ("scholarship application and fee reimbursement delay", "Administrative"),
    ("certificate issue and student records correction", "Administrative"),
    ("office staff are not responding to document request", "Administrative"),
    ("complaint does not fit any other category", "Other"),
    ("request for general information and help", "Other"),
]
_pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1,2), max_features=500)),
    ("classifier", LogisticRegression(max_iter=1000, random_state=42))
])
_pipeline.fit([x[0] for x in TRAINING], [x[1] for x in TRAINING])

def classify(text):
    probabilities = _pipeline.predict_proba([text])[0]
    labels = _pipeline.classes_
    index = int(probabilities.argmax())
    return str(labels[index]), float(probabilities[index])

def predict_priority(text):
    """Transparent demo heuristic; admin can override."""
    text = (text or "").lower()
    critical_terms = ["fire", "electrocution", "threat", "unsafe", "violence", "emergency", "suicide"]
    high_terms = ["urgent", "harassment", "broken", "not working", "unsafe", "exam tomorrow", "water leak"]
    if any(term in text for term in critical_terms):
        return "Critical"
    if any(term in text for term in high_terms):
        return "High"
    if len(text.split()) > 35:
        return "Medium"
    return "Low"

def department_for(category):
    return {
        "Academic": "Academic Department",
        "Administrative": "Administrative Office",
        "Infrastructure": "Infrastructure Department",
        "Technical": "IT Department",
        "Examination": "Examination Branch",
        "Hostel": "Hostel Administration",
        "Other": "General Grievance Cell",
    }.get(category, "General Grievance Cell")
