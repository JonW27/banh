import os
from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def index():
    return render_template('auth.html');

def editor():
    
    return render_template('editor.html');

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='127.0.0.1', port=port)
