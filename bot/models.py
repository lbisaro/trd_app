from django.conf import settings
from django.db import models, connection
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum, F, Case, When, Value, FloatField

import scripts.functions as fn
import os, fnmatch
import importlib
from scripts.Exchange import Exchange
from bot.model_kline import Kline, Symbol
import pandas as pd
import datetime as dt
from django_pandas.io import read_frame
from scripts.Bot_Core_utils import Order as BotUtilsOrder


class GenericBotClass:
    
    def get_clases(self):
        clases = []
        folder = os.path.join(settings.BASE_DIR,'scripts/bots')
        files = [file for file in os.listdir(folder) if fnmatch.fnmatch(file, 'Bot*.py')]
        for file in files:
            file = file.replace('.py','')
            clases.append(file)
        return clases
    
    def get_instance(self,clase):
        modulo = importlib.import_module(f'scripts.bots.{clase}')
        obj = eval(f'modulo.{clase}()')
        return obj

class Estrategia(models.Model):
    nombre = models.CharField(max_length = 100, null=False, unique = True, blank=False)
    clase = models.SlugField(max_length = 50, null=False, blank=False)
    parametros = models.TextField(null=False, blank=False)
    descripcion = models.TextField(null=False, blank=False)
    interval_id = models.CharField(max_length = 8, null=False, blank=False)
    creado = models.DateField(default=timezone.now)
    activo = models.IntegerField(default=0)  
    max_drawdown = models.FloatField(null=False, blank=False)
    
    class Meta:
        verbose_name = "Estrategia"
        verbose_name_plural='Estrategias'
    
    def __str__(self):
        str = self.nombre

        prms = self.parse_parametros()
        str += ' '+prms['symbol']['v']

        intervalo = fn.get_intervals(self.interval_id,'binance')
        str += ' '+intervalo

        return str
    
    def get_intervalo(self):
        return fn.get_intervals(self.interval_id,'binance')
    
    def get_descripcion(self):
        gen_bot = GenericBotClass()
        run_bot = gen_bot.get_instance(self.clase)
        run_bot.set(self.parametros)
        intervalo = fn.get_intervals(self.interval_id,'pandas_resample')
        add_nombre = f'[{intervalo}] '+run_bot.get_add_nombre()  
        return add_nombre
    
    def can_delete(self):
        bots = Bot.objects.filter(estrategia_id=self.id)
        qtyBots = len(bots)
        return True if (qtyBots == 0 and self.activo == 0) else False
         
    
    def clean(self):
        gen_bot = GenericBotClass().get_instance(self.clase)
        gen_bot.set(self.parse_parametros())
        
        try:
            gen_bot.valid()
        except Exception as e:
            raise ValidationError(e)

    def parse_parametros(self):
        gen_bot = GenericBotClass().get_instance(self.clase)
        parametros = gen_bot.parametros
        pe = eval(self.parametros)
        for prm in pe:
            for v in prm:
                parametros[v]['v'] = prm[v]
                parametros[v]['str'] = str(prm[v])

                if parametros[v]['t'] == 'perc':
                    val = float(parametros[v]['v'])
                    parametros[v]['str'] = f'{val:.2f} %'

                if parametros[v]['t'] == 't_int':
                    if parametros[v]['v'] == 's':
                        parametros[v]['str'] = 'Simple'
                    elif parametros[v]['v'] == 'c':
                        parametros[v]['str'] = 'Compuesto'

                if parametros[v]['t'] == 'bin':
                    if int(parametros[v]['v']) > 0:
                        parametros[v]['str'] = 'Si'
                    else:
                        parametros[v]['str'] = 'No'
                    
        return parametros

    def str_parametros(self):
        prm = self.parse_parametros()
        str = ''
        for p in prm:
            if str != '':
                str += ', '
            str += prm[p]['sn']+': '+prm[p]['str']
        return f"{str}"

    def get_estrategias_to_run(intervals):
        query = "SELECT * "
        query += "FROM bot_estrategia "
        query += "WHERE activo = 1 AND interval_id in ("+intervals+") "
        query += "AND (SELECT count(id) FROM bot_bot WHERE activo = 1 AND bot_bot.estrategia_id = bot_estrategia.id)"
        query += "ORDER BY bot_estrategia.id"
        estrategias = Estrategia.objects.raw(query)
        return estrategias

    def get_instance(self):
        gen_bot = GenericBotClass().get_instance(self.clase)
        gen_bot.set(self.parse_parametros())
        gen_bot.interval_id = self.interval_id

        return gen_bot


