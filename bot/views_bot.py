from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
import scripts.functions as fn
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.template import RequestContext
import numpy as np
import os
import json
from django.conf import settings

from bot.models import *
from bot.model_kline import *
from user.models import UserProfile
import local__config as local
from scripts.Bot_Core_utils import Order as ord_u

@login_required
def bots(request):
    bots = Bot.objects.filter(usuario=request.user).order_by('-activo','estrategia__nombre') 
    
    formattedBots = []
    for b in bots:
        intervalo = fn.get_intervals(b.estrategia.interval_id,'binance')
        status = eval(b.status) if len(b.status) > 0 else []
        formattedBots.append({'bot_id':b.id, 
                             'estrategia':b.estrategia.nombre,
                             'estrategia_activo':b.estrategia.activo,
                             'quote_qty': round(b.quote_qty,2),
                             'usuario': b.usuario,
                             'intervalo': intervalo,
                             'activo': b.activo,
                             'status': status,
                             })

    pnl_diario = BotPnl.get_pnl_diario_general()
    pnl_diario['date'] = pd.to_datetime(pnl_diario['date'])
    pnl_diario['str_dt'] = pnl_diario['date'].dt.strftime('%Y-%m-%d')
    pnl_diario = pnl_diario[['str_dt', 'pnl']].copy()
    pnl_diario = pnl_diario.values.tolist()

    if request.method == 'GET':
        return render(request, 'bots.html',{
            'bots': formattedBots,
            'pnl_diario': pnl_diario,
        })

@login_required
def bot(request, bot_id):
    bot = get_object_or_404(Bot, pk=bot_id,usuario=request.user)
    intervalo = fn.get_intervals(bot.estrategia.interval_id,'name')
    status = eval(bot.status) if len(bot.status) > 0 else []

    quote_actual = bot.quote_qty
    if 'wallet_tot' in status: 
        quote_actual = status['wallet_tot']['r']
        del status['wallet_tot']

    #Avisos por entornos de ejecucion de TEST
    environment_advertisement = []
    usuario=request.user
    usuario_id = usuario.id
    profile = UserProfile.objects.get(user_id=usuario_id)
    profile_config = profile.parse_config()
    if profile_config['bnc']['bnc_env'] == 'test':
        environment_advertisement.append('El Bot se ejecuta en entorno de TEST')

    #### Creando grafica de la operacion del bot
    botClass = bot.get_instance()
    symbol_info = Exchange('info','bnc',prms=None).get_symbol_info(symbol=botClass.symbol)
    quote_asset = symbol_info['quote_asset']
    
    pnl = quote_actual-bot.quote_qty
    pnl_perc = (pnl/bot.quote_qty)*100

    main_data = []
    orders_data = []
    trades_data = []

    #bot.add_order_log(order_id=2,side=0,price=0.094)
    
    #Obteniendo datos de PNL y Price registrado por el Bot
    pnl_log = bot.get_pnl()
    max_drawdown_reg = 0
    if len(pnl_log) > 0:
        pnl_log['datetime'] = pnl_log['datetime'].dt.floor('T')
                
        #Historico de PNL
        if len(pnl_log)>0:
            max_drawdown_reg = botClass.ind_maximo_drawdown(pnl_log,'pnl')
            pnl_log['str_dt'] = pnl_log['datetime'].dt.strftime('%Y-%m-%d %H:%M')
            main_data = pnl_log[['str_dt', 'price', 'pnl']].copy()
            main_data = main_data.values.tolist()
            
        #Historico de ordenes
        hst_orders = BotOrderLog.objects.filter(bot_id=bot_id)
        hst_orders = pd.DataFrame.from_records(hst_orders.values())
        
        if len(hst_orders)>0:
            order_ids = hst_orders['order_id'].unique().tolist()
            hst_orders['str_dt'] = hst_orders['datetime'].dt.strftime('%Y-%m-%d %H:%M')
            hst_orders = hst_orders[['str_dt', 'price', 'side','order_id']].copy()
            orders_data = []
            for order_id in order_ids:
                orders_data.append(hst_orders[hst_orders['order_id']==order_id].values.tolist())
                
            for i in orders_data:
                print(i)
        #Ordenes 
        open_pos = False
        db_trades = bot.get_orders()
        df_trades = pd.DataFrame.from_records(db_trades.values())
        df_trades['str_dt'] = df_trades['datetime'].dt.strftime('%Y-%m-%d %H:%M')
        trades_data = df_trades[df_trades['completed']>0][['str_dt', 'price', 'side']].copy()
        trades_data = trades_data.values.tolist()





        """
        #Indicadores
        indicators = []
        if len(botClass.indicadores)>0:
            for indicador in botClass.indicadores:
                if indicador['col'] in klines:
                    indicators.append(indicador)
        if not open_pos and 'close' in klines:
            klines['price'] = klines['close']
        """
    
    return render(request, 'bot.html',{
        'symbol': botClass.symbol,
        'title': str(bot),
        'nav_title': str(bot),
        'bot_id': bot.id,
        'estrategia': bot.estrategia.nombre,
        'descripcion': bot.estrategia.descripcion,
        'estrategia_activo': bot.estrategia.activo,
        'intervalo': intervalo,
        'estrategia_id': bot.estrategia.id,
        'activo': bot.activo,
        'creado': bot.creado,
        'quote_qty': round(bot.quote_qty,2),
        'quote_actual': round(quote_actual,2),
        'stop_loss': round(bot.stop_loss,2),
        'max_drawdown': round(bot.max_drawdown,2),
        'max_drawdown_reg': round(max_drawdown_reg,2),
        'can_delete': bot.can_delete(),
        'can_activar': bot.can_activar(),
        'parametros': bot.parse_parametros(),
        'trades': bot.get_trades(),
        'orders': bot.get_orders_en_curso(),
        'status': status,
        'pnl': pnl,
        'pnl_perc': pnl_perc,
        'environment_advertisement': environment_advertisement,
        'quote_asset': quote_asset,
        'log': bot.get_log(),
        'main_data': main_data,
        'orders_data': orders_data,
        'trades_data': trades_data,
        'open_pos': open_pos,
        'qd_price': symbol_info['qty_decs_price'],
    })

