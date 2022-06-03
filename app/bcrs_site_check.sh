#!/bin/bash

source /usr/local/virtualenv/pyenv-3.8.10/activate

cd /var/www/devapihowsthebeach/app

export FLASK_APP=/var/www/devapihowsthebeach/app/manage.py

flask get_bcrs_sites --params follybeach "32.569375 -80.043630,32.750204 -79.807029"

source /usr/local/virtualenv/pyenv-3.8.10/activate
