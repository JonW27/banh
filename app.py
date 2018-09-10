import os
from flask import Flask, render_template, request, redirect, url_for, Response, escape, session
from flask_assets import Environment, Bundle
import psycopg2
import pypandoc
import tempfile
import bcrypt

import logging

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = os.urandom(24)
assets = Environment(app)
version = 0.1

DATABASE_URL = os.environ['DATABASE_URL']

css = Bundle('css/main.css', filters="cssmin", output="gen/main.css")
assets.register('css_all', css)

cm_js = Bundle('codemirror-5.34.0/lib/codemirror.js', 'codemirror-5.34.0/mode/markdown/markdown.js', filters='jsmin', output='gen/cm.js')
assets.register('cm_js', cm_js)

cm_css = Bundle('codemirror-5.34.0/lib/codemirror.css', filters="cssmin", output="gen/cm.css")
assets.register('cm_css', cm_css)

spectre_css = Bundle('css/spectre.min.css', output="gen/spectre.css")
assets.register('spectre_css', spectre_css)

preview = Bundle('demo.pdf')
assets.register('preview', preview)

# js = Bundle('jquery.js', 'base.js', 'widgets.js', filters='jsmin', output='gen/packed.js')
# assets.register('js_all', js)

@app.route("/")
def index():
    return render_template('auth.html')

@app.route("/signup")
def signup():
    return render_template('signup.html')

@app.route("/signup_handler", methods=['GET', 'POST'])
def signup_handler():
    if request.method == "POST":
        unsanitized_username = request.form['username']
        unsanitized_passwd = request.form['passwd']
        if not unsanitized_username or not unsanitized_passwd:
            return Response("Username and/or password cannot be empty", status=400, mimetype="application/txt")
        ### put further sanitization other than request's here
        username = unsanitized_username.encode("utf-8")
        passwd = unsanitized_passwd.encode("utf-8")
        ### end zone

        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute("""SELECT * FROM users WHERE username = (%s);""", (username,))
        if cur.fetchone() is not None:
            return Response("Username already taken.", 200, mimetype="application/txt")

        # hash password
        hashed_pw = bcrypt.hashpw(passwd, bcrypt.gensalt(16)) # 16 means a roughly 10 second wait, as there are roughly ~56000 combinations

        try:
            cur.execute("""INSERT INTO users (username, password) VALUES (%s, %s);""", (username, hashed_pw))
        except:
            return Response("Record could not be inserted into database.", 400, mimetype="application/txt")
        conn.commit()
        cur.close()
        conn.close()
        return Response(status=204)    
    else:
        return redirect(url_for("signup"))

@app.route("/login")
def login():
    if 'username' in session:
        return redirect(url_for("app_dashboard_handler"))
    else:    
        return render_template('login.html')

@app.route("/login_handler", methods=['GET', 'POST'])
def login_handler():
    if request.method == "POST":
        unsanitized_username = request.form["username"]
        unsanitized_passwd = request.form['passwd']
        if not unsanitized_username or not unsanitized_passwd:
            return Response("Username and/or password cannot be empty", status=400, mimetype="application/txt")
        ### put further sanitization other than request's here
        username = unsanitized_username.encode("utf-8")
        passwd = unsanitized_passwd.encode("utf-8")
        ### end zone
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute("""SELECT * FROM users WHERE username = (%s);""", (username,))
        data = cur.fetchone()
        if data is None:
            return Response("We do not have a record of that username.", 200, mimetype="application/txt")
        hashed_passwd = data[2]
        cur.close()
        conn.close()
        if bcrypt.checkpw(passwd, hashed_passwd):
            session['username'] = username
            return Response(status=204)
        else:
            return Response("Incorrect password.", 200, mimetype="application/html")
    else:
        return redirect(url_for("login"))

@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.pop('username', None)
    return redirect(url_for('index'))        

@app.route("/app")
def app_dashboard_handler():
    if 'username' in session:
        # get user files from database files table
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()

        username = escape(session['username'])

        cur.execute("""SELECT id FROM users WHERE username = (%s);""", (username,))
        uid = cur.fetchone()
        cur.execute("""SELECT content FROM files WHERE id = (%s);""", (uid,))
        files = cur.fetchall()
        conn.close()
        cur.close()
        app.logger.info(files)
        return render_template('app.html', username = username, files = files)
    else:
        return redirect(url_for("login"))

@app.route("/editor")
def editor():    
    return render_template('editor.html')

@app.route("/update", methods=['GET', 'POST'])
def update():
    if request.method == "POST":
        # do the processing of the content var sent in xhttp request by update(), run pandoc on it, generate file
        unsanitized_input = request.form['content']
        f = tempfile.NamedTemporaryFile(suffix='.md')
        f.write(unsanitized_input.encode("utf-8"))
        app.logger.info("temp file generated is %s", f.name)

        f.seek(0) # reset marker to beginning of file

        output = pypandoc.convert_file(f.name, 'pdf', outputfile="static/demo.pdf")

        app.logger.info("data received")
        f.close()
        return Response("ALL GOOD", status=200, mimetype='application/txt')
    else:
        return redirect(url_for("index"))

@app.route("/about")
def future():
    return render_template('about.html', version=version)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True) # turn debug off for production!
