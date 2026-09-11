"""
Token model for API authentication
"""
import datetime
import secrets
from arm.ui import db


class Token(db.Model):
    """
    Class to hold API tokens for external application authentication
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    token_hash = db.Column(db.String(128), unique=True, nullable=False)
    expiry = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    last_used = db.Column(db.DateTime)

    def __init__(self, user_id, token_hash=None, expiry_hours=24):
        self.user_id = user_id
        if token_hash is None:
            self.token_hash = secrets.token_urlsafe(32)
        else:
            self.token_hash = token_hash
        self.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=expiry_hours)

    def is_expired(self):
        """Check if token is expired"""
        expiry = self.expiry
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=datetime.timezone.utc)
        return datetime.datetime.now(datetime.timezone.utc) > expiry

    def update_last_used(self):
        """Update last used timestamp"""
        self.last_used = datetime.datetime.now(datetime.timezone.utc)
        db.session.commit()

    @staticmethod
    def generate_token(user_id, expiry_hours=24):
        """Generate a new token for a user"""
        token = Token(user_id=user_id, expiry_hours=expiry_hours)
        db.session.add(token)
        db.session.commit()
        return token

    @staticmethod
    def validate_token(token_hash):
        """Validate a token and return the associated user if valid"""
        from arm.models.user import User

        token = Token.query.filter_by(token_hash=token_hash).first()
        if token and not token.is_expired():
            token.update_last_used()
            return User.query.get(token.user_id)
        return None

    @staticmethod
    def revoke_token(token_hash):
        """Revoke a token"""
        token = Token.query.filter_by(token_hash=token_hash).first()
        if token:
            db.session.delete(token)
            db.session.commit()
            return True
        return False

    def __repr__(self):
        return f'<Token {self.id} for user {self.user_id}>'
