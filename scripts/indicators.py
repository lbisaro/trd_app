import pandas as pd
import pandas_ta
import numpy as np

def supertrend(df,length=7,multiplier=3):
    """
    Al dataframe le agrega las siguientes columnas
    st_trend: Muestra la tendencia del precio
    st_trigger: Indica el cambio de tendencia


    Los valores de las columnas pueden ser:
    1  (Alcista)          -1 (Bajista)          0  (Neutro)      
    
    """
    st_length = length
    st_multiplier = multiplier
    df.ta.supertrend(length=st_length, multiplier=st_multiplier, append=True)

    ### Renombrando columnas del SuperTrend
    cols = df.columns
    posfix = ''
    for col in cols:
        if col.startswith('SUPERT_'):
            posfix = col.replace('SUPERT','')
    for col in cols:
        if col.endswith(posfix):
            new_col = col.replace(posfix,'')
            df.rename(columns={col: new_col}, inplace=True)
    ###

    df['st_trend'] = df['SUPERTd']
    df['st_trigger'] = np.where((df['SUPERTd']>0) & (df['SUPERTd'].shift(1)<=0) ,1,0)
    df['st_trigger'] = np.where((df['SUPERTd']<0) & (df['SUPERTd'].shift(1)>=0) ,-1,df['st_trigger']) 
    df['st_low'] = df['SUPERTl']
    df['st_high'] = df['SUPERTs']
    df = df.drop(['SUPERTd','SUPERTl','SUPERTs','SUPERT'], axis=1)

    return df

def volume_level(df,period=50,level_extrahigh=2.0,level_high=1.0,level_medium=0.0,level_low=-1.0):
    """
    Level:
        ExtraHigh   =   2.0     3.0
        High        =   1.0     1.5
        Medium      =   0.0     0.2
        Normal      =  -1.0    -0.5

       Lectura
           vol_signal = 1  -> Volumen optimo para entradas en Long
           vol_signal = -1 -> Volumen optimo para entradas en Short
        
           vol_range = [1 a 5] El volumen standard es vol_range = 3 - vol_range = 1 minimo - vol_range = 5 maximo

    """
    vol_period = period
    thresholdExtraHigh = level_extrahigh
    thresholdHigh = level_high
    thresholdMedium = level_medium
    thresholdLow = level_low

    df['vol_mean'] = df['volume'].rolling(window=vol_period).mean()
    df['vol_std']  = df['volume'].rolling(window=vol_period).std()
    df['vol_eh'] = df['vol_std'] * thresholdExtraHigh + df['vol_mean']
    df['vol_h'] = df['vol_std'] * thresholdHigh + df['vol_mean']
    df['vol_m'] = df['vol_std'] * thresholdMedium + df['vol_mean']
    df['vol_n'] = df['vol_std'] * thresholdLow + df['vol_mean']
    df['vol_range'] = np.where((df['volume']>0)&(df['volume']<=df['vol_n']),1,0)
    df['vol_range'] = np.where((df['volume']>df['vol_n'])&(df['volume']<=df['vol_m']),2,df['vol_range'])
    df['vol_range'] = np.where((df['volume']>df['vol_m'])&(df['volume']<=df['vol_h']),3,df['vol_range'])
    df['vol_range'] = np.where((df['volume']>df['vol_h'])&(df['volume']<=df['vol_eh']),4,df['vol_range'])
    df['vol_range'] = np.where((df['volume']>df['vol_eh']),5,df['vol_range'])

    df['signal_sign'] = np.where(df['close']>df['open'],1,-1)
    
    #El volumen debe estar entre medio (vol_l) y alto (vol_h)
    df['vol_signal'] = np.where((df['vol_range']==3), 1 * df['signal_sign'],None)

    df = df.drop(['vol_mean','vol_std','vol_eh','vol_h','vol_eh','signal_sign'], axis=1)
    return df

def volatility_level(df,period=40,level_extrahigh=2.5,level_high=0.75,level_medium=-0.25,level_low=-0.75):
    """
    Level:
        ExtraHigh   =   2.50
        High        =   0.75
        Medium      =  -0.25
        Normal      =  -0.75

        Lectura
           vlt_signal = 1  -> Volatilidad optima para entradas en Long
           vlt_signal = -1 -> Volatilidad optima para entradas en Short
        
           vlt_range = [1 a 5] La volatilidad standard es vlt_range = 2 - vlt_range = 1 minimo - vlt_range = 5 maximo

    """
    vlt_period = period
    thresholdExtraHigh = level_extrahigh
    thresholdHigh = level_high
    thresholdMedium = level_medium
    thresholdNormal = level_low


    df['vlt'] = abs( ((df['open']/df['close'])-1)*100 )
    df['vlt_mean'] = df['vlt'].rolling(window=vlt_period).mean()
    df['vlt_std']  = df['vlt'].rolling(window=vlt_period).std()
    df['vlt_eh'] = df['vlt_std'] * thresholdExtraHigh + df['vlt_mean']
    df['vlt_h'] = df['vlt_std'] * thresholdHigh + df['vlt_mean']
    df['vlt_m'] = df['vlt_std'] * thresholdMedium + df['vlt_mean']
    df['vlt_n'] = df['vlt_std'] * thresholdNormal + df['vlt_mean']
    df['vlt_range'] = np.where((df['vlt']>0)&(df['vlt']<=df['vlt_n']),1,0)
    df['vlt_range'] = np.where((df['vlt']>df['vlt_n'])&(df['vlt']<=df['vlt_m']),2,df['vlt_range'])
    df['vlt_range'] = np.where((df['vlt']>df['vlt_m'])&(df['vlt']<=df['vlt_h']),3,df['vlt_range'])
    df['vlt_range'] = np.where((df['vlt']>df['vlt_h'])&(df['vlt']<=df['vlt_eh']),4,df['vlt_range'])
    df['vlt_range'] = np.where((df['vlt']>df['vlt_eh']),5,df['vlt_range'])

    df['signal_sign'] = np.where(df['close']>df['open'],1,-1)
    
    #El volumen debe estar entre medio (vol_l) y alto (vol_h)
    df['vlt_signal'] = np.where((df['vlt_range']==2), 1 * df['signal_sign'],None)

    df = df.drop(['vlt_mean','vlt_std','vlt_eh','vlt_h','vlt_eh','signal_sign'], axis=1)
    return df


