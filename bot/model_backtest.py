from django.conf import settings
from django.db import models
from django.utils import timezone
from bot.models import GenericBotClass
from user.models import User
import pandas as pd
import json
import scripts.functions as fn
import glob
import os
import pickle

class Backtest(models.Model):

    ESTADO_CREADO = 0
    ESTADO_INICIADO = 10
    ESTADO_ENCURSO = 50
    ESTADO_COMPLETO = 100

    tendencias = ['Completo'] #,'Alcista','Lateral','Bajista'

    klines_folder = os.path.join(settings.BASE_DIR,'backtest','klines')
    results_folder = os.path.join(settings.BASE_DIR,'backtest','results')

    clase = models.SlugField(max_length = 50, null=False, blank=False)
    parametros = models.TextField(null=False, blank=False)
    interval_id = models.CharField(max_length = 8, null=False, blank=False)
    estado = models.IntegerField(null=False, blank=False, default=0)
    completo = models.FloatField(null=False, blank=False, default=0)
    creado = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(User, on_delete = models.CASCADE) 
    scoring = models.FloatField(null=False, blank=False, default=0)
    scoring_str = models.TextField(null=False, blank=True, default='')
    
    class Meta:
        verbose_name = "BackTest"
        verbose_name_plural='BackTests'
    
    def __str__(self):
        interval = fn.get_intervals(self.interval_id,'binance')
        str = f'{self.clase} {interval} {self.creado}'
        return str
    
    def name(self):
        return f'{self.clase} #{self.id}'

    def str_estado(self):
        estados = {}
        estados[self.ESTADO_CREADO] = 'Creado'
        estados[self.ESTADO_INICIADO] = 'Iniciado'
        estados[self.ESTADO_ENCURSO] = 'En curso'
        estados[self.ESTADO_COMPLETO] = 'Completo'
        return estados[self.estado]
    
    def str_interval(self):
        interval = fn.get_intervals(self.interval_id,'binance')
        return interval

    def iniciar(self):
        resultados = {}
        resultados['id'] = self.id
        resultados['periodos'] = self.get_periodos(self.interval_id)
        self.set_resultados(resultados)
        self.estado = self.ESTADO_INICIADO
        self.save()

    def log_resultados(self,resultados,msg):
        resultados['log'].append({'dt':timezone.now,'msg':msg,})

    def set_resultados(self,resultados):
        with open(self.get_results_file(), 'wb') as f:
            pickle.dump(resultados, f)
        return resultados
    
    def get_resultados(self):
        with open(self.get_results_file(), 'rb') as f:
            resultados = pickle.load(f)
        return resultados

    def get_resumen_resultados(self):
        resultados = self.get_resultados()

        json_rsp = {}
        for periodo in resultados['periodos']:

            start_date = periodo['start']
            end_date = periodo['end']
            symbol = periodo['symbol']
            tendencia = periodo['tendencia']
            if periodo['bt']:
                if not tendencia in json_rsp:
                    json_rsp[tendencia] = pd.DataFrame(periodo['bt'],columns=['ind',symbol])
                else:
                    tmp_df = pd.DataFrame(periodo['bt'],columns=['ind',symbol])
                    json_rsp[tendencia][symbol] = tmp_df[symbol]
    
        
        for tendencia in self.tendencias:
            #Eliminando metricas que no se van a medir
            json_rsp[tendencia].drop(json_rsp[tendencia][json_rsp[tendencia]['ind'] == 'maximo_operaciones_negativas_consecutivas'].index, inplace=True)
            json_rsp[tendencia].drop(json_rsp[tendencia][json_rsp[tendencia]['ind'] == 'ratio_dias_sin_operar'].index, inplace=True)
            json_rsp[tendencia].drop(json_rsp[tendencia][json_rsp[tendencia]['ind'] == 'trades_x_mes'].index, inplace=True)

            json_rsp[tendencia]['Media'] = json_rsp[tendencia].drop(columns=['ind']).mean(axis=1)
            json_rsp[tendencia]['Dev.Est.'] = json_rsp[tendencia].drop(columns=['ind']).std(axis=1)
            json_rsp[tendencia]['Dev.Est.(%)'] = (json_rsp[tendencia].drop(columns=['ind']).std(axis=1)/json_rsp[tendencia]['Media'])
        
            col_media_tendencia = f'Media {tendencia}'
            col_scoring_tendencia = f'Scoring {tendencia}'
            if not 'Media' in json_rsp:
                json_rsp['Media'] = json_rsp[tendencia][['ind','Media']]
                json_rsp['Media'] = json_rsp['Media'].rename(columns={'Media': col_media_tendencia})
            else:
                json_rsp['Media'][col_media_tendencia] = json_rsp[tendencia]['Media']

            json_rsp['Media'][col_scoring_tendencia] = json_rsp['Media'].apply(lambda row: self.calcular_scoring_columna(row['ind'], row[col_media_tendencia],col_media_tendencia), axis=1)
        
        #Formateando los dataframes generados
        ind_names = []
        ind_names.append({'ind':'cagr',
                          'name':'CAGR (Rendimiento anual %)'}) 
        ind_names.append({'ind':'max_drawdown_cap',
                          'name':'Max. DrawDown (%)'})
        ind_names.append({'ind':'maximo_operaciones_negativas_consecutivas',
                          'name':'Max.Op. negativas consecutivas'}) 
        ind_names.append({'ind':'ratio_dias_sin_operar',
                          'name':'Ratio de Dias sin operar'})  
        ind_names.append({'ind':'trades_x_mes',
                          'name':'Operaciones mensuales'})
        ind_names.append({'ind':'ratio_trade_pos',
                          'name':'Operaciones positivas/total (%)'})
        ind_names.append({'ind':'ratio_perdida_ganancia',
                          'name':'Ratio de Perdida vs Ganancia'}) 
        ind_names.append({'ind':'ratio_max_perdida_ganancia',
                          'name':'Ratio Max.Perdida/Max.Ganancia'}) 
        ind_names.append({'ind':'ratio_volatilidad',
                          'name':'Ratio de Volatilidad'})
        ind_names.append({'ind':'ratio_max_drawdown',
                          'name':'Ratio Max.DrawDown Capital/Par'})
        ind_names.append({'ind':'ratio_max_drawup',
                          'name':'Ratio Max. DrawUp Capital/Par'})
        ind_names.append({'ind':'ratio_calmar',
                          'name':'Ratio CALMAR (CAGR/DrawDown)'})
        ind_names.append({'ind':'modificacion_sharpe',
                          'name':'Ratio SHARPE Modificado'})
        ind_names.append({'ind':'mea_promedio',
                          'name':'MEA Promedio'}) 
        ind_names.append({'ind':'mef_promedio',
                          'name':'MEF Promedio'}) 
        df_ind_names = pd.DataFrame(ind_names, columns=['ind','name'])
        df_ind_names = df_ind_names.set_index('ind')

        for key in json_rsp:
            json_rsp[key] = json_rsp[key].set_index('ind')
            json_rsp[key] = json_rsp[key].round(2)
            json_rsp[key].insert(0, 'Metrica', df_ind_names['name'])

        return json_rsp

    def get_scoring_str(self,resumen_resultados):
        tendencias = Backtest.tendencias
        scoring_str = ''
        for tendencia in tendencias:
            media = resumen_resultados['Media'][f'Media {tendencia}']
            cagr = media.loc['cagr']
            max_drawdown_cap = media.loc['max_drawdown_cap']
            scoring_str = f'CAGR {cagr:.2f} DD {max_drawdown_cap:.2f} '
        return scoring_str

    def calcular_scoring_columna(self,ind,col_media,col_media_tendencia):
        tendencia = col_media_tendencia[6:]
        
        niveles = [6,10,20]
        
        if ind == 'cagr':
            if col_media <= niveles[0]:
                return 0
            elif col_media <= niveles[1]:
                return 1
            elif col_media <= niveles[2]:
                return 2
            else:
                return 3
        
        elif ind == 'max_drawdown_cap':
            if col_media >= 30:
                return 0
            elif col_media >= 20:
                return 1
            else:
                return 2

        elif ind == 'ratio_trade_pos':
            if col_media <= 30:
                return 0
            elif col_media <= 50:
                return 1
            elif col_media <= 60:
                return 2
            else:
                return 3
        elif ind == 'ratio_perdida_ganancia':
            """ 
            Revisar
            """
            if col_media <= 0.9:
                return 0
            elif col_media <= 1.2:
                return 1
            elif col_media <= 2:
                return 2
            else:
                return 3
        elif ind == 'ratio_max_perdida_ganancia':
            """ 
            Revisar
            """
            if col_media <= 1.5:
                return 0
            elif col_media <= 2.0:
                return 1
            elif col_media <= 2.5:
                return 2
            else:
                return 3
        elif ind == 'ratio_volatilidad':
            if col_media >= 85:
                return 0
            elif col_media >= 60:
                return 1
            elif col_media >= 40:
                return 2
            else:
                return 3
        elif ind == 'ratio_max_drawdown':
            if col_media >= 85:
                return 0
            elif col_media >= 60:
                return 1
            elif col_media >= 40:
                return 2
            else:
                return 3
        elif ind == 'ratio_max_drawup':
            if col_media <= 20:
                return 0
            elif col_media <= 50:
                return 1
            elif col_media <= 80:
                return 2
            else:
                return 3
        elif ind == 'ratio_calmar':
            if col_media <= 1:
                return 0
            elif col_media <= 2:
                return 1
            elif col_media <= 3:
                return 2
            else:
                return 3
        elif ind == 'modificacion_sharpe':
            if col_media <= 1:
                return 0
            elif col_media <= 2:
                return 1
            elif col_media <= 3:
                return 2
            else:
                return 3
        return -1
    
    def calcular_scoring_completo(self,resumen_resultados):
        json_rsp = {}

        tendencias = Backtest.tendencias

        #max_scoring surge de: 
        # un valor promedio de 3 como maximo para cada merica
        # multiplicado por el valor maximo de cagr (3) 
        # multiplicado por el valor maximo de max_drawdown_cap (2)
        # 3 * 3 * 2 = 18 
        max_scoring = 18

        for tendencia in tendencias:
            scoring = resumen_resultados['Media'][f'Scoring {tendencia}']
            cagr = scoring.loc['cagr']
            max_drawdown_cap = scoring.loc['max_drawdown_cap']
            count = scoring.count()
            sum = scoring.sum() - cagr - max_drawdown_cap
            avg = sum / (count-2)
            json_rsp[tendencia] = (( cagr * max_drawdown_cap * avg ) /18 ) *100  

        return json_rsp

    def get_results_file(self):
        file = f'{self.results_folder}/id_{self.id}.json'
        return file

    def get_periodos(self,interval_id,all_tendencias=False):
        
        periodos = [] 
        folders = glob.glob(self.klines_folder+os.sep+'*')
        for fld in folders:
            folder = fld
            folder = folder.replace(self.klines_folder+os.sep, '')
            interval = fn.get_intervals(folder,'binance')
            if interval:
                if interval_id == 'ALL' or folder == interval_id:
                    mask = os.path.join(self.klines_folder,folder,'*.DataFrame*')
                    files = glob.glob(mask)
                    
                    for f in files:
                        
                        file = f
                        f = f.replace('.DataFrame', '')
                        f = f.replace(fld, '')
                        f = f.replace(os.sep, '')
                        parts = f.split('_')
                        tendencia = parts[0]
                        symbol = parts[1]
                        tendencia = parts[0]
                        start = parts[3]
                        end = parts[4]
                        key = len(periodos)
                        if all_tendencias or tendencia in self.tendencias:
                            periodos.append({
                                        'key': key,
                                        'tendencia':tendencia,
                                        'interval':interval,
                                        'interval_id': folder,
                                        'start': start,
                                        'end': end,
                                        'symbol': symbol,
                                        'str': f'{symbol} {interval} {tendencia} desde el {start} al {end}',
                                        'file': file,
                                        'procesado': 'NO',
                                        }
                                    )
                                   
        return periodos
    
    def parse_parametros(self):
        gen_bot = GenericBotClass().get_instance(self.clase)
        parametros = gen_bot.parametros
        pe = eval(self.parametros)
        for prm in pe:
            for v in prm:
                if v in parametros:
                    parametros[v]['v'] = prm[v]
                    parametros[v]['str'] = prm[v]

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
        for p,values in prm.items():
            if (p != 'symbol') or (p == 'symbol' and values['v'] != 'BACKTEST'):
                if str != '':
                    str += ', '
                v = values['v']
                sn = values['sn']
                str += f'{sn}: {v}'
        return str

    def get_instance(self):
        gen_bot = GenericBotClass().get_instance(self.clase)
        gen_bot.set(self.parse_parametros())
        gen_bot.interval_id = self.interval_id

        return gen_bot

    def get_df_from_file(self,file):
        with open(file, 'rb') as f:
            df = pickle.load(f)
        return df
    
    def get_sub_df_from_file(self,file):
        aux = file.split('_')
        timeframe = aux[-3]
        if timeframe == '0m01':
            file = file.replace(timeframe, '0m01')
        elif timeframe == '0m05':
            file = file.replace(timeframe, '0m01')
        elif timeframe == '0m15':
            file = file.replace(timeframe, '0m01')
        elif timeframe == '0m30':
            file = file.replace(timeframe, '0m05')
        elif timeframe == '1h01':
            file = file.replace(timeframe, '0m15')
        elif timeframe == '1h04':
            file = file.replace(timeframe, '0m15')
        elif timeframe == '2d01':
            file = file.replace(timeframe, '1h01')
        else:
            raise Exception(f'\n{self.__class__.__name__} No se ha encontrado un time frame valido para las sub_velas')

        with open(file, 'rb') as f:
            df = pickle.load(f)
        return df
