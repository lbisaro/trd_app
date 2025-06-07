import pandas as pd
import pandas_ta
import numpy as np
import pandas_ta as ta
from pandas_ta.trend import adx

def resample(df,periods,reset_index=True):
    """
    Genera un dataframe resampleado de acuerdo a la cantidad de periodos establecidos
    Ej.: Si df es tiene un timeframe de 15m, y periods = 4, el resample se hace en 1h

    Ejemplo de uso de resample y join_after_resample:

    dfx4 = resample(df,4)
    rsi_x4 = ta.rsi(dfx4['close'], length=21)
    df = join_after_resample(df,rsi_x4,'rsi')
    df['rsi_sma'] = df['rsi'].rolling(14).mean()

    """

    timeframe = df['datetime'].iloc[1]-df['datetime'].iloc[0]
    resample = timeframe * periods
    df['base_index'] = df.index

    if reset_index:
        agg_func = {
            'datetime': 'first',
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
        }
    else:
        agg_func = {
            'datetime': 'first',
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'base_index': 'first'
        }        
  
    # Resamplear el dataframe 
    dfx = df.resample(resample, on="datetime").agg(agg_func)
    if reset_index:
        dfx.reset_index(inplace=True,drop=True)
    else:
        dfx.set_index('base_index',inplace=True,drop=True)
        dfx.rename_axis(None, inplace=True)
    return dfx

def join_after_resample(df,serie,column,periods=None):
    """
    Agrega una serie resampleada al dataframe df, asignando la columna column
    Asociando los registros con la columna datetime

    Ejemplo de uso de resample y join_after_resample:

    dfx4 = resample(df,4)
    rsi_x4 = ta.rsi(dfx4['close'], length=21)
    df = join_after_resample(df,rsi_x4,'rsi')
    df['rsi_sma'] = df['rsi'].rolling(14).mean()

    """

    df.set_index('datetime', inplace=True, drop=False)
    serie.set_index('datetime', inplace=True, drop=False)
    df = df.merge(serie[[column]], left_on=df['datetime'], right_index=True, how='left')

    if periods is None:
        df[column] = df[column].ffill()
    elif periods > 0:
        df[column] = df[column].fillna(method='ffill', limit=periods)
    
    return df

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
    df['pivot_last'] = ''
    df['max_pivots'] = None
    df['min_pivots'] = None
    df['max_trend'] = None
    df['min_trend'] = None
    df['max_last'] = None
    df['min_last'] = None
    df['max_diff'] = 0
    df['min_diff'] = 0


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

        dict[i]['pivot_last'] = last
        #Diferencia de maximos y minimos
        if dict[i]['max_pivots'] is not None:
            dict[i]['max_last'] = dict[i]['max_pivots']
            if i>0 and dict[i-1]['max_last'] is not None:
                if dict[i]['max_last']>dict[i-1]['max_last']:
                    dict[i]['max_diff'] = 1  
                elif dict[i]['max_last']<dict[i-1]['max_last']:
                    dict[i]['max_diff'] = -1  
        elif i>0:
            dict[i]['max_last'] = dict[i-1]['max_last']
            dict[i]['max_diff'] = dict[i-1]['max_diff']

        if dict[i]['min_pivots'] is not None:
            dict[i]['min_last'] = dict[i]['min_pivots']
            if i>0 and dict[i-1]['min_last'] is not None:
                if dict[i]['min_last']>dict[i-1]['min_last']:
                    dict[i]['min_diff'] = 1  
                elif dict[i]['min_last']<dict[i-1]['min_last']:
                    dict[i]['min_diff'] = -1  
        elif i>0:
            dict[i]['min_last'] = dict[i-1]['min_last']
            dict[i]['min_diff'] = dict[i-1]['min_diff']


    df = pd.DataFrame.from_dict(dict, orient='index')
    return df

def fibonacci_levels(start, end):
    levels = [0.0,23.6,38.2,50.0,61.8,78.6,100.0,127.2,161.8]
    prices = {}
    if start > end:
        high = start
        low = end
        diff = high - low
        for i in range(len(levels)):
            key = f'{levels[i]:.1f}%'
            prices[key] = low + (levels[i]/100) * diff
    else:
        high = end
        low = start
        diff = high - low
        for i in range(len(levels)):
            key = f'{levels[i]:.1f}%'
            prices[key] = high - (levels[i]/100) * diff

    return prices  

