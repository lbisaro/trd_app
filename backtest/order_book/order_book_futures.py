import websocket # pip install websocket-client
import requests
import json
import time
import pickle # Para guardar/cargar el DataFrame
import os
from datetime import datetime, timezone # Usar timezone-aware datetime
import threading
from sortedcontainers import SortedDict # pip install sortedcontainers
import sys
import pandas as pd # pip install pandas
from decimal import Decimal, ROUND_HALF_UP # Import Decimal
from binance.client import Client as BinanceClient

# --- Configuración ---
SYMBOL = "btcusdt" # Símbolo en minúsculas para WebSocket
SYMBOL_UPPER = "BTCUSDT" # Símbolo en mayúsculas para REST API
CONNECT_DURATION_SECONDS = 30 #180 # 3 minutos (Duración de la conexión WS)
SNAPSHOT_LIMIT = 1000 # Profundidad del snapshot inicial REST
SAVE_DIRECTORY = "orderbook_data" # Directorio para el archivo acumulativo
FILENAME = "cumulative_snapshots.pkl" # Nombre del archivo pickle para el DataFrame
FILE_PATH = os.path.join(SAVE_DIRECTORY, FILENAME)
TOP_N_LEVELS = 20 # Cuántos niveles de mayor volumen guardar

client = BinanceClient()
market = 's'

if market == 'f':
    BINANCE_WS_URL = f"wss://fstream.binance.com/ws/{SYMBOL}@depth@100ms" # Diff. Depth Stream (100ms updates)
    BINANCE_API_URL = "https://fapi.binance.com/fapi/v1/depth"
else:
    BINANCE_WS_URL = f"wss://stream.binance.com:9443/ws/{SYMBOL}@depth@100ms"
    BINANCE_API_URL = "https://api.binance.com/api/v3/depth"



# --- Variables Globales (para la sesión única) ---
# El order_book ahora usará Decimal como clave y valor
order_book = {'bids': SortedDict(), 'asks': SortedDict()}
last_update_id = None
initial_snapshot_processed = False
message_buffer = []
ws_connection_active = False
ws_app = None # Para mantener referencia a la app WebSocket

# --- Funciones WebSocket ---

def on_message(ws, message):
    """Callback para manejar mensajes del WebSocket."""
    global last_update_id, initial_snapshot_processed, order_book
    try:
        data = json.loads(message)
        # Ignorar mensajes que no sean de profundidad
        if 'e' not in data or data['e'] != 'depthUpdate':
            return
        # Si aún no hemos procesado el snapshot inicial, almacenar en buffer
        if not initial_snapshot_processed:
            message_buffer.append(data)
            return
        # Procesar mensaje si ya tenemos snapshot
        process_depth_update(data) # Esta función ahora manejará Decimal
    except json.JSONDecodeError:
        print("Error decoding WebSocket message:", message)
    except Exception as e:
        print(f"Error in on_message: {e}")


def process_depth_update(data):
    """Aplica una actualización diferencial al order book local usando Decimal keys/values."""
    global last_update_id, order_book
    try:
        # Aplicar actualizaciones de bids (b)
        for price_level_str, quantity_str in data.get('b', []):
            price_level = Decimal(price_level_str) # Convertir precio a Decimal
            quantity = Decimal(quantity_str)     # Convertir cantidad a Decimal
            if quantity == 0:
                order_book['bids'].pop(price_level, None) # Pop usando la clave Decimal
            else:
                order_book['bids'][price_level] = quantity # Insertar/actualizar con clave Decimal

        # Aplicar actualizaciones de asks (a)
        for price_level_str, quantity_str in data.get('a', []):
            price_level = Decimal(price_level_str) # Convertir precio a Decimal
            quantity = Decimal(quantity_str)     # Convertir cantidad a Decimal
            if quantity == 0:
                order_book['asks'].pop(price_level, None) # Pop usando la clave Decimal
            else:
                order_book['asks'][price_level] = quantity # Insertar/actualizar con clave Decimal

        # Actualizar el último ID procesado del stream
        last_update_id = data['u']
    except ValueError as e:
         # Error común si los datos no son numéricos válidos
         print(f"Error converting price/qty to Decimal in depth update: {e} - Data: {data}")
    except Exception as e:
        print(f"Error processing depth update: {e}")


def on_error(ws, error):
    """Callback para errores."""
    print(f"WebSocket Error: {error}")
    global ws_connection_active
    ws_connection_active = False # Marcar como inactiva en caso de error

