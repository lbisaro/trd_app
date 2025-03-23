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
    #assets_brief_total_buyed = round(sum(data['buyed'] for data in assets_brief.values()),2)
    #assets_brief_total_cap   = round(sum(data['cap'] for data in assets_brief.values()),2)
    #assets_brief_result = round(((assets_brief_total_cap/assets_brief_total_buyed)-1)*100,2) if assets_brief_total_buyed != 0 else 0

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
        #'assets_brief_total_buyed': assets_brief_total_buyed,
        #'assets_brief_total_cap':   assets_brief_total_cap,
        #'assets_brief_result':   assets_brief_result,
    }

    return render(request, 'sw.html', data)

def view_orders(request, sw_id, symbol_id):
    sw = get_object_or_404(Sw, pk=sw_id, usuario=request.user)
    symbol = get_object_or_404(Symbol, pk=symbol_id)
    swo = sw.get_orders(symbol=symbol)

    #Buscando precios de los symbols
    exchInfo = Exchange(type='info',exchange='bnc',prms=None)
    prices = exchInfo.get_all_prices()
    actual_price = prices[symbol.base_asset+symbol.quote_asset]
    
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
                      'capital': True if o.is_capital > 0 else False
                      }
        orders.append(full_order)
        results = sw.calcular_rendimiento(symbol,orders,o.price)
        for k,v in results.items():
            full_order[k] = v
        full_order['valor_orden'] = round(full_order['qty']*full_order['price'],2)
        full_order['row_class'] = 'text-danger' if full_order['side'] == 1 else 'text-success'
        if full_order['capital'] and full_order['side'] == 0:
            full_order['capital_class'] = 'text-success'
        elif full_order['capital'] and full_order['side'] == 1:
            full_order['capital_class'] = 'text-danger'
        
        full_orders.append(full_order)

    #Analisis del resultado a la fecha
    results = sw.calcular_rendimiento(symbol,orders,actual_price)
    results['price'] = actual_price
    results['datetime'] = timezone.now()
    full_orders.append(results)


    #Obteniendo las velas del Symbol desde el inicio de las operaciones para adjuntar las ordenes
    klines = exchInfo.get_klines(symbol=symbol.base_asset+symbol.quote_asset,
                                 interval_id='2d01',
                                 limit=limit_days+1)
    klines['price'] = klines['close']
    df_orders = pd.DataFrame(full_orders[0:-1])
    df_orders["datetime"] = pd.to_datetime(df_orders["datetime"])
    df = pd.concat([klines, df_orders], ignore_index=True)
    df = df.sort_values(by="datetime")
    #df.set_index('datetime',inplace=True)


    # Guardar log del dataframe para su estudio
    LOG_DIR = os.path.join(settings.BASE_DIR,'log')
    DATA_FILE = os.path.join(LOG_DIR, f'SW_{sw.name}_{symbol.base_asset}.pkl')
    with open(DATA_FILE, "wb") as archivo:
            pickle.dump(df, archivo)
       
    #Ajustando valores del dataframe para charts
    #ffill
    df["stock_total"] = df["stock_total"].fillna(method="ffill")
    df["stock_quote"] = df["stock_quote"].fillna(method="ffill")
    df["valor_capital"] = df["valor_capital"].fillna(method="ffill")
    df["precio_promedio"] = df["precio_promedio"].fillna(method="ffill")
    df["ganancias_realizadas"] = df["ganancias_realizadas"].fillna(method="ffill")
    #Calculos
    df["valor_stock"] = df["stock_total"]*df['price'] 
    df['valor_actual_total'] = df['stock_quote'] + df['valor_stock']
    df["rendimiento_ganancias"] = (df["ganancias_realizadas"] / df['valor_capital'] )*100
    df["rendimiento_valor"] = (df["valor_actual_total"] / df['valor_capital'] - 1 )*100
    #Eventos
    df['buy'] = np.where((df['side']==0)&(df['capital'] == False),df['price'],None)
    df['sell'] = np.where((df['side']==1)&(df['capital'] == False),df['price'],None)
    df['aporte'] = np.where((df['side']==0)&(df['capital'] == True),df['price'],None)
    df['retiro'] = np.where((df['side']==1)&(df['capital'] == True),df['price'],None)

    #Creando Chart 
    chart_rows = 3
    row_heights=[300,150,150]
    total_height = sum(row_heights)

    fig = make_subplots(rows=chart_rows, 
                        shared_xaxes=True,
                        row_heights=row_heights)

    fig.add_trace(
            go.Scatter(
                x=df["datetime"], y=df["price"], name=f'{symbol.base_asset}{symbol.quote_asset}', mode="lines",  
                line={'width': 0.5},  
                marker=dict(color='gray'),
            ),
            row=1,
            col=1,
        )  
    fig.add_trace(
            go.Scatter(
                x=df["datetime"], y=df["precio_promedio"], name=f'Precio Promedio', mode="lines",  
                line={'width': 0.5},  
                marker=dict(color='#f8b935'),
            ),
            row=1,
            col=1,
        )  

    fig.add_trace(
            go.Scatter(x=df["datetime"], y=df['buy'], name='Compras', mode='markers', 
                    marker=dict(symbol='circle',size=4,color='#0ecb81',line=dict(width=0.75, color="black"),),
                    ),row=1,col=1,
    )
    fig.add_trace(
            go.Scatter(x=df["datetime"], y=df['sell'], name='Ventas', mode='markers', 
                    marker=dict(symbol='circle',size=4,color='#f6465d',line=dict(width=0.75, color="black"),),
                    ),row=1,col=1,
        )
    fig.add_trace(
            go.Scatter(x=df["datetime"], y=df['aporte'], name='Aportes', mode='markers', 
                    marker=dict(symbol='triangle-up',size=8,color='#0ecb81',line=dict(width=0.75, color="black"),),
                    ),row=1,col=1,
        )
    fig.add_trace(
            go.Scatter(x=df["datetime"], y=df['retiro'], name='Retiros', mode='markers', 
                    marker=dict(symbol='triangle-down',size=8,color='#f6465d',line=dict(width=0.75, color="black"),),
                    ),row=1,col=1,
        )


    fig.add_trace(
            go.Scatter(
                x=df["datetime"], y=df["ganancias_realizadas"], name=f'Ganancias', mode="lines",  
                line={'width': 0.5},  
                marker=dict(color='#0dcaf0'),
            ),
            row=2,
            col=1,
        )  
    fig.add_trace(
            go.Scatter(
                x=df["datetime"], y=df["valor_capital"], name=f'Capital', mode="lines",  
                line={'width': 0.5},  
                marker=dict(color='gray'),
            ),
            row=2,
            col=1,
        )  

    fig.add_trace(
            go.Scatter(
                x=df["datetime"], y=df["rendimiento_ganancias"], name=f'Ganancias (%)', mode="lines",  
                line={'width': 0.5},  
                marker=dict(color='#fcd535'),
            ),
            row=3,
            col=1,
        )  
    fig.add_trace(
            go.Scatter(
                x=df["datetime"], y=df["rendimiento_valor"], name=f'Valor (%)', mode="lines",  
                line={'width': 0.5},  
                marker=dict(color='#fd7e14'),
            ),
            row=3,
            col=1,
        )  

    # Adjust layout for subplots
    fig.update_layout(
        font=dict(color="#ffffff", family="Helvetica"),
        paper_bgcolor="rgba(0,0,0,0)",  # Transparent background
        plot_bgcolor="rgba(0,0,0,0)",  # Transparent plot area 
        height=total_height,
        xaxis_rangeslider_visible=False,
        modebar_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation = 'h',
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
    )

    #Ajustar el tamaño de cada sub_plot
    fig.update_layout(
        yaxis1=dict(title="Precio",showticklabels=True,
                    zeroline=False,),
        yaxis2=dict(title="USDT",showticklabels=True,),
        yaxis3=dict(title="(%)",showticklabels=True,),
    )
    fig.update_xaxes(showline=True, linewidth=0.5,linecolor='#40444e', gridcolor='#40444e')
    fig.update_yaxes(showline=False, linewidth=0.5, zeroline= False, linecolor='#40444e', gridcolor='rgba(40,40,40,10)')    
    chart = fig.to_html(config = {'scrollZoom': True, })
    
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
        json_rsp['error'] = 'No es psible eliminar la Smart Wallet'
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