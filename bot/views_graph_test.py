from django.shortcuts import render
from scripts.functions import ohlc_chart, plotly_to_json
import numpy as np
from django.http import JsonResponse


import pickle


# Create your views here.
def chart(request):
    context = {'chart': chart}
    return render(request, 'chart.html', context)

def chart_get(request,symbol):
    klines_file = './backtest/klines/0m15/Lateral_'+symbol+'_0m15_2023-06-20_2023-10-09.DataFrame'
    with open(klines_file, 'rb') as file:
        klines = pickle.load(file)
    
    klines["MA_F"] = klines["close"].rolling(21).mean()
    klines["MA_S"] = klines["close"].rolling(100).mean()
    klines['MA_cross'] = np.where((klines['MA_F']>klines['MA_S']) & (klines['MA_F'].shift(1)<klines['MA_S'].shift(1)),klines['MA_F'],None)
    klines['MA_cross'] = np.where((klines['MA_F']<klines['MA_S']) & (klines['MA_F'].shift(1)>klines['MA_S'].shift(1)),klines['MA_F'],klines['MA_cross'])
    
    indicators = [
        {'col': 'MA_F',
         'name': 'MA Fast',
         'color': 'yellow',
         },
        {'col': 'MA_S',
         'name': 'MA Slow',
         'color': 'green',
         },
    ]
    signals = [
        {'col':'MA_cross',
         'name': 'MA Cross',
         'color': 'yellow',
         'symbol': 'circle-open' 
        }
    ]

    klines['pnl'] = klines['close']
    fig = ohlc_chart(klines, indicators=indicators,signals=signals)
    fig_json = plotly_to_json(fig)

    json_rsp = {}
    json_rsp['ok'] = True
    json_rsp['error'] = False
    json_rsp['fig_json'] = fig_json
    return JsonResponse(json_rsp)