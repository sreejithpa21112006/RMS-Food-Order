from flask_mail import Mail
import firebase_admin
from firebase_admin import credentials, auth
import os

mail = Mail()

def init_firebase():
    try:
        if not firebase_admin._apps:
            cert_path = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
            if os.path.exists(cert_path):
                cred = credentials.Certificate(cert_path)
                firebase_admin.initialize_app(cred)
            else:
                print(f"WARNING: Firebase credentials not found at {cert_path}")
    except Exception as e:
        print("WARNING: Firebase Admin initialization failed.")
        print("Error:", e)
