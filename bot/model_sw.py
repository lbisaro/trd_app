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

from collections import deque
import math
from datetime import datetime

from scripts.Bot_Core_utils import Order as BotUtilsOrder
from bot.models import Symbol

class WalletLog(models.Model):
    usuario = models.ForeignKey(User, on_delete = models.CASCADE)
    date = models.DateField(null=False, blank=False, db_index=True)
    total_usd = models.FloatField(null=False, blank=False)

class WalletCapital(models.Model):
    usuario = models.ForeignKey(User, on_delete = models.CASCADE)
    date = models.DateField(null=False, blank=False, db_index=True)
    total_usd = models.FloatField(null=False, blank=False)
    reference = models.CharField(max_length = 50, unique = False, null=False, blank=False)

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
        orders = self.get_orders()
        qty = len(orders)
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
        orders = self.get_orders()
        qty = len(orders)
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
    
    def get_symbols(self):
        symbols = Symbol.objects.filter(sworder__sw=self).distinct()
        return symbols

    def get_assets(self):
        cap = SwOrder.objects.filter(sw=self).order_by('symbol__base_asset')
        base_assets = cap.values_list('symbol__base_asset', flat=True).distinct()
        return list(base_assets)
    
    def get_orders(self,**kwargs):
        if 'symbol' in kwargs:
            orders = SwOrder.objects.filter(sw=self,symbol=kwargs['symbol']).order_by('datetime')
        else:
            orders = SwOrder.objects.filter(sw=self).order_by('datetime')

        return list(orders)

    def get_asset_brief(self, symbol, orders, current_price):
        """
        Analiza un historial de órdenes para un activo específico usando FIFO.

        Calcula P&L realizado, estado de la posición abierta, P&L total,
        precio de break-even global y distancia porcentual al precio promedio.

        Args:
            symbol: Objeto Symbol que representa el activo.
            orders (list): Lista de diccionarios de órdenes.
            current_price (float): Precio actual de mercado del activo.

        Returns:
            dict: Un diccionario con las métricas clave del análisis:
                  'symbol_name': Identificador del símbolo.
                  'realized_pnl': Ganancia/Pérdida total de operaciones cerradas.
                  'open_quantity': Cantidad actual en posesión.
                  'open_cost_basis': Costo total de la posición abierta.
                  'average_buy_price': Precio promedio de compra de la posición abierta.
                  'current_market_value': Valor de mercado actual de la posición abierta.
                  'unrealized_pnl': Ganancia/Pérdida no realizada de la posición abierta.
                  'total_pnl': P&L realizado + P&L no realizado.
                  'break_even_price': Precio de venta para P&L total = 0 (None si no hay pos. abierta).
                  'price_distance_percent': Distancia % entre precio actual y avg_buy_price (None si no aplica).
        """

        # --- 1. Validación y Preparación Inicial ---
        if not orders:
            return {
                'symbol_name': getattr(symbol, 'name', str(symbol)),
                'realized_pnl': 0.0,
                'open_quantity': 0.0,
                'open_quantity_in_usd':0,
                'open_cost_basis': 0.0,
                'average_buy_price': 0.0,
                'current_market_value': 0.0,
                'unrealized_pnl': 0.0,
                'total_pnl': 0.0,
                'break_even_price': None,
                'price_distance_percent': None, # Nuevo campo
            }

        # --- 2. Procesamiento FIFO ---
        open_positions = deque()
        realized_pnl = 0.0
        open_quantity = 0.0
        open_cost_basis = 0.0
        float_tolerance = 1e-9 # Ajustar si se necesita más/menos precisión

        for order in orders:
            qty = order['qty']
            price = order['price']
            side = order['side']

            if not isinstance(qty, (int, float)) or not isinstance(price, (int, float)) or qty <= 0 or price <= 0:
                print(f"Advertencia: Orden inválida encontrada y omitida en {order.get('datetime', 'N/A')} "
                      f"(qty={qty}, price={price}).")
                continue

            if side == 0:
                open_positions.append((qty, price))
                open_quantity += qty
                open_cost_basis += qty * price
            elif side == 1:
                qty_to_sell = qty
                sell_price = price
                while qty_to_sell > float_tolerance and open_positions:
                    buy_qty, buy_price = open_positions[0]
                    match_qty = min(qty_to_sell, buy_qty)
                    pnl_contribution = match_qty * (sell_price - buy_price)
                    realized_pnl += pnl_contribution
                    open_quantity -= match_qty
                    open_cost_basis -= match_qty * buy_price
                    if abs(buy_qty - match_qty) < float_tolerance:
                        open_positions.popleft()
                    else:
                        open_positions[0] = (buy_qty - match_qty, buy_price)
                    qty_to_sell -= match_qty
                # Omitido el warning de venta corta por brevedad

        # --- 3. Cálculos Finales ---
        if open_quantity < float_tolerance:
            open_quantity = 0.0
            open_cost_basis = 0.0

        average_buy_price = 0.0
        current_market_value = 0.0
        unrealized_pnl = 0.0
        break_even_price = None
        price_distance_percent = None # Inicializar como None

        if open_quantity > float_tolerance:
            # Calcular métricas estándar de posición abierta
            average_buy_price = open_cost_basis / open_quantity
            current_market_value = current_price * open_quantity
            unrealized_pnl = current_market_value - open_cost_basis

            # Calcular Break-Even Price
            try:
                break_even_price = (open_cost_basis - realized_pnl) / open_quantity
            except ZeroDivisionError:
                 break_even_price = None # Seguridad, aunque no debería pasar aquí

            # *** NUEVO: Calcular Distancia Porcentual ***
            # Solo si average_buy_price es válido (no cero)
            if abs(average_buy_price) > float_tolerance:
                 try:
                    price_distance_percent = (current_price / average_buy_price - 1) * 100
                 except ZeroDivisionError:
                    price_distance_percent = None # Seguridad adicional
            else:
                # Si avg buy price es 0, la distancia % no es significativa
                price_distance_percent = None

        else:
            # No hay posición abierta, los valores por defecto (0 o None) se mantienen
            pass

        total_pnl = realized_pnl + unrealized_pnl

        # --- 4. Devolver Resultados ---
        # Usar los decimales definidos en el objeto symbol
        qty_decs_qty = getattr(symbol, 'qty_decs_qty', 8) # Default 8 si no existe
        qty_decs_price = getattr(symbol, 'qty_decs_price', 5) # Default 5 si no existe

        return {
            'symbol_id': symbol.id,
            'realized_pnl': round(realized_pnl, 2),
            'open_quantity': round(open_quantity, qty_decs_qty),
            'open_quantity_in_usd': round(open_quantity*current_price, 2),
            'open_cost_basis': round(open_cost_basis, 2),
            'average_buy_price': round(average_buy_price, qty_decs_price) if average_buy_price is not None else 0.0,
            'current_price': round(current_price, qty_decs_price),
            'current_market_value': round(current_market_value, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'total_pnl': round(total_pnl, 2),
            'break_even_price': round(break_even_price, qty_decs_price) if break_even_price is not None else None,
            'price_distance_percent': round(price_distance_percent, 2) if price_distance_percent is not None else None, # Redondeado a 2 decimales para %
        }

        return {
            'stock_total': round(total_qty_open,symbol.qty_decs_qty),
            'valor_stock': round(valor_stock,2),
            'precio_promedio': round(average_buy_price,symbol.qty_decs_price),
            'valor_compras': round(total_cost_open,2),
            'stock_quote': round(total_qty_open,2),
            'total_stock_en_usd': round(valor_stock,2),
            'precio_actual': round(precio_actual,symbol.qty_decs_price),
            'ganancias_realizadas':  round(realized_pnl,2),
            'distancia_ppc': round(distancia_ppc,2),
            'ganancias_y_stock': round(ganancias_y_stock,2),
            'symbol_id': symbol.id,
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
            db_orders = self.get_orders(symbol=symbol)

            orders = []
            for o in db_orders:
                if o.symbol == symbol:
                    orders.append({'qty':o.qty, 'price': o.price,'side':o.side})
            
            assets_brief[asset] = self.get_asset_brief(symbol,orders,price)

        return assets_brief
    
class SwOrder(models.Model):
    sw = models.ForeignKey(Sw, on_delete = models.CASCADE)
    datetime = models.DateTimeField(default=timezone.now)
    completed = models.IntegerField(default=0, null=False, blank=False, db_index=True)
    qty = models.FloatField(null=False, blank=False)
    price = models.FloatField(null=False, blank=False)
    orderid = models.CharField(default='NA', max_length = 20, null=False, blank=True, db_index=True)
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
