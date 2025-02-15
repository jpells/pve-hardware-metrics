# Proxmox Hardware Metrics

A Python-based metrics collector for gathering and exporting hardware data from Proxmox hosts to InfluxDB. This tool provides detailed system metrics, including sensor data, NVMe/SATA device information, and VM disk usage statistics.

> **Note:** This tool is a great alternative for those who prefer not to install [Telegraf](https://www.influxdata.com/time-series-platform/telegraf/) on their Proxmox host.

## Features

- **System Metrics:** Collect sensor data from Proxmox hosts.
- **Device Monitoring:** Monitor NVMe and SATA device metrics.
- **VM Disk Usage Tracking:** Fill gaps in Proxmox's native reporting by capturing detailed VM disk usage statistics.
- **Flexible Configuration:** Configure easily through environment variables or command-line options.
- **Robust Logging:** Leverage a comprehensive logging system for seamless debugging and monitoring.

## Installation

### Prerequisites

- Python >= 3.11
- Access to a Proxmox host
- A running InfluxDB instance

### Dependencies

Install the required dependencies using pip:
```bash
pip install "influxdb-client>=1.48.0" "python-dotenv>=1.0.1"
```

## Configuration

### Environment Variables

Configure the script using the following environment variables:

| **Variable**         | **Description**               | **Required** |
|----------------------|-------------------------------|--------------|
| `HOST_TAG`           | Proxmox host name             | Yes          |
| `INFLUX_HOST`        | InfluxDB server address       | Yes          |
| `INFLUX_PORT`        | InfluxDB server port          | Yes          |
| `INFLUX_TOKEN`       | Authentication token          | Yes          |
| `INFLUX_ORGANIZATION`| InfluxDB organization name    | Yes          |
| `INFLUX_BUCKET`      | Target bucket name            | Yes          |

You can also store these environment variables in a `.env` file in the project directory. The `python-dotenv` library will automatically load them.

## Usage

### Basic Operation

Run the script with default settings:
```bash
python pve_hardware_metrics.py
```

### Additional Options

- **Include VM Disk Metrics:**
  Use this option to collect VM disk usage details that Proxmox’s `pvestatd` misses.
  ```bash
  python pve_hardware_metrics.py --vm-disk
  ```

- **Test Mode:**
  Run the script without uploading data to InfluxDB.
  ```bash
  python pve_hardware_metrics.py --test
  ```

- **Delete Specific Measurements:**
  Remove older data and schemas in case of InfluxDB data type inconsistencies.
  ```bash
  python pve_hardware_metrics.py --delete <measurement_name>
  ```

- **Help Menu:**
  View all available options and flags.
  ```bash
  python pve_hardware_metrics.py --help
  ```

### Handling Data Type Inconsistencies

InfluxDB can occasionally report data type conflicts. To resolve this, delete older measurements (and their associated schemas) using the `--delete` option. For example:
```bash
python pve_hardware_metrics.py --delete <measurement_name>
```

This ensures the script can continue uploading data without issues.

## SMART Reporting

SMART data reporting varies across devices. While this script has been tested on a wide range of NVMe and SATA devices, certain hardware configurations may require modifications to the script’s parsing logic.

If you encounter issues or discrepancies in reported data, please adjust the logic to match your specific hardware and let us know. Your feedback helps us improve compatibility and enhance the tool’s reliability.

## Acknowledgements

Special thanks to [MightySlaytanic](https://github.com/MightySlaytanic/pve-monitoring) for their work on Proxmox monitoring tools, which inspired this project.

## License

This project is licensed under the **MIT License**. For details, refer to the [LICENSE](./LICENSE) file.