class Bot(models.Model):
    estrategia = models.ForeignKey(Estrategia, on_delete = models.CASCADE)
    usuario = models.ForeignKey(User, on_delete = models.CASCADE)
    creado = models.DateField(default=timezone.now)
    finalizado = models.DateField(null=True, blank=True)
    activo = models.IntegerField(default=0)
    quote_qty = models.FloatField(null=False, blank=False)
    max_drawdown = models.FloatField(null=False, blank=False)
    stop_loss = models.FloatField(null=False, blank=False)
    status = models.TextField(null=False, blank=True)
    
    class Meta:
        verbose_name = "Bot"
        verbose_name_plural='Bots'
    
    def __str__(self):
        str = f"Bot {self.estrategia.nombre}"

        prms = self.parse_parametros()
        symbol = prms['symbol']['v']

        strInterval = ''
        if self.estrategia.interval_id:
            strInterval = fn.get_intervals(self.estrategia.interval_id,'binance')
            
        str += f" [{symbol} {strInterval}] [{self.usuario.username}]"

        
        return str
    
    def can_delete(self):
        orders = Order.objects.filter(bot_id=self.id)
        qtyOrders = len(orders)
        return True if (qtyOrders == 0 and self.activo == 0) else False
    
    def parse_parametros(self):
        return self.estrategia.parse_parametros()
    
    def get_instance(self):
        botClass = self.estrategia.get_instance()
        botClass.set(self.parse_parametros())
        botClass.quote_qty = self.quote_qty
        botClass.valid()
        return botClass

    def get_bots_activos():
        query = "SELECT * FROM bot_bot "\
                "WHERE bot_bot.activo = 1 "\
                "ORDER BY usuario_id"
        bots = Bot.objects.raw(query)
        return bots
    
    def make_operaciones(self):
        orders = self.get_pos_orders()
        acum_qty = 0
        buy = 0
        sell = 0
        start_order_id = 0
        ref_price = 0.0
        update = {}
        for order in orders:
            ref_price = order.price
            if order.side == BotUtilsOrder.SIDE_BUY:
                buy += 1
                acum_qty += order.qty
            if order.side == BotUtilsOrder.SIDE_SELL:
                sell += 1
                acum_qty -= order.qty
            if start_order_id == 0:
                start_order_id = order.id
                update[start_order_id] = []
            update[start_order_id].append(order.id)
            
            #Crea la operacion y reinicia los valores para la proxima 
            #Si hubo compras y ventas, y la sumatoria de unidades compradas-vendidas es < a 2 USD
            if buy > 0 and sell > 0 and abs(acum_qty*ref_price) < 2.0:
                Order.objects.filter(id__in=update[start_order_id]).update(pos_order_id=start_order_id)
                start_order_id = 0
                acum_qty = 0
                buy = 0
                sell = 0
    
    def desactivar(self,texto=''):
        self.bloquear()
    
    def bloquear(self,texto=''):
        self.activo = 0
        self.save()
        self.add_log(BotLog.LOG_DESACTIVAR,texto)
    
    def activar(self):
        self.activo = 1
        self.save()
        self.add_log(BotLog.LOG_ACTIVAR)
    
    def add_log(self,log_id,texto=''):
        bot_log = BotLog()
        bot_log.bot = self
        bot_log.log_type_id = log_id
        bot_log.texto = texto
        bot_log.save()

    def get_orders(self):
        orders = Order.objects.filter(bot=self).order_by('datetime')
        return orders

    def get_orders_en_curso(self):
        orders = Order.objects.filter(bot=self,pos_order_id=0).order_by('datetime')
        return orders

    # Ordenes correspondientes a la Posicion abierta (Actual)
    def get_pos_orders(self):
        pos_orders = Order.objects.filter(bot=self,pos_order_id=0,completed=1).order_by('datetime')
        return pos_orders
    
    def get_wallet(self):
        resultados = Order.objects.filter(bot=self,completed=1).aggregate(
            quote_compras=Sum(
                Case(
                    When(side=0, then=F('qty') * F('price') * -1),
                    default=Value(0),
                    output_field=FloatField(),
                )
            ),
            base_compras=Sum(
                Case(
                    When(side=0, then=F('qty') ),
                    default=Value(0),
                    output_field=FloatField(),
                )
            ),
            quote_ventas=Sum(
                Case(
                    When(side=1, then=F('qty') * F('price') ),
                    default=Value(0),
                    output_field=FloatField(),
                )
            ),
            base_ventas=Sum(
                Case(
                    When(side=1, then=F('qty')  * -1),
                    default=Value(0),
                    output_field=FloatField(),
                )
            )
        )
        if not resultados['base_ventas']:
            resultados['base_ventas'] = 0.0
        if not resultados['quote_ventas']:
            resultados['quote_ventas'] = 0.0
        if not resultados['base_compras']:
            resultados['base_compras'] = 0.0
        if not resultados['quote_compras']:
            resultados['quote_compras'] = 0.0

        return resultados
        
    def get_trades(self):
        orders = self.get_orders()
        
        last_posorder_id = -1
        trades = {}
        trade = {}
        key = 0
        
        for o in orders:
            if o.completed > 0 and o.pos_order_id > 0:
                
                #Reinicio de la posicion
                if o.pos_order_id != last_posorder_id:
                    last_posorder_id = o.pos_order_id
                    key = o.pos_order_id
                    trades[key] = {}
                    trade = {}
                    trade['start'] = o.datetime
                    trade['buy_price'] = 0.0
                    trade['qty'] = 0.0
                    trade['end'] = None
                    trade['flag_type'] = ''
                    trade['sell_price'] = 0.0
                    trade['comision'] = 0.0
                    trade['buy_ops'] = 0
                    trade['buy_acum_quote'] = 0.0
                    trade['buy_acum_base'] = 0.0
                    trade['buy_avg_price'] = 0.0
                    trade['sell_ops'] = 0
                    trade['sell_acum_quote'] = 0.0
                    trade['sell_acum_base'] = 0.0
                    trade['sell_avg_price'] = 0.0
                    trade['result_qty'] = 0.0
                    trade['result_quote'] = 0.0
                    trade['result_perc'] = 0.0
                    trade['orders'] = 0
                    
                        
                    
                trade['orders'] += 1
                if o.side == BotUtilsOrder.SIDE_BUY:
                    trade['buy_ops'] += 1
                    trade['buy_acum_quote'] += o.price * o.qty
                    trade['buy_acum_base'] += o.qty
                    trade['result_qty'] += o.qty
            
                else:
                    trade['sell_ops'] += 1
                    trade['sell_acum_quote'] += o.price * o.qty
                    trade['sell_acum_base'] += o.qty
                    trade['result_qty'] -= o.qty
                    

                #Calculos
                trade['comision'] = round(trade['comision'] + o.price * o.qty * (BotUtilsOrder.live_exch_comision_perc/100) ,4)
                if trade['buy_acum_base'] != 0:
                    trade['buy_avg_price'] = round(trade['buy_acum_quote'] / trade['buy_acum_base'],o.symbol.qty_decs_price)
                if trade['sell_acum_base'] != 0:
                    trade['sell_avg_price'] = round(trade['sell_acum_quote'] / trade['sell_acum_base'],o.symbol.qty_decs_price)
                if trade['buy_avg_price'] != 0:
                    trade['result_perc'] = round(((trade['sell_avg_price']/trade['buy_avg_price'])-1)*100 - (BotUtilsOrder.live_exch_comision_perc*2) , 2)
                
                trade['result_quote'] = round(trade['sell_acum_quote']-trade['buy_acum_quote']-trade['comision'],o.symbol.qty_decs_quote)
                

                trade['end'] = o.datetime

                if o.type == BotUtilsOrder.TYPE_LIMIT:
                   trade['flag_type'] += 'Limit '
                elif o.type == BotUtilsOrder.TYPE_TRAILING:
                   trade['flag_type'] += 'Trail '

                if o.flag == BotUtilsOrder.FLAG_STOPLOSS:
                   trade['flag_type'] += 'SL '
                elif o.flag == BotUtilsOrder.FLAG_TAKEPROFIT:
                   trade['flag_type'] += 'TP '

                
                trades[key] = trade

        #transforma el diccinoario de diccionarios en una lista de diccionarios
        list_trades = []
        for t in trades:
            dif = trades[t]['end'] - trades[t]['start']
            days = round(dif.total_seconds() / 60 / 60 / 24 , 2)
            trades[t]['duracion'] = days
            list_trades.append(trades[t])
        return list_trades 
                

    
    def can_activar(self):
        if self.estrategia.activo > 0:
            return True
        return False
    
    def get_log(self):
        log = BotLog.objects.filter(bot_id=self.id).order_by('datetime')
        jsonLog = []
        jsonLog.append({
                'datetime': dt.datetime(self.creado.year,self.creado.month,self.creado.day),
                'type': 'CREADO',
                'texto': '',
                'class': '',
            })
        for l in log:
            jsonLog.append({
                'datetime': l.datetime,
                'type': l.get_type(),
                'texto': l.texto,
                'class': l.get_class(),

            })
        if self.finalizado:
            jsonLog.append({
                'datetime': dt.datetime(self.finalizado.year,self.finalizado.month,self.finalizado.day),
                'type': 'FINALIZADO',
                'texto': '',
                'class': '',
            })
        return jsonLog
    
    def get_resultados(self):
        json_rsp = {}
        json_rsp['general'] = []
        json_rsp['operaciones'] = []
        json_rsp['indicadores'] = []
        interval_id = self.estrategia.interval_id
        from_date = self.creado.strftime('%Y-%m-%d')
        to_date = timezone.now().strftime('%Y-%m-%d')
        run_bot = self.get_instance()
        symbol = run_bot.symbol
        orders = self.get_orders()


        klines = Kline.get_df(strSymbol=symbol,
                            interval_id=interval_id,
                            from_date = from_date,
                            to_date = to_date)
        
        df_orders = read_frame(orders)
        df_orders['qty'] = (df_orders['qty'] * -1).where(df_orders['side'] > 0, df_orders['qty'])
        df_orders['usd'] = round(-1*df_orders['qty']*df_orders['price'], 2)
        
        
        pandas_interval = fn.get_intervals(interval_id,'pandas_resample')
        agg_funcs = {
                "qty": "sum",
                "usd": "sum",
            }   
        df_orders = df_orders.resample(pandas_interval, on="datetime").agg(agg_funcs).reset_index()
        
        
        merged_df = pd.merge(klines, df_orders, on=['datetime'], how='outer').sort_values(by='datetime')



        start_quote = run_bot.quote_qty * (run_bot.quote_perc/100)
        start_price = klines.loc[0]['close']
        hold_base_qty = start_quote/start_price
        merged_df['qty'].fillna(0.0, inplace=True)
        merged_df['usd'].fillna(0.0, inplace=True)


        merged_df['usd_hold'] = round(merged_df['close']*hold_base_qty + run_bot.quote_qty-start_quote ,2)

        merged_df['base_wallet'] = merged_df['qty'].cumsum()
        merged_df['usd_wallet']     = round(merged_df['usd'].cumsum() , 2)
        merged_df['usd_wallet']     = round(merged_df['usd_wallet'] + run_bot.quote_qty , 2)
        merged_df['usd_estrategia'] = round(merged_df['base_wallet']*merged_df['close'] + merged_df['usd_wallet'] , 2)

        trades = self.get_trades()
        df_trades = pd.DataFrame(trades)


        
        kline_ini = klines.loc[klines.index[0]]
        kline_end = klines.loc[klines.index[-1]]
        dif_days = kline_end['datetime'] - kline_ini['datetime']
        dias_operando = dif_days.total_seconds() / 3600 / 24
        dias_trades = df_trades['duracion'].sum()
        dias_sin_operar = dias_operando - dias_trades
        usd_final = self.quote_qty + df_orders['usd'].sum()
        
        resultado_usd = usd_final-self.quote_qty
        resultado_perc = (resultado_usd/self.quote_qty)*100
        resultado_mensual = (resultado_perc/dias_operando)*run_bot.DIAS_X_MES

        volatilidad_cap  = run_bot.ind_volatilidad(merged_df,'usd_estrategia')
        volatilidad_sym  = run_bot.ind_volatilidad(merged_df,'usd_hold')
        max_drawdown_cap = run_bot.ind_maximo_drawdown(merged_df,'usd_estrategia')
        max_drawdown_sym = run_bot.ind_maximo_drawdown(merged_df,'usd_hold')

        json_rsp['general'] = []
        json_rsp['general'].append({'t':'Periodo','v':kline_ini['datetime'].strftime('%d-%m-%Y %H:%M')+' - '+kline_end['datetime'].strftime('%d-%m-%Y %H:%M')})
        json_rsp['general'].append({'t':'Dias del periodo','v':f'{dias_operando:.1f}'})
        json_rsp['general'].append({'t':'Dias sin operar','v':f'{dias_sin_operar:.2f}'})

        json_rsp['general'].append({'t':'Resultado general','v':   f'USD {resultado_usd:.2f} ({resultado_perc:.2f} %)',
                                   'c':'text-danger' if resultado_perc < 0 else 'text-success'})

        json_rsp['general'].append({'t':'Resultado mensual (Estimado)','v':   f'{resultado_mensual:.2f} %',
                                   'c':'text-danger' if resultado_mensual < 0 else 'text-success'})

        json_rsp['operaciones'] = [{'t':'Operaciones','v':'inicio Operaciones a fin'},
                              {'t':'Operaciones 2','v':'inicio Operaciones a fin 2'},
                              ]
        
        json_rsp['indicadores'].append({'t':'Volatilidad del capital','v':   f'{volatilidad_cap:.2f} %'})
        json_rsp['indicadores'].append({'t':'Volatilidad del par','v':       f'{volatilidad_sym:.2f} %'})
        json_rsp['indicadores'].append({'t':'Max DrawDown del capital','v':  f'{max_drawdown_cap:.2f} %'})
        json_rsp['indicadores'].append({'t':'Max DrawDown del par','v':      f'{max_drawdown_sym:.2f} %'})
                              


        return json_rsp

    
    def get_resultados__GRAPH(self):
        json_rsp = {}
        orders = self.get_orders()
        trades = self.get_trades()

        
        botClass = self.get_instance()
        botClass.reset_res()
        botClass.reset_pos()
        symbol = botClass.symbol
        kline_ini = self.creado
        if self.finalizado:
            kline_end = self.finalizado
        else:
            kline_end = timezone.now()

        pandas_interval = fn.get_intervals(self.estrategia.interval_id,'pandas_resample')

        klines = Kline.get_df(strSymbol=symbol, 
                              interval_id=self.estrategia.interval_id,
                              from_date = kline_ini.strftime('%Y-%m-%d'),
                              to_date = kline_end.strftime('%Y-%m-%d'),
                              )
        botClass.klines = klines
        order_columns = ['datetime','symbol','side','qty','price','flag','comision']
        last_posorder_id = 0
        for o in orders:
            comision = round(o.price * o.qty * (BotUtilsOrder.live_exch_comision_perc/100) ,4)
            order_datetime = pd.to_datetime(o.datetime)
            order_datetime = order_datetime.floor(pandas_interval)
            
            if o.completed > 0 and o.pos_order_id > 0:
                order = [
                    order_datetime,
                    o.symbol.symbol,
                    o.side,
                    o.qty,
                    o.price,
                    o.flag,
                    comision,
                ] 
                
                if o.pos_order_id != last_posorder_id:
                    last_posorder_id = o.pos_order_id
                    botClass.open_pos(o.datetime.strftime("%Y-%m-%d %H:%M"),o.price,o.qty)
                else:
                    botClass.close_pos(o.datetime.strftime("%Y-%m-%d %H:%M"),o.price,o.flag)

                botClass.res['orders'].append(order)
            

        df_orders = pd.DataFrame(botClass.res['orders'], columns=order_columns)
        df_orders.set_index('datetime', inplace=True)

        klines['side'] = None
        klines['qty'] = None
        klines['price'] = None
        klines['flag'] = None
        klines['comision'] = None

        botClass.wallet_base = 0.0
        botClass.wallet_quote = self.quote_qty 
        hold_qty = 0
        for i in klines.index:
            k = klines.loc[i]
            timestamp = pd.Timestamp(k['datetime']).timestamp()
            unix_dt = int( (timestamp*1000) +  10800000 ) #Convierte a milisegundos y agrega 3 horas
            
            buy = None
            sell_s = None
            sell_sl = None
            sell_tp = None
            flag = None
            if k['datetime'] in df_orders.index:
                o = df_orders.loc[k['datetime']]
                if o.side == BotUtilsOrder.SIDE_BUY:
                    botClass.wallet_quote = botClass.wallet_quote - (o.qty * o.price)
                    botClass.wallet_base = botClass.wallet_base + o.qty
                    buy = float(o.price)
                if o.side == BotUtilsOrder.SIDE_SELL:
                    botClass.wallet_quote = botClass.wallet_quote + (o.qty * o.price)
                    botClass.wallet_base = botClass.wallet_base - o.qty
                    if o.flag == BotUtilsOrder.FLAG_SIGNAL:
                        sell_s = float(o.price)
                    if o.flag == BotUtilsOrder.FLAG_STOPLOSS:
                        sell_sl = float(o.price)
                    if o.flag == BotUtilsOrder.FLAG_TAKEPROFIT:
                        sell_tp = float(o.price)
                flag = int(o.flag)

            if hold_qty == 0:
                hold_qty = botClass.wallet_quote / k['close']
            usdH = float(hold_qty*k['close']) + (self.quote_qty - hold_qty)

            usdW = botClass.wallet_quote + (botClass.wallet_base * k['close'])

            data = {'dt': unix_dt,
                    'o': k['open'],
                    'h': k['high'],
                    'l': k['low'],
                    'c': k['close'],
                    'v': k['volume'],
                    'sigB': None,
                    'sigS': None,
                    'buy': buy,
                    'sell_s': sell_s,
                    'sell_sl': sell_sl,
                    'sell_tp': sell_tp,
                    'flag': flag,
                    'usdH': usdH,
                    'usdW': usdW,
                    'dd': 0.0,
                    'SL': None,
                    'TP': None,
                } 
            botClass.res['data'].append(data)
        
        
        json_rsp['parametros'] = {
            'interes': botClass.interes,
            'interval_id': self.estrategia.interval_id,
            'quote_perc': botClass.quote_perc,
            'quote_qty': botClass.quote_qty,
            'stop_loss': botClass.stop_loss,
            'take_profit': botClass.take_profit,
            'symbol': symbol,

        }
        exch = Exchange(type='info',exchange='bnc',prms=None)
        symbol_info = exch.get_symbol_info(symbol)
        botClass.base_asset = symbol_info['base_asset']
        botClass.quote_asset = symbol_info['quote_asset']
        botClass.qd_price = symbol_info['qty_decs_price']
        botClass.qd_qty = symbol_info['qty_decs_qty']
        botClass.qd_quote = symbol_info['qty_decs_quote']

        botClass.res['symbol'] = symbol
        botClass.res['periods'] = int(klines['close'].count())
        botClass.res['from'] = kline_ini.strftime('%Y-%m-%d')
        botClass.res['to'] = kline_end.strftime('%Y-%m-%d')
        botClass.res['base_asset'] = botClass.wallet_base
        botClass.res['quote_asset'] = botClass.wallet_quote
        botClass.res['qd_price'] = botClass.qd_price
        botClass.res['qd_qty'] = botClass.qd_qty
        botClass.res['qd_quote'] = botClass.qd_quote
        botClass.res['interval_id'] = self.estrategia.interval_id

        botClass.res['brief'] = botClass.get_brief()

        json_rsp['bt'] = botClass.res
        json_rsp['ok'] = True
        
        return json_rsp
    
    def update_status(self,new_status):
        actual_status = eval(self.status) if len(self.status) > 0 else {}
        for k in new_status:
            actual_status[k] = new_status[k]
        self.status = str(actual_status)
        self.save()

        #Analizando si aplica registrar el PNL de acuerdo al timeframe del bot
        apply_intervals = fn.get_apply_intervals(timezone.now())
        print('.',end='')
        if self.estrategia.interval_id in apply_intervals:
            print(timezone.now(),' - Actualizando PNL')
            self.add_pnl(actual_status['wallet_tot']['r'],actual_status['price']['r'])
    
    def add_pnl(self,pnl,price):
        botpnl = BotPnl()
        botpnl.bot = self
        botpnl.pnl = pnl
        botpnl.price = price
        botpnl.save()

