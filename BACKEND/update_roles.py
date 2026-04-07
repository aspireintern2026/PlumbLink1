from app import create_app
from app.extensions import db
from app.models import User

app = create_app()
with app.app_context():
    admin = User.query.filter_by(email='admin123@gmail.com').first()
    if admin:
        admin.role = 'admin'
        db.session.commit()
        print("✓ Updated admin123@gmail.com to role: admin")

    customer = User.query.filter_by(email='customer123@gmail.com').first()
    if customer:
        customer.role = 'customer'
        db.session.commit()
        print("✓ Updated customer123@gmail.com to role: customer")

    plumber = User.query.filter_by(email='plumber123@gmail.com').first()
    if plumber:
        plumber.role = 'plumber'
        db.session.commit()
        print("✓ Updated plumber123@gmail.com to role: plumber")

    print("\nAll users updated successfully!")
