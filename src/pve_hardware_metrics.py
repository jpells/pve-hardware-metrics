"""A Python-based metrics collector for gathering and exporting hardware data
from Proxmox hosts to InfluxDB.

This tool provides detailed system metrics, including sensor data, NVMe/SATA
device information, and VM disk usage statistics.
"""  # noqa: D205

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import re
import socket
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Generator

logging.basicConfig(
    level="INFO", format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(Path(__file__).name)


def run_command(command: list[str]) -> str:
    """Run a shell command and return its output.

    Args:
        command (list): The command to run as a list of arguments.

    Returns:
        str: The standard output of the command.

    Raises:
        SystemExit: If the command fails.

    """
    try:
        result = run(command, capture_output=True, text=True, check=True)  # noqa: S603
    except CalledProcessError as e:
        logger.exception(
            "Command '%s' failed with error: %s",
            " ".join(command),
            e.stderr,
        )
        sys.exit(1)
    else:
        return result.stdout


def get_sensors_data() -> dict[str, Any]:
    """Get sensor data in JSON format.

    Returns:
        dict: The parsed JSON data from sensors.

    """
    try:
        parsed_data: dict[str, Any] = json.loads(
            run_command(["/usr/bin/sensors", "-j"])
        )
    except json.JSONDecodeError:
        logger.exception(
            "Failed to get or parse JSON output from sensors."
            " Please make sure you have the lm-sensors package installed."
        )
        return {}
    else:
        return parsed_data


def parse_sensors_data(host: str, sensors_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse sensor data into a list of measurements.

    Args:
        host (str): The host name.
        sensors_data (dict): The raw sensor data.

    Returns:
        list: A list of parsed measurements.

    """
    data = []
    for sensor, details in sensors_data.items():
        # "coretemp-isa-0000" -> "sensors.coretemp"
        measurement = f"sensors.{sensor.split('-')[0]}"
        tags = {"host": host}
        tags["adapter"] = details["Adapter"]
        fields = {}

        for key, value in details.items():
            if key == "Adapter":
                # Adapter is already in tags
                continue

            for field, field_value in value.items():
                # Ignore double-nested "temp1"
                if key == "temp1" and "temp1" in field.lower():
                    field_key = f"{field.lower()}"
                else:
                    field_key = f"{key.lower().replace(' ', '_')}_{field.lower()}"
                # Dynamically remove the number after "temp"
                field_key = re.sub(r"temp\d+_", "temp_", field_key)
                fields[field_key] = field_value

        data.append(
            {
                "measurement": measurement,
                "tags": tags,
                "fields": fields,
            },
        )

    return data


def get_disks() -> list[str]:
    """Get a list of disk names.

    Returns:
        list: A list of disk names.

    Raises:
        SystemExit: If the JSON data cannot be parsed.

    """
    try:
        result = json.loads(run_command(["/usr/bin/lsblk", "-J", "-o", "NAME,TYPE"]))
        return [
            device["name"]
            for device in result["blockdevices"]
            if device["type"] == "disk"
        ]
    except json.JSONDecodeError:
        logger.exception(
            "Failed to parse JSON output from lsblk."
            " Please make sure you have the util-linux package installed."
        )
        sys.exit(1)


def get_smartctl_data(disk: str) -> dict[str, Any]:
    """Get SMART data for a given disk.

    Args:
        disk (str): The disk name.

    Returns:
        dict: The SMART data output.

    """
    try:
        parsed_data: dict[str, Any] = json.loads(
            run_command(["/usr/sbin/smartctl", "-A", "-j", f"/dev/{disk}"])
        )
    except json.JSONDecodeError:
        logger.exception(
            "Failed to get or parse JSON output from smartctl."
            " Please make sure you have the smartmontools package installed."
        )
        return {}
    else:
        return parsed_data


def parse_smartctl_data(host: str, disk: str, data: dict[str, Any]) -> dict[str, Any]:
    """Parse SMART data into a measurement.

    Args:
        host (str): The host name.
        disk (str): The disk name.
        data (dict): The raw SMART data.

    Returns:
        dict: A parsed measurement.

    """
    if disk.startswith("nvme"):
        return parse_nvme_smartctl_data(host, disk, data)
    return parse_sata_smartctl_data(host, disk, data)


def parse_nvme_smartctl_data(
    host: str, disk: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Parse SMART data for NVMe disks into a measurement.

    Args:
        host (str): The host name.
        disk (str): The disk name.
        data (dict): The raw SMART data in JSON format.

    Returns:
        dict: A parsed measurement.

    """
    nvme_data = data.get("nvme_smart_health_information_log", {})
    stats = {}
    for key, value in nvme_data.items():
        if isinstance(value, list):
            for i, item in enumerate(value):
                stats[f"{key}_{i + 1}"] = item
        else:
            stats[key] = value
    return {
        "measurement": f"smartctl.{disk}",
        "tags": {"host": host},
        "fields": stats,
    }


# Constants for SMART attribute IDs
TEMPERATURE_CELSIUS_ID = 194
PERCENT_LIFETIME_REMAIN_ID = 202


def parse_sata_smartctl_data(
    host: str, disk: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Parse SMART data for SATA disks into a measurement.

    Args:
        host (str): The host name.
        disk (str): The disk name.
        data (dict): The raw SMART data in JSON format.

    Returns:
        dict: A parsed measurement.

    """
    sata_data = data.get("ata_smart_attributes", {}).get("table", [])
    stats = {}
    for attribute in sata_data:
        attribute_id = attribute["id"]
        attribute_name = attribute["name"].lower().replace("-", "_")
        raw_value = attribute["raw"]["value"]
        raw_string = attribute["raw"]["string"]
        normalized_value = attribute["value"]
        if attribute_id == TEMPERATURE_CELSIUS_ID and (
            match := re.search(r"(\d+)", raw_string)
        ):
            stats[attribute_name] = float(match.group(1))
        elif attribute_id == PERCENT_LIFETIME_REMAIN_ID:
            stats[attribute_name] = normalized_value
        else:
            stats[attribute_name] = raw_value
    return {
        "measurement": f"smartctl.{disk}",
        "tags": {"host": host},
        "fields": stats,
    }


def get_vms() -> list[tuple[str, str]]:
    """Get a list of running VM IDs and their names.

    Returns:
        list: A list of tuples containing VM ID and VM name.

    """
    result = run_command(["/usr/sbin/qm", "list"])
    vm_list = result.strip().split("\n")[1:]
    return [
        (vm_info.split()[0], vm_info.split()[1])
        for vm_info in vm_list
        if "running" in vm_info
    ]


def get_vm_disk_data(vm_id: str) -> str:
    """Get filesystem information for a given VM.

    Args:
        vm_id (str): The VM ID.

    Returns:
        str: The filesystem information output.

    """
    return run_command(["/usr/sbin/qm", "agent", vm_id, "get-fsinfo"])


def parse_vm_disk_data(
    host: str, vm_id: str, vm_name: str, data: str
) -> dict[str, Any]:
    """Parse filesystem information into a measurement.

    Args:
        host (str): The host name.
        vm_id (str): The VM ID.
        vm_name (str): The VM name.
        data (str): The raw filesystem information.

    Returns:
        dict: A parsed measurement.

    """
    fsinfo = json.loads(data)
    total_used = 0
    for fs in fsinfo:
        if fs["name"] == "sda1" and fs["mountpoint"] == "/":
            total_used += fs["used-bytes"]
    # Mimic Proxmox but with accurate disk usage
    return {
        "measurement": "system",
        "tags": {
            "host": vm_name,
            "nodename": host,
            "object": "qemu",
            "vmid": vm_id,
        },
        "fields": {"disk": float(total_used)},
    }


@contextmanager
def influxdb_client(
    influx_creds: dict[str, str],
) -> Generator[InfluxDBClient, None, None]:
    """Context manager for InfluxDBClient initialization and exception handling.

    Args:
        influx_creds (dict): The InfluxDB credentials.

    Yields:
        InfluxDBClient: The InfluxDB client instance.

    """
    try:
        client = InfluxDBClient(
            url=influx_creds["url"],
            token=influx_creds["token"],
            org=influx_creds["org"],
            timeout=30000,
        )
        yield client
    except (TimeoutError, InfluxDBError, Exception):
        logger.exception(
            "Connection Error: Could not connect to %s", influx_creds["url"]
        )
        sys.exit(1)
    else:
        client.close()  # type: ignore[no-untyped-call]


def upload_measurements(
    influx_creds: dict[str, str], measurements_list: list[dict[str, Any]]
) -> None:
    """Upload measurements to InfluxDB.

    Args:
        influx_creds (dict): The InfluxDB credentials.
        measurements_list (list): The list of measurements to upload.

    Raises:
        SystemExit: If the upload fails.

    """
    with influxdb_client(influx_creds) as client:
        write_api = client.write_api(write_options=SYNCHRONOUS)
        write_api.write(influx_creds["bucket"], influx_creds["org"], measurements_list)
        logger.info("Data written to InfluxDB successfully.")


def delete_measurement(influx_creds: dict[str, str], measurement: str) -> None:
    """Delete all data for a specific measurement or field from InfluxDB.

    Args:
        influx_creds (dict): The InfluxDB credentials.
        measurement (str): The measurement to delete.

    Raises:
        SystemExit: If the deletion fails.

    """
    with influxdb_client(influx_creds) as client:
        delete_api = client.delete_api()
        start = "1970-01-01T00:00:00Z"
        stop = datetime.now(UTC).isoformat()
        predicate = f'_measurement="{measurement}"'
        delete_api.delete(
            start,
            stop,
            predicate,
            bucket=influx_creds["bucket"],
            org=influx_creds["org"],
        )
        logger.info(
            "Measurement %s deleted successfully from InfluxDB.",
            measurement,
        )


def collect_measurements(host: str, *, vm_disk: bool) -> list[dict[str, Any]]:
    """Collect sensor, smartctl, and VM disk data measurements.

    Args:
        host (str): The host name.
        vm_disk (bool): Whether to collect VM disk data.

    Returns:
        list: A list of collected measurements.

    """
    # Sensors
    measurements = parse_sensors_data(host, get_sensors_data())

    # SMART data
    for disk in get_disks():
        disk_name = disk
        if disk.startswith("nvme"):
            # Trim suffix from nvmes
            disk_name = disk[: disk.rfind("n")]
        measurements.append(
            parse_smartctl_data(host, disk_name, get_smartctl_data(disk_name)),
        )

    # VM disk data
    if vm_disk:
        for vm_id, vm_name in get_vms():
            measurements.append(
                parse_vm_disk_data(host, vm_id, vm_name, get_vm_disk_data(vm_id))
            )

    return measurements


def main() -> None:
    """Entres vous."""
    parser = argparse.ArgumentParser(
        usage="%(prog)s [options]"
        " - Collect and export Proxmox hardware metrics to InfluxDB"
    )
    parser.add_argument(
        "--vm-disk",
        help="Enable VM disk data collection",
        action="store_true",
    )
    parser.add_argument(
        "-t",
        "--test",
        help="Just print the results without uploading to InfluxDB",
        action="store_true",
    )
    parser.add_argument(
        "-d",
        "--delete",
        help="Delete the specified measurement from InfluxDB",
        type=str,
    )
    args = parser.parse_args()

    # Validate and get environment variables
    load_dotenv()  # Load environment variables
    host = os.getenv("HOST_NAME", socket.gethostname())
    influx_creds = {
        "url": os.getenv("INFLUX_URL", "http://localhost:8086"),
        "token": os.getenv("INFLUX_TOKEN", "token"),
        "org": os.getenv("INFLUX_ORG", "organization"),
        "bucket": os.getenv("INFLUX_BUCKET", "bucket"),
    }

    if args.delete:
        delete_measurement(influx_creds, args.delete)
        sys.exit(0)

    # Collect measurements
    measurements = collect_measurements(host, vm_disk=args.vm_disk)

    if args.test:
        # just testing :)
        logger.info("\nMeasurements for host %s", host)
        logger.info(json.dumps(measurements, indent=4))
    else:
        upload_measurements(influx_creds, measurements)


if __name__ == "__main__":  # pragma: no cover
    main()
