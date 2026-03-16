"""
ITBP RTC Grain Shop Management System - Flask API
Main Application Entry Point
"""
import os
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    
    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Initialize JWT
    jwt = JWTManager(app)
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.users import users_bp
    from routes.contractors import contractors_bp
    from routes.items import items_bp
    from routes.mess import mess_bp
    from routes.grain_shop import grain_shop_bp
    from routes.distribution import distribution_bp
    from routes.reports import reports_bp
    from routes.approvals import approvals_bp
    from routes.demands import demands_bp
    from routes.supplies import supplies_bp
    from routes.price_changes import price_changes_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(contractors_bp, url_prefix='/api/contractors')
    app.register_blueprint(items_bp, url_prefix='/api/items')
    app.register_blueprint(mess_bp, url_prefix='/api/mess')
    app.register_blueprint(grain_shop_bp, url_prefix='/api/grain-shop')
    app.register_blueprint(distribution_bp, url_prefix='/api/distribution')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(approvals_bp, url_prefix='/api/approvals')
    app.register_blueprint(demands_bp, url_prefix='/api/demands')
    app.register_blueprint(supplies_bp, url_prefix='/api/supplies')
    app.register_blueprint(price_changes_bp, url_prefix='/api/price-changes')
    
    @app.route('/api/health')
    def health_check():
        return {'status': 'healthy', 'message': 'ITBP RTC Grain Shop API is running'}
    
    return app


if __name__ == '__main__':
    app = create_app()
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(host=host, port=port, debug=debug)
