from flask import Flask
from config import Config
from extensions import mail, init_firebase, socketio
from database import init_db_schema

# Import blueprints
from routes.auth import auth_bp
from routes.food_items import food_items_bp
from routes.orders import orders_bp
from routes.public import public_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    # Initialize extensions
    mail.init_app(app)
    socketio.init_app(app)
    init_firebase()

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(food_items_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(public_bp)

    # Fix for running behind a reverse proxy (like Render)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    return app

app = create_app()

if __name__ == "__main__":
    init_db_schema()
    socketio.run(app, debug=True)
