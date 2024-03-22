from bot.models import *
from user.models import UserProfile

from scripts.app_log import app_log as Log
from bot.model_indicator import Indicator
import scripts.functions as fn
from datetime import datetime


def run():
    startDt = datetime.now()
    hr = startDt.strftime('%H')
    mn = startDt.strftime('%M')
    
    if mn[1]=='0': #Solo entra en los minutos multiplo de 10 / Representa que se ejecuta cada 0 minutos

        print('Revisndo indicadores ',startDt)
        indicator = Indicator()
        indicator.update()

    
