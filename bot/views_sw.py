from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError

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
    swc = sw.get_capital()

    assets = sw.get_assets()

    assets_brief = sw.get_assets_brief()
    #assets_brief_total_buyed = round(sum(data['buyed'] for data in assets_brief.values()),2)
    #assets_brief_total_cap   = round(sum(data['cap'] for data in assets_brief.values()),2)
    #assets_brief_result = round(((assets_brief_total_cap/assets_brief_total_buyed)-1)*100,2) if assets_brief_total_buyed != 0 else 0

    #Configurando el estado del SW en la DDBB de acuerdo a la informacion registrada
    act_estado = sw.estado
    new_estado = act_estado
    if len(swc) > 0:
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