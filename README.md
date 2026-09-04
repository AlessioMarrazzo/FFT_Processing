# SHM Pendulum - Python FFT Analysis Engine

This module serves as the data processing backend for the pendulum's Structural Health Monitoring (SHM) IoT system. The script acts as a continuous daemon that extracts raw accelerometric data from InfluxDB, applies Digital Signal Processing (DSP) algorithms for frequency analysis, and reinserts the calculated spectra into the database, making them ready for dashboard visualization.

## Digital Signal Processing (DSP) Architecture

The code is structured to maximize the resolution of structural resonance peaks starting from fragmented payloads, applying advanced signal processing concepts:

* **Welch's Method:** Instead of a standard single FFT, the calculation averages the spectra of 4 consecutive packets (`BURSTS_TO_AVERAGE = 4`). This drastically reduces the noise floor, stabilizing the main harmonic components.
* **DC Component Removal:** Subtracting the local mean zeroes out the static gravitational offset (particularly noticeable on the Z-axis), preventing the 0 Hz component from masking the pendulum's low-frequency oscillations.
* **Zero-Padding (`nfft=256`):** Expanding the data points for the Fourier transform compared to the actual window acts as an interpolation in the frequency domain. It guarantees extremely smooth magnitude curves to pinpoint the system's poles with precision.

## Configuration and Requirements

The environment requires a local instance of InfluxDB (v2.x) and the installation of dependencies for scientific computing and database connection:

```bash
pip install numpy scipy influxdb-client
```

The system utilizes two separate buckets within the `TesiUni` organization to isolate the data flow and prevent read/write bottlenecks:
* **`pendulum_data`**: Source bucket containing the upstream sampled `raw_acceleration`.
* **`fft_data`**: Destination bucket where the frequency analysis results (`fft_magnitudo`) are stored.

## Calculation Parameters

The sampling and grouping parameters must be strictly aligned with the sensor node firmware to ensure analysis integrity.

| Parameter | Value | Description |
| :--- | :---: | :--- |
| **FS** | `10.0 Hz` | Original sampling frequency of the MPU6050 sensor. |
| **SAMPLES_PER_BURST** | `40` | Exact payload size transmitted via LoRaWAN/P2P. |
| **BURSTS_TO_AVERAGE** | `4` | Windows used for Welch's average (160 total accumulated points). |
| **UPDATE_INTERVAL** | `5 s` | Polling cycle to query InfluxDB and recalculate the new spectrum. |