def fibonacci_retroceso(fb_a,fb_b,level):
    #Los puntos a y b se ingresan en el orden que aparecen en funcion del tiempo
    # a: Primer punto (inicio de la tendencia).
    # b: Segundo punto (final del primer movimiento).

    base = abs(fb_a - fb_b) 
    if fb_b>fb_a:
        price = fb_b - base*level
        return price
    elif fb_b<fb_a:
        price = fb_b + base*level
        return price
    return None

def fibonacci_extension(fb_a, fb_b, fb_c, level):
    #Los puntos a, b y c se ingresan en el orden que aparecen en funcion del tiempo
    # a: Primer punto (inicio de la tendencia).
    # b: Segundo punto (final del primer movimiento).
    # c: Tercer punto (retroceso dentro de la tendencia).

    base = abs(fb_b - fb_a)  
    if fb_a < fb_b:  #Alcista
        price = fb_c + base * level
    elif fb_a > fb_b:  #Bajista
        price = fb_c - base * level
    else:
        return None  
    return price

def polyfit_trend(df, column='close',window=7,fwd=1, prefix='pf'):
    df[f'{prefix}_pred'] = df[column].rolling(window).apply(lambda x: predict_price(x,fwd))
    df[f'{prefix}_change']  = ((df[f'{prefix}_pred']/df[f'{prefix}_pred'].shift(1))-1)*100
    df[f'{prefix}_trend']   = np.where(df[f'{prefix}_change'].rolling(window=window).max() == df[f'{prefix}_change'], 1 , None)
    df[f'{prefix}_trend']   = np.where(df[f'{prefix}_change'].rolling(window=window).min() == df[f'{prefix}_change'], -1 , df[f'{prefix}_trend'])
    df[f'{prefix}_trend'].ffill(inplace=True)
    return df


def predict_price(window,fwd=1):
    
    x_pred = len(window) + fwd - 1

    x = np.arange(len(window))  # Índice temporal de la ventana
    y = window.values  # Valores de 'price' en la ventana
    
    # Ajuste de grado 1 para la pendiente
    a, b = np.polyfit(x, y, 1)

    pred = x_pred * a + b

    return pred  

def zigzag(df,af=2, resample_periods=1):

    if resample_periods > 1:
        df_r = resample(df, periods=resample_periods, reset_index = False)
        df_r = psar(df_r,af0=af/100,af=af/10) 
        df_r['ZigZag'] = np.where((df_r['psar_high']>0) & (df_r['psar_low'].shift(1)>0), df_r['psar_high'] , None)
        df_r['ZigZag'] = np.where((df_r['psar_low']>0) & (df_r['psar_high'].shift(1)>0), df_r['psar_low'] , df_r['ZigZag'])
        df_r = df_r[df_r['ZigZag']>0]
        df['ZigZag'] = None
        for i,row in df_r.iterrows():
            df.at[i,'ZigZag'] = row['ZigZag']
    
    else:
        df = psar(df,af0=af/100,af=af/10) 
        df['ZigZag'] = np.where((df['psar_high']>0) & (df['psar_low'].shift(1)>0), df['psar_high'] , None)
        df['ZigZag'] = np.where((df['psar_low']>0) & (df['psar_high'].shift(1)>0), df['psar_low'] , df['ZigZag'])
        df.drop(columns=['psar_high','psar_low'],inplace=True)
            
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

