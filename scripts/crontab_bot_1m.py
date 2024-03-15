from scripts.Exchange import Exchange
from bot.models import *
from bot.model_kline import *
from user.models import UserProfile
import scripts.functions as fn

from scripts.app_log import app_log as Log


def run():
    log = Log()
    json_rsp = {}
    startDt = datetime.now()
    #log.info(f'START {startDt}')
    #print(f'START {startDt}')

    json_rsp['error'] = []

    ### Establecer hora y minutos de start para definir que estrategias ejecutar de acuerdo al intervalo
    apply_intervals = fn.get_apply_intervals(startDt)
    json_rsp['apply_intervals'] = apply_intervals
    #print(f'Intervalo: {apply_intervals}')
    
    ### Obtener estrategias activas (Activas y Con bots activos) con intervalos aplicables a la hora de ejecucion del script
    ### Crear una lista con los Symbol de las estrategias activas
    estrategias = Estrategia.get_estrategias_to_run(apply_intervals)
    active_symbols = []
    for estr in estrategias:
        #log.info(f'Estrategia: {estr}')
        #print(f'Estrategia: {estr}')
        gen_bot = GenericBotClass().get_instance(estr.clase)
        gen_bot.set(estr.parse_parametros())
        try:
            gen_bot.valid()
            symbol = gen_bot.symbol
            active_symbols.append(symbol)
        except Exception as err:
            raise ValidationError(err)
    
    exchInfo = Exchange(type='info',exchange='bnc',prms=None)
    
    ### Si hay estrategias activas
    signal_rows = {}
    
        
    ### Buscar Señales
    for estr in estrategias:
        botClass = estr.get_instance()
        klines = exchInfo.get_klines(botClass.symbol, estr.interval_id, limit=201)
        signal_row = botClass.live_get_signal(klines)
        #signal = signal_row['signal']
        #log.info(f'{estr} {signal}')
        #print(estr, signal_row['datetime'], signal_row['signal'])
        signal_rows[estr.id] = signal_row
    
    ### - Obtener lista de bots activos ordenados por usuario_id
    bots = Bot.get_bots_activos()
    usuario_id = -1
    for bot in bots:
        #print(f'Bot: {bot}')
        try:
            botClass = bot.get_instance()
            botClass.bot_id = bot.id
            botClass.username = bot.usuario.username

            if bot.usuario.id != usuario_id:
                #log.info(f'Usuario: {bot.usuario.username}')

                usuario_id = bot.usuario.id
                profile = UserProfile.objects.get(user_id=bot.usuario.id)
                profile_config = profile.parse_config()
                prms = {}
                prms['bnc_apk'] = profile_config['bnc']['bnc_apk']
                prms['bnc_aps'] = profile_config['bnc']['bnc_aps']
                prms['bnc_env'] = profile_config['bnc']['bnc_env']

                exch = Exchange(type='user_apikey',exchange='bnc',prms=prms)                

            #log.info(f'Bot: {bot}')
                
            
            ### - Disparar las señales a los bots activos
            ### - Cuando se dispare una señal a un Bot 
            ###     - Si el bot NO PUEDE EJECUTARLA por cuestiones relacionadas con el capital. Inactivar el Bot
            signal = 'NEUTRO'
            signal_row = pd.DataFrame()
            if bot.estrategia_id in signal_rows:
                signal_row = signal_rows[bot.estrategia_id]
                signal = signal_row['signal']
            if signal != 'NEUTRO':
                log.info(f'{bot} - aa Signal: {signal}')


            #Cargando Billetera del Bot
            resultados = bot.get_wallet()
            symbol_info = exch.get_symbol_info(botClass.symbol)
            qd_qty = symbol_info['qty_decs_qty']
            qd_quote = symbol_info['qty_decs_quote']
            botClass.wallet_quote = round(bot.quote_qty + resultados['quote_compras'] + resultados['quote_ventas'] , qd_quote)
            botClass.wallet_base  = round(resultados['base_compras'] + resultados['base_ventas'] , qd_qty)
            
            #Cargando Billetera del Exchange
            exchange_wallet = exch.get_wallet() 


            #Cargando Ordenes en curso
            orders = bot.get_orders_en_curso()
            botClass._trades = {}
            botClass._orders = {}
            for order in orders:
                if order.completed > 0:
                    botClass._trades[order.id] = order
                else:
                    botClass._orders[order.id] = order
            
            # Obtener precios de los symbols activos en cada iteracion de usuario
            price = exchInfo.get_symbol_price(botClass.symbol)
            if abs(botClass.wallet_base*price) < 2: #Si el total de qty representa menos de 2 dolares, se toma como 0
                botClass.wallet_base = 0.0

            #Cargando datos para la ejecucion
            botClass.signal = signal
            botClass.row = signal_row
            botClass.exchange = exch
            botClass.price = price
            botClass.exchange_wallet = exchange_wallet
            execRes = botClass.live_execute()

            #if len(execRes) > 0:
            #    log.info(f'Execute: {execRes}')

            bot.make_operaciones()

            #Procesando estado actual del bot
            status = botClass.get_status()
            bot.update_status(status)
            

        except Exception as e:
            log.error(f'bot.id: {bot.id} {e}')
            json_rsp['error'].append(f'bot.id: {bot.id} {e}')
            

    """
    ### Actualizar velas de los Symbols
    try:
        update_klines = exchInfo.update_klines()
        json_rsp['klines'] = update_klines
                
    except Exception as err:
        err = str(err)
        msg_text = f'No fue posible encontrar velas\n{err}'
        json_rsp['error'].append(msg_text)
    """

    #Buscar ordenes incompletas, agrupadas por usuario
    #Si existen, reconectar con el Exchange para cada usuario 
    # Repetir la busqueda de ordenes incompletas en un bucle para todos los usuarios  
    # El bucle no puede ser infinito
    # Si quedan ordenes incompletas, se revisaran en la proxima corrida del crontab


    #Para cada job activo recalcular max-drawdown y demas indicadores y cachearlo en la db
    # Luego del recalculo verificar si se debe detener el bot por exceder
    # el max-drawdown general o el stop-loss general

    
    ### Control de errores
    if len(json_rsp['error']) > 0:
        json_rsp['ok'] = False
    else:
        json_rsp['ok'] = True
    if not json_rsp['ok']:
        
        for k,v in json_rsp.items():
            if k == 'error':
                for err in json_rsp['error']:
                    print(f"ERROR -> {err}")
                    log.error(f"{err}")    
            else:
                log.info(f"{k}: {v}")

    #print('Ready')

    #endDt = datetime.now()
    #log.info(f'END {endDt}')
    #durationDt = endDt-startDt
    #print('Duracion del proceso: ',durationDt)

