# fuente: https://www.youtube.com/watch?v=mAAEqRJdn8E&list=PLNoiCkWIym-2sr6cBzjII50F4kfAVhHWX&index=1&t=17s

import yfinance as yf
import backtrader as bt
import matplotlib
import matplotlib.pyplot as plt
import backtrader.plot
import datetime

class Strategy(bt.Strategy):
    params = dict(
            ma=bt.ind.SMA,
            p1=5,
            p2=15,
            limit=0.005,
            limdays=3,
            limdays2=1000,
            hold=10,
            usebracket=False,  # use order_target_size
            switchp1p2=False,  # switch prices of order1 and order2
        )
        
    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(),txt))
    
    def __init__(self):
        self.psar = bt.ind.ParabolicSAR()
        self.sma = bt.ind.SMA(period=100)
        self.ema = bt.ind.SMA(period=21)
        self.order = None
        self.orefs = list()
        
    def notify_order(self,order):
        if (order.status in [order.Submitted, order.Accepted]):
            return
        
        if order.status in [order.Completed]:
            #if order.isbuy():
            #    self.log('BUY EXECUTED, %.2f, \[ %.2f \]' % (order.executed.price,cerebro.broker.getvalue()))
            #if order.issell():
            #    self.log('SELL EXECUTED, %.2f, \[ %.2f \]' % (order.executed.price,cerebro.broker.getvalue()))
            
            self.bar_executed = len(self)
        
        #elif order.status in [order.Cancelled, order.Margin, order.Rejected]:
        #    self.log('Order Cancelled/Margin/Rejected')
            
        self.order = None
        
    def next(self):
        #self.log('Close, %.2f' % self.dataclose[0])
        #Si hay una orden en curso no hacer nada
        if self.order:
            return
        if not self.position:
            if self.psar < self.data.close and self.ema> self.sma:
                close = self.data.close[0]
                p1 = close * (1.0 - self.p.limit)
                p2 = p1 * 0.98
                p3 = p1 * 1.20

                valid1 = datetime.timedelta(self.p.limdays)
                valid2 = valid3 = datetime.timedelta(self.p.limdays2)

                os = self.buy_bracket(
                        price=p1, valid=valid1,
                        stopprice=p2, stopargs=dict(valid=valid2),
                        limitprice=p3, limitargs=dict(valid=valid3),)

                self.orefs = [o.ref for o in os]
                    
cerebro = bt.Cerebro()
cerebro.addstrategy(Strategy)

data = bt.feeds.PandasData(dataname=yf.download(
    tickers = 'BTC-USD', 
    interval = "1d",
    start='2019-01-01', 
    end='2024-10-15'))

cerebro.adddata(data)
cerebro.broker.setcash(1000000.0)
cerebro.broker.setcommission(commission=0.001)
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

results = cerebro.run()

strategy = results[0]

# Obtener resultados de cada analyzer
drawdown = strategy.analyzers.drawdown.get_analysis()
returns = strategy.analyzers.returns.get_analysis()
trades = strategy.analyzers.trades.get_analysis()

# Imprimir resultados
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

#El plot se debe ejecutar por consola fuera de Spyder
#cerebro.plot(height= 30, iplot= False)[0][0]
