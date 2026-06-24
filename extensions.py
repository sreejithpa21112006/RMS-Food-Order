from flask_mail import Mail
from flask_socketio import SocketIO
import firebase_admin
from firebase_admin import credentials, auth
import os

mail = Mail()
socketio = SocketIO(cors_allowed_origins="*")

def init_firebase():
    try:
        if not firebase_admin._apps:
            firebase_env = os.environ.get('FIREBASE_CREDENTIALS')
            if firebase_env:
                import json
                cred_dict = json.loads(firebase_env)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                print("Firebase Admin initialized from environment variable.")
            else:
                cert_path = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
                if os.path.exists(cert_path):
                    cred = credentials.Certificate(cert_path)
                    firebase_admin.initialize_app(cred)
                    print("Firebase Admin initialized from local file.")
                else:
                    print("WARNING: Firebase credentials not found! Set FIREBASE_CREDENTIALS env var or add serviceAccountKey.json")
    except Exception as e:
        print("WARNING: Firebase Admin initialization failed.")
        print("Error:", e)
