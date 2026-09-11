"""
ARM REST API v1 Blueprint
Provides modern RESTful endpoints for external applications
"""
from flask import Blueprint

api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

from . import auth, jobs, logs, settings, system, notifications, websockets