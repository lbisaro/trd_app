from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
import requests
import json

import plotly.graph_objects as go

import numpy as np
from datetime import datetime, timedelta
import time

from scripts.crontab_futures_alerts import DATA_FILE, KLINES_TO_GET_ALERTS, INTERVAL_ID, load_data_file, ohlc_from_prices, alert_add_data
from scripts.Exchange import Exchange
from scripts.functions import get_intervals
from scripts.indicators import technical_summary, contar_decimales, resample, supertrend, zigzag
import pandas_ta as ta 
from bot.models import *
from bot.model_sw import *
from binance.exceptions import BinanceAPIException, BinanceOrderException



@login_required
def list(request):

    data = load_data_file(DATA_FILE)
    qty_symbols = len(data['symbols'])
    updated = data['updated']
    proc_duration = data['proc_duration']
    analized_symbols = data['analized_symbols']
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
    
    k_to_delete = []
    for k in log_alerts:
        log_alerts[k] = alert_add_data(log_alerts[k],actual_prices[log_alerts[k]['symbol']])
        if 'status_class' in log_alerts[k] and log_alerts[k]['status_class'] != 'status_ok':
            k_to_delete.append(k)
    ##Eliminando Alertas que estan fuera de rango
    #for k in k_to_delete:
    #    del(log_alerts[k])

    if 'c_1m' in data['symbols']['BTCUSDT']:
        qty_c_1m = len(data['symbols']['BTCUSDT']['c_1m'])
    else:
        qty_c_1m = 0

    return render(request, 'alerts_list.html',{
        'DATA_FILE': DATA_FILE ,
        'qty_symbols': qty_symbols ,
        'analized_symbols': analized_symbols ,
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
        alert['name'] = alert['symbol']+' '+alert['timeframe']+' '+alert['origin']
        
        interval_id = INTERVAL_ID
        interval_minutes = get_intervals(interval_id,'minutes')
        ahora = datetime.now()

        exchInfo = Exchange(type='info',exchange='bnc',prms=None)
        start_str = (ahora - timedelta(minutes=15*200)).strftime("%Y-%m-%d")
        klines = exchInfo.get_futures_klines(alert['symbol'],interval_id,start_str=start_str)
        exchPrice = klines.iloc[-1]['close']
        
        qty_decs_price = contar_decimales(exchPrice)

        alert = alert_add_data(alert, actual_price=exchPrice)
        alert['start_dt'] = (alert['start']- timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
        alert['actual_price'] = exchPrice       
        alert['qty_decs_price'] = qty_decs_price       
        
        ia_prompt = get_ia_prompt(alert,klines)
        
        return render(request, 'alerts_analyze.html',{
            'DATA_FILE': DATA_FILE ,
            'key': key,
            'alert': alert,
            'ia_prompt': ia_prompt,
            'actual_price': exchPrice,
            'qty_decs_price': qty_decs_price,
            'json_klines': klines.to_json(orient='records'),
        })


    else:
        return render(request, 'alerts_analyze.html',{}) 

@login_required
def execute(request):
    json_rsp = {}

    symbol = request.POST['symbol']
    side = int(request.POST['side'])
    in_price = float(request.POST['in_price'])
    tp1 = float(request.POST['tp1'])
    sl1 = float(request.POST['sl1'])
    quote_qty = round(float(request.POST['quote_qty']),2)
    leverage = 1
    margin_type = 'ISOLATED'
    
    
    #Preparando el trade
    usuario=request.user
    usuario_id = usuario.id
    profile = UserProfile.objects.get(user_id=usuario_id)
    profile_config = profile.parse_config()
    prms = {}
    prms['bnc_apk'] = profile_config['bnc']['bnc_apk']
    prms['bnc_aps'] = profile_config['bnc']['bnc_aps']
    prms['bnc_env'] = profile_config['bnc']['bnc_env']
    exch = Exchange(type='user_apikey',exchange='bnc',prms=prms)
    client = exch.client

    #Configura margen y apalancamiento.
    print(f"\n--- Configurando Entorno para {symbol} ---")
    try:
        client.futures_change_margin_type(symbol=symbol, marginType=margin_type)
        print(f"Tipo de Margen para {symbol} configurado a {margin_type}.")
    except BinanceAPIException as e:
        if e.code == -4046: print(f"Margen ya estaba configurado a {margin_type}.")
        else: raise # Re-lanzar la excepción para ser capturada por el bloque try principal    
    client.futures_change_leverage(symbol=symbol, leverage=leverage)

    #Obtiene información del símbolo (precisiones, mínimos).
    symbol_info = exch.get_futures_symbol_info(symbol)
    qd_price = symbol_info['qty_decs_price']
    qd_qty = symbol_info['qty_decs_qty']
    qd_quote = symbol_info['qty_decs_quote']
    #json_rsp['symbol_info'] = symbol_info

    #Calcula la cantidad para la orden MARKET de 100 USDT.
    ticker = client.futures_symbol_ticker(symbol=symbol)
    current_price = float(ticker['price'])
    json_rsp['current_price'] = current_price
    if current_price <= 0:
        json_rsp['error'] = "No fue posible obtener el precio actual"
        return json_rsp
    base_qty = round(quote_qty / current_price, qd_qty)
    if base_qty*current_price < 10:
        json_rsp['error'] = "El monto a comprar debe ser mayor a 10 USDT"
        return json_rsp
    
    #Verificando el precio actual vs SL y TP
    if side > 0:
        if current_price > tp1 or current_price < sl1:
            json_rsp['error'] = f'El precio actual ({current_price}) se encuentra fuera del rango del TakeProfit y el StopLoss'
            return json_rsp
    else:
        if current_price < tp1 or current_price > sl1:
            json_rsp['error'] = f'El precio actual ({current_price}) se encuentra fuera del rango del TakeProfit y el StopLoss'
            return json_rsp
            
    #Coloca la orden MARKET.
    print(f"\nColocando orden MARKET")
    market_order = client.futures_create_order(
        symbol=symbol,
        side=client.SIDE_BUY if side > 0 else client.SIDE_SELL,
        type=client.FUTURE_ORDER_TYPE_MARKET,
        quantity=base_qty
    )
    order_id = market_order['orderId']
    json_rsp['order_id'] = order_id
    json_rsp['base_qty'] = base_qty

    #Espera a que la orden MARKET se llene y obtiene el precio de entrada y cantidad ejecutada.
    order_filled = False
    start_time = time.time()
    timeout_seconds = 60
    while time.time() - start_time < timeout_seconds:
        order_status = client.futures_get_order(symbol=symbol, orderId=order_id)
        if order_status['status'] == 'FILLED':
            entry_price = float(order_status['avgPrice'])
            executed_qty_str = order_status['executedQty'] # Usar la cantidad real ejecutada
            executed_qty = round(float(executed_qty_str),qd_qty)
            json_rsp['executed_qty'] = executed_qty_str
            if entry_price == 0 and float(order_status['cumQuote']) > 0 and float(executed_qty_str) > 0:
                    entry_price = float(order_status['cumQuote']) / float(executed_qty_str)
            
            print(f"\n¡Orden MARKET [{order_id}] ejecutada!")
            print(f"  Cantidad Ejecutada: {executed_qty_str} {symbol[:-4]}")
            print(f"  Precio Promedio Entrada: {round(entry_price, qd_price)} USDT")
            order_filled = True
            break
        elif order_status['status'] in ['CANCELED', 'EXPIRED', 'REJECTED', 'PARTIALLY_CANCELED']:
            print(f"Error: Orden MARKET [{order_id}] no completada. Status: {order_status['status']}")
            return json_rsp
        print(f"Esperando ejecución de la orden MARKET [{order_id}]... Status: {order_status['status']}")
        time.sleep(2)
    
    if not order_filled or entry_price is None or entry_price <= 0 or executed_qty_str is None or float(executed_qty_str) <= 0:
        print(f"Error: Orden MARKET [{order_id}] no se confirmó como FILLED o datos inválidos.")
        # Considerar cancelar si aún está pendiente
        try:
            status_check = client.futures_get_order(symbol=symbol, orderId=order_id)
            if status_check['status'] == 'NEW' or status_check['status'] == 'PARTIALLY_FILLED':
                client.futures_cancel_order(symbol=symbol, orderId=order_id)
                print(f"Orden MARKET [{order_id}] pendiente cancelada.")
        except Exception as e_cancel:
            print(f"Error al intentar cancelar orden MARKET pendiente: {e_cancel}")
        return json_rsp
    
    #Coloca una orden LIMIT para el Take Profit
    tp_order = client.futures_create_order(
        symbol=symbol, 
        side=client.SIDE_SELL if side > 0 else client.SIDE_BUY, 
        type=client.FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
        quantity=executed_qty, 
        stopPrice=tp1,    
        workingType='MARK_PRICE',
        timeInForce=client.TIME_IN_FORCE_GTC, 
        reduceOnly=True
    )
    tp_order_id = tp_order['orderId']
    json_rsp['tp_order_id'] = tp_order_id

    #Coloca una orden STOP_MARKET para el Stop Loss
    sl_order = client.futures_create_order(
        symbol=symbol, 
        side=client.SIDE_SELL if side > 0 else client.SIDE_BUY, 
        type=client.FUTURE_ORDER_TYPE_STOP_MARKET,
        quantity=executed_qty, 
        stopprice=sl1, 
        workingType='CONTRACT_PRICE',
        reduceOnly=True
    )
    sl_order_id = sl_order['orderId']
    json_rsp['sl_order_id'] = sl_order_id
    
    #Entra en un bucle de monitoreo:
    #Cada 10 segundos, revisa el estado de las órdenes TP y SL.
    #Si una se llena (FILLED), intenta cancelar la otra.
    #Si una es cancelada/rechazada/expirada, deja de monitorearla.
    #El bucle termina cuando ambas órdenes (TP y SL) ya no están en un estado que requiera monitoreo (ej. una se llenó y la otra se canceló, o ambas fueron canceladas/rechazadas).


    json_rsp['symbol'] = symbol
    json_rsp['side'] = side
    json_rsp['in_price'] = in_price
    json_rsp['tp1'] = tp1
    json_rsp['sl1'] = sl1
    json_rsp['quote_qty'] = quote_qty
    
    if not 'error' in json_rsp:
        json_rsp['ok'] = 1

    return JsonResponse(json_rsp)

def get_ia_prompt(alert,klines):

    #Preparando el prompt
    klines = supertrend(klines)
    klines = zigzag(klines)
    period = 14
    klines.ta.rsi(length=period, append=True)
    klines.ta.adx(length=period, append=True)
    klines.fillna(np.nan,inplace=True)

    klines.rename(columns={'st_high': 'supertrend H', 
                            'st_low': 'supertrend L', 
                            'ZigZag': 'pivots',
                            f'RSI_{period}': 'RSI',
                            f'ADX_{period}': 'ADX',
                            }, inplace=True)
    kline_columns = ['close','volume','supertrend H','supertrend L','pivots','RSI','ADX']
    qdp = alert['qty_decs_price']
    klines[klines['supertrend H']>0]['supertrend H'] = klines['supertrend H'].round(qdp)
    klines[klines['supertrend L']>0]['supertrend L'] = klines['supertrend L'].round(qdp)

    klines.loc[klines['supertrend H'] > 0, 'supertrend H'] = klines.loc[klines['supertrend H'] > 0, 'supertrend H'].round(qdp)
    klines.loc[klines['supertrend L'] > 0, 'supertrend L'] = klines.loc[klines['supertrend L'] > 0, 'supertrend L'].round(qdp)
    klines.loc[klines['pivots'] > 0, 'pivots'] = klines.loc[klines['pivots'] > 0, 'pivots'].round(qdp)
    klines.loc[klines['RSI'] > 0, 'RSI'] = klines.loc[klines['RSI'] > 0, 'RSI'].round(1)
    klines.loc[klines['ADX'] > 0, 'ADX'] = klines.loc[klines['ADX'] > 0, 'ADX'].round(1)
        
    kline_data = klines[kline_columns].values.tolist()
    # Construir el prompt estructurado
    print(kline_data)
    prompt_dict = {
        "actual_price": alert['actual_price'],
        "klines": {
            "columns": kline_columns,
            "data": kline_data,
        },
    }
    
    return json.dumps(prompt_dict, indent=2)


@login_required
def ia_prompt(request):
    json_rsp = {}
    prompt = request.POST['prompt']
    json_rsp['prompt'] = prompt

    url = 'http://192.168.1.8/ia/prompt/'
    #url = 'http://localhost:5000/prompt/'
    data = {'prompt': prompt,
            'instruction': 'pivots'
            }  
    try:

        response = requests.post(url, json=data)
        response.raise_for_status()  
        
        json_data = response.json()  # Convierte la respuesta a JSON
        json_rsp = json_data
        
    
    except requests.exceptions.RequestException as e:
        json_rsp['error'] = 'No fue posible obtener el analisis de Gemini'
    """
    """
    return JsonResponse(json_rsp)

@login_required
def technical_analysis(request):
    json_rsp = {}
    klines = json.loads(request.POST['klines'])

    df = pd.DataFrame(klines, columns=['open','high','low','close','volume'])
    
    ta_result = technical_summary(df)
    json_rsp['ok'] = 1
    json_rsp['result'] = ta_result
    return JsonResponse(json_rsp)