from flask import Flask
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Mongo setup
from mongo import mongo                # from first code
from database.mongo import init_db      # from second code

# Blueprints
from routes.user_routes import user_bp
from routes.auth_routes import auth_bp
from routes.pricing_routes import pricing_bp

from routes.warehouse_routes import warehouse_bp


def create_app():
    app = Flask(__name__)

    # Configuration
    app.config["MONGO_URI"] = os.getenv(
        "MONGO_URI", "mongodb://localhost:27017/ewaste_db"
    )
    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY", "dev_secret"
    )

    # Initialize MongoDB
    mongo.init_app(app)   # from first codebase
    init_db(app)          # from second codebase

    # Register Blueprints
    app.register_blueprint(user_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(pricing_bp)
    app.register_blueprint(warehouse_bp, url_prefix="/warehouse")

    # Landing Route
    @app.route("/")
    def index():
        return """
        <h1>User Module Test Runner</h1>
        <p><a href="/dev/login">Click here to Login as User</a></p>
        """

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)






# from flask import Flask
# from dotenv import load_dotenv
# import os

# from database.mongo import init_db

# # Blueprints
# from routes.warehouse_routes import warehouse_bp

# load_dotenv()

# def create_app():
#     app = Flask(__name__)

#     app.config["MONGO_URI"] = os.getenv("MONGO_URI")
#     app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

#     init_db(app)

#     # Register Blueprints
#     app.register_blueprint(warehouse_bp, url_prefix="/warehouse")

#     return app

# if __name__ == "__main__":
#     app = create_app()
#     app.run(debug=True)
