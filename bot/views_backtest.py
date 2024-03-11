from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.template.loader import get_template
from django.template import Context


from bot.models import *
from bot.model_kline import *
from bot.model_backtest import *
import backtest.config as bt_config

@login_required
def backtest(request):
    gen_bot = GenericBotClass()
    classList = gen_bot.get_clases()

    backtests = Backtest.objects.filter().order_by('estado','clase','interval_id','creado')
    clases = []
    for c in classList:
        obj = gen_bot.get_instance(c)
        cls = {'class':c,'descripcion':obj.descripcion, }
        clases.append(cls)
    if request.method == 'GET':
        return render(request, 'backtest.html',{
            'clases': clases,
            'backtests': backtests,
        })

@login_required
def config(request,bot_class_name,backtest_id_to_clone=0):

    intervals = bt_config.intervals.to_dict('records')

    if backtest_id_to_clone==0:
        gen_bot = GenericBotClass()
        obj = gen_bot.get_instance(bot_class_name)
        parametros = obj.parametros
        interval_id = None

    else:
        backtest = get_object_or_404(Backtest, pk=backtest_id_to_clone)
        bot_class_name = backtest.clase
        gen_bot = GenericBotClass()
        obj = gen_bot.get_instance(bot_class_name)
        parametros = backtest.parse_parametros()
        interval_id = backtest.interval_id
        
            
    if request.method == 'GET':
        return render(request, 'backtest_create.html',{
            'bot_class_name': bot_class_name,
            'intervals': intervals,
            'parametros': parametros,
            'interval_id': interval_id,
        })

@login_required
def create(request):
    if request.method == 'POST':
        json_rsp = {}
        
        botClass    = request.POST['bot_class_name']
        interval_id = request.POST['interval_id']
        parametros  = request.POST['parametros']
        if request.POST['rewrite'] == 'YES':
            rewrite = True
        else:
            rewrite = False

        #Creando instancia del proceso de Backtest
        
        existentes = Backtest.objects.filter(interval_id=interval_id,
                                     clase=botClass,
                                     parametros=parametros)
        
        if existentes and existentes.count() > 0 and rewrite:
            for instance in existentes:
                bt = instance
                bt.usuario=request.user
                bt.completo = 0
                bt.creado = timezone.now()
                pass
                

        elif existentes and existentes.count() > 0 and not rewrite:
            json_rsp['ok'] = False
            json_rsp['confirm_rewrite'] = True
            return JsonResponse(json_rsp)
        else:
            bt = Backtest()
        
        bt.clase = botClass
        bt.interval_id = interval_id
        bt.usuario=request.user
        bt.parametros=parametros

        run_bot = bt.get_instance()
        run_bot.quote_qty = 1000
        run_bot.interval_id = interval_id
        prmPost = eval(request.POST['parametros'])
        for dict in prmPost:
            for k,v in dict.items():
                run_bot.__setattr__(k, v)

        atributos = run_bot.__dict__

        json_rsp['parametros'] = {}
        run_botValid = False
        for attr in atributos:
            val = atributos[attr]
            if attr != '_strategy':
                json_rsp['parametros'][attr] = val

        try:
            run_bot.valid()
            run_botValid = True
        
        except Exception as e:
            json_rsp['ok'] = False
            json_rsp['error'] = str(e)

        if run_botValid:
            try:
                bt.save()
                bt.iniciar()

                json_rsp['ok'] = True
                json_rsp['id'] = bt.id

            except ValidationError as e:
                strError = ''
                for err in e:
                    if err[0] != '__all__':
                        strError += '<br/><b>'+err[0]+'</b> '
                    for desc in err[1]:
                        strError += desc+" "
                json_rsp['ok'] = False
                json_rsp['error'] = strError
        return JsonResponse(json_rsp)


