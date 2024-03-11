from bot.model_kline import *
import numpy as np
from ..Bot_CoreLong import Bot_CoreLong
from ta.trend import ADXIndicator

class BotSRCANDLE(Bot_CoreLong):

    descripcion = 'Opera en largo \n'\
                  'Ejecuta la compra al recibir una señal, '\
                  'y cierra la operación por Stop Loss o Take Profit (Si se definen con un % mayor a cero) '\
                  'La señal se genera de acuerdo a un patro de vela y a la cercania con soportes y resistencias'
    

    def support(self, l, n1, n2): #n1 n2 before and after candle l
        for i in range(l-n1+1, l+1):
            if(self.klines.low[i]>self.klines.low[i-1]):
                return 0
        for i in range(l+1,l+n2+1):
            if(self.klines.low[i]<self.klines.low[i-1]):
                return 0
        return 1

    def resistance(self, l, n1, n2): #n1 n2 before and after candle l
        for i in range(l-n1+1, l+1):
            if(self.klines.high[i]<self.klines.high[i-1]):
                return 0
        for i in range(l+1,l+n2+1):
            if(self.klines.high[i]>self.klines.high[i-1]):
                return 0
        return 1

    def isEngulfing(self,l):
        row=l
        self.bodydiff[row] = abs(self._open[row]-self._close[row])
        if self.bodydiff[row]<0.000001:
            self.bodydiff[row]=0.000001      

        bodydiffmin = 0.002
        if (self.bodydiff[row]>bodydiffmin and self.bodydiff[row-1]>bodydiffmin and
            self._open[row-1]<self._close[row-1] and
            self._open[row]>self._close[row] and 
            (self._open[row]-self._close[row-1])>=-0e-5 and self._close[row]<self._open[row-1]): #+0e-5 -5e-5
            return 1

        elif(self.bodydiff[row]>bodydiffmin and self.bodydiff[row-1]>bodydiffmin and
            self._open[row-1]>self._close[row-1] and
            self._open[row]<self._close[row] and 
            (self._open[row]-self._close[row-1])<=+0e-5 and self._close[row]>self._open[row-1]):#-0e-5 +5e-5
            return 2
        else:
            return 0
        
    def isStar(self,l):
        bodydiffmin = 0.0020
        row=l
        self.highdiff[row] = self._high[row]-max(self._open[row],self._close[row])
        self.lowdiff[row] = min(self._open[row],self._close[row])-self._low[row]
        self.bodydiff[row] = abs(self._open[row]-self._close[row])
        if self.bodydiff[row]<0.000001:
            self.bodydiff[row]=0.000001
        self.ratio1[row] = self.highdiff[row]/self.bodydiff[row]
        self.ratio2[row] = self.lowdiff[row]/self.bodydiff[row]

        if (self.ratio1[row]>1 and self.lowdiff[row]<0.2*self.highdiff[row] and self.bodydiff[row]>bodydiffmin):# and self._open[row]>self._close[row]):
            return 1
        elif (self.ratio2[row]>1 and self.highdiff[row]<0.2*self.lowdiff[row] and self.bodydiff[row]>bodydiffmin):# and self._open[row]<self._close[row]):
            return 2
        else:
            return 0
        
    def closeResistance(self,l,levels,lim):
        if len(levels)==0:
            return 0
        c1 = abs(self._high[l]-min(levels, key=lambda x:abs(x-self._high[l])))<=lim
        c2 = abs(max(self._open[l],self._close[l])-min(levels, key=lambda x:abs(x-self._high[l])))<=lim
        c3 = min(self._open[l],self._close[l])<min(levels, key=lambda x:abs(x-self._high[l]))
        c4 = self._low[l]<min(levels, key=lambda x:abs(x-self._high[l]))
        if( (c1 or c2) and c3 and c4 ):
            return 1
        else:
            return 0
        
    def closeSupport(self,l,levels,lim):
        if len(levels)==0:
            return 0
        c1 = abs(self._low[l]-min(levels, key=lambda x:abs(x-self._low[l])))<=lim
        c2 = abs(min(self._open[l],self._close[l])-min(levels, key=lambda x:abs(x-self._low[l])))<=lim
        c3 = max(self._open[l],self._close[l])>min(levels, key=lambda x:abs(x-self._low[l]))
        c4 = self._high[l]>min(levels, key=lambda x:abs(x-self._low[l]))
        if( (c1 or c2) and c3 and c4 ):
            return 1
        else:
            return 0

    def start(self):
        self.length = len(self.klines)
        self._high = list(self.klines['high'])
        self._low = list(self.klines['low'])
        self._close = list(self.klines['close'])
        self._open = list(self.klines['open'])
        self.bodydiff = [0] * self.length

        self.highdiff = [0] * self.length
        self.lowdiff = [0] * self.length
        self.ratio1 = [0] * self.length
        self.ratio2 = [0] * self.length

        n1=2
        n2=2
        backCandles=30
        signal = [0] * self.length

        self.graph_open_orders = False
        self.print_orders = False

        for row in range(backCandles, self.length-n2):
            ss = []
            rr = []
            for subrow in range(row-backCandles+n1, row+1):
                if self.support(subrow, n1, n2):
                    ss.append(self._low[subrow])
                if self.resistance(subrow, n1, n2):
                    rr.append(self._high[subrow])
            #!!!! parameters
            if ((self.isEngulfing(row)==1 or self.isStar(row)==1) and self.closeResistance(row, rr, 150e-5) ):#and df.RSI[row]<30
                signal[row] = 'NEUTRO' #Esto seria una señal de entrada en Short
            elif((self.isEngulfing(row)==2 or self.isStar(row)==2) and self.closeSupport(row, ss, 150e-5)):#and df.RSI[row]>70
                signal[row] = 'COMPRA'
            else:
                signal[row] = 'NEUTRO'

        self.klines['signal']=signal
        
      