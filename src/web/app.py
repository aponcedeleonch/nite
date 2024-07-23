from flask import Flask
from flask import render_template


app = Flask(__name__)


@app.route('/edit/')
@app.route('/edit/<name>')
def edit(name=None):
    return render_template('edit.html', person=name)