@login_required
def bot_create(request):
    json_rsp = {}
    if request.method == 'GET':
        intervals = fn.get_intervals().to_dict('records')
        symbols = Symbol.objects.filter(activo=1).order_by('symbol')
        return render(request, 'bot_edit.html',{
            'title': 'Crear Bot',
            'nav_title': 'Crear Bot',
            'intervals': intervals,
            'symbols': symbols,
            'estrategias': Estrategia.objects.filter(activo__gt=0),
            'bot_id': 0,
            'estrategia_id': 0,
        })
    else:
        bot = Bot()
        
        bot.estrategia_id=request.POST['estrategia_id']
        bot.quote_qty=request.POST['quote_qty']
        bot.max_drawdown=request.POST['max_drawdown']
        bot.stop_loss=request.POST['stop_loss']
        bot.usuario=request.user
        
        try:
            bot.full_clean()

            bot.save()
            json_rsp['ok'] = '/bot/bot/'+str(bot.id)

        except ValidationError as e:
            strError = ''
            for err in e:
                if err[0] != '__all__':
                    strError += '<br/><b>'+err[0]+'</b> '
                for desc in err[1]:
                    strError += desc+" "
            json_rsp['error'] = strError

        return JsonResponse(json_rsp)
        
@login_required
def get_parametros_estrategia(request,estrategia_id):
    json_rsp = {}
    estrategia = Estrategia.objects.get(pk=estrategia_id)
    parametros = estrategia.parse_parametros(),

    descripcion = estrategia.descripcion
    intervalo = fn.get_intervals(estrategia.interval_id,'name')
    json_rsp['ok'] = len(parametros)
    json_rsp['max_drawdown'] = estrategia.max_drawdown
    json_rsp['descripcion'] = descripcion
    json_rsp['intervalo'] = intervalo
    json_rsp['parametros'] = parametros
    return JsonResponse(json_rsp)



@login_required
def bot_edit(request,bot_id):
    json_rsp = {}
    bot = get_object_or_404(Bot, pk=bot_id,usuario=request.user)
    if request.method == 'GET':
        symbols = Symbol.objects.filter(activo=1).order_by('symbol')
        
        return render(request, 'bot_edit.html',{
            'title': 'Editar Bot '+str(bot),
            'nav_title': 'Editar Bot',
            'bot_id': bot.id,
            'symbols': symbols,
            'quote_qty': round(bot.quote_qty,2),
            'stop_loss': round(bot.stop_loss,2),
            'max_drawdown': round(bot.max_drawdown,2),
            'estrategia_id': bot.estrategia.id,
            'estrategias': Estrategia.objects.filter(Q(activo__gt=0) | Q(pk=bot.estrategia.id)),
            'activo': bot.activo,
        })
    else:

        bot.estrategia_id=request.POST['estrategia_id']
        bot.stop_loss=request.POST['stop_loss']
        bot.max_drawdown=request.POST['max_drawdown']
        bot.quote_qty=request.POST['quote_qty']

        try:
            bot.full_clean()

            bot.save()
            json_rsp['ok'] = '/bot/bot/'+str(bot.id)

        except ValidationError as e:
            strError = ''
            for err in e:
                if err[0] != '__all__':
                    strError += '<br/><b>'+err[0]+'</b> '
                for desc in err[1]:
                    strError += desc+" "
            json_rsp['error'] = strError

        return JsonResponse(json_rsp)

