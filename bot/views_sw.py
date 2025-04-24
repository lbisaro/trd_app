from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError

import plotly.graph_objects as go
from plotly.subplots import make_subplots

import numpy as np


from bot.models import *
from bot.model_sw import *

@login_required
def list(request):
    sws = Sw.objects.filter(usuario=request.user).order_by('-activo') 
    formattedSw = []
    for sw in sws:
        assets = sw.get_assets()
        formattedSw.append({'sw_id':sw.id, 
                             'name': sw.name,
                             'assets': ", ".join(assets),
                             'activo': sw.activo,
                             'quote_asset': sw.quote_asset,
                             })
    if request.method == 'GET':
        return render(request, 'sws.html',{
            'sws': formattedSw,
        })

@login_required
def create(request):

    json_rsp = {}
    if request.method == 'GET':
        return render(request, 'sw_edit.html',{
            'title': 'Crear Smart Wallet',
            'nav_title': 'Crear Smart Wallet',
            'quote_asset': 'USDT',
        })
    else:
        sw = Sw()
        
        sw.usuario = request.user
        sw.estado = 0
        sw.creado = timezone.now()
        sw.quote_asset=request.POST['quote_asset']
        sw.name=request.POST['name']

        try:
            sw.full_clean()

            sw.save()
            json_rsp['ok'] = f'/sw/view/{sw.id}'

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
def view(request, sw_id):
    sw = get_object_or_404(Sw, pk=sw_id, usuario=request.user)
    swo = sw.get_orders()

    assets = sw.get_assets()

    assets_brief = sw.get_assets_brief()
    total_realized_pnl = round(sum(data['realized_pnl'] for data in assets_brief.values()),2)
    total_unrealized_pnl = round(sum(data['unrealized_pnl'] for data in assets_brief.values()),2)
    total_total_pnl = round(sum(data['total_pnl'] for data in assets_brief.values()),2)

    #Configurando el estado del SW en la DDBB de acuerdo a la informacion registrada
    act_estado = sw.estado
    new_estado = act_estado
    if len(swo) > 0:
        if act_estado != sw.ESTADO_ERROR and act_estado != sw.ESTADO_STOPPED and act_estado != sw.ESTADO_STANDBY:
            new_estado = sw.ESTADO_ONLINE
    else:
        new_estado = sw.ESTADO_NODATA
    if act_estado != new_estado:
        sw.estado = new_estado
        sw.save()

    data = {
        'title': f'Smart Wallet {sw.name}',
        'nav_title': f'Smart Wallet {sw.name}',
        'name': sw.name,
        'sw_id': sw.id,
        'quote_asset': sw.quote_asset,
        'str_estado': sw.str_estado(),
        'estado_class': sw.estado_class(),
        'activo': sw.activo,
        'assets': ", ".join(assets),
        'creado': sw.creado,
        'finalizado': sw.finalizado,
        'can_activar': sw.can_activar(),
        'can_delete': sw.can_delete(),
        'assets_brief': assets_brief,
        'total_realized_pnl': total_realized_pnl,
        'total_unrealized_pnl': total_unrealized_pnl,
        'total_total_pnl': total_total_pnl,
    }

    return render(request, 'sw.html', data)

def add_trades_empty(request, sw_id):
    sw = get_object_or_404(Sw, pk=sw_id, usuario=request.user)
    symbols = Symbol.objects.filter(quote_asset=sw.quote_asset).order_by('symbol')

    data = {
        'title': f'Smart Wallet {sw.name} - Agregar Ordenes',
        'nav_title': f'Smart Wallet {sw.name} - Agregar Ordenes',
        'sw_id': sw.id,
        'name': sw.name,
        'symbols': symbols,
        'sw': sw,
        
    }
    return render(request, 'sw_add_trades.html', data)    

def add_trades(request, sw_id, symbol_id):
    sw = get_object_or_404(Sw, pk=sw_id, usuario=request.user)

    symbol = get_object_or_404(Symbol, pk=symbol_id)
    swo = sw.get_orders(symbol=symbol)

    data = {
        'title': f'Smart Wallet {sw.name} - Agregar Ordenes',
        'nav_title': f'Smart Wallet {sw.name} - Agregar Ordenes',
        'sw_id': sw.id,
        'symbol_id': symbol.id,
        'name': sw.name,
        'sw': sw,
        'symbol': symbol,
        
    }
    return render(request, 'sw_add_trades.html', data)