class Order(models.Model):
    bot = models.ForeignKey(Bot, on_delete = models.CASCADE)
    datetime = models.DateTimeField(default=timezone.now)
    completed = models.IntegerField(default=0, null=False, blank=False, db_index=True)
    qty = models.FloatField(null=False, blank=False)
    price = models.FloatField(null=False, blank=False)
    orderid = models.CharField(max_length = 20, null=False, blank=True, db_index=True)
    pos_order_id = models.IntegerField(default=0, null=False, blank=False, db_index=True)
    symbol = models.ForeignKey(Symbol, on_delete = models.CASCADE)
    #Definido en BotUtilsOrder: SIDE_BUY, SIDE_SELL
    side = models.IntegerField(default=0, null=False, blank=False, db_index=True)
    #Definido en BotUtilsOrder: FLAG_SIGNAL, FLAG_STOPLOSS, FLAG_TAKEPROFIT
    flag = models.IntegerField(default=0, null=False, blank=False)
    #Definido en BotUtilsOrder: TYPE_MARKET, TYPE_LIMIT, FLAG_TRAIL
    type = models.IntegerField(default=0, null=False, blank=False)
    limit_price = models.FloatField(null=False, blank=True, default=0.0)
    activation_price = models.FloatField(null=False, blank=True, default=0.0)
    active = models.IntegerField(null=False, blank=False, default=0)
    trail_perc = models.FloatField(null=False, blank=True, default=0.0)
    tag = models.TextField(null=False, blank=True, default='')
    
    class Meta:
        verbose_name = "Bot Order"
        verbose_name_plural='Bot Orders'
    
    def __str__(self):
        params = f'{self.datetime:%Y-%m-%d %Z %H:%M:%S} #{self.id} {self.str_side()}\t{self.qty}\t{self.price} {self.str_type()} {self.str_flag()} '
        if self.type != BotUtilsOrder.TYPE_MARKET:
            params += f'Limit Price {self.limit_price} '
        if self.type == BotUtilsOrder.TYPE_TRAILING:
            params += f'Trl {self.trail_perc}% '     
            if self.active:
                params += ' ACT'   
        if len(self.tag):
            params += f' {self.tag} '    

        return f'{params}'
        
    def str_side(self):
        if self.side == BotUtilsOrder.SIDE_BUY:
            return 'Compra'
        elif self.side == BotUtilsOrder.SIDE_SELL:
            return 'Venta'
        return ''
    
    def str_flag(self):
        if self.flag == BotUtilsOrder.FLAG_STOPLOSS:
            return 'Stop-Loss'
        elif self.flag == BotUtilsOrder.FLAG_TAKEPROFIT:
            return 'Take-Profit'
        return ''

    def str_type(self):
        if self.type == BotUtilsOrder.TYPE_TRAILING:
            return 'TRAIL'        
        elif self.type == BotUtilsOrder.TYPE_LIMIT:
            return 'LIMIT'
        else:
            return ''
    
    def quote_qty(self):
        return round( self.price * self.qty , self.symbol.qty_decs_quote)
    
    def comision(self):
        return round(self.quote_qty() * (BotUtilsOrder.live_exch_comision_perc/100) , self.symbol.qty_decs_quote )