@login_required
def view(request,backtest_id):
    backtest = get_object_or_404(Backtest, pk=backtest_id)
    resultados = backtest.get_resultados()

    df_resultados = None
    next = None
    context = {
            'backtest': backtest,
            'parametros': backtest.parse_parametros(),
            'resultados': resultados,
            'periodos': resultados['periodos'],
            'str_parametros': backtest.str_parametros,
        }
    if backtest.completo < 100:
        
        for i in range(0,len(resultados['periodos'])-1):
            if not next and resultados['periodos'][i]['procesado'] == 'NO':
                next = resultados['periodos'][i]
        
        context['next'] = next
      

    else:           
        rango_fechas_completo = ''
        rango_fechas_alcista = ''
        rango_fechas_lateral = ''
        rango_fechas_bajista = ''
        for periodo in resultados['periodos']:
            if periodo['tendencia'] == 'Completo' and rango_fechas_completo == '':
                rango_fechas_completo += dt.datetime.strptime(periodo['start'],'%Y-%m-%d').strftime('%d-%m-%Y')
                rango_fechas_completo += ' '+dt.datetime.strptime(periodo['end'],'%Y-%m-%d').strftime('%d-%m-%Y')
            if periodo['tendencia'] == 'Alcista' and rango_fechas_alcista == '':
                rango_fechas_alcista += dt.datetime.strptime(periodo['start'],'%Y-%m-%d').strftime('%d-%m-%Y')
                rango_fechas_alcista += ' '+dt.datetime.strptime(periodo['end'],'%Y-%m-%d').strftime('%d-%m-%Y')
            if periodo['tendencia'] == 'Bajista' and rango_fechas_bajista == '':
                rango_fechas_bajista += dt.datetime.strptime(periodo['start'],'%Y-%m-%d').strftime('%d-%m-%Y')
                rango_fechas_bajista += ' '+dt.datetime.strptime(periodo['end'],'%Y-%m-%d').strftime('%d-%m-%Y')
            if periodo['tendencia'] == 'Lateral' and rango_fechas_lateral == '':
                rango_fechas_lateral += dt.datetime.strptime(periodo['start'],'%Y-%m-%d').strftime('%d-%m-%Y')
                rango_fechas_lateral += ' '+dt.datetime.strptime(periodo['end'],'%Y-%m-%d').strftime('%d-%m-%Y')
                
        df_resultados = backtest.get_resumen_resultados()
        plantilla = get_template('backtest_results_table.html')
        context['html_General']    = plantilla.render({'df': df_resultados['Media']    })
        context['html_Completo']   = plantilla.render({'df': df_resultados['Completo']})
        context['html_Alcista']    = plantilla.render({'df': df_resultados['Alcista']  })
        context['html_Lateral']    = plantilla.render({'df': df_resultados['Lateral']  })
        context['html_Bajista']    = plantilla.render({'df': df_resultados['Bajista']  })
        context['titulo_general']  = 'General'    
        context['titulo_completo'] = 'Completo '+rango_fechas_completo   
        context['titulo_alcista']  = 'Alcista '+rango_fechas_alcista    
        context['titulo_lateral']  = 'Lateral '+rango_fechas_lateral    
        context['titulo_bajista']  = 'Bajista '+rango_fechas_bajista   

        scoring = backtest.calcular_scoring_completpo(df_resultados)

        backtest.scoring = round(scoring['Completo'],1)
        scoring_alcista = scoring['Alcista']
        scoring_bajista = scoring['Bajista']
        scoring_lateral = scoring['Lateral']
        backtest.scoring_str = f'Alcista: {scoring_alcista:.1f} Bajista: {scoring_bajista:.1f} Lateral: {scoring_lateral:.1f} '
        backtest.save()
        context['scoring']  = f'{backtest.scoring:.1f}'
        context['scoring_str']  = backtest.scoring_str  

    return render(request, 'backtest_view.html',context)

@login_required
def execute(request,backtest_id):
    if request.method == 'POST':
        json_rsp = {}
        backtest = get_object_or_404(Backtest, pk=backtest_id)
        resultados = backtest.get_resultados()
        
        key = int(request.POST['key'])

        json_rsp['ok'] = False
        json_rsp['key'] = key
        json_rsp['get'] = resultados['periodos'][key]

        periodo = resultados['periodos'][key]
        
        #ejecutando BackTest
        run_bot = backtest.get_instance()
        run_bot.quote_qty = 1000.0
        run_bot.symbol = periodo['symbol']

        try:
            run_bot.valid()
            
            klines = backtest.get_df_from_file(periodo['file'])
            sub_klines = backtest.get_sub_df_from_file(periodo['file'])
            bt = run_bot.backtest(klines,periodo['start'],periodo['end'],'ind',sub_klines)
            json_rsp['bt'] = bt
            json_rsp['ok'] = True
                    
            


            #Actualizar resultados
            resultados['periodos'][key]['procesado'] = 'YES'
            resultados['periodos'][key]['bt'] = bt
            resultados = backtest.set_resultados(resultados)
            periodos_q = len(resultados['periodos'])
            periodos_completos = 0
            for i in range(0,periodos_q):
                if resultados['periodos'][i]['procesado'] == 'YES':
                    periodos_completos += 1
            backtest.completo = int((periodos_completos/periodos_q)*100)
            if backtest.completo < 100:
                backtest.estado = backtest.ESTADO_ENCURSO
            else:
                backtest.estado = backtest.ESTADO_COMPLETO
            backtest.save()

            json_rsp['completo'] = backtest.completo
            json_rsp['str_estado'] = backtest.str_estado()
            
            plantilla = get_template('backtest_view_periodos.html')
            contexto = {'periodos': resultados['periodos']}
            json_rsp['html_periodos'] = plantilla.render(contexto)

            #Preparando el proceso en caso que exista
            next_key = key+1
            if next_key < len(resultados['periodos']):
                json_rsp['next_key'] = resultados['periodos'][next_key]['key']
                json_rsp['next_str'] = resultados['periodos'][next_key]['str']
            
        except Exception as e:
            json_rsp['error'] = 'No fue posible procesar el BackTest'
            json_rsp['error'] += '<br>'+str(e)
            json_rsp['ok'] = False
        
        return JsonResponse(json_rsp)

@login_required
def delete(request,backtest_id):
    backtest = get_object_or_404(Backtest, pk=backtest_id)
    file = backtest.get_results_file()
    backtest.delete()
    os.remove(file)

    return redirect('backtest')

