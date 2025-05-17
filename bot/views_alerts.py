from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError

import plotly.graph_objects as go

import numpy as np
from datetime import datetime, timedelta

from scripts.crontab_futures_alerts import DATA_FILE, KLINES_TO_GET_ALERTS, load_data_file
from scripts.Exchange import Exchange
from scripts.functions import ohlc_chart
from scripts.indicators import zigzag
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
            if log_alerts[k]['side'] == 1: #LONG
                log_alerts[k]['class'] = 'success'
                log_alerts[k]['tp1_perc'] = round((log_alerts[k]['tp1']/log_alerts[k]['in_price']-1)*100,2)
                log_alerts[k]['sl1_perc'] = round((log_alerts[k]['sl1']/log_alerts[k]['in_price']-1)*100,2)
            else:   #SHORT
                log_alerts[k]['class'] = 'danger'
                log_alerts[k]['tp1_perc'] = round((log_alerts[k]['in_price']/log_alerts[k]['tp1']-1)*100,2)
                log_alerts[k]['sl1_perc'] = round((log_alerts[k]['in_price']/log_alerts[k]['sl1']-1)*100,2)

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

@login_required
def analyze(request, key):
    data = load_data_file(DATA_FILE)
    log_alerts = data['log_alerts']
    if key in log_alerts:
        alert = log_alerts[key]
        alert['name'] = alert['symbol']+' '+alert['timeframe']+' '+alert['origin']

        if alert['side'] == 1: #LONG
            alert['class'] = 'success'
            alert['tp1_perc'] = round((alert['tp1']/alert['in_price']-1)*100,2)
            alert['sl1_perc'] = round((alert['sl1']/alert['in_price']-1)*100,2)
        else:   #SHORT
            alert['class'] = 'danger'
            alert['tp1_perc'] = round((alert['in_price']/alert['tp1']-1)*100,2)
            alert['sl1_perc'] = round((alert['in_price']/alert['sl1']-1)*100,2)

        interval_id = '0m15'
        velas = 15
        ahora = datetime.now()
        diferencia = ahora - alert['start']
        diferencia_en_velas = abs(int(diferencia.total_seconds() / 60 / velas))
        limit = diferencia_en_velas + KLINES_TO_GET_ALERTS
        
        exchInfo = Exchange(type='info',exchange='bnc',prms=None)
        klines = exchInfo.get_klines(alert['symbol'],interval_id,limit=limit)
        klines = zigzag(klines)

        events = pd.DataFrame(data=[
                                    {
                                     'datetime': alert['start'],
                                     'in_price': alert['in_price'],
                                     'sl1': alert['sl1'],
                                     'tp1': alert['tp1'],
                                    },
                                    {'datetime': ahora+timedelta(minutes=30),
                                     'in_price': alert['in_price'],
                                     'sl1': alert['sl1'],
                                     'tp1': alert['tp1'],
                                    },
                                    ])
        indicators = [
                {'col': 'ZigZag','color': 'white','row': 1, 'mode':'lines',},
            ]
        fig = ohlc_chart(klines,show_volume=False,show_pnl=False, indicators=indicators)
        fig.add_trace(
            go.Scatter(
                x=events["datetime"], y=events["in_price"], name="Entrada", mode="lines", showlegend=True, 
                line={'width': 1}, marker=dict(color='white'),
            ),row=1,col=1,
        ) 
        fig.add_trace(
            go.Scatter(
                x=events["datetime"], y=events["sl1"], name="Stop Loss", mode="lines", showlegend=True, 
                line={'width': 1}, marker=dict(color='red'),
            ),row=1,col=1,
        ) 
        fig.add_trace(
            go.Scatter(
                x=events["datetime"], y=events["tp1"], name="Take Profit", mode="lines", showlegend=True, 
                line={'width': 1}, marker=dict(color='green'),
            ),row=1,col=1,
        ) 

        
        return render(request, 'alerts_analyze.html',{
            'DATA_FILE': DATA_FILE ,
            'key': key,
            'alert': alert,
            'chart': fig.to_html(config = {'scrollZoom': True, }),
        })


    else:
        return render(request, 'alerts_analyze.html',{}) 
