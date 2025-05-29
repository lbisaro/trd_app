# Configura el logging de la app
import os
from datetime import datetime
from django.conf import settings
import scripts.functions as fn

class app_log:
    filename = ''
    date_format = '%Y-%m-%d %H:%M:%S'

    def __init__(self,filename='bot'):
        if not filename.strip():
            filename = 'bot'
        self.filename = os.path.join(settings.BASE_DIR,f'log/{filename}')

    def write(self,type,msg):
        dt = datetime.now()
        line = dt.strftime(self.date_format)+' - '+type+' - '+msg
        if type=='ALERT':
            fn.telegram_send(msg)
        else: 
            filename_add = dt.strftime('%Y%m%d')
            with open(self.filename+'_'+filename_add+'.log', 'a') as file:
                file.write(line + '\n')
            if type=='ERROR':
                filename_add = '.error'
                with open(self.filename+'_'+filename_add+'.log', 'a') as file:
                    file.write(line + '\n')


    def info(self,msg):
       self.write(type='INFO',msg=msg)

    def alert(self,msg):
       self.write(type='ALERT',msg=msg)

    def warning(self,msg):
       self.write(type='WARNING',msg=msg)

    def error(self,msg):
       self.write(type='ERROR',msg=msg)

    def criticalError(self,msg):
       self.write(type='CRITICAL ERROR',msg=msg)
       exit(msg)