def ITG_Scalper(df, len=14 , FfastLength=12 , FslowLength=26 , FsignalLength=9 , nfilter=False):
    """
    Basado en un indicador de Trading View
    https://www.tradingview.com/script/AcrZjl6Q-ITG-Scalper/

    Genera columnas: long, short, buy_alert, sell_alert
    """

    

    # Calculating Triple EMA
    ema1 = df['close'].ewm(span=len, min_periods=len).mean()
    ema2 = ema1.ewm(span=len, min_periods=len).mean()
    ema3 = ema2.ewm(span=len, min_periods=len).mean()
    avg = 3 * (ema1 - ema2) + ema3

    # Trend calculation
    ma_up = avg >= avg.shift(1)
    ma_down = avg < avg.shift(1)

    # MACD Filter
    FfastMA = df['close'].ewm(span=FfastLength, min_periods=FfastLength).mean()
    FslowMA = df['close'].ewm(span=FslowLength, min_periods=FslowLength).mean()
    Fmacd = FfastMA - FslowMA
    Fsignal = Fmacd.rolling(window=FsignalLength).mean()

    Fbuy = (Fmacd >= Fsignal) | ~nfilter
    Fsell = (Fmacd < Fsignal) | ~nfilter

    # Entry & exit conditions
    long = ma_up & Fbuy.shift(1)
    short = ma_down & Fsell.shift(1)

    # Alert conditions
    buy_alert = long & long.shift(1)
    sell_alert = short & short.shift(1)
    
    df['long'] = long
    df['short'] = short
    df['buy_alert'] = buy_alert
    df['sell_alert'] = sell_alert

    return df

def Edri_Extreme_Points_Buy_Sell(df, ccimomCross='CCI' , ccimomLength=10 , 
                                     useDivergence=True , rsiOverbought=65 , 
                                     rsiOversold=35 , rsiLength=14 , 
                                     emaPeriod=200 , bandMultiplier=1.8):
    """
    Basado en un indicador de Trading View
    https://es.tradingview.com/script/ZXIm3q7G-Edri-Extreme-Points-Buy-Sell/

    Genera columnas: long_entry, short_entry, mean_reversion, upper_band, lower_band
    """
    
    # CCI and Momentum calculation
    momLength = ccimomLength if ccimomCross == 'Momentum' else 10
    mom = df['close'] - df['close'].shift(momLength)
    cci = (df['close'] - df['close'].rolling(window=ccimomLength).mean()) / (0.015 * df['close'].rolling(window=ccimomLength).std())
    ccimomCrossUp = (mom > 0) if ccimomCross == 'Momentum' else (cci > 0)
    ccimomCrossDown = (mom < 0) if ccimomCross == 'Momentum' else (cci < 0)

    # RSI calculation
    src = df['close']
    up = src.diff().where(src.diff() > 0, 0).rolling(window=rsiLength).mean()
    down = -src.diff().where(src.diff() < 0, 0).rolling(window=rsiLength).mean()
    rs = up / down
    rsi = 100 - (100 / (1 + rs))
    oversoldAgo = (rsi <= rsiOversold).any()
    overboughtAgo = (rsi >= rsiOverbought).any()
    
    # Regular Divergence Conditions
    bullishDivergenceCondition = (rsi.shift() > rsi.shift(2)) & (rsi.shift(2) < rsi.shift(4))
    bearishDivergenceCondition = (rsi.shift() < rsi.shift(2)) & (rsi.shift(2) > rsi.shift(4))

    # Entry Conditions
    longEntryCondition = ccimomCrossUp & oversoldAgo & (~useDivergence | bullishDivergenceCondition)
    shortEntryCondition = ccimomCrossDown & overboughtAgo & (~useDivergence | bearishDivergenceCondition)

    # Mean Reversion Indicator
    meanReversion = df['close'].ewm(span=emaPeriod, adjust=False).mean()
    stdDev = df['close'].rolling(window=emaPeriod).std()
    upperBand = meanReversion + stdDev * bandMultiplier
    lowerBand = meanReversion - stdDev * bandMultiplier
    df['long_entry'] = longEntryCondition
    df['short_entry'] = shortEntryCondition
    df['mean_reversion'] = meanReversion
    df['upper_band'] = upperBand
    df['lower_band'] = lowerBand
    return df

def psar(df, af0=0.02, af=0.2, max_af=0.2):
    tmp = pandas_ta.trend.psar(df['high'], df['low'], df['close'], af0=af0, af=af, max_af=max_af)
    df['psar_low'] = tmp.filter(like='PSARl').iloc[:, 0]
    df['psar_high'] = tmp.filter(like='PSARs').iloc[:, 0]
    return df