@login_required
def activar(request,bot_id):
    bot = get_object_or_404(Bot, pk=bot_id,usuario=request.user)
    if bot.can_activar():
        bot.activar()
    return redirect('/bot/bot/'+str(bot.id))
            
@login_required
def desactivar(request,bot_id,action):
    bot = get_object_or_404(Bot, pk=bot_id,usuario=request.user)
    intervalo = fn.get_intervals(bot.estrategia.interval_id,'name')
    status = eval(bot.status) if len(bot.status) > 0 else []

    quote_actual = bot.quote_qty
    if 'wallet_tot' in status: 
        quote_actual = status['wallet_tot']['r']
        del status['wallet_tot']

    #Avisos por entornos de ejecucion de TEST
    environment_advertisement = []
    usuario=request.user
    usuario_id = usuario.id
    profile = UserProfile.objects.get(user_id=usuario_id)
    profile_config = profile.parse_config()
    if profile_config['bnc']['bnc_env'] == 'test':
        environment_advertisement.append('El Bot se ejecuta en entorno de TEST')

    #### Creando grafica de la operacion del bot
    botClass = bot.get_instance()
    symbol_info = Exchange('info','bnc',prms=None).get_symbol_info(symbol=botClass.symbol)
    quote_asset = symbol_info['quote_asset']
    
    pnl = quote_actual-bot.quote_qty
    pnl_perc = (pnl/bot.quote_qty)*100
    
    ordenes_en_curso = bot.get_orders_en_curso()
    comprado = 0
    if 'wallet_base' in status:
        comprado = status['wallet_base']['r']
    
    if action == 'no_close' or (comprado == 0 and len(ordenes_en_curso) == 0):
        bot.desactivar(close=True)
        return redirect('/bot/bot/'+str(bot.id))
    if action == 'close':
        bot.desactivar(close=True)
        return redirect('/bot/bot/'+str(bot.id))


        
    return render(request, 'bot_desactivar.html',{
        'title': str(bot),
        'nav_title': str(bot),
        'bot_id': bot.id,
        'estrategia': bot.estrategia.nombre,
        'descripcion': bot.estrategia.descripcion,
        'estrategia_activo': bot.estrategia.activo,
        'intervalo': intervalo,
        'estrategia_id': bot.estrategia.id,
        'creado': bot.creado,
        'quote_qty': round(bot.quote_qty,2),
        'quote_actual': round(quote_actual,2),
        'stop_loss': round(bot.stop_loss,2),
        'max_drawdown': round(bot.max_drawdown,2),
        'parametros': bot.parse_parametros(),
        'orders': ordenes_en_curso,
        'status': status,
        'pnl': pnl,
        'pnl_perc': pnl_perc,
        'environment_advertisement': environment_advertisement,
        'quote_asset': quote_asset,
    })

@login_required
def bot_delete(request,bot_id):
    json_rsp = {}
    bot = get_object_or_404(Bot, pk=bot_id,usuario=request.user)
    if bot.can_delete():
        bot.delete()
        json_rsp['ok'] = True
    else:
        json_rsp['error'] = 'No es psible eliminar el Bot'
    return JsonResponse(json_rsp)
    
def get_resultados(request,bot_id):
    json_rsp = {}
    
    bot = get_object_or_404(Bot, pk=bot_id,usuario=request.user)
    if bot:
        json_rsp = bot.get_resultados()
    else:
        json_rsp['error'] = 'No existe el bot con ID: '+bot_id
    return JsonResponse(json_rsp)   
 
@login_required
def bot_order_echange_info(request,order_id):
    json_rsp = {}
    order = Order.objects.get(pk=order_id)

    usuario=request.user
    usuario_id = usuario.id
    profile = UserProfile.objects.get(user_id=usuario_id)
    profile_config = profile.parse_config()
    prms = {}
    prms['bnc_apk'] = profile_config['bnc']['bnc_apk']
    prms['bnc_aps'] = profile_config['bnc']['bnc_aps']
    prms['bnc_env'] = profile_config['bnc']['bnc_env']
            

    exch = Exchange(type='user_apikey',exchange='bnc',prms=prms)
    exch_order_info = exch.get_order(symbol=order.symbol.symbol,orderId=order.orderid)
    
    json_rsp['ok'] = True
    json_rsp['id'] = order.id

    for k in exch_order_info:
        if k == 'time':
            json_rsp[k] = exch_order_info[k].strftime('%d-%m-%Y %H:%M')+' Hs.'
        else:
            json_rsp[k] = exch_order_info[k]
    
    return JsonResponse(json_rsp)