def on_close(ws, close_status_code, close_msg):
    """Callback cuando la conexión se cierra."""
    print(f"WebSocket Closed: {close_status_code} {close_msg}")
    global ws_connection_active
    ws_connection_active = False

def on_open(ws):
    """Callback cuando la conexión se abre."""
    print("WebSocket Connection Opened.")
    # Nota: La suscripción se hace en la URL, no se envía mensaje aquí para depth stream


# --- Funciones de Lógica Principal ---

def get_initial_snapshot(symbol: str, limit: int) -> bool:
    """Obtiene y procesa el snapshot inicial usando Decimal keys/values."""
    global order_book, last_update_id, initial_snapshot_processed, message_buffer
    params = {"symbol": symbol, "limit": limit}
    try:
        print("Requesting initial snapshot via REST API...")
        response = requests.get(BINANCE_API_URL, params=params, timeout=15) # Aumentado timeout
        response.raise_for_status()
        snapshot = response.json()
        snapshot_last_update_id = snapshot['lastUpdateId']
        print(f"Snapshot received. LastUpdateId: {snapshot_last_update_id}")

        # Cargar snapshot inicial usando Decimal como clave y valor
        # Limpiar el book antes de cargar para asegurar estado fresco
        order_book['bids'] = SortedDict()
        order_book['asks'] = SortedDict()

        print("Loading snapshot data with Decimal keys/values...")
        for price_str, qty_str in snapshot['bids']:
            try:
                order_book['bids'][Decimal(price_str)] = Decimal(qty_str) # Clave y valor Decimal
            except ValueError:
                print(f"Warning: Skipping invalid bid format in snapshot: P={price_str}, Q={qty_str}")

        for price_str, qty_str in snapshot['asks']:
             try:
                 order_book['asks'][Decimal(price_str)] = Decimal(qty_str) # Clave y valor Decimal
             except ValueError:
                print(f"Warning: Skipping invalid ask format in snapshot: P={price_str}, Q={qty_str}")

        last_update_id = snapshot_last_update_id # Establecer inicialmente

        print(f"Initial book loaded (Decimal keys/values). Bids: {len(order_book['bids'])}, Asks: {len(order_book['asks'])}")

        # Procesar el buffer acumulado durante la llamada REST
        # process_depth_update ya usa Decimal
        print(f"Processing {len(message_buffer)} buffered messages...")
        temp_buffer = message_buffer[:] # Copiar buffer para iterar
        message_buffer = [] # Limpiar buffer global

        processed_count = 0
        for data in temp_buffer:
             # Condición de sincronización de Binance:
            if data['u'] <= snapshot_last_update_id:
                 continue # Descartar evento totalmente anterior al snapshot
            # Aplicar si el evento se solapa o es posterior al snapshot
            if data['U'] <= snapshot_last_update_id + 1 and data['u'] >= snapshot_last_update_id + 1:
                 process_depth_update(data)
                 processed_count += 1
            elif data['U'] > snapshot_last_update_id + 1: # Estrictamente posterior
                 process_depth_update(data)
                 processed_count += 1

        print(f"Processed {processed_count} messages from buffer.")
        initial_snapshot_processed = True # Marcar como listo para procesar mensajes en tiempo real
        print("Initial snapshot processed. Ready for real-time updates.")
        return True

    # Capturar errores específicos
    except requests.exceptions.Timeout:
        print(f"Error: Timeout getting initial snapshot for {symbol}.")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error getting initial snapshot: {e.response.status_code} {e.response.text}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Network Error getting initial snapshot: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"Error decoding snapshot JSON: {e}")
        return False
    except ValueError as e: # Capturar errores de conversión a Decimal en snapshot
         print(f"Error converting snapshot price/qty to Decimal: {e}")
         return False
    except Exception as e:
        print(f"Unexpected error during snapshot processing: {e}")
        # import traceback; print(traceback.format_exc()) # Descomentar para debug
        return False


