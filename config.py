import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SECRET_KEY = 'your-secret-key-here'
SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "instance", "users.db")}'
SQLALCHEMY_TRACK_MODIFICATIONS = False
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
MAX_CONTENT_LENGTH = 8 * 1024 * 1024
SESSION_TYPE = 'filesystem'

#Email configurations
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'your-email@gmail.com' #Mail to reset password
MAIL_PASSWORD = 'your-app-password'  #Gmail app password



