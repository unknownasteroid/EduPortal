import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key'
    OAUTH_CREDENTIALS = {
        'google': {
            'id': 'your-google-client-id',
            'secret': 'your-google-client-secret'
        },
        'yandex': {
            'id': 'your-yandex-client-id',
            'secret': 'your-yandex-client-secret'
        }
    }
    DATA_FOLDER = 'data/'
    UPLOAD_FOLDER = 'static/uploads/'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