def process_and_append_snapshot(symbol: str, file_path: str):
    """Procesa el OB final (con Decimal keys/values), carga DF existente, añade fila y guarda."""
    global order_book, last_update_id

    if not order_book['bids'] and not order_book['asks']:
        print("Order book is empty after session, nothing to process or save.")
        return False # Indicar fallo

    try:
        print("Processing final order book (Decimal keys/values)...")
        # Usar timezone-aware datetime para el timestamp
        processing_timestamp = datetime.now(timezone.utc)

        # --- Cálculos desde el order_book local (con claves y valores Decimal) ---
        # Sumar cantidades (que son Decimal)
        total_bid_volume = sum(order_book['bids'].values()) # Suma Decimals
        total_ask_volume = sum(order_book['asks'].values()) # Suma Decimals

        local_mid_price = None
        local_best_bid = None # Ahora serán Decimals
        local_best_ask = None # Ahora serán Decimals

        if order_book['bids'] and order_book['asks']:
            try:
                # peekitem devuelve (Decimal(precio), Decimal(cantidad))
                # Claves Decimal => ordenación numérica correcta
                local_best_bid, _ = order_book['bids'].peekitem(-1) # Último item = Máximo precio (Decimal)
                local_best_ask, _ = order_book['asks'].peekitem(0)  # Primer item = Mínimo precio (Decimal)

                # Calcular mid price (Decimal)
                local_mid_price = (local_best_bid + local_best_ask) / Decimal(2)

            except IndexError:
                print("Warning: Could not peek best bid/ask from local book (IndexError).")
            except Exception as e: # Captura genérica por si acaso
                 print(f"Error calculating local best bid/ask/midprice: {e}")


        # --- Verificación Opcional con API REST (BookTicker) ---
        api_best_bid_dec = None
        api_best_ask_dec = None
        api_mid_price_dec = None
        try:
            print("Verifying with fapi/v1/ticker/bookTicker...")
            ticker_url = f"https://fapi.binance.com/fapi/v1/ticker/bookTicker?symbol={symbol}"
            response = requests.get(ticker_url, timeout=5)
            response.raise_for_status()
            ticker_data = response.json()
            # Convertir respuesta de API a Decimal para comparar
            api_best_bid_dec = Decimal(ticker_data['bidPrice'])
            api_best_ask_dec = Decimal(ticker_data['askPrice'])
            api_mid_price_dec = (api_best_bid_dec + api_best_ask_dec) / Decimal(2)

            print(f"  Local Best Bid/Ask (Decimal): {local_best_bid} / {local_best_ask} (Mid: {local_mid_price})")
            print(f"  API   Best Bid/Ask (Decimal): {api_best_bid_dec} / {api_best_ask_dec} (Mid: {api_mid_price_dec})")

            # Comparar Decimals
            # ¡¡¡IMPORTANTE: VERIFICAR EL TICK SIZE CORRECTO PARA BTCUSDT FUTURES!!!
            tick_size_dec = Decimal("0.1") # AJUSTAR ESTE VALOR AL TICK SIZE REAL
            if local_best_bid is not None and abs(local_best_bid - api_best_bid_dec) > tick_size_dec:
                 print(f"  WARNING: Significant difference (> {tick_size_dec}) in BEST BID")
            if local_best_ask is not None and abs(local_best_ask - api_best_ask_dec) > tick_size_dec:
                 print(f"  WARNING: Significant difference (> {tick_size_dec}) in BEST ASK")

        except requests.exceptions.RequestException as e:
            print(f"  Could not verify with bookTicker API: {e}")
        except (KeyError, ValueError, TypeError) as e:
             print(f"  Error processing bookTicker API response: {e}")
        except Exception as e: # Captura genérica
             print(f"  Unexpected error during bookTicker verification: {e}")
        # --- Fin de la Verificación ---


        # Top N niveles por volumen (calculado desde el order_book local con Decimal)
        # Guardaremos listas de [float(precio), float(cantidad)] en el DF
        bids_by_volume = sorted(
            [(price, qty) for price, qty in order_book['bids'].items()],
            key=lambda item: item[1], # Ordenar por cantidad Decimal (item[1])
            reverse=True
        )
        asks_by_volume = sorted(
             [(price, qty) for price, qty in order_book['asks'].items()],
            key=lambda item: item[1], # Ordenar por cantidad Decimal (item[1])
            reverse=True
        )
        # Convertir a float para guardar
        top_bids_float = [[float(p), float(q)] for p, q in bids_by_volume[:TOP_N_LEVELS]]
        top_asks_float = [[float(p), float(q)] for p, q in asks_by_volume[:TOP_N_LEVELS]]


        # --- Preparar datos para la nueva fila (convirtiendo Decimals a float) ---
        new_data = {
            "TimestampUTC": processing_timestamp,
            "Symbol": symbol,
            "LastUpdateID": last_update_id,
            "TotalBidVolume": float(total_bid_volume), # Convertir a float
            "TotalAskVolume": float(total_ask_volume), # Convertir a float
            "BestBidPrice": float(local_best_bid) if local_best_bid is not None else None, # Convertir a float
            "BestAskPrice": float(local_best_ask) if local_best_ask is not None else None, # Convertir a float
            "MidPrice": float(local_mid_price) if local_mid_price is not None else None,       # Convertir a float
            f"Top{TOP_N_LEVELS}BidsByVol": top_bids_float, # Lista de floats
            f"Top{TOP_N_LEVELS}AsksByVol": top_asks_float, # Lista de floats
            "NumBidLevels": len(order_book['bids']),
            "NumAskLevels": len(order_book['asks']),
            "APIBestBid": float(api_best_bid_dec) if api_best_bid_dec is not None else None, # Convertir a float
            "APIBestAsk": float(api_best_ask_dec) if api_best_ask_dec is not None else None, # Convertir a float
            "APIMidPrice": float(api_mid_price_dec) if api_mid_price_dec is not None else None # Convertir a float
        }

        # --- Cargar/Crear DataFrame y añadir fila ---
        df = None
        if os.path.exists(file_path):
            print(f"Loading existing DataFrame from: {file_path}")
            try:
                df = pd.read_pickle(file_path)
                print(f"Loaded DataFrame with {len(df)} existing records.")
                # Validar columnas existentes vs nuevas (opcional)
                existing_cols = set(df.columns)
                new_cols = set(new_data.keys())
                if existing_cols != new_cols:
                    print("Warning: Column mismatch detected between loaded DF and new data.")
                    # Podrías añadir lógica aquí para alinear columnas si es necesario
                    # Ejemplo simple: añadir columnas faltantes al DF cargado
                    for col in new_cols - existing_cols:
                        print(f"Adding missing column '{col}' to loaded DataFrame.")
                        df[col] = pd.NA # O None o un valor por defecto apropiado
                    # Ejemplo simple: quitar columnas extra del DF cargado (más peligroso)
                    # for col in existing_cols - new_cols:
                    #     print(f"Warning: Removing extra column '{col}' from loaded DataFrame.")
                    #     df = df.drop(columns=[col])

            except (pickle.UnpicklingError, EOFError, FileNotFoundError, ImportError) as e:
                print(f"Error loading pickle file '{file_path}': {e}. Creating a new DataFrame.")
                df = None
            except Exception as e: # Captura genérica para otros posibles errores
                 print(f"Unexpected error loading pickle file '{file_path}': {e}. Creating a new DataFrame.")
                 df = None

        if df is None:
            print("Creating new DataFrame.")
            df = pd.DataFrame(columns=list(new_data.keys()))
            # Definir tipos float64 para datos numéricos, object para listas
            # Asegurar que los tipos coincidan con los datos en 'new_data'
            df = df.astype({
                'TimestampUTC': 'datetime64[ns, UTC]', 'Symbol': 'object',
                'LastUpdateID': 'Int64', 'TotalBidVolume': 'float64',
                'TotalAskVolume': 'float64', 'BestBidPrice': 'float64',
                'BestAskPrice': 'float64', 'MidPrice': 'float64',
                f'Top{TOP_N_LEVELS}BidsByVol': 'object', # Listas van como object
                f'Top{TOP_N_LEVELS}AsksByVol': 'object',
                'NumBidLevels': 'int64', 'NumAskLevels': 'int64',
                'APIBestBid': 'float64', 'APIBestAsk': 'float64', 'APIMidPrice': 'float64'
            })


        # --- Añadir la nueva fila ---
        new_row_df = pd.DataFrame([new_data])

        # Alinear columnas y asegurar tipos antes de concatenar
        # Esto ayuda si el DF cargado tenía columnas ligeramente diferentes
        current_df_cols = df.columns
        new_row_df = new_row_df.reindex(columns=current_df_cols, fill_value=pd.NA)
        try:
             new_row_df = new_row_df.astype(df.dtypes.to_dict())
        except Exception as e:
             # Si la conversión de tipos falla (podría ocurrir con NA y tipos específicos)
             print(f"Warning: Type conversion failed before concat: {e}. Attempting concat without forced astype.")

        df = pd.concat([df, new_row_df], ignore_index=True)
        print(f"Appended new snapshot. DataFrame now has {len(df)} records.")

        # --- Guardar el DataFrame actualizado ---
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        # Guardar usando pickle
        df.to_pickle(file_path)
        print(f"Updated DataFrame saved to: {file_path}")
        # Imprimir el mid-price guardado (que se convirtió a float)
        print(f"  Saved Mid Price (float): {new_data['MidPrice']}")

        return True # Indicar éxito

    except Exception as e:
        print(f"Error during processing and saving snapshot: {e}")
        import traceback
        print(traceback.format_exc()) # Imprimir stack trace completo para depuración
        return False # Indicar fallo


