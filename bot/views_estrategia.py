from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Count, Case, When, IntegerField
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError

from bot.models import *
from bot.model_kline import *

@login_required
def estrategias(request):
    estrategias = Estrategia.objects.annotate(qtyBots=Count('bot'),
                qtyBotsActivos=Count(Case(When(bot__activo__gt=0, then=1),output_field=IntegerField()))
                )

    if request.method == 'GET':
        return render(request, 'estrategias.html',{
            'estrategias': estrategias,
        })

@login_required
def estrategia(request, estrategia_id):
    estrategia = get_object_or_404(Estrategia, pk=estrategia_id)
    bots = Bot.objects.filter(estrategia_id=estrategia_id)
    intervalo = fn.get_intervals(estrategia.interval_id,'name')
    qtyBots = len(bots)
    
    return render(request, 'estrategia.html',{
        'estrategia_id': estrategia.id,
        'nombre': estrategia.nombre,
        'clase': estrategia.clase,
        'max_drawdown': estrategia.max_drawdown,
        'descripcion': estrategia.descripcion,
        'intervalo': intervalo,
        'activo': estrategia.activo,
        'creado': estrategia.creado,
        'qtyBots': qtyBots,
        'can_delete': estrategia.can_delete(),
        'parametros': estrategia.parse_parametros(),
    })

@login_required
def estrategia_create(request):
    json_rsp = {}
    if request.method == 'GET':
        gen_bot = GenericBotClass()
        clases = gen_bot.get_clases()
        symbols = Symbol.objects.order_by('symbol')
        intervals = fn.get_intervals().to_dict('records')
        return render(request, 'estrategia_edit.html',{
            'title': 'Crear estrategia',
            'clases': clases,
            'symbols': symbols,
            'intervals': intervals,
            'qtyBots': 0,
            'estrategia_id': 0,
        })
    else:
        estrategia = Estrategia()
        estrategia.nombre=request.POST['nombre'] 
        estrategia.clase=request.POST['clase']
        estrategia.descripcion=request.POST['descripcion']
        estrategia.interval_id=request.POST['interval_id']
        estrategia.max_drawdown=request.POST['max_drawdown']
        estrategia.parametros=request.POST['parametros']
        
        try:
            estrategia.full_clean()

            estrategia.save()
            json_rsp['ok'] = '/bot/estrategia/'+str(estrategia.id)

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
def load_parametros(request,clase):
    json_rsp = {}
    gen_bot = GenericBotClass().get_instance(clase)
    parametros = gen_bot.parametros
    descripcion = gen_bot.descripcion
    json_rsp['ok'] = len(parametros)
    json_rsp['parametros'] = parametros
    json_rsp['descripcion'] = descripcion
    return JsonResponse(json_rsp)


@login_required
def estrategia_edit(request,estrategia_id):
    json_rsp = {}
    estrategia = get_object_or_404(Estrategia, pk=estrategia_id)
    bots = Bot.objects.filter(estrategia_id=estrategia_id)
    gen_bot = GenericBotClass()
    clases = gen_bot.get_clases()
    qtyBots = len(bots)
    symbols = Symbol.objects.order_by('symbol')
    intervals = fn.get_intervals().to_dict('records')
    if request.method == 'GET':
        return render(request, 'estrategia_edit.html',{
            'title': 'Editar estrategia '+estrategia.nombre,
            'estrategia_id': estrategia.id,
            'nombre': estrategia.nombre,
            'clase': estrategia.clase,
            'descripcion': estrategia.descripcion,
            'max_drawdown': estrategia.max_drawdown,
            'interval_id': estrategia.interval_id,
            'intervals': intervals,
            'clases': clases,
            'activo': estrategia.activo,
            'qtyBots': qtyBots,
            'symbols': symbols,
            'parametros': estrategia.parse_parametros(),
        })
    else:

        estrategia.nombre=request.POST['nombre'] 
        estrategia.clase=request.POST['clase']
        estrategia.descripcion=request.POST['descripcion']
        estrategia.interval_id=request.POST['interval_id']
        estrategia.max_drawdown=request.POST['max_drawdown']
        estrategia.parametros=request.POST['parametros']
        
        try:
            estrategia.full_clean()

            estrategia.save()
            json_rsp['ok'] = '/bot/estrategia/'+str(estrategia.id)

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
def estrategia_toogle_activo(request,estrategia_id):
    estrategia = get_object_or_404(Estrategia, pk=estrategia_id)
    if estrategia.activo > 0:
        estrategia.activo = 0
    else:
        estrategia.activo = 1
    estrategia.save()
    return redirect('/bot/estrategia/'+str(estrategia.id))

@login_required
def estrategia_delete(request,estrategia_id):
    json_rsp = {}
    estrategia = get_object_or_404(Estrategia, pk=estrategia_id)
    
    if estrategia.can_delete():
        estrategia.delete()
        json_rsp['ok'] = True
    else:
        json_rsp['error'] = 'No es psible eliminar la estrategia'
    return JsonResponse(json_rsp)
    
    
