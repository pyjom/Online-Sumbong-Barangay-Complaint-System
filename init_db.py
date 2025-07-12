from main_app import app, db, User

# --- IMPORTANT ---
# Change these credentials before running the script in a production environment.
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'password123'

with app.app_context():
    # Create all database tables
    db.create_all()
    print("Database tables created.")

    # Check if the admin user already exists
    if User.query.filter_by(username=ADMIN_USERNAME).first() is None:
        # Create a default admin user
        admin_user = User(username=ADMIN_USERNAME)
        admin_user.set_password(ADMIN_PASSWORD)
        db.session.add(admin_user)
        db.session.commit()
        print(f"Admin user '{ADMIN_USERNAME}' created with password '{ADMIN_PASSWORD}'.")
    else:
        print(f"Admin user '{ADMIN_USERNAME}' already exists.")

