from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Count, Case, When, IntegerField
from django.contrib.auth.decorators import login_required

from scripts.Exchange import Exchange
from bot.models import *
from bot.model_kline import *


@login_required
def symbols(request):
    symbols = Symbol.objects.raw("SELECT bot_symbol.*, "+\
                                       " min(bot_kline.datetime) as first_kline, "+\
                                       " max(bot_kline.datetime) as last_kline "+\
                                    "FROM bot_symbol "+\
                                    "LEFT JOIN bot_kline ON bot_kline.symbol_id = bot_symbol.id "+\
                                    "GROUP BY bot_symbol.id")
    if request.method == 'GET':
        return render(request, 'symbols.html',{
            'symbols': symbols,
        })

@login_required
def symbol(request, symbol_id):
    symbol = get_object_or_404(Symbol, pk=symbol_id)
    qry = f"SELECT id, min(bot_kline.datetime) as first_kline, \
                max(bot_kline.datetime) as last_kline \
            FROM bot_kline \
            WHERE bot_kline.symbol_id = {symbol_id}" 
    return render(request, 'symbol.html',{
        'symbol': symbol,
    })

@login_required
def symbol_add(request):
    json_rsp = {}
    if request.method == 'GET':
        return render(request, 'symbol_add.html')
    else:
        symbol = Symbol()
        symbol.symbol = request.POST['symbol']
        symbol.base_asset = request.POST['base_asset']
        symbol.quote_asset = request.POST['quote_asset']
        symbol.qty_decs_qty = request.POST['qty_decs_qty']
        symbol.qty_decs_price = request.POST['qty_decs_price']
        symbol.qty_decs_quote = request.POST['qty_decs_quote']
        
        try:
            symbol.full_clean()

            symbol.save()
            json_rsp['ok'] = '/bot/symbol/'+str(symbol.id)

        except ValidationError as e:
            strError = ''
            for err in e:
                if err[0] != '__all__':
                    strError += '<br/><b>'+err[0]+'</b> '
                for desc in err[1]:
                    strError += desc+" "
            json_rsp['error'] = strError

        return JsonResponse(json_rsp)
        
def symbol_get_info(request,symbol):
    json_rsp = {}
    exch = Exchange('info',exchange='bnc',prms=None)
    symbol = symbol.upper()
    
    try:
        info = exch.get_symbol_info(symbol)
        json_rsp['ok'] = True
        json_rsp['base_asset'] = info['base_asset']
        json_rsp['quote_asset'] = info['quote_asset']
        json_rsp['qty_decs_qty'] = info['qty_decs_qty']
        
        json_rsp['qty_decs_price'] = info['qty_decs_price']
        json_rsp['qty_decs_quote'] = info['qty_decs_quote']

        if info['quote_asset'] != 'USDT' and info['quote_asset'] != 'BUSD' and info['quote_asset'] != 'USDC':
            json_rsp['ok'] = False
            json_rsp['error'] = 'Solo se permite agregar Symbols contra USDT, BUSD o USDC'

    except Exception as e:
        e = str(e)
        msg_text = f'No fue posible encontrar informacion sobre el Symbol {symbol}\n{e}'
        json_rsp['error'] = msg_text
        json_rsp['ok'] = False
    
    return JsonResponse(json_rsp)

def update_klines(request,symbol):
    json_rsp = {}
    exch = Exchange('info',exchange='bnc',prms=None)
    symbol = symbol.upper()
    try:
        res = exch.update_klines(symbol)
        json_rsp['ok'] = True
        json_rsp['res'] = res
                
    except Exception as e:
        e = str(e)
        msg_text = f'No fue posible encontrar velas para el Symbol {symbol}\n{e}'
        json_rsp['error'] = msg_text
        json_rsp['ok'] = False
    
    return JsonResponse(json_rsp)

@login_required
def symbol_toogle_activo(request,symbol_id):
    symbol = get_object_or_404(Symbol, pk=symbol_id)
    symbol.toogle_activo()
            
    return redirect('/bot/symbol/'+str(symbol.id))