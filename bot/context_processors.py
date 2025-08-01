from local__config import SERVER_IDENTIFIER, DEBUG
from pathlib import Path
from django.conf import settings

def local_values(request):
    """
    Agrega valores de settings.py al contexto del template base.html.
    """

    #Verificando si existen archivos de datos para backtest
    backtest_data_folder = settings.BASE_DIR / 'backtest/klines/0m01'
    backtest_available = False
    if backtest_data_folder.exists():
        data_files = list(backtest_data_folder.glob('*.DataFrame'))
        if len(data_files) > 0:
            backtest_available = True

    return {
        'SERVER_IDENTIFIER': SERVER_IDENTIFIER,
        'DEBUG': DEBUG,
        'backtest_available': backtest_available,
    }