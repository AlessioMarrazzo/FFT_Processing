import time
import numpy as np
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# --- CONFIGURAZIONE INFLUXDB ---
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "ReipSDvpMNWQBvWaaBAg47S4YSbJPz2q2ZHq8cUlTkZ4SBO6l8xfQgfO9VhCLb3DL9TfjHcZlMGuHT4Ub3Si9Q=="
INFLUX_ORG = "TesiUni"

# I due bucket!
BUCKET_READ = "pendulum_data"
BUCKET_WRITE = "fft_data"

# Frequenza di campionamento del tuo ESP32
FS = 20.0 # 20 Hz
WINDOW_SECONDS = 5 # Quanti secondi di dati analizzare ogni volta

def calcola_e_salva_fft():
    # 1. Inizializza il client
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()
    write_api = client.write_api(write_options=SYNCHRONOUS)

    print(f"[{time.strftime('%H:%M:%S')}] Estrazione ultimi {WINDOW_SECONDS} secondi di dati...")

    # 2. Query Flux per estrarre gli assi X, Y, Z degli ultimi secondi
    query = f'''
        from(bucket: "{BUCKET_READ}")
        |> range(start: -{WINDOW_SECONDS}s)
        |> filter(fn: (r) => r._measurement == "raw_acceleration")
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    
    tables = query_api.query(query)
    
    # Raccogliamo i dati in liste
    x_data, y_data, z_data = [], [], []
    for table in tables:
        for record in table.records:
            x_data.append(record["x"])
            y_data.append(record["y"])
            z_data.append(record["z"])

    N = len(x_data)
    if N < 10: # Sicurezza: calcoliamo la FFT solo se abbiamo abbastanza campioni
        print("Dati insufficienti in questa finestra. Attendo...")
        return

    print(f"Calcolo FFT su {N} campioni...")

    # 3. Calcolo FFT con NumPy
    # Togliamo la media (componente continua) per centrare il segnale attorno allo zero
    x_signal = np.array(x_data) - np.mean(x_data)
    y_signal = np.array(y_data) - np.mean(y_data)
    z_signal = np.array(z_data) - np.mean(z_data)

    # Calcolo delle frequenze (Asse X del grafico in Grafana)
    freqs = np.fft.rfftfreq(N, d=1/FS)
    
    # Calcolo della Magnitudo (Asse Y del grafico in Grafana)
    # abs() prende il valore assoluto dei numeri complessi generati dalla FFT
    fft_x = np.abs(np.fft.rfft(x_signal))
    fft_y = np.abs(np.fft.rfft(y_signal))
    fft_z = np.abs(np.fft.rfft(z_signal))

    # 4. Salvataggio nel bucket fft_data
    points_to_write = []
    for i in range(len(freqs)):
        # Evitiamo la frequenza 0 (continua) che di solito è solo rumore statico
        if freqs[i] == 0:
            continue
            
        point = Point("fft_magnitudo") \
            .tag("device", "esp32_pendolo") \
            .field("freq", float(freqs[i])) \
            .field("mag_x", float(fft_x[i])) \
            .field("mag_y", float(fft_y[i])) \
            .field("mag_z", float(fft_z[i])) \
            .time(time.time_ns(), WritePrecision.NS)
        
        points_to_write.append(point)

    write_api.write(bucket=BUCKET_WRITE, record=points_to_write)
    print("--> FFT salvata in InfluxDB!")

# 5. Loop infinito: esegue la FFT ogni 'X' secondi
if __name__ == "__main__":
    while True:
        try:
            calcola_e_salva_fft()
        except Exception as e:
            print(f"Errore: {e}")
        
        # Aspetta 5 secondi prima di elaborare la prossima finestra
        time.sleep(WINDOW_SECONDS)