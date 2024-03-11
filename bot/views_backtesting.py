from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Count, Case, When, IntegerField
from django.contrib.auth.decorators import login_required
import json

from bot.models import *
from bot.model_kline import *
from bot.model_backtest import *
import backtest.config as bt_config



@login_required
def backtesting(request):
    gen_bot = GenericBotClass()
    classList = gen_bot.get_clases()
    clases = []
    for c in classList:
        obj = gen_bot.get_instance(c)
        cls = {'class':c,'descripcion':obj.descripcion, }
        clases.append(cls)
    if request.method == 'GET':
        return render(request, 'backtesting.html',{
            'clases': clases,
        })

@login_required
def config(request,bot_class_name):
    gen_bot = GenericBotClass()
    obj = gen_bot.get_instance(bot_class_name)
    periodos = Backtest().get_periodos(interval_id='ALL',all_tendencias=True)
        
    if request.method == 'GET':
        return render(request, 'backtesting_run.html',{
            'bot_class_name': bot_class_name,
            'periodos': periodos,
            'parametros': obj.parametros,
        })


@login_required
def run(request):
    if request.method == 'POST':
        json_rsp = {}
        bot_class_name = request.POST['bot_class_name']
        gen_bot = GenericBotClass()
        run_bot = gen_bot.get_instance(bot_class_name)
        


        prmPost = eval(request.POST['parametros'])
        for dict in prmPost:
            for k,v in dict.items():
                run_bot.__setattr__(k, v)

        run_bot.quote_qty = float(request.POST['quote_qty'])
        run_bot.interval_id = request.POST['interval_id']
        run_bot.symbol = request.POST['symbol']

        backtest_file = request.POST['file']

        from_date = request.POST['from_date']
        to_date = request.POST['to_date']

        atributos = run_bot.__dict__
        json_rsp['parametros'] = {}
        for attr in atributos:
            val = atributos[attr]
            if attr != 'row':
                json_rsp['parametros'][attr] = val

        try:
            run_bot.valid()
        except Exception as e:
            json_rsp['ok'] = False
            json_rsp['error'] = str(e)
            return JsonResponse(json_rsp)
        
        backtest = Backtest()
        klines = backtest.get_df_from_file(backtest_file)
        sub_klines = backtest.get_sub_df_from_file(backtest_file)
        bt = run_bot.backtest(klines,from_date,to_date,'completed',sub_klines)
        json_rsp['bt'] = bt

        if bt['error']:
            json_rsp['error'] = bt['error']
            json_rsp['ok'] = False
        else:
            json_rsp['ok'] = True
            
        return JsonResponse(json_rsp)
    


