SHELL=/bin/bash
cd ~/trd_app
source venv/bin/activate
python --version
python manage.py runscript crontab_bot_1m >> live_run.log