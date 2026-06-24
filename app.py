from flask import Flask
from config import Config
from extensions import mail, init_firebase
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
    mail.init_app(app)
    init_firebase()

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(food_items_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(public_bp)

    return app

app = create_app()

if __name__ == "__main__":
    init_db_schema()
    app.run(debug=True)