# Función para calcular los pivotes de máximos y mínimos
def find_pivots(df,dev_threshold=0,dev_trend=0.33):
    df['max_pivots'] = None
    df['min_pivots'] = None
    df['max_trend'] = None
    df['min_trend'] = None

    if 1 < dev_trend < 0:
        assert "dev_trend debe ser un valor entre 0 y 1"
    
    dict = df.to_dict(orient='index')
    if dev_threshold == 0:
        df['mean'] = (df['high'] - df['low']) / ((df['high'] + df['low']) / 2) * 100
        dev_threshold = round(df['mean'].mean() * 1.5,3)
        if dev_threshold < 3:
            dev_threshold = 3
    
    max_val = None
    min_val = None
    last = None

    for i in dict:
        high = dict[i]['high']
        low = dict[i]['low']

        if max_val is None or high > max_val:
            max_val = high
        if min_val is None or low < min_val:
            min_val = low

        #Tendencias
        if (max_val- high) / max_val * 100 >= dev_threshold*dev_trend:
            if last is None or last != 'max':
                dict[i]['max_trend'] = max_val
        if (low - min_val) / min_val * 100 >= dev_threshold*dev_trend:
            if last is None or last != 'min':
                dict[i]['min_trend'] = min_val
        
        #Pivots
        if (max_val- high) / max_val * 100 >= dev_threshold:
            if last is None or last != 'max':
                dict[i]['max_pivots'] = max_val
            last = 'max'
            max_val = None
        elif (low - min_val) / min_val * 100 >= dev_threshold:
            if last is None or last != 'min':
                dict[i]['min_pivots'] = min_val
            last = 'min'
            min_val = None

    df = pd.DataFrame.from_dict(dict, orient='index')
    return df


class Fibonacci:
    """
    Uso: ff = Fibonacci().long(df, dev_threshold=0, dev_trend = 0.33)
    """
    
    last_pivots = [['',0],['',0],['',0]]
    last_fibo = None

    def evaluate_long(self, min):
        if self.last_pivots[0][0] == 'min' and self.last_pivots[1][0] == 'max' and self.last_pivots[2][0] == 'min':
            #Si los ultimos 3 pivotes son min, max, min
            if self.last_pivots[0][1] > self.last_pivots[2][1] and self.last_pivots[1][1] > self.last_pivots[0][1]:
                #Si El ultimo min es mayor al primer min, y el max es mayor al ultimo min
                #Hay un pull-back, entonces devuelve el [max,ultimo min]
                return [self.last_pivots[1][1],self.last_pivots[0][1]]
        elif min > 0 and self.last_pivots[0][0] == 'max' and self.last_pivots[1][0] == 'min' :
            #Si no hay un pull-back pero
            #Hay tendencia a un min y los ultimos pivots son max, min  
            if min > self.last_pivots[1][1] and self.last_pivots[0][1] > min:
                #Si el ultimo min es mayor a la tendencia min y el max es mayor al ultimo min
                return [self.last_pivots[0][1],min]
            
        return None

    def add_pivots(self,type,price):
        self.last_pivots[2] = self.last_pivots[1]
        self.last_pivots[1] = self.last_pivots[0]
        self.last_pivots[0] = [type,price]

    def long(self,df,dev_threshold=0,dev_trend = 0.33):
        self.dev_threshold=dev_threshold
        self.dev_trend = dev_trend

        df = df
        df = find_pivots(df,self.dev_threshold,self.dev_trend) 

        df['fibo_0.000'] = None
        df['fibo_1.000'] = None
        df['fibo'] = None

        df_dict = df.to_dict(orient='index')

        self.last_pivots = [['',0],['',0],['',0]]
        self.last_fibo = None

        for i in df.index:
            row = df.loc[i]
            
            if row['max_pivots'] > 0:
                self.add_pivots('max',row['max_pivots'])
            if row['min_pivots'] > 0: 
                self.add_pivots('min',row['min_pivots'])
            
            fibo = self.evaluate_long(row['min_trend'])

            df_dict[i]['fibo'] = 0
            if fibo is not None: 
                if fibo != self.last_fibo:
                    df_dict[i]['fibo'] = 1
                df_dict[i]['fibo_0.000'] = fibo[0]
                df_dict[i]['fibo_1.000'] = fibo[1]
            self.last_fibo = fibo

        df = pd.DataFrame.from_dict(df_dict, orient='index')
        df.reset_index(inplace=True)
        return df

def donchian(df, period = 20):
    df['dch_max'] = df['high'].rolling(window=period).max()
    df['dch_min'] = df['low'].rolling(window=period).min()
    df['dch_mean'] = (df['dch_max']+df['dch_min'])/2
    return df