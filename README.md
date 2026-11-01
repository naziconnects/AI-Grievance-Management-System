# AI-Powered Intelligent Grievance Management and Resolution Prediction System

## Features
- Public landing page, registration, login, grievance submission and public tracking
- User-specific grievance history
- Admin login/dashboard, search/filter, details and status/priority/department updates
- SQLite database with users, admins, grievances and notifications
- TF-IDF + Logistic Regression category classifier trained from a small demonstration dataset
- Transparent priority heuristic and historical median resolution-time estimate
- Upload validation for PDF, PNG, JPG and JPEG

## Setup (Windows / VS Code)
1. Extract the ZIP.
2. Open the extracted `ai_grievance_system_professional` folder in VS Code.
3. Open Terminal (`Terminal > New Terminal`).
4. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again.
5. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
6. Set a secret key and admin credentials (optional but recommended):
   ```powershell
   $env:FLASK_SECRET_KEY="replace-with-a-long-random-secret"
   $env:ADMIN_USERNAME="admin"
   $env:ADMIN_PASSWORD="ChangeThisAdminPassword123!"
   ```
7. Run:
   ```powershell
   python app.py
   ```
8. Open `http://127.0.0.1:5000`

## Default admin
If `ADMIN_USERNAME` and `ADMIN_PASSWORD` are not set, the app creates:
- Username: `admin`
- Password: `Admin@12345`

Change this immediately for any real deployment. This is a local academic demo, not production-ready.

## AI model note
`models/grievance_model.py` trains a TF-IDF + Logistic Regression classifier from an included small demonstration dataset. This demonstrates the ML pipeline; its performance is not validated for real institutional use. Replace the dataset with anonymized, labeled real grievance examples and evaluate using a held-out test set before claiming accuracy.

## Resolution estimate note
The estimated resolution time uses the median resolved duration for the matching category when enough history exists; otherwise it uses a clearly labeled demonstration fallback. It is not a guaranteed deadline.

## Database
The app creates `instance/grievances.db` automatically. Existing database files are not imported or overwritten. To use your old records, back up the old database first and migrate records carefully; schemas may differ.

## Testing
- Register a user, log in, submit a grievance, and save its tracking ID.
- Open Track Grievance and enter the tracking ID.
- Log out, log in as admin, open dashboard and update status/priority/department.
- Log in as the user and verify the grievance history/status.