class BotLog(models.Model):

    LOG_ACTIVAR = 1
    LOG_DESACTIVAR = 2

    bot = models.ForeignKey(Bot, on_delete = models.CASCADE)
    datetime = models.DateTimeField(default=timezone.now)
    log_type_id = models.IntegerField(default=0, null=False, blank=False, db_index=True)
    texto = models.TextField(null=False, blank=True, default='')
    
    class Meta:
        verbose_name = "Bot Log"
        verbose_name_plural='Bot Logs'
    
    def get_type(self):
        if self.log_type_id == self.LOG_ACTIVAR:
            return 'Activar'
        if self.log_type_id == self.LOG_DESACTIVAR:
            return 'Desactivar'
        return 'Evento'
    
    def get_class(self):
        if self.log_type_id == self.LOG_ACTIVAR:
            return 'green'
        if self.log_type_id == self.LOG_DESACTIVAR:
            return 'red'
        return ''
        
class BotPnl(models.Model):

    bot = models.ForeignKey(Bot, on_delete = models.CASCADE)
    datetime = models.DateTimeField(default=timezone.now)
    pnl = models.FloatField(null=False, blank=False, default=0.0)
    price = models.FloatField(null=False, blank=False, default=0.0)
    
    class Meta:
        verbose_name = "Bot PNL"
        verbose_name_plural='Bot PNL'
        