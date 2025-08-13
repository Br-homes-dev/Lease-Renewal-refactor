"""
Flask app to support lease renewal logic:
- Reads property and rent data from Google sheets
- Computes whether 3% rent increase meets cash flow requirements
- Updates salesforce opportunity with this updated data via JWT OAuth 
- Optionally (Not yet implemented) sends a PandaDoc lease with the new rent to the tenant
"""


import os
from flask import Flask, send_from_directory
from dotenv import load_dotenv
from config import logger
from routes import routes
from salesforce import get_salesforce_access_token

# Load environment variables from .env file at runtime
load_dotenv()

app = Flask(__name__, static_folder='static',static_url_path='')
app.register_blueprint(routes)

@app.route('/<path:filename>')
def serve_static_file(filename: str):
    """
    Serve static files from the static directory.
    """
    return send_from_directory('static', filename)

@app.route('/')
def root():
    """
    Redirect root URL to the index page.
    """
    return app.send_static_file('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host="0.0.0.0", port=port, debug=True)