def view_orders(request, sw_id, symbol_id):
    sw = get_object_or_404(Sw, pk=sw_id, usuario=request.user)
    symbol = get_object_or_404(Symbol, pk=symbol_id)
    swo = sw.get_orders(symbol=symbol)

    orders = []
    full_orders = []
    limit_days = 0
    for o in swo:
        if limit_days == 0:
            limit_days = (timezone.now() - o.datetime).days
        full_order = {'datetime':o.datetime,
                      'qty':o.qty, 
                      'price': o.price,
                      'side':o.side,
                      }
        orders.append(full_order)
        results = sw.get_asset_brief(symbol,orders,o.price)
        for k,v in results.items():
            full_order[k] = v
        full_order['valor_orden'] = round(full_order['qty']*full_order['price'],2)
        full_order['row_class'] = 'text-danger' if full_order['side'] == 1 else 'text-success'
        
        full_orders.append(full_order)
    
    #Obteniendo las velas del Symbol desde el inicio de las operaciones para adjuntar las ordenes
    exchInfo = Exchange(type='info',exchange='bnc',prms=None)
    klines = exchInfo.get_klines(symbol=symbol.base_asset+symbol.quote_asset,
                                 interval_id='2d01',
                                 limit=limit_days+1)
    actual_price = klines.iloc[-1]['close']

    #Analisis del resultado a la fecha
    results = sw.get_asset_brief(symbol,orders,actual_price)
    results['price'] = actual_price
    results['datetime'] = timezone.now()
    full_orders.append(results)

    #Unificando ordenes con klines 
    klines['price'] = klines['close']
    df_orders = pd.DataFrame(full_orders[0:-1])
    df_orders["datetime"] = pd.to_datetime(df_orders["datetime"])
    df = pd.concat([klines, df_orders], ignore_index=True)
    df = df.sort_values(by="datetime")
       
    #Ajustando valores del dataframe para charts
    #ffill
    df["open_quantity"] = df["open_quantity"].fillna(method="ffill")
    df["average_buy_price"] = df["average_buy_price"].fillna(method="ffill")
    df["realized_pnl"] = df["realized_pnl"].fillna(method="ffill")
    df["unrealized_pnl"] = df["unrealized_pnl"].fillna(method="ffill")
    df["total_pnl"] = df["total_pnl"].fillna(method="ffill")

    #ajustes
    df['average_buy_price'] = np.where(df['average_buy_price']!=0,df['average_buy_price'],None)

    #Calculos
    df["valor_stock"] = df["open_quantity"]*df['price'] 
    #df['total_stock_en_usd'] = df['stock_quote'] + df['valor_stock']
    #df['ganancias_y_stock'] = df['total_stock_en_usd'] + df['ganancias_realizadas']
    df["distancia_ppc"] = (df["price"] / df['average_buy_price'] - 1 )*100

    #Eventos
    df['buy']  = np.where((df['side']==0),df['price'],None)
    df['sell'] = np.where((df['side']==1),df['price'],None)

        
    # Guardar log del dataframe para su estudio
    LOG_DIR = os.path.join(settings.BASE_DIR,'log')
    DATA_FILE = os.path.join(LOG_DIR, f'SW_{sw.name}_{symbol.base_asset}.pkl')
    with open(DATA_FILE, "wb") as archivo:
            pickle.dump(df, archivo)

    #Creando Chart 
    chart_rows = 3
    row_heights=[250,250,100]
    total_height = sum(row_heights)

    fig = make_subplots(rows=chart_rows, 
                        shared_xaxes=True,
                        row_heights=row_heights,
                        )

    fig.add_trace(
            go.Scatter(
                x=df["datetime"], y=df["price"], name=f'{symbol.base_asset}{symbol.quote_asset}', mode="lines",  
                line={'width': 0.75},  
                marker=dict(color='gray'),
                legendgroup = '1',
            ),
            row=1,
            col=1,
        )  
    fig.add_trace(
            go.Scatter(
                x=df["datetime"], y=df["average_buy_price"], name=f'Precio Promedio', mode="lines",  
                line={'width': 1},  
                marker=dict(color='#f8b935'),
                legendgroup = '1',
            ),
            row=1,
            col=1,
        )  

    fig.add_trace(
            go.Scatter(x=df["datetime"], y=df['buy'], name='Compras', mode='markers', 
                    marker=dict(symbol='circle',size=6,color='#0ecb81',line=dict(width=0.75, color="black"),),
                    legendgroup = '1',
                    ),row=1,col=1,
    )
    fig.add_trace(
            go.Scatter(x=df["datetime"], y=df['sell'], name='Ventas', mode='markers', 
                    marker=dict(symbol='circle',size=6,color='#f6465d',line=dict(width=0.75, color="black"),),
                    legendgroup = '1',
                    ),row=1,col=1,
        )

    fig.add_trace(
            go.Scatter(
                x=df["datetime"], y=df["realized_pnl"], name=f'Ganancias Realizadas', mode="lines",  
                line={'width': 0.75},  
                marker=dict(color='#0dcaf0'),
                legendgroup = '2',
            ),
            row=2,
            col=1,
        )  

    fig.add_trace(
            go.Scatter(
                x=df["datetime"], y=df["unrealized_pnl"], name=f'Ganancias No Realizadas', mode="lines",  
                line={'width': 0.75},  
                marker=dict(color='#fcd535'),
                legendgroup = '2',
            ),
            row=2,
            col=1,
        )  

    fig.add_trace(
            go.Scatter(
                x=df["datetime"], y=df["total_pnl"], name=f'Ganancias Totales', mode="lines",  
                line={'width': 1},  
                marker=dict(color='green'),
                legendgroup = '2',
            ),
            row=2,
            col=1,
        )  

    fig.add_trace(
            go.Scatter(
                x=df["datetime"], y=df["distancia_ppc"], name=f'Precio / P.Promedio', mode="lines",  
                line={'width': 1},  
                marker=dict(color='#fcd535'),
                legendgroup = '3',
            ),
            row=3,
            col=1,
        )  


    # Adjust layout for subplots
    fig.update_layout(
        font=dict(color="#ffffff", family="Helvetica"),
        paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
        plot_bgcolor="#162024",  
        height=total_height,
        xaxis_rangeslider_visible=False,
        modebar_bgcolor="rgba(0,0,0,0)",
        legend_tracegroupgap = 100,
    )

    #Ajustar el tamaño de cada sub_plot
    fig.update_layout(
        yaxis1=dict(title="Precio",showticklabels=True,
                    zeroline=False,),
        yaxis2=dict(title="USDT",showticklabels=True,),
        yaxis3=dict(title="(%)",showticklabels=True,),
    )
    fig.update_xaxes(showline=False, linewidth=2,linecolor='#000000', gridcolor='rgba(0,0,0,0)')
    fig.update_yaxes(showline=False, linewidth=2, zeroline= False, linecolor='#ff0000', gridcolor='rgba(50,50,50,255)')     
    chart = fig.to_html(config = {'scrollZoom': True, }) #'displayModeBar': False
    
    data = {
        'title': f'Smart Wallet {sw.name} - {symbol.base_asset}',
        'nav_title': f'Smart Wallet {sw.name} - {symbol.base_asset}',
        'name': sw.name,
        'sw_id': sw.id,
        'symbol_id': symbol.id,
        'symbol': symbol,
        'full_orders': full_orders,
        'chart': chart,


    }

    return render(request, 'sw_view_orders.html', data)

