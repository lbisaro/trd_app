from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError

import plotly.graph_objects as go
from plotly.subplots import make_subplots

import numpy as np
import pandas as pd


from bot.models import *
from bot.model_sw import *

@login_required
def list(request):
    sws = Sw.objects.filter(usuario=request.user).order_by('-activo') 
    formattedSw = []
    sw_assets = {}
    for sw in sws:
        assets = sw.get_assets()
        formattedSw.append({'sw_id':sw.id, 
                             'name': sw.name,
                             'assets': ", ".join(assets),
                             'activo': sw.activo,
                             'quote_asset': sw.quote_asset,
                             })
        for asset in assets:
            sw_assets[asset] = {}
        
    #Procesando PNL historico
    wallet_log = WalletLog.objects.filter(usuario=request.user).order_by('date')
    df = pd.DataFrame.from_records( wallet_log.values('date', 'total_usd') )
    df.rename(columns={'total_usd':'wallet'},inplace=True)

    wallet_capital = WalletCapital.objects.filter(usuario=request.user).order_by('date')
    df_cap = pd.DataFrame.from_records( wallet_capital.values('date', 'total_usd') )
    df_cap.rename(columns={'total_usd':'capital'},inplace=True)
    df_cap['capital_acum'] = df_cap['capital'].cumsum()
    df['capital'] = 0
    for i,row in df_cap.iterrows():
        date = row['date']
        capital = row['capital_acum']
        df['capital'][df['date']>=date] = capital

    df['date'] = pd.to_datetime(df['date'])
    df['pnl'] = df['wallet']-df['capital']
    df['str_date'] = df['date'].dt.strftime('%Y-%m-%d')

    #Obteniendo informacion de la wallet
    usuario=request.user
    usuario_id = usuario.id
    profile = UserProfile.objects.get(user_id=usuario_id)
    profile_config = profile.parse_config()
    prms = {}
    prms['bnc_apk'] = profile_config['bnc']['bnc_apk']
    prms['bnc_aps'] = profile_config['bnc']['bnc_aps']
    prms['bnc_env'] = profile_config['bnc']['bnc_env']
    exch = Exchange(type='user_apikey',exchange='bnc',prms=prms)      

    symbols = Symbol.objects.filter()
    for symbol in symbols:
        sw_assets[symbol.base_asset] = {
            'qd_qty': symbol.qty_decs_qty,
            'qd_price': symbol.qty_decs_price,
            'qd_quote': symbol.qty_decs_quote,
        }
    
    wallet_full = exch.get_wallet()
    wallet = {}
    for asset in wallet_full:
        free = wallet_full[asset]['free']
        locked = wallet_full[asset]['locked']
        total = free + locked

        tag = 'OTHERS'
        if Exchange.is_stable_coin(asset):
            tag = 'STABLE'
        elif Exchange.is_main_coin(asset):
            tag = 'MAIN'
        elif asset in sw_assets:
            tag = 'ALT'

        if total>0:
            wallet[asset] = {
                'free': free,
                'locked': locked,
                'total': total,
                'price': 0.0,
                'tag': tag,
                }

    prices = exch.get_all_prices()
    total_usd_assets = 0
    wallet_data = {}
    wallet_data['assets'] = {
        'STABLE': { 'tag_name': 'Stable Coins', 'total': 0.0, 'assets': {}} ,
        'MAIN': {   'tag_name': 'Main Coins',   'total': 0.0, 'assets': {}} ,
        'ALT': {    'tag_name': 'Alt Coins',    'total': 0.0, 'assets': {}} ,
        'OTHERS': { 'tag_name': 'Otros',        'total': 0.0, 'assets': {}} ,
    }
    for asset in wallet:
        if asset == 'USDT':
            price = 1.0
        elif asset+'USDT' in prices:
            price = prices[asset+'USDT']
        else:
            price = 0.0
        wallet[asset]['price'] = price
        tag = 'OTHERS'
        if wallet[asset]['tag'] in wallet_data['assets']:
            tag = wallet[asset]['tag']
        total_usd = price * wallet[asset]['total']
        total_usd_assets += total_usd
        if total_usd > 0:
            wallet_data['assets'][tag]['total'] += total_usd
            wallet_data['assets'][tag]['assets'][asset] = wallet[asset]

    for tag in wallet_data['assets']:
        wallet_data['assets'][tag]['total'] =  round(wallet_data['assets'][tag]['total'],2)
        perc = (wallet_data['assets'][tag]['total'] / total_usd_assets) * 100
        wallet_data['assets'][tag]['perc'] = round(perc,2)
        for asset in wallet_data['assets'][tag]['assets']:
            qd_qty = 8
            if asset in sw_assets and 'qd_qty' in sw_assets[asset]:
                qd_qty = sw_assets[asset]['qd_qty']
            if Exchange.is_stable_coin(asset):
                qd_qty = 2
            wallet_data['assets'][tag]['assets'][asset]['free_usd'] = round(wallet_data['assets'][tag]['assets'][asset]['free']*wallet_data['assets'][tag]['assets'][asset]['price'],2)
            wallet_data['assets'][tag]['assets'][asset]['locked_usd'] = round(wallet_data['assets'][tag]['assets'][asset]['locked']*wallet_data['assets'][tag]['assets'][asset]['price'],2)
            wallet_data['assets'][tag]['assets'][asset]['total_usd'] = round(wallet_data['assets'][tag]['assets'][asset]['total']*wallet_data['assets'][tag]['assets'][asset]['price'],2)
            wallet_data['assets'][tag]['assets'][asset]['free'] = round(wallet_data['assets'][tag]['assets'][asset]['free'],qd_qty)
            wallet_data['assets'][tag]['assets'][asset]['locked'] = round(wallet_data['assets'][tag]['assets'][asset]['locked'],qd_qty)
            wallet_data['assets'][tag]['assets'][asset]['total'] = round(wallet_data['assets'][tag]['assets'][asset]['total'],qd_qty)
    
    df['str_dt'] = df['date'].dt.strftime('%Y-%m-%d')
    pnl_data = df[['str_date', 'pnl']].copy()
    pnl_data = pnl_data.values.tolist()

    if request.method == 'GET':
        return render(request, 'sws.html',{
            'sws': formattedSw,
            'wallet_data': wallet_data,
            'pnl_data': pnl_data,
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
    
    df["unrealized_pnl"] = df["open_quantity"] * df["price"] - df["open_quantity"] * df["average_buy_price"]
    
    df["total_pnl"] = df["realized_pnl"] + df["unrealized_pnl"]

    #ajustes
    df['average_buy_price'] = np.where(df['average_buy_price']!=0,df['average_buy_price'],None)

    #Calculos
    df["valor_stock"] = df["open_quantity"]*df['price'] 
    
    #Eventos
    df['buy']  = np.where((df['side']==0),df['price'],None)
    df['sell'] = np.where((df['side']==1),df['price'],None)

        
    # Guardar log del dataframe para su estudio
    LOG_DIR = os.path.join(settings.BASE_DIR,'log')
    DATA_FILE = os.path.join(LOG_DIR, f'SW_{sw.name}_{symbol.base_asset}.pkl')
    with open(DATA_FILE, "wb") as archivo:
            pickle.dump(df, archivo)

    #Creando Chart 
    chart_rows = 2
    row_heights=[250,250]
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

@login_required
def capital(request):
    capital = WalletCapital.objects.filter(usuario=request.user).order_by('date')
    
    return render(request, 'sw_capital.html', {
        'capital': capital,
        'today': datetime.now().date().strftime("%d-%m-%Y")
    })

@login_required
def capital_registrar(request):

    json_rsp = {}
    if request.method == 'POST':
    
        capital = WalletCapital()
        total_usd = float(request.POST['total_usd'])
        date = datetime.strptime(request.POST['date'], '%d-%m-%Y').date()
        reference = request.POST['reference']
        if date > datetime.now().date():
            json_rsp['error'] = 'La fecha no puedde ser posterior a la actual'
        if total_usd == 0:
            json_rsp['error'] = 'El Capital debe ser distinto de 0'
        if len(reference) == 0:
            json_rsp['error'] = 'Se ebe especificar un texto de referencia'

        if not 'error' in json_rsp:
        
            capital.usuario = request.user
            capital.date = date
            capital.total_usd = total_usd
            capital.reference=reference

            try:
                capital.full_clean()

                capital.save()
                json_rsp['ok'] = True
                json_rsp['redirect'] = '/bot/sw/capital/'

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
def capital_eliminar(request,capital_log_id):
    json_rsp = {}
    capital = get_object_or_404(WalletCapital, pk=capital_log_id,usuario=request.user)
    if capital.delete():
        json_rsp['ok'] = True
    else:
        json_rsp['error'] = 'No es posible eliminar el registro'
    return JsonResponse(json_rsp)
