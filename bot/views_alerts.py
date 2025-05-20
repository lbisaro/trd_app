from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError

import plotly.graph_objects as go

import numpy as np
from datetime import datetime, timedelta

from scripts.crontab_futures_alerts import DATA_FILE, KLINES_TO_GET_ALERTS, INTERVAL_ID, load_data_file, ohlc_from_prices
from scripts.Exchange import Exchange
from scripts.functions import ohlc_chart, get_intervals
from scripts.indicators import get_pivots_alert
from bot.models import *
from bot.model_sw import *

def alert_add_data(alert, actual_price):
    alert['actual_price_legend'] = ''
    alert['actual_price_class'] = ''  
    if alert['side'] == 1: #LONG
        alert['class'] = 'success'
        alert['tp1_perc'] = round((alert['tp1']/alert['in_price']-1)*100,2)
        alert['sl1_perc'] = round((alert['sl1']/alert['in_price']-1)*100,2)
        actual_price_perc = round((actual_price/alert['in_price']-1)*100,2)
        if actual_price > alert['tp1'] or actual_price < alert['sl1']:
            alert['actual_price_legend'] = 'El precio actual se encuentra fuera de rango'
            alert['actual_price_class'] = 'text-danger'
        elif abs(actual_price_perc) < alert['tp1_perc']/3:
            alert['actual_price_legend'] = f'Precio a {actual_price_perc}% de la entrada'
            alert['actual_price_class'] = 'text-success'
        else:
            alert['actual_price_legend'] = f'Precio a {actual_price_perc}% de la entrada'
            alert['actual_price_class'] = 'text-warning'

    else:   #SHORT
        alert['class'] = 'danger'
        alert['tp1_perc'] = round((alert['in_price']/alert['tp1']-1)*100,2)
        alert['sl1_perc'] = round((alert['in_price']/alert['sl1']-1)*100,2)
        actual_price_perc = round((alert['in_price']/actual_price-1)*100,2)
        if actual_price < alert['tp1'] or actual_price > alert['sl1']:
            alert['actual_price_legend'] = 'El precio actual se encuentra fuera de rango'
            alert['actual_price_class'] = 'text-danger'
        elif abs(actual_price_perc) < alert['tp1_perc']/3:
            alert['actual_price_legend'] = f'Precio a {actual_price_perc}% de la entrada'
            alert['actual_price_class'] = 'text-success'
        else:
            alert['actual_price_legend'] = f'Precio a {actual_price_perc}% de la entrada'
            alert['actual_price_class'] = 'text-warning'

            
        

    return alert

@login_required
def list(request):

    data = load_data_file(DATA_FILE)
    qty_symbols = len(data['symbols'])
    updated = data['updated']
    proc_duration = data['proc_duration']
    log_alerts = data['log_alerts']
    # Ordenar por 'start' descendente y reconstruir el diccionario
    log_alerts = dict(
        sorted(
            log_alerts.items(),
            key=lambda item: item[1]['start'],
            reverse=True
        )
    )

    exchInfo = Exchange(type='info', exchange='bnc', prms=None)

    # Obtener prices actuales
    actual_prices = {}
    tickers = exchInfo.client.futures_symbol_ticker()
    for ticker in tickers:
        symbol = ticker['symbol']
        actual_prices[symbol] = float(ticker['price'])
    
    for k in log_alerts:
        log_alerts[k] = alert_add_data(log_alerts[k],actual_prices[log_alerts[k]['symbol']])

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


@login_required
def analyze(request, key):
    data = load_data_file(DATA_FILE)
    log_alerts = data['log_alerts']
    if key in log_alerts:
        alert = log_alerts[key]

        interval_id = INTERVAL_ID
        interval_minutes = get_intervals(interval_id,'minutes')
        ahora = datetime.now()

        exchInfo = Exchange(type='info',exchange='bnc',prms=None)
        exchPrice = exchInfo.client.futures_mark_price(symbol=alert['symbol'])
        exchPrice = float(exchPrice['markPrice'])

        alert['name'] = alert['symbol']+' '+alert['timeframe']+' '+alert['origin']

        alert = alert_add_data(alert, actual_price=exchPrice)
        
        symbol = alert['symbol']
        prices = data['symbols'][symbol]['c_1m']
        interval_minutes = get_intervals(INTERVAL_ID,'minutes')
        df = ohlc_from_prices(data['datetime'],prices,interval_minutes)
        pivot_alert = get_pivots_alert(df)
        klines = pivot_alert['df']
    
        events = pd.DataFrame(data=[
                                    {
                                     'datetime': alert['start'],
                                     'in_price': alert['in_price'],
                                     'sl1': alert['sl1'],
                                     'tp1': alert['tp1'],
                                     'actual_price': None,
                                    },
                                    {'datetime': ahora+timedelta(minutes=30),
                                     'in_price': alert['in_price'],
                                     'sl1': alert['sl1'],
                                     'tp1': alert['tp1'],
                                     'actual_price': None,
                                    },
                                    {'datetime': ahora,
                                     'in_price': alert['in_price'],
                                     'sl1': alert['sl1'],
                                     'tp1': alert['tp1'],
                                     'actual_price': exchPrice,
                                    },
                                    ])
        indicators = [
                {'col': 'ZigZag','name': 'Pivots', 'color': 'white','row': 1, 'mode':'lines',},
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
        fig.add_trace(
            go.Scatter(
                x=events["datetime"], y=events["actual_price"], name="Precio Actual", mode="markers", showlegend=True, 
                line={'width': 1}, marker=dict(color='yellow'),
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


@login_required
def execute(request, key):
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

        interval_id = INTERVAL_ID
        interval_minutes = get_intervals(interval_id,'minutes')
        ahora = datetime.now()

        #td_minutes = int(interval_minutes*(KLINES_TO_GET_ALERTS+1))
        #start_str = (datetime.now() - timedelta(minutes=td_minutes)).strftime("%Y-%m-%d")
        #exchInfo = Exchange(type='info',exchange='bnc',prms=None)
        #klines = exchInfo.get_futures_klines(alert['symbol'],interval_id,start_str=start_str)
        #klines = zigzag(klines)
        symbol = alert['symbol']
        prices = data['symbols'][symbol]['c_1m']
        interval_minutes = get_intervals(INTERVAL_ID,'minutes')
        df = ohlc_from_prices(data['datetime'],prices,interval_minutes)
        pivot_alert = get_pivots_alert(df)
        klines = pivot_alert['df']

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
