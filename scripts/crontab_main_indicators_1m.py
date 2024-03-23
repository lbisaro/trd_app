from bot.models import *
from user.models import UserProfile

from scripts.app_log import app_log as Log
from bot.model_indicator import Indicator
import scripts.functions as fn
from datetime import datetime


def run():

    indicator = Indicator()
    indicator.update()

    
