from flask import Flask
from flask import render_template

from .nite.environment_ops import NiteEnvironmentOps


app = Flask(__name__)


@app.route('/edit/')
@app.route('/edit/<saved_env>')
def edit(saved_env=None):
    nite_env_ops = NiteEnvironmentOps()
    loaded_env = nite_env_ops.load(saved_env)
    return render_template('edit.html', nite_env=loaded_env)
