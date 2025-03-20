from django.conf import settings
from django.db import models
from django.contrib.auth.models import User

from django.db.models import Sum
from django.utils import timezone
import pandas as pd
from scripts.Exchange import Exchange
import pickle
import os
from django.conf import settings


from scripts.Bot_Core_utils import Order as BotUtilsOrder
from bot.models import Symbol

class Sw(models.Model):
    name = models.CharField(max_length = 50, unique = True, null=False, blank=False)
    usuario = models.ForeignKey(User, on_delete = models.CASCADE)
    quote_asset = models.CharField(max_length = 16, null=False, blank=False)
    estado = models.IntegerField(default=timezone.now, null=False, blank=False)
    creado = models.DateTimeField(null=False, blank=False, db_index=True)
    finalizado = models.DateTimeField(null=True, blank=True, db_index=True)
    activo = models.IntegerField(default=0)  

    ESTADO_NODATA = 0
    ESTADO_ONLINE = 10
    ESTADO_STANDBY = 20
    ESTADO_ERROR = 30
    ESTADO_STOPPED = 90

   
    def __str__(self):
        return f'Usuario {self.usuario.username}'
    
    class Meta:
        verbose_name = "Smart Wallet"
        verbose_name_plural='Smart Wallets'

    def can_activar(self):
        cap = self.get_capital()
        orders = self.get_orders()
        qty = len(orders)+len(cap)
        return True if (qty > 0 and self.activo == 0) else False
    
    def activar(self):
        self.activo = 1
        self.estado = self.ESTADO_NODATA
        self.save()
        
    def desactivar(self):
        self.activo = 0
        self.estado = self.ESTADO_STOPPED
        self.save()

    def can_delete(self):
        cap = self.get_capital()
        orders = self.get_orders()
        qty = len(orders)+len(cap)
        return True if (qty == 0 and self.activo == 0) else False
    
    def str_estado(self):
        arr = {
            self.ESTADO_NODATA      : 'Pendiente de incorporar ordenes',
            self.ESTADO_ONLINE      : 'En curso',
            self.ESTADO_STANDBY     : 'En pausa',
            self.ESTADO_ERROR       : 'Error',
            self.ESTADO_STOPPED     : 'Detenido',
        }
        str_activo = 'Activado -' if self.activo > 0 else 'Desactivado -'
        return str_activo+' '+arr.get(self.estado)


    def estado_class(self):
        arr = {
            self.ESTADO_NODATA    : 'text-danger',
            self.ESTADO_ONLINE    : 'text-success',
            self.ESTADO_STANDBY   : 'text-warning',
            self.ESTADO_ERROR     : 'text-danger',
            self.ESTADO_STOPPED   : 'text-secondary',
        }
        return arr.get(self.estado)
    
    
    def get_capital(self):
        cap = SwCapital.objects.filter(sw=self).order_by('datetime')
        return list(cap)
    
    def get_symbols(self):
        symbols = Symbol.objects.filter(swcapital__sw=self).distinct()
        return symbols

    def get_assets(self):
        cap = SwCapital.objects.filter(sw=self).order_by('symbol__base_asset')
        base_assets = cap.values_list('symbol__base_asset', flat=True).distinct()
        return list(base_assets)
    
    def get_orders(self):
        orders = SwOrder.objects.filter(sw=self).order_by('datetime')
        return list(orders)

    def calcular_rendimiento(self, symbol, orders, price):

        #Calcular el stock total
        stock_compra = sum(o['qty'] for o in orders if (o['side']==0))
        stock_venta  = sum(o['qty'] for o in orders if (o['side']==1))
        stock_total = stock_compra - stock_venta
        
        #Calcular el costo neto invertido
        costo_compras_orders = sum(o['qty']*o['price'] for o in orders if (o['side']==0 and o['type']=='O'))
        costo_aportes = sum(o['qty']*o['price'] for o in orders if (o['side']==0 and o['type']=='C'))
        valor_retiros = sum(o['qty']*o['price'] for o in orders if (o['side']==1 and o['type']=='C'))
        costo_neto = costo_compras_orders + costo_aportes - valor_retiros

        #Calcular las ganancias y el valor actual total
        qty_comprada = sum(o['qty'] for o in orders if (o['side']==0 ))
        costo_qty_comprada = sum(o['qty']*o['price'] for o in orders if (o['side']==0 ))
        precio_promedio = costo_qty_comprada/qty_comprada
        ganancias_realizadas = sum(o['qty']* (o['price'] - precio_promedio) for o in orders if (o['side']==1))
        ganancias_netas = ganancias_realizadas - valor_retiros

        valor_stock = stock_total * price
        valor_actual_total = ganancias_netas + valor_stock
        ganancia_absoluta = ganancias_realizadas + valor_stock
        ganancia_neta_total = ganancia_absoluta - costo_neto

        #Calcular el rendimiento total (%)
        if costo_neto > 0:
            rendimiento = ((valor_actual_total / costo_neto) - 1) * 100
        else:
            rendimiento = float('inf') if valor_actual_total > 0 else 0

        # Calcular el PPPAG (Precio Promedio Ponderado Ajustado por Ganancias)
        if stock_total > 0:
            costo_ajustado = costo_qty_comprada - ganancias_realizadas
            pppag = costo_ajustado / stock_total
        else:
            pppag = None  # No hay stock, no tiene sentido calcularlo

        return {
            'stock_total': round(stock_total,symbol.qty_decs_qty),
            'costo_neto': round(costo_neto,2),
            'valor_retiros': round(valor_retiros,symbol.qty_decs_price),
            'valor_stock': round(valor_stock,symbol.qty_decs_price),
            'valor_actual_total': round(valor_actual_total,2),
            'precio_actual': round(price,symbol.qty_decs_price),
            'ganancias_realizadas':  round(ganancias_realizadas,2),
            'ganancias_netas':  round(ganancias_netas,2),
            'ganancia_absoluta': round(ganancia_absoluta,2),
            'ganancia_neta_total': round(ganancia_neta_total,2),
            'rendimiento': round(rendimiento,2),
            'pppag': round(pppag,symbol.qty_decs_price),
        }

    def get_assets_brief(self):

        symbols = self.get_symbols()
        assets_brief = {}
        
        #Buscando precios de los symbols
        exchInfo = Exchange(type='info',exchange='bnc',prms=None)
        prices = exchInfo.get_all_prices()

        for symbol in symbols:
            asset = symbol.base_asset
            price = prices[symbol.base_asset+symbol.quote_asset] 
            orders_capital = self.get_capital()
            orders_orders = self.get_orders()

            orders = []
            for o in orders_capital:
                if o.symbol == symbol:
                    qty = o.qty if o.qty > 0 else -o.qty
                    side = 0 if o.qty > 0 else 1
                    orders.append({'qty':qty, 'price': o.price,'type':'C','side':side})
            for o in orders_orders:
                if o.symbol == symbol:
                    orders.append({'qty':o.qty, 'price': o.price,'type':'O','side':o.side})
            
            assets_brief[asset] = self.calcular_rendimiento(symbol,orders,price)

        return assets_brief
        
