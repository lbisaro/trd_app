from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError

import numpy as np

from scripts.crontab_check_price_change import DATA_FILE, load_data_file
from scripts.functions import ohlc_chart
from bot.models import *
from bot.model_sw import *

@login_required
def list(request):

    try:
        data = load_data_file(DATA_FILE)
        qty_symbols = len(data['symbols'])
        updated = data['updated']
        proc_duration = data['proc_duration']

        log_alerts = data['log_alerts']
        for k in log_alerts:
            log_alerts[k]['class'] = 'success' if log_alerts[k]['side']>0 else 'danger'
            print(log_alerts[k]['class'])
            for i in log_alerts[k]:
                print(i,' -> ',log_alerts[k][i])

        if 'c_1m' in data['symbols']['BTCUSDT']:
            qty_c_1m = len(data['symbols']['BTCUSDT']['c_1m'])
        else:
            qty_c_1m = 0
        return render(request, 'alerts_list.html',{
            'DATA_FILE': DATA_FILE ,
            'qty_symbols': qty_symbols ,
            'qty_c_1m': qty_c_1m ,
            'updated': updated ,
            'proc_duration': proc_duration ,
            'log_alerts': log_alerts ,
        })
    except:
        return render(request, 'alerts_list.html',{})