def run_websocket_session():
    """Ejecuta una única sesión de WebSocket y guarda/añade al DF."""
    global ws_app, ws_connection_active, initial_snapshot_processed, message_buffer, order_book, last_update_id

    # Reiniciar estado al inicio de la sesión
    order_book = {'bids': SortedDict(), 'asks': SortedDict()}
    last_update_id = None
    initial_snapshot_processed = False
    message_buffer = []
    ws_connection_active = False

    print("Initializing WebSocketApp...")
    ws_app = websocket.WebSocketApp(BINANCE_WS_URL,
                                  on_open=on_open,
                                  on_message=on_message,
                                  on_error=on_error,
                                  on_close=on_close)

    # Iniciar WebSocket en un hilo separado para no bloquear
    ws_thread = threading.Thread(target=ws_app.run_forever, daemon=True)
    ws_thread.start()
    ws_connection_active = True # Asumir activo inicialmente
    print(f"WebSocket thread started. Waiting for connection and initial snapshot...")

    # Esperar un poco para que la conexión se establezca antes de pedir snapshot
    # Aumentar ligeramente si la conexión a veces falla al inicio
    time.sleep(5)

    if not ws_connection_active:
         print("Failed to establish WebSocket connection after wait. Aborting.")
         # El hilo puede que no haya terminado si run_forever no llegó a ejecutarse bien
         if ws_thread.is_alive():
             # No hay un método directo para 'forzar' la detención de run_forever
             # de forma limpia desde fuera si nunca conectó.
             # run_forever debería salir si hay error de conexión, on_close/on_error lo gestionan.
             print("Waiting briefly for WebSocket thread to potentially exit...")
             ws_thread.join(timeout=2)
         return False # Indicar fallo

    # Obtener el snapshot inicial (mientras el WS ya está bufferizando)
    snapshot_success = get_initial_snapshot(SYMBOL_UPPER, SNAPSHOT_LIMIT)

    if not snapshot_success:
        print("Failed to get or process initial snapshot. Aborting session.")
        if ws_app and ws_connection_active: ws_app.close() # Intentar cierre limpio
        # Esperar a que el hilo del WS termine (debería llamar a on_close)
        ws_thread.join(timeout=5)
        return False # Indicar fallo

    # Mantener la conexión y procesar mensajes durante el tiempo especificado
    print(f"Maintaining connection for ~{CONNECT_DURATION_SECONDS} seconds...")
    start_time = time.time()
    while time.time() < start_time + CONNECT_DURATION_SECONDS:
        if not ws_connection_active:
             print("WebSocket connection lost during active period.")
             break # Salir del bucle si la conexión cae (on_close/on_error ya lo reportaron)
        time.sleep(1) # Simplemente esperar, el procesamiento ocurre en el hilo del WS
    else: # Se ejecuta si el bucle while termina normalmente (sin break)
        print("Connection duration elapsed.")

    # Procesar y añadir al DataFrame acumulativo
    save_success = process_and_append_snapshot(SYMBOL_UPPER, FILE_PATH)

    # Cerrar la conexión WebSocket
    print("Closing WebSocket connection...")
    if ws_app and ws_connection_active: # Solo intentar cerrar si creemos que está activa
        ws_app.close()
    # Esperar a que el hilo del WebSocket termine limpiamente
    if ws_thread.is_alive():
        print("Waiting for WebSocket thread to finish...")
        ws_thread.join(timeout=5)
    print("WebSocket thread finished.")
    ws_connection_active = False # Asegurarse de marcar como inactiva

    # Devolver True si se guardó algo, False si no
    return save_success


# --- Ejecución Principal (para una sola ejecución tipo cron) ---
if __name__ == "__main__":
    start_script_time = datetime.now(timezone.utc)
    print(f"--- Starting single order book snapshot session: {start_script_time} ---")
    print(f"Symbol: {SYMBOL_UPPER}, Duration: {CONNECT_DURATION_SECONDS}s")
    print(f"Data will be appended to: '{FILE_PATH}'")
    print("--- Using Decimal keys for order book ---") # Mensaje clave

    success = run_websocket_session()

    end_script_time = datetime.now(timezone.utc)
    total_duration = end_script_time - start_script_time
    print(f"--- Script finished at: {end_script_time} (Total duration: {total_duration}) ---")

    if success:
        print(f"--- Session completed successfully. Data saved/appended. ---")
        sys.exit(0) # Salida exitosa para cron
    else:
        print(f"--- Session failed or data could not be saved. ---")
        sys.exit(1) # Salida con error para cron