import asyncio
import json
import pandas as pd
from decimal import Decimal
from datetime import datetime
import aiohttp
import websockets

class OrderBook:
    def __init__(self, snapshot):
        self._lock = asyncio.Lock()
        self.bids = {}
        self.asks = {}
        self.last_update_id = snapshot['lastUpdateId']
        self._initialize_book(snapshot)
        self.snapshots = pd.DataFrame(columns=[
            'timestamp', 'total_bid', 'total_ask', 'price', 'top_bids', 'top_asks'
        ])

    def _initialize_book(self, snapshot):
        for bid in snapshot['bids']:
            price = Decimal(bid[0])
            qty = Decimal(bid[1])
            if qty > 0:
                self.bids[price] = qty
                
        for ask in snapshot['asks']:
            price = Decimal(ask[0])
            qty = Decimal(ask[1])
            if qty > 0:
                self.asks[price] = qty

    async def process_update(self, event):
        async with self._lock:
            U = event['U']
            u = event['u']
            pu = event.get('pu', self.last_update_id)
            
            if pu != self.last_update_id:
                return False

            # Actualizar bids
            for price_str, qty_str in event.get('b', []):
                price = Decimal(price_str)
                qty = Decimal(qty_str)
                if qty == 0:
                    self.bids.pop(price, None)
                else:
                    self.bids[price] = qty

            # Actualizar asks
            for price_str, qty_str in event.get('a', []):
                price = Decimal(price_str)
                qty = Decimal(qty_str)
                if qty == 0:
                    self.asks.pop(price, None)
                else:
                    self.asks[price] = qty

            self.last_update_id = u
            return True

    def get_current_state(self):
        return {
            'bids': self.bids.copy(),
            'asks': self.asks.copy(),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

async def fetch_snapshot(session, symbol):
    url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=1000"
    async with session.get(url) as response:
        return await response.json()

async def save_snapshot(order_book):
    try:
        state = order_book.get_current_state()
        bids = state['bids']
        asks = state['asks']
        
        # Calcular precio actual
        if bids and asks:
            max_bid = max(bids.keys())
            min_ask = min(asks.keys())
            current_price = float((max_bid + min_ask) / 2)
        else:
            current_price = 0.0  # Caso de fallback teórico
        
        # Convertir Decimal a float para pandas
        total_bid = float(sum(bids.values())) if bids else 0.0
        total_ask = float(sum(asks.values())) if asks else 0.0

        print('bids',len(bids),'asks',len(asks),flush=True)
        print('bids',max(bids.keys()),min(bids.keys()),'asks',max(asks.keys()),min(asks.keys()),flush=True)
        
        # Obtener top 5 y convertir a float
        top_bids = sorted([(float(p), float(q)) for p, q in bids.items()], reverse=True)[:5] if bids else []
        top_asks = sorted([(float(p), float(q)) for p, q in asks.items()])[:5] if asks else []
        
        # Crear nueva fila
        new_row = {
            'timestamp': state['timestamp'],
            'total_bid': total_bid,
            'total_ask': total_ask,
            'price': current_price,
            'top_bids': [top_bids],
            'top_asks': [top_asks]
        }
        
        # Añadir al DataFrame
        order_book.snapshots = pd.concat([
            order_book.snapshots,
            pd.DataFrame(new_row)
        ], ignore_index=True)
        
        # Guardar en pickle
        order_book.snapshots.to_pickle('order_book.pkl')
        print(f"Snapshot guardado: {state['timestamp']}")

    except Exception as e:
        print(f"Error guardando snapshot: {str(e)}")

async def periodic_save(order_book):
    while True:
        await asyncio.sleep(60)  # 1 minuto
        await save_snapshot(order_book)

async def manage_order_book(symbol):
    while True:
        saver = None
        try:
            async with aiohttp.ClientSession() as session:
                snapshot = await fetch_snapshot(session, symbol)
                order_book = OrderBook(snapshot)
                
            ws_url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@depth@100ms"
            async with websockets.connect(ws_url) as ws:
                saver = asyncio.create_task(periodic_save(order_book))
                
                async for message in ws:
                    data = json.loads(message)
                    success = await order_book.process_update(data)
                    if not success:
                        print("Brecha detectada, reinicializando...")
                        break
                        
        except websockets.ConnectionClosed:
            print("Conexión cerrada, reconectando...")
        except Exception as e:
            print(f"Error general: {str(e)}")
        finally:
            if saver and not saver.done():
                saver.cancel()
                try:
                    await saver
                except asyncio.CancelledError:
                    pass
            await asyncio.sleep(1)

if __name__ == "__main__":
    symbol = "BTCUSDT"
    try:
        asyncio.run(manage_order_book(symbol))
    except KeyboardInterrupt:
        print("Script detenido por el usuario")