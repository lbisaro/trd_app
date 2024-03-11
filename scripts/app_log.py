# Configura el logging de la app
import os
from datetime import datetime
from django.conf import settings

class app_log:
    filename = os.path.join(settings.BASE_DIR,'log/bot')
    date_format = '%Y-%m-%d %H:%M:%S'

    def write(self,type,msg):
        dt = datetime.now()
        line = dt.strftime(self.date_format)+' - '+type+' - '+msg
        filename_add = dt.strftime('%Y%m%d%H')
        with open(self.filename+'_'+filename_add+'.log', 'a') as file:
            file.write(line + '\n')

    def info(self,msg):
       self.write(type='INFO',msg=msg)

    def warning(self,msg):
       self.write(type='WARNING',msg=msg)

    def error(self,msg):
       self.write(type='ERROR',msg=msg)

    def criticalError(self,msg):
       self.write(type='CRITICAL ERROR',msg=msg)
       exit(msg)
