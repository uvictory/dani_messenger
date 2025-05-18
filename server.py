from flask import Flask, send_from_directory
import os

app = Flask(__name__)
BASE_DIR = os.path.abspath("static")

@app.route("/static/<path:filename>")
def serve_file(filename):
    return send_from_directory(BASE_DIR, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=30007)