#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# This collects Admin CSS/JS for WhiteNoise
python manage.py collectstatic --no-input

# This applies your models to the Neon database
python manage.py migrate