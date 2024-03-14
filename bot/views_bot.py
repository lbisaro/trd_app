from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q
import scripts.functions as fn
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.template import RequestContext
import numpy as np

from bot.models import *
from bot.model_kline import *
from user.models import UserProfile
from scripts.functions import ohlc_chart 
import local__config as local
from scripts.Bot_Core_utils import Order as ord_u

@login_required
def bots(request):
    bots = Bot.objects.filter(usuario=request.user).order_by('-activo','estrategia__nombre') 
    formattedBots = []
    for b in bots:
        intervalo = fn.get_intervals(b.estrategia.interval_id,'name')
        formattedBots.append({'bot_id':b.id, 
                             'estrategia':b.estrategia.nombre,
                             'estrategia_activo':b.estrategia.activo,
                             'quote_qty': round(b.quote_qty,2),
                             'usuario': b.usuario,
                             'intervalo': intervalo,
                             'activo': b.activo,
                             })
    if request.method == 'GET':
        return render(request, 'bots.html',{
            'bots': formattedBots,
        })

@login_required
def bot(request, bot_id):
    bot = get_object_or_404(Bot, pk=bot_id,usuario=request.user)
    intervalo = fn.get_intervals(bot.estrategia.interval_id,'name')
    status = eval(bot.status) if len(bot.status) > 0 else []

    #Avisos por entornos de ejecucion de TEST
    environment_advertisement = []
    #Entorno General
    if local.LOC_BNC_TESNET:
        environment_advertisement.append('El analisis de estrategias se ejecuta en entorno de TEST')
    #Entorno de usuario
    usuario=request.user
    usuario_id = usuario.id
    profile = UserProfile.objects.get(user_id=usuario_id)
    profile_config = profile.parse_config()
    if profile_config['bnc']['bnc_env'] == 'test':
        environment_advertisement.append('El Bot se ejecuta en entorno de TEST')

    #Creando grafica de la operacion del bot
    botClass = bot.get_instance()
    klines = bot.get_pnl()
    klines.drop(columns=['id', 'bot_id'],inplace=True)
    ultimo_registro = klines.iloc[-1,:]
    nuevo_registro = pd.DataFrame({
        "datetime": [datetime.now()],
        "price": [ultimo_registro["price"]],
        "pnl": [ultimo_registro["pnl"]]
    })
    klines = pd.concat([klines, nuevo_registro], ignore_index=True)

    #Ordenes 
    db_orders = bot.get_orders()
    df_orders = pd.DataFrame.from_records(db_orders.values())
    #Ordenes Ejecutadas
    df_orders['buy']     = df_orders[(df_orders['side'] == ord_u.SIDE_BUY) &(df_orders['completed']>0)&(df_orders['type']==ord_u.FLAG_SIGNAL)]['price']
    df_orders['sell']    = df_orders[(df_orders['side'] == ord_u.SIDE_SELL)&(df_orders['completed']>0)&(df_orders['type']==ord_u.FLAG_SIGNAL)]['price']
    df_orders['buy_tp']  = df_orders[(df_orders['side'] == ord_u.SIDE_BUY) &(df_orders['completed']>0)&(df_orders['type']==ord_u.FLAG_TAKEPROFIT)]['price']
    df_orders['sell_tp'] = df_orders[(df_orders['side'] == ord_u.SIDE_SELL)&(df_orders['completed']>0)&(df_orders['type']==ord_u.FLAG_TAKEPROFIT)]['price']
    df_orders['buy_sl']  = df_orders[(df_orders['side'] == ord_u.SIDE_BUY) &(df_orders['completed']>0)&(df_orders['type']==ord_u.FLAG_STOPLOSS)]['price']
    df_orders['sell_sl'] = df_orders[(df_orders['side'] == ord_u.SIDE_SELL)&(df_orders['completed']>0)&(df_orders['type']==ord_u.FLAG_STOPLOSS)]['price']
    
    #Ordenes Abiertas
    open_orders = []
    for i in df_orders[df_orders['completed']<1].index:
        row = df_orders.iloc[i]
        key = 'OPEN_'+str(row['id'])
        color = 'red' if row['side'] == ord_u.SIDE_SELL else 'green'
        klines[key] = np.where(klines['datetime']>=row['datetime'],row['limit_price'],None)
        open_orders.append({'col': key,'color': color,})
        

    print(klines.head())
    print(klines.tail())
    df_orders.drop(columns=['id', 'bot_id', 'completed', 'qty', 'price', 'orderid',
       'pos_order_id', 'symbol_id', 'side', 'flag', 'type', 'limit_price',
       'activation_price', 'active', 'trail_perc', 'tag'],inplace=True)
    






    events = []
    if df_orders['buy'].count() > 0:
        events.append({'df':df_orders,'col':'buy'    ,'name': 'BUY' ,    'color': 'green','symbol': 'circle' })
    if df_orders['sell'].count() > 0:
        events.append({'df':df_orders,'col':'sell'   ,'name': 'SELL',    'color': 'red',  'symbol': 'circle' })
    if df_orders['buy_tp'].count() > 0:
        events.append({'df':df_orders,'col':'buy_tp' ,'name': 'BUY-TP' , 'color': 'green','symbol': 'triangle-up' })
    if df_orders['sell_tp'].count() > 0:
        events.append({'df':df_orders,'col':'sell_tp','name': 'SELL-TP', 'color': 'red',  'symbol': 'triangle-up' })
    if df_orders['buy_sl'].count() > 0:
        events.append({'df':df_orders,'col':'buy_sl' ,'name': 'BUY-SL' , 'color': 'green','symbol': 'triangle-down' })
    if df_orders['sell_sl'].count() > 0:
        events.append({'df':df_orders,'col':'sell_sl','name': 'SELL-SL', 'color': 'red',  'symbol': 'triangle-down' })
    


    fig = ohlc_chart(klines, open_orders=open_orders, events=events)
    chart = fig.to_html(config = {'scrollZoom': True, }) 


    return render(request, 'bot.html',{
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
        'stop_loss': round(bot.stop_loss,2),
        'max_drawdown': round(bot.max_drawdown,2),
        'can_delete': bot.can_delete(),
        'can_activar': bot.can_activar(),
        'parametros': bot.parse_parametros(),
        'trades': bot.get_trades(),
        'orders': bot.get_orders_en_curso(),
        'status': status,
        'environment_advertisement': environment_advertisement,
        #'resultados': bot.get_resultados(),
        'log': bot.get_log(),
        'chart': chart,
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
def bot_toogle_activo(request,bot_id):
    bot = get_object_or_404(Bot, pk=bot_id,usuario=request.user)
    if bot.activo > 0:
        bot.desactivar()
    elif bot.can_activar():
        bot.activar()
            
    return redirect('/bot/bot/'+str(bot.id))
 
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