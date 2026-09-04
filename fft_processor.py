import time
import numpy as np
from scipy import signal
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# ==========================================
# CONFIGURAZIONE INFLUXDB
# ==========================================
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "ReipSDvpMNWQBvWaaBAg47S4YSbJPz2q2ZHq8cUlTkZ4SBO6l8xfQgfO9VhCLb3DL9TfjHcZlMGuHT4Ub3Si9Q=="
INFLUX_ORG = "TesiUni"

BUCKET_READ = "pendulum_data"
BUCKET_WRITE = "fft_data"

# ==========================================
# PARAMETRI DI ELABORAZIONE
# ==========================================
FS = 10.0               # Frequenza di campionamento (10 Hz)
SAMPLES_PER_BURST = 40  # Il numero esatto di campioni in un pacchetto LoRa
BURSTS_TO_AVERAGE = 4   # Quanti pacchetti usare per fare la media Welch
TOTAL_POINTS = SAMPLES_PER_BURST * BURSTS_TO_AVERAGE # 160 punti totali
UPDATE_INTERVAL = 5     # Attesa in secondi tra un calcolo e l'altro

def calculate_save_fft():
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = client.query_api()
    write_api = client.write_api(write_options=SYNCHRONOUS)

    # 1. Query temporale che scarta i dati vecchi di oltre 3 minuti
    query = f'''
        from(bucket: "{BUCKET_READ}")
        |> range(start: -3m) 
        |> filter(fn: (r) => r._measurement == "raw_acceleration")
        |> tail(n: {TOTAL_POINTS})
    '''
    
    tables = query_api.query(query)
    
    # 2. Smistamento manuale
    x_data, y_data, z_data = [], [], []
    for table in tables:
        for record in table.records:
            field = record.get_field()
            val = record.get_value()
            if field == "x":
                x_data.append(val)
            elif field == "y":
                y_data.append(val)
            elif field == "z":
                z_data.append(val)

    # Prendiamo la lunghezza minima per assicurarci di avere array uguali
    N = min(len(x_data), len(y_data), len(z_data))
    
    # 3. Controllo quantità dati
    if N < TOTAL_POINTS: 
        print(f"[{time.strftime('%H:%M:%S')}] Dati insufficienti (Servono {TOTAL_POINTS}) -> X:{len(x_data)}. Attesa...")
        client.close()
        return

    print(f"[{time.strftime('%H:%M:%S')}] Calcolo Welch FFT su {BURSTS_TO_AVERAGE} pacchetti (Tot: {N} campioni)...")

    # Tagliamo gli array alla stessa lunghezza (N) e togliamo la media (rimuove la componente DC)
    x_signal = np.array(x_data[:N]) - np.mean(x_data[:N])
    y_signal = np.array(y_data[:N]) - np.mean(y_data[:N])
    z_signal = np.array(z_data[:N]) - np.mean(z_data[:N])

    # 4. VERO Calcolo FFT di Welch con ZERO-PADDING (nfft=256)
    # L'aggiunta di nfft=256 fa l'interpolazione nel dominio della frequenza, 
    # rendendo le curve estremamente lisce e migliorando la risoluzione di lettura del picco.
    freqs, pxx_x = signal.welch(x_signal, fs=FS, nperseg=SAMPLES_PER_BURST, noverlap=0, nfft=256, scaling='spectrum')
    freqs, pxx_y = signal.welch(y_signal, fs=FS, nperseg=SAMPLES_PER_BURST, noverlap=0, nfft=256, scaling='spectrum')
    freqs, pxx_z = signal.welch(z_signal, fs=FS, nperseg=SAMPLES_PER_BURST, noverlap=0, nfft=256, scaling='spectrum')

    mag_x = np.sqrt(pxx_x)
    mag_y = np.sqrt(pxx_y)
    mag_z = np.sqrt(pxx_z)

    # 5. Salvataggio
    points_to_write = []
    for i in range(len(freqs)):
        if freqs[i] == 0: 
            continue
            
        point = Point("fft_magnitudo") \
            .tag("device", "esp32_pendolo") \
            .field("freq", float(freqs[i])) \
            .field("mag_x", float(mag_x[i])) \
            .field("mag_y", float(mag_y[i])) \
            .field("mag_z", float(mag_z[i])) \
            .time(time.time_ns(), WritePrecision.NS)
        
        points_to_write.append(point)

    write_api.write(bucket=BUCKET_WRITE, record=points_to_write)
    print("--> Spettro FFT salvato con successo su InfluxDB!")
    
    client.close()
    
# ==========================================
# LOOP PRINCIPALE
# ==========================================
if __name__ == "__main__":
    print("==================================================")
    print(" MOTORE FFT AVVIATO E IN ASCOLTO SU INFLUXDB")
    print("==================================================")
    
    while True:
        try:
            calculate_save_fft()
        except KeyboardInterrupt:
            print("\nArresto manuale dello script richiesto dall'utente. Uscita...")
            break
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Errore di elaborazione: {e}")
        
        time.sleep(UPDATE_INTERVAL)