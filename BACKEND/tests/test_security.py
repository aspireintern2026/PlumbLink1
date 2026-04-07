import pytest
import sys
import os
from plumbapp.app import app

# Add parent directory to path
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')
))


@pytest.fixture
def client():
    """Flask test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestSecurityHeaders:
    """Test CORS and security headers"""

    def test_cors_headers_present(self, client):
        """Verify CORS headers are returned"""
        response = client.get('/api/bookings')
        assert 'Access-Control-Allow-Origin' in response.headers
        assert response.headers['Access-Control-Allow-Origin'] == '*'

    def test_cors_methods_allowed(self, client):
        """Verify allowed methods are advertised"""
        response = client.get('/api/bookings')
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'GET' in response.headers['Access-Control-Allow-Methods']
        assert 'POST' in response.headers['Access-Control-Allow-Methods']

    def test_options_request_returns_204(self, client):
        """Verify OPTIONS requests return 204"""
        response = client.options('/api/bookings')
        assert response.status_code == 204


class TestAPIEndpoints:
    """Test API endpoints functionality"""

    def test_get_bookings(self, client):
        """Verify GET /api/bookings returns data"""
        response = client.get('/api/bookings')
        assert response.status_code == 200

    def test_health_endpoint(self, client):
        """Verify health check endpoint"""
        response = client.get('/')
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling"""

    def test_invalid_route_returns_404(self, client):
        """Verify 404 for non-existent routes"""
        response = client.get('/api/nonexistent')
        assert response.status_code == 404
