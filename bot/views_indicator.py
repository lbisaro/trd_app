from django.shortcuts import render
from django.http import JsonResponse
import numpy as np
import pandas as pd
from bot.model_indicator import Indicator
from bot.model_kline import Symbol
from scripts.functions import get_intervals 


# Create your views here.
def panel(request):
    symbols = Symbol.objects.filter(activo = 1)
    indicators = Indicator.objects.filter(last=True)
    for i in indicators:
        print(i)
    intervals_id = Indicator.intervals
    intervals = []
    for interval_id in intervals_id:
        intervals.append({'id':interval_id,'name':get_intervals(interval_id,'name'),})
    context = {
        'symbols': symbols,
        'intervals': intervals,
        'indicators': indicators,
        'INDICATOR_ID_TREND': Indicator.INDICATOR_ID_TREND,
        'INDICATOR_ID_VOLUME': Indicator.INDICATOR_ID_VOLUME,
        'INDICATOR_ID_VOLATILITY': Indicator.INDICATOR_ID_VOLATILITY,
        'indicators_type':[{'id':Indicator.INDICATOR_ID_TREND,'name':'Tendencia'},
                           {'id':Indicator.INDICATOR_ID_VOLUME,'name':'Volumen'},
                           {'id':Indicator.INDICATOR_ID_VOLATILITY,'name':'Volatilidad'},
                          ],
       }
    return render(request, 'indicator_panel.html', context)

