from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64
import hashlib
import os
import pickle
from PIL import Image
from io import BytesIO
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.config.from_pyfile('config.py')

db = SQLAlchemy(app)

#OAuth
oauth = OAuth(app)

#Google Registration
CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'
google = oauth.register(
    name='google',
    server_metadata_url=CONF_URL,
    client_id='your gmail api id',
    client_secret='your google secret key',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

#User database
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)

#ML model part
rf_model = None
if os.path.exists('models/rf_model.pkl'):
    with open('models/rf_model.pkl', 'rb') as f:
        rf_model = pickle.load(f)


def derive_key(secret_key):
    return hashlib.sha256(secret_key.encode()).digest()

def encrypt_message(message, secret_key):
    key = derive_key(secret_key)
    cipher = AES.new(key, AES.MODE_CBC)
    iv = cipher.iv
    encrypted_data = cipher.encrypt(pad(message.encode(), AES.block_size))
    return base64.b64encode(iv + encrypted_data).decode()

def decrypt_message(encrypted_message, secret_key):
    try:
        key = derive_key(secret_key)
        data = base64.b64decode(encrypted_message)
        iv = data[:16]
        encrypted_data = data[16:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(encrypted_data), AES.block_size).decode()
    except Exception:
        return None

def encrypt_image(image_path, message, secret_key):
    image = Image.open(image_path).convert("RGB")
    
    #PNG conversion part
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    image = Image.open(BytesIO(buffered.getvalue()))

    pixels = image.load()
    encrypted_message = encrypt_message(message, secret_key)
    message_binary = ''.join(format(ord(c), '08b') for c in encrypted_message)
    message_length = f"{len(message_binary):032b}"
    full_data = message_length + message_binary

    if len(full_data) > image.width * image.height:
        raise ValueError("Message is too large to fit in the image!")

    pixel_index = 0
    for row in range(image.height):
        for col in range(image.width):
            if pixel_index < len(full_data):
                r, g, b = pixels[col, row]
                r = r & 0xFE | int(full_data[pixel_index])
                pixels[col, row] = (r, g, b)
                pixel_index += 1

    return image

def decrypt_image(image_path, secret_key):
    image = Image.open(image_path).convert("RGB")
    pixels = image.load()
    message_bin = ""

    for row in range(image.height):
        for col in range(image.width):
            r, g, b = pixels[col, row]
            message_bin += str(r & 1)

    message_length = int(message_bin[:32], 2)
    encrypted_message_bin = message_bin[32:32 + message_length]
    encrypted_message = "".join(chr(int(encrypted_message_bin[i:i+8], 2)) for i in range(0, len(encrypted_message_bin), 8))
    
    decrypted_message = decrypt_message(encrypted_message, secret_key)
    
    if decrypted_message is None:
        raise ValueError("Incorrect secret key! Decryption failed.")
    
    return decrypted_message

def predict_accuracy(message):
    if rf_model is None:
        return "Model not loaded"
    
    feature = [[len(message)]]
    prediction = rf_model.predict(feature)
    
    return "100%" if prediction[0] == 1 else "<100%"

@app.route('/')
def index():
    return redirect(url_for('welcome'))

@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['username'] = user.username
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'error')
        return render_template('login.html')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html')
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/google-login')
def google_login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = google.authorize_access_token()
    user_info = token['userinfo']
    email = user_info.get('email')
    
    #Existing user checking
    existing_user = User.query.filter_by(email=email).first()
    if existing_user is None:
        #create password page redirection
        session['email'] = email
        return redirect(url_for('create_password'))
    else:
        #Login existing user
        session['username'] = existing_user.username
        return redirect(url_for('dashboard'))

@app.route('/create-password', methods=['GET', 'POST'])
def create_password():
    if 'email' not in session:
        return redirect(url_for('google_login'))
    
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            return render_template('create_password.html', error='Passwords do not match')
        
        #username
        base_username = 'google_user'
        i = 1
        while True:
            username = f'{base_username}{i}' if i > 1 else base_username
            existing_user = User.query.filter_by(username=username).first()
            if not existing_user:
                break
            i += 1
        
        new_user = User(username=username, password=generate_password_hash(password), email=session['email'])
        db.session.add(new_user)
        db.session.commit()
        
        #Login
        session['username'] = new_user.username
        return redirect(url_for('dashboard'))
    
    return render_template('create_password.html')

from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash, check_password_hash


from config import *

app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['SESSION_TYPE'] = SESSION_TYPE

app.config['MAIL_SERVER'] = MAIL_SERVER
app.config['MAIL_PORT'] = MAIL_PORT
app.config['MAIL_USE_TLS'] = MAIL_USE_TLS
app.config['MAIL_USERNAME'] = MAIL_USERNAME
app.config['MAIL_PASSWORD'] = MAIL_PASSWORD
mail = Mail(app)

def generate_password_reset_token(user):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(user.id)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Email not found', 'error')
            return render_template('forgot_password.html')
        
        #Generating password reset token
        token = generate_password_reset_token(user)
        
        #Sending email
        subject = 'Password Reset Request'
        body = f'''
        To reset your password, visit the following link:
        {url_for('reset_password', token=token, _external=True)}
        '''
        msg = Message(subject, sender='your-email@gmail.com', recipients=[user.email])
        msg.body = body
        mail.send(msg)
        
        flash('Password reset email sent', 'success')
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('reset_password.html', token=token)
        
        serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        try:
            user_id = serializer.loads(token, max_age=3600)
        except:
            flash('Invalid or expired token', 'error')
            return redirect(url_for('login'))
        
        user = User.query.get(user_id)
        user.password = generate_password_hash(new_password)
        db.session.commit()
        flash('Password reset successfully', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token)



@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    image_preview = None

    if request.method == 'POST' and request.files['image']:
        image = request.files['image']
        try:
            img = Image.open(image)
            img.thumbnail((150, 150))

            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            image_preview = f"data:image/png;base64,{img_str}"

        except Exception as e:
            print(f"Error creating image preview: {e}")
            flash(f'Error creating image preview: {str(e)}', 'error')
    return render_template('dashboard.html', image_preview=image_preview)

@app.route('/process', methods=['POST'])
def process():
    if 'username' not in session:
        return redirect(url_for('login'))

    operation = request.form.get('operation')
    secret_key = request.form.get('secret_key')
    image = request.files['image']
    message = request.form.get('message')  

    if not all([operation, secret_key, image]):
        flash('Missing fields', 'error')
        return redirect(url_for('dashboard'))

    filename = secure_filename(image.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    image.save(file_path)
    
    try:
        if operation == 'encrypt':
            if not message:
                flash('Message required', 'error')
                return redirect(url_for('dashboard'))
            
            encrypted_img = encrypt_image(file_path, message, secret_key)
            encrypted_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'encrypted_{os.path.splitext(filename)[0]}.png')
            encrypted_img.save(encrypted_file_path)
            return send_from_directory(app.config['UPLOAD_FOLDER'], f'encrypted_{os.path.splitext(filename)[0]}.png', as_attachment=True)

        elif operation == 'decrypt':
            decrypted_message = decrypt_image(file_path, secret_key)
            accuracy = predict_accuracy(decrypted_message)
            return render_template('result.html', message=decrypted_message, accuracy=accuracy)

    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('welcome'))

if __name__ == '__main__':
    os.makedirs('instance', exist_ok=True)
    os.makedirs('uploads', exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(debug=True)