@login_required
def activar(request,sw_id):
    sw = get_object_or_404(Sw, pk=sw_id,usuario=request.user)
    sw.activar()
    json_rsp = {}
    json_rsp['ok'] = True
    return JsonResponse(json_rsp)
            
@login_required
def desactivar(request,sw_id,action):
    sw = get_object_or_404(Sw, pk=sw_id,usuario=request.user)
    sw.desactivar()
    json_rsp = {}
    json_rsp['ok'] = True
    return JsonResponse(json_rsp)

@login_required
def delete(request,sw_id):
    json_rsp = {}
    sw = get_object_or_404(Sw, pk=sw_id,usuario=request.user)
    if sw.can_delete():
        sw.delete()
        json_rsp['ok'] = True
    else:
        json_rsp['error'] = 'No es posible eliminar la Smart Wallet'
    return JsonResponse(json_rsp)


@login_required
def get_orders(request,symbol_id):
    json_rsp = {}
    symbol = get_object_or_404(Symbol, pk=symbol_id)
    symbol_orders = SwOrder.objects.filter(symbol=symbol)
    check_orderid = {}
    for so in symbol_orders:
        check_orderid[so.orderid] = so

    usuario=request.user
    usuario_id = usuario.id
    profile = UserProfile.objects.get(user_id=usuario_id)
    profile_config = profile.parse_config()
    prms = {}
    prms['bnc_apk'] = profile_config['bnc']['bnc_apk']
    prms['bnc_aps'] = profile_config['bnc']['bnc_aps']
    prms['bnc_env'] = profile_config['bnc']['bnc_env']
    exch = Exchange(type='user_apikey',exchange='bnc',prms=prms)

    bnc_orders = exch.get_all_orders(symbol=symbol.base_asset+symbol.quote_asset)
    orders = []
    for o in bnc_orders:
        if o['status'] == 'FILLED':
            info = {}
            info['symbol'] = o['symbol']
            info['datetime'] = o['time'].strftime('%d/%m/%Y %H:%M')
            info['side'] = 0 if o['side'] == 'BUY' else 1
            info['qty'] = o['qty']
            info['price'] = o['price']
            info['orderid'] = str(o['orderId'])
            info['completed'] = 1 
            info['exists'] = 1 if info['orderid'] in check_orderid else 0
            orders = [info] + orders #Agrega elementos al inicio            


    json_rsp['ok'] = True
    json_rsp['qd_qty'] = symbol.qty_decs_qty
    json_rsp['qd_price'] = symbol.qty_decs_price
    json_rsp['orders'] = orders

    return JsonResponse(json_rsp)

@login_required
def add_order(request,sw_id):
    json_rsp = {}
    sw = get_object_or_404(Sw, pk=sw_id,usuario=request.user)
    symbol = get_object_or_404(Symbol, pk=int(request.POST['symbol_id']))
    order = SwOrder()

    order.sw = sw
    order.symbol = symbol
    order.datetime = (dt.datetime.strptime(request.POST['datetime'], "%d/%m/%Y %H:%M") )
    order.side = int(request.POST['side'])
    order.qty = float(request.POST['qty'])
    order.price = float(request.POST['price'])
    order.orderid = request.POST['orderid']

    order.full_clean()
    order.save()

    json_rsp['ok'] = True
    json_rsp['go_to'] = True
    return JsonResponse(json_rsp)
"""        
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
"""
