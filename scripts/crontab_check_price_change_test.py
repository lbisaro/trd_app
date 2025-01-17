import pandas as pd
import numpy as np
import os
import pickle
from datetime import datetime, timedelta

from django.conf import settings

from functions import ohlc_chart


DATA_FILE = "log/pchange_data.pkl"
def load_data_file(ruta):
    try:
        if os.path.exists(ruta):
            with open(ruta, "rb") as archivo:
                return pickle.load(archivo)
    except Exception as e:
        print(f"Error al cargar el archivo {ruta}: {e}")
    return {}


data = load_data_file(DATA_FILE)

symbol = 'BTCUSDT'
prices = data['symbols'][symbol]['c_1m']


