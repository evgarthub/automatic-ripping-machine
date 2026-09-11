"""
SPA hosting for the React UI

Serves the built arm-react bundle under the /app/ URL prefix, alongside the
legacy Jinja UI which keeps the root path until it is retired.
"""
import os

from flask import Blueprint, Response, send_from_directory
from werkzeug.utils import safe_join

route_spa = Blueprint("route_spa", __name__)

SPA_DIR_ENV = "ARM_SPA_DIR"
INDEX_FILE = "index.html"
ASSETS_DIR = "assets"
SPA_MISSING_HINT = "SPA build not found — build arm-react first"
INDEX_CACHE_CONTROL = "no-store"
ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"


def get_spa_dir():
    """
    Resolve the directory holding the built SPA files

    honours ARM_SPA_DIR when set, otherwise defaults to
    <repo root>/arm-react/dist derived from the arm package location
    """
    configured = os.environ.get(SPA_DIR_ENV)
    if configured:
        return configured
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(repo_root, "arm-react", "dist")


def _spa_file_response(spa_dir, filename):
    """
    Send a file from the SPA dist directory with the matching cache policy

    index.html is never cached so SPA updates propagate, hashed assets under
    assets/ are immutable and cached long term
    """
    response = send_from_directory(spa_dir, filename)
    if filename == INDEX_FILE:
        response.headers["Cache-Control"] = INDEX_CACHE_CONTROL
    elif filename.startswith(ASSETS_DIR + "/"):
        response.headers["Cache-Control"] = ASSET_CACHE_CONTROL
    return response


@route_spa.route("/app/", defaults={"path": ""}, methods=["GET"])
@route_spa.route("/app/<path:path>", methods=["GET"])
def serve_spa(path):
    """
    Serve the SPA at /app/ with a client-side routing fallback

    existing files are sent as-is, any other path below /app/ falls back to
    index.html so React Router can resolve it client side
    """
    spa_dir = get_spa_dir()
    if not os.path.isfile(os.path.join(spa_dir, INDEX_FILE)):
        return Response(SPA_MISSING_HINT, status=404, mimetype="text/plain")
    candidate = safe_join(spa_dir, path) if path else None
    if candidate and os.path.isfile(candidate):
        return _spa_file_response(spa_dir, path)
    return _spa_file_response(spa_dir, INDEX_FILE)