class SwCapital(models.Model):
    sw = models.ForeignKey(Sw, on_delete = models.CASCADE)
    datetime = models.DateTimeField(default=timezone.now)
    qty = models.FloatField(null=False, blank=False) #Positivo para inyeccion de capital y negativo para retiros
    price = models.FloatField(null=False, blank=False)
    symbol = models.ForeignKey(Symbol, on_delete = models.CASCADE)
    
class SwOrder(models.Model):
    sw = models.ForeignKey(Sw, on_delete = models.CASCADE)
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
    #Definido en BotUtilsOrder: TYPE_MARKET, TYPE_LIMIT
    type = models.IntegerField(default=0, null=False, blank=False)
    limit_price = models.FloatField(null=False, blank=True, default=0.0)
    tag = models.TextField(null=False, blank=True, default='')
    
    class Meta:
        verbose_name = "SW Order"
        verbose_name_plural='SW Orders'
    
    def __str__(self):
        params = f'{self.datetime:%Y-%m-%d %Z %H:%M} #{self.id} {self.str_side()}\t{self.qty}\t{self.price} {self.str_type()} {self.str_flag()} '
        if self.type != BotUtilsOrder.TYPE_MARKET:
            params += f'Limit Price {self.limit_price} '
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
        if self.type == BotUtilsOrder.TYPE_LIMIT:
            return 'LIMIT'
        else:
            return ''
    
    def quote_qty(self):
        return round( self.price * self.qty , self.symbol.qty_decs_quote)
    
    def comision(self):
        return round(self.quote_qty() * (BotUtilsOrder.live_exch_comision_perc/100) , self.symbol.qty_decs_quote+4 )
