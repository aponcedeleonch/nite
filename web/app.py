from flask import Flask
from flask import render_template, request, redirect, url_for

from .nite.environment_ops import NiteEnvParser, NiteEnvLoader, NiteEnvSaver
from .nite.constants import (
    ORBITPOINT_NAME, VELOCITY_NAME, COLOR_NAME, SHAPE_NAME, NUMBER_OF_PARTICLES_NAME, KILL_OLD_NAME
)


app = Flask(__name__)


@app.route('/edit/', methods=['GET'])
@app.route('/edit/<saved_env>', methods=['GET'])
def edit(saved_env=None):
    nite_env_ops = NiteEnvLoader()
    loaded_env = nite_env_ops.load_from_file(saved_env)
    return render_template(
                        'edit.html',
                        nite_env=loaded_env,
                        orbitpoint_name=ORBITPOINT_NAME,
                        velocity_name=VELOCITY_NAME,
                        color_name=COLOR_NAME,
                        shape_name=SHAPE_NAME,
                        number_of_particles_name=NUMBER_OF_PARTICLES_NAME,
                        kill_old_name=KILL_OLD_NAME
                    )


@app.route('/save/', methods=['POST'])
def save():
    nite_env_dict = request.form
    nite_env_ops = NiteEnvParser()
    parsed_env = nite_env_ops.parse_form_dict(nite_env_dict)
    NiteEnvSaver(parsed_env).save_to_file()
    return redirect(url_for('edit'))
