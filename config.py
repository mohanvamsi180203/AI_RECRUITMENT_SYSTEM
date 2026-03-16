import os

class Config:
    SECRET_KEY = "super_secret_key"

    MONGO_URI = "mongodb://localhost:27017/"
    DATABASE_NAME = "ai_recruitment_db"

    UPLOAD_FOLDER = "uploads"

    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = ''
    MAIL_PASSWORD = ''
    MAIL_DEFAULT_SENDER = 'your_email@gmail.com'
