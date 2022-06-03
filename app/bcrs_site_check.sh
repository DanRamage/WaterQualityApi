#!/bin/bash

source /usr/local/virtualenv/pyenv-3.8.10/bin/activate

cd /var/www/devapihowsthebeach/app

export FLASK_APP=/var/www/devapihowsthebeach/app/manage.py

flask get_bcrs_sites --params follybeach "32.569375 -80.043630,32.750204 -79.807029"

flask get_bcrs_sites --params charleston "32.569375 -80.043630,32.860402 -79.685711"

flask get_bcrs_sites --params sarasota "27.547242 -82.524490,27.255850 -82.814941"
