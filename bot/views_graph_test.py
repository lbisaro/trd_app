from django.shortcuts import render
#import plotly.express as px
from scripts.functions import ohlc_chart 
import numpy as np


import pickle
import os

# Create your views here.
def chart(request):
    klines_file = './www/backtest/klines/2d01/Lateral_BTCUSDT_2d01_2023-06-20_2023-10-09.DataFrame'
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
         'symbol': 'circle-open' #https://plotly.com/python/reference/scatter/#scatter-marker-symbol
        }
    ]

    klines['pnl'] = klines['close']
    fig = ohlc_chart(klines, indicators=indicators,signals=signals)

    chart = fig.to_html(config = {'scrollZoom': True, }) 
    context = {'chart': chart}
    return render(request, 'chart.html', context)