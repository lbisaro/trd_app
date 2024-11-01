# fuente: https://www.youtube.com/watch?v=mAAEqRJdn8E&list=PLNoiCkWIym-2sr6cBzjII50F4kfAVhHWX&index=1&t=17s
import backtrader as bt
import matplotlib
import matplotlib.pyplot as plt
import backtrader.plot
import datetime

import pandas as pd
import numpy as np


import pickle


klines_file  = './backtest/klines/1h01/Full_BTCUSDT_1h01_2019-01-01_2024-10-15.DataFrame'
#klines_file  = './backtest/klines/1h01/Completo_BNBUSDT_1h01_2021-01-01_2023-07-31.DataFrame'
#klines_file  = './backtest/klines/1h01/Completo_ETHUSDT_1h01_2021-01-01_2023-07-31.DataFrame'
#klines_file  = './backtest/klines/1h01/Completo_BTCUSDT_1h01_2021-01-01_2023-07-31.DataFrame'


with open(klines_file, 'rb') as file:
    df = pickle.load(file)



# Clase de la estrategia
class MyStrategy(bt.Strategy):
    params = dict(
        limit=0.005,
        limdays=3,
        limdays2=10000,
        stop_loss=0.5,
        take_profit=5,
    )

    def __init__(self):
        # Indicadores
        self.sma10 = bt.ind.SMA(period=21)
        self.sma100 = bt.ind.SMA(period=100)
        self.parabolic_sar = bt.ind.ParabolicSAR()

        self.order = None  # Para rastrear órdenes abiertas

    def next(self):
        # Verifica si hay una posición abierta
        if not self.position:
            if (self.sma10[0] > self.sma100[0]) and (self.data.close[0] > self.parabolic_sar[0]):
                close = self.data.close[0]
                p1 = close * (1.0 - self.p.limit)
                p2 = p1 * ((100-self.p.stop_loss)/100)
                p3 = p1 * ((100+self.p.take_profit)/100)

                valid1 = datetime.timedelta(self.p.limdays)
                valid2 = valid3 = datetime.timedelta(self.p.limdays2)

                os = self.buy_bracket(
                        price=p1, #valid=valid1,
                        stopprice=p2, #stopargs=dict(valid=valid2),
                        limitprice=p3, #limitargs=dict(valid=valid3),
                        )

                self.orefs = [o.ref for o in os]

# Configuración del cerebro
cerebro = bt.Cerebro()
cerebro.addstrategy(MyStrategy)

# Convertir el DataFrame al formato de Backtrader
df['datetime'] = pd.to_datetime(df['datetime'])
df.set_index('datetime', inplace=True)
data = bt.feeds.PandasData(dataname=df, timeframe=bt.TimeFrame.Minutes, compression=3600)
cerebro.adddata(data)

# Añadir analyzers
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

# Ejecutar el backtest
results = cerebro.run()
strategy = results[0]

# Obtener y mostrar los resultados de los analyzers
drawdown = strategy.analyzers.drawdown.get_analysis()
returns = strategy.analyzers.returns.get_analysis()
trades = strategy.analyzers.trades.get_analysis()


if trades.total.total>0:
    print("=== Drawdown ===")
    print(f"Max Drawdown: {drawdown.max.drawdown}%")
    print(f"Max Drawdown Duration: {drawdown.max.len} bars")

    print("\n=== Returns ===")
    print(f"Total Return: {returns['rtot'] * 100}%")
    print(f"Annual Return: {returns['rnorm100']}%")

    print("\n=== Trade Analysis ===")
    print(f"Total Trades: {trades.total.total}")
    print(f"Winning Trades: {trades.won.total}")
    print(f"Losing Trades: {trades.lost.total}")
    print(f"PnL Net: {trades.pnl.net.total}")
    cerebro.plot()
else:
    print("\n=== Trade Analysis ===")
    print(f"Total Trades: {trades.total.total}")