def HeikinAshi(df):
    
    #Calculo segun Binance y TradingView
    df['HA_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    df['HA_open'] = (df['open'] + df['close']) / 2
    df['HA_open'] = ((df['HA_open'].shift(1) + df['HA_close'].shift(1)) / 2).fillna(df['HA_open'])
    
    df['HA_high'] = df[['high', 'HA_open', 'HA_close']].max(axis=1)
    df['HA_low'] =  df[['low', 'HA_open', 'HA_close']].min(axis=1)
    df['HA_side'] = np.where(df['HA_close']>df['HA_open'],1,-1)
    #df['HA_side'] = np.where(df['HA_close']>df['HA_open'],1,-1)

    #Analizando tipo de vela
    df['HA_cuerpo'] = abs(df['HA_close'] - df['HA_open'])
    df['HA_sombra_inferior'] = df[['HA_open', 'HA_close']].min(axis=1) - df['HA_low']
    df['HA_sombra_superior'] = df['HA_high'] - df[['HA_open', 'HA_close']].max(axis=1)
    condicion_indecision = (
        (df['HA_cuerpo'] <= 0.1 * (df['HA_sombra_inferior'] + df['HA_sombra_superior'])) &  # Cuerpo pequeño
        (df['HA_sombra_inferior'] >= 2 * df['HA_cuerpo']) &  # Sombra inferior larga
        (df['HA_sombra_superior'] >= 2 * df['HA_cuerpo'])    # Sombra superior larga
    )
    df['HA_vela_indecision'] = condicion_indecision
    df['HA_side'] = np.where(df['HA_vela_indecision'],0,df['HA_side'])
    df['HA_low_trend'] = np.where(df['HA_vela_indecision'],1,None)
    df.drop(['HA_vela_indecision','HA_cuerpo','HA_sombra_inferior','HA_sombra_superior'], axis=1, inplace=True)
    return df

def get_pivots_alert(df,threshold=1.5):

    def contar_decimales(f):
        s = str(f)
        if '.' in s:
            return len(s.split('.')[1].rstrip('0'))
        return 0

    data = {}
    data['alert'] = 0
    min_periods = 50
    price = df.iloc[-1]['close']
    if df['close'].count() >= min_periods:
        
        adx_length = 14
        adx_data = adx(df['high'],df['low'],df['close'],length=adx_length)
        last_adx = adx_data.iloc[-1][f'ADX_{adx_length}']
        adx_data['adx_ma'] = adx_data[f'ADX_{adx_length}'].rolling(window=5).mean()
        last_adx_ma = adx_data.iloc[-1]['adx_ma']
                
        if last_adx > 26:
            
            df = supertrend(df)
            trend = int(df.iloc[-1]['st_trend'])
            
            if trend >= 1 or trend <= -1:

                df = zigzag(df)
                pivots = df[df['ZigZag']>0]['ZigZag'].tolist()
                
                if len(pivots) >= 5: #Se busca que existan mas pivots de lo necesario par apoder formarlos

                    df_pivots = df[df['ZigZag']>0]
                    lpdt = df_pivots.iloc[-1]['datetime'] #Last Pivot Datetime
                    max_flp = df[df['datetime']>lpdt]['high'].max() #Max From last pivot
                    min_flp = df[df['datetime']>lpdt]['low'].min()  #Min From last pivot

                    if trend >=1:
                        #Alertas en LONG

                        #Busqueda de pivots con el siguiente formato 
                        #              -1
                        #       -3
                        #                         Precio
                        #                  min_flp
                        #          -2
                        #   -4
                    
                        alert_type = 'Dual Pullback LONG'
                        last_pivots_diff = pivots[-1]-min_flp
                        valid_pivots_type = pivots[-1] > pivots[-3] and pivots[-3] > min_flp and \
                                            min_flp > pivots[-2] and pivots[-2] > pivots[-4] 
                        in_price = min_flp+last_pivots_diff/3
                        valid_price = in_price*(1-(0.25/100)) < price < in_price*(1+(0.25/100))
                        valid_pivot_delta = pivots[-1] > min_flp*(1+threshold/100) and min_flp > pivots[-2]*(1+(threshold/3)/100) \
                                            and pivots[-1] > pivots[-4]*(1+(2*threshold)/100) 
                        if valid_pivots_type and valid_price and valid_pivot_delta:

                            data['alert'] = 1
                            data['side'] = 1
                            data['alert_str'] = alert_type
                            data['sl1'] = min_flp
                            data['tp1'] = pivots[-1] 
                            data['in_price'] = data['sl1']+((data['tp1']-data['sl1'])/3) #Genera un ratio 2:1
                        
                    elif trend <= -1:
                        # Alertas en SHORT

                        #Busqueda de pivots con el siguiente formato 
                        #   -4
                        #           -2
                        #                   max_flp
                        #                              Precio
                        #       -3
                        #               -1
                        alert_type = 'Dual Pullback SHORT'
                        last_pivots_diff = max_flp-pivots[-1]
                        valid_pivots_type = pivots[-1] < pivots[-3] and pivots[-3] < max_flp and \
                                            max_flp < pivots[-2] and pivots[-2] < pivots[-4] 
                        in_price = max_flp-last_pivots_diff/3
                        valid_price = in_price*(1-(0.25/100)) < price < in_price*(1+(0.25/100))
                        valid_pivot_delta = pivots[-1] < max_flp*(1-threshold/100) and max_flp < pivots[-2]*(1-(threshold/3)/100) \
                                            and pivots[-1] < pivots[-4]*(1-(2*threshold)/100) 
                        if valid_pivots_type and valid_price and valid_pivot_delta:
                            data['alert'] = -1
                            data['side'] = -1
                            data['alert_str'] = alert_type
                            data['sl1'] = max_flp
                            data['tp1'] = pivots[-1] 
                            data['in_price'] = data['sl1']-((data['sl1']-data['tp1'])/3) #Genera un ratio 2:1


                if data['alert'] != 0:
                    decs = max(contar_decimales(data['sl1']), contar_decimales(data['tp1']))
                    data['in_price'] = round(data['in_price'],decs)
                    data['df'] = df
                    data['datetime'] = df.iloc[-1]['datetime']
                    data['last_pivot'] = lpdt
                    data['adx'] = last_adx
                    data['adx_ma'] = last_adx_ma

    return data

def get_technical_summary(df):
    """
    Analiza el DataFrame y devuelve un resumen técnico similar a TradingView.
    """
    signals = []
    
    # Asegurarse de que el df tenga las columnas correctas
    df.columns = df.columns.str.lower()
    
    # --- CÁLCULO DE INDICADORES ---
    # Usamos pandas_ta para calcular todos los indicadores de una vez
    # Parámetros basados en el widget de TradingView
    df.ta.rsi(length=14, append=True)
    df.ta.stoch(k=14, d=3, smooth_k=3, append=True)
    df.ta.cci(length=20, append=True)
    df.ta.adx(length=14, append=True)
    df.ta.ao(append=True)
    df.ta.mom(length=10, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)
    df.ta.willr(length=14, append=True)
    # Bull Bear Power no está directamente en pandas_ta, pero se puede calcular
    ema13 = ta.ema(df['close'], length=13)
    df['BULLP'] = df['high'] - ema13
    df['BEARP'] = df['low'] - ema13
    df.ta.uo(fast=7, medium=14, slow=28, append=True)
    
    # Medias Móviles
    for period in [10, 20, 30, 50, 100, 200]:
        df.ta.ema(length=period, append=True)
        df.ta.sma(length=period, append=True)
        
    df.ta.vwma(length=20, append=True)
    df.ta.hma(length=9, append=True)
    # Ichimoku. La "Base Line" es la Kijun Sen
    ichimoku = df.ta.ichimoku(tenkan=9, kijun=26, senkou=52)
    df['ISA_9_26_52'] = ichimoku[0]['ISA_9'] # Tenkan-sen
    df['ISB_26'] = ichimoku[0]['ISB_26'] # Kijun-sen

    # Tomar la última vela completa para el análisis
    last_row = df.iloc[-1]
    
    # --- ANÁLISIS DE OSCILADORES ---
    
    # RSI
    rsi = last_row['RSI_14']
    if rsi > 55: signals.append({'Indicator': 'RSI(14)', 'Value': rsi, 'Signal': 'Compra', 'Type': 'Oscillator'})
    elif rsi < 45: signals.append({'Indicator': 'RSI(14)', 'Value': rsi, 'Signal': 'Venta', 'Type': 'Oscillator'})
    else: signals.append({'Indicator': 'RSI(14)', 'Value': rsi, 'Signal': 'Neutral', 'Type': 'Oscillator'})

    # Stochastic %K
    stoch_k, stoch_d = last_row['STOCHk_14_3_3'], last_row['STOCHd_14_3_3']
    if stoch_k > stoch_d: signals.append({'Indicator': 'Stoch %K(14,3,3)', 'Value': stoch_k, 'Signal': 'Compra', 'Type': 'Oscillator'})
    else: signals.append({'Indicator': 'Stoch %K(14,3,3)', 'Value': stoch_k, 'Signal': 'Venta', 'Type': 'Oscillator'})

    # CCI
    cci = last_row['CCI_20_0.015']
    if cci > 100: signals.append({'Indicator': 'CCI(20)', 'Value': cci, 'Signal': 'Venta', 'Type': 'Oscillator'}) # Sobrecompra -> Venta
    elif cci < -100: signals.append({'Indicator': 'CCI(20)', 'Value': cci, 'Signal': 'Compra', 'Type': 'Oscillator'}) # Sobreventa -> Compra
    else: signals.append({'Indicator': 'CCI(20)', 'Value': cci, 'Signal': 'Neutral', 'Type': 'Oscillator'})
    
    # ADX
    adx, dmp, dmn = last_row['ADX_14'], last_row['DMP_14'], last_row['DMN_14']
    if adx > 25 and dmp > dmn: signals.append({'Indicator': 'ADX(14)', 'Value': adx, 'Signal': 'Compra', 'Type': 'Oscillator'})
    elif adx > 25 and dmn > dmp: signals.append({'Indicator': 'ADX(14)', 'Value': adx, 'Signal': 'Venta', 'Type': 'Oscillator'})
    else: signals.append({'Indicator': 'ADX(14)', 'Value': adx, 'Signal': 'Neutral', 'Type': 'Oscillator'})
    
    # Awesome Oscillator
    ao = last_row['AO_5_34']
    if ao > 0: signals.append({'Indicator': 'Awesome Osc.', 'Value': ao, 'Signal': 'Compra', 'Type': 'Oscillator'})
    else: signals.append({'Indicator': 'Awesome Osc.', 'Value': ao, 'Signal': 'Venta', 'Type': 'Oscillator'})

    # Momentum
    mom = last_row['MOM_10']
    if mom > 0: signals.append({'Indicator': 'Momentum(10)', 'Value': mom, 'Signal': 'Compra', 'Type': 'Oscillator'})
    else: signals.append({'Indicator': 'Momentum(10)', 'Value': mom, 'Signal': 'Venta', 'Type': 'Oscillator'})

    # MACD Level
    macd, macd_s = last_row['MACD_12_26_9'], last_row['MACDs_12_26_9']
    if macd > macd_s: signals.append({'Indicator': 'MACD Level(12,26)', 'Value': macd, 'Signal': 'Compra', 'Type': 'Oscillator'})
    else: signals.append({'Indicator': 'MACD Level(12,26)', 'Value': macd, 'Signal': 'Venta', 'Type': 'Oscillator'})

    # Stochastic RSI
    stoch_rsi_k, stoch_rsi_d = last_row['STOCHRSIk_14_14_3_3'], last_row['STOCHRSId_14_14_3_3']
    if stoch_rsi_k > stoch_rsi_d: signals.append({'Indicator': 'Stoch RSI Fast(3,3,14,14)', 'Value': stoch_rsi_k, 'Signal': 'Compra', 'Type': 'Oscillator'})
    else: signals.append({'Indicator': 'Stoch RSI Fast(3,3,14,14)', 'Value': stoch_rsi_k, 'Signal': 'Venta', 'Type': 'Oscillator'})

    # Williams %R
    willr = last_row['WILLR_14']
    if willr < -80: signals.append({'Indicator': 'Williams %R(14)', 'Value': willr, 'Signal': 'Compra', 'Type': 'Oscillator'})
    elif willr > -20: signals.append({'Indicator': 'Williams %R(14)', 'Value': willr, 'Signal': 'Venta', 'Type': 'Oscillator'})
    else: signals.append({'Indicator': 'Williams %R(14)', 'Value': willr, 'Signal': 'Neutral', 'Type': 'Oscillator'})

    # Bull Bear Power (simplificado)
    bullp, bearp = last_row['BULLP'], last_row['BEARP']
    if bullp > 0: signals.append({'Indicator': 'Bull Bear Power', 'Value': bullp, 'Signal': 'Compra', 'Type': 'Oscillator'})
    else: signals.append({'Indicator': 'Bull Bear Power', 'Value': bullp, 'Signal': 'Venta', 'Type': 'Oscillator'})
    
    # Ultimate Oscillator
    uo = last_row['UO_7_14_28']
    if uo > 70: signals.append({'Indicator': 'Ultimate Osc.(7,14,28)', 'Value': uo, 'Signal': 'Venta', 'Type': 'Oscillator'})
    elif uo < 30: signals.append({'Indicator': 'Ultimate Osc.(7,14,28)', 'Value': uo, 'Signal': 'Compra', 'Type': 'Oscillator'})
    else: signals.append({'Indicator': 'Ultimate Osc.(7,14,28)', 'Value': uo, 'Signal': 'Neutral', 'Type': 'Oscillator'})
    
    # --- ANÁLISIS DE MEDIAS MÓVILES ---
    price = last_row['close']
    ma_list = [
        ('EMA(10)', f'EMA_10'), ('SMA(10)', f'SMA_10'),
        ('EMA(20)', f'EMA_20'), ('SMA(20)', f'SMA_20'),
        ('EMA(30)', f'EMA_30'), ('SMA(30)', f'SMA_30'),
        ('EMA(50)', f'EMA_50'), ('SMA(50)', f'SMA_50'),
        ('EMA(100)', f'EMA_100'), ('SMA(100)', f'SMA_100'),
        ('EMA(200)', f'EMA_200'), ('SMA(200)', f'SMA_200'),
        ('Ichimoku Base(9,26,52)', 'ISB_26'), # Kijun Sen
        ('VWMA(20)', 'VWMA_20'),
        ('Hull MA(9)', 'HMA_9')
    ]
    
    for name, col in ma_list:
        ma_value = last_row[col]
        if price > ma_value: signals.append({'Indicator': name, 'Value': ma_value, 'Signal': 'Compra', 'Type': 'MA'})
        else: signals.append({'Indicator': name, 'Value': ma_value, 'Signal': 'Venta', 'Type': 'MA'})

    results_df = pd.DataFrame(signals)

    """
    Imprime el resumen de manera clara, similar a TradingView, 
    con un veredicto final de 5 categorías.
    """
    brief = {}

    if results_df.empty:
        print("No hay resultados para analizar.")
        return brief

    # --- 1. Conteo de Señales ---
    buy_signals = len(results_df[results_df['Signal'] == 'Compra'])
    sell_signals = len(results_df[results_df['Signal'] == 'Venta'])
    neutral_signals = len(results_df[results_df['Signal'] == 'Neutral'])
    
    # Total de indicadores que dan una señal activa (no neutral)
    total_active_signals = buy_signals + sell_signals

    # --- 2. Cálculo del Puntaje y Ratio ---
    # Compra = +1, Venta = -1, Neutral = 0
    net_score = buy_signals - sell_signals
    
    # Evitar división por cero si todos los indicadores son neutrales
    if total_active_signals > 0:
        sentiment_ratio = net_score / total_active_signals
    else:
        sentiment_ratio = 0 # Si no hay señales activas, el sentimiento es neutral

    # --- 3. Determinación del Veredicto Final (5 categorías) ---
    if sentiment_ratio > 0.75:
        final_verdict = 'Compra Fuerte'
    elif sentiment_ratio > 0.25:
        final_verdict = 'Compra'
    elif sentiment_ratio >= -0.25:
        final_verdict = 'Neutral'
    elif sentiment_ratio >= -0.75:
        final_verdict = 'Venta'
    else: # sentiment_ratio < -0.75
        final_verdict = 'Venta Fuerte'

    brief['final_verdict'] = final_verdict
    brief['buy_signals'] = buy_signals
    brief['sell_signals'] = sell_signals
    brief['neutral_signals'] = neutral_signals
    brief['sentiment_ratio'] = round(sentiment_ratio,2)

    return brief