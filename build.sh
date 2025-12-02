#!/usr/bin/env bash

set -o errexit  # exit on error

pip install -r requirements.txt
playwright install chromium

python manage.py collectstatic --no-input
python manage.py migrate
