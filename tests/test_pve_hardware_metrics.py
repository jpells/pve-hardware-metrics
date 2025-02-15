"""Unit tests for the pve_hardware_metrics module."""

import argparse
import subprocess
from unittest import mock
from unittest.mock import Mock, patch

import pytest
from influxdb_client.client.exceptions import InfluxDBError

import pve_hardware_metrics


@patch("subprocess.check_output")
def test_get_sensors_data(mock_check_output: Mock) -> None:
    """Test the get_sensors_data function.

    Args:
        mock_check_output (Mock): Mocked check_output function.

    """
    mock_check_output.return_value = '{"sensor": {"Adapter": "ISA adapter"}}'
    assert pve_hardware_metrics.get_sensors_data() == {
        "sensor": {"Adapter": "ISA adapter"}
    }
    mock_check_output.return_value = "invalid json"
    assert pve_hardware_metrics.get_sensors_data() == {}


def test_parse_sensors_data() -> None:
    """Test the parse_sensors_data function."""
    sensors_data = {
        "coretemp-isa-0000": {
            "Adapter": "ISA adapter",
            "Package id 0": {
                "temp1_input": 42.000,
                "temp1_max": 100.000,
                "temp1_crit": 100.000,
                "temp1_crit_alarm": 0.000,
            },
            "Core 0": {
                "temp2_input": 37.000,
                "temp2_max": 100.000,
                "temp2_crit": 100.000,
                "temp2_crit_alarm": 0.000,
            },
            "Core 1": {
                "temp6_input": 39.000,
                "temp6_max": 100.000,
                "temp6_crit": 100.000,
                "temp6_crit_alarm": 0.000,
            },
        },
        "acpitz-acpi-0": {
            "Adapter": "ACPI interface",
            "temp1": {"temp1_input": 27.800},
        },
        "mt7921_phy0-pci-0400": {
            "Adapter": "PCI adapter",
            "temp1": {"temp1_input": 46.000},
        },
        "nvme-pci-0100": {
            "Adapter": "PCI adapter",
            "Composite": {
                "temp1_input": 45.850,
                "temp1_max": 81.850,
                "temp1_min": -273.150,
                "temp1_crit": 84.850,
                "temp1_alarm": 0.000,
            },
            "Sensor 1": {
                "temp2_input": 45.850,
                "temp2_max": 65261.850,
                "temp2_min": -273.150,
            },
            "Sensor 2": {
                "temp3_input": 54.850,
                "temp3_max": 65261.850,
                "temp3_min": -273.150,
            },
        },
    }
    expected = [
        {
            "measurement": "sensors.coretemp",
            "tags": {"host": "test_host", "adapter": "ISA adapter"},
            "fields": {
                "package_id_0_temp_input": 42.0,
                "package_id_0_temp_max": 100.0,
                "package_id_0_temp_crit": 100.0,
                "package_id_0_temp_crit_alarm": 0.0,
                "core_0_temp_input": 37.0,
                "core_0_temp_max": 100.0,
                "core_0_temp_crit": 100.0,
                "core_0_temp_crit_alarm": 0.0,
                "core_1_temp_input": 39.0,
                "core_1_temp_max": 100.0,
                "core_1_temp_crit": 100.0,
                "core_1_temp_crit_alarm": 0.0,
            },
        },
        {
            "fields": {
                "temp_input": 27.8,
            },
            "measurement": "sensors.acpitz",
            "tags": {
                "adapter": "ACPI interface",
                "host": "test_host",
            },
        },
        {
            "fields": {
                "temp_input": 46.0,
            },
            "measurement": "sensors.mt7921_phy0",
            "tags": {
                "adapter": "PCI adapter",
                "host": "test_host",
            },
        },
        {
            "fields": {
                "composite_temp_alarm": 0.0,
                "composite_temp_crit": 84.85,
                "composite_temp_input": 45.85,
                "composite_temp_max": 81.85,
                "composite_temp_min": -273.15,
                "sensor_1_temp_input": 45.85,
                "sensor_1_temp_max": 65261.85,
                "sensor_1_temp_min": -273.15,
                "sensor_2_temp_input": 54.85,
                "sensor_2_temp_max": 65261.85,
                "sensor_2_temp_min": -273.15,
            },
            "measurement": "sensors.nvme",
            "tags": {
                "adapter": "PCI adapter",
                "host": "test_host",
            },
        },
    ]
    assert (
        pve_hardware_metrics.parse_sensors_data("test_host", sensors_data) == expected
    )


@patch("subprocess.check_output")
def test_get_disks(mock_check_output: Mock) -> None:
    """Test the get_disks function.

    Args:
        mock_check_output (Mock): Mocked check_output function.

    """
    mock_check_output.return_value = (
        '{"blockdevices": [{"name": "sda", "type": "disk"}]}'
    )
    assert pve_hardware_metrics.get_disks() == ["sda"]


@patch("subprocess.check_output")
def test_get_disks_fail(mock_check_output: Mock) -> None:
    """Test the get_disks function with malformed JSON.

    Args:
        mock_check_output (Mock): Mocked check_output function.

    """
    mock_check_output.return_value = "invalid json"
    with pytest.raises(SystemExit):
        pve_hardware_metrics.get_disks()


@patch("subprocess.check_output")
def test_get_smartctl_data(mock_check_output: Mock) -> None:
    """Test the get_smartctl_data function.

    Args:
        mock_check_output (Mock): Mocked check_output function.

    """
    mock_check_output.return_value = (
        """{"json_format_version": [1,0], "smartctl": {"version": [7,3]}}"""
    )
    assert pve_hardware_metrics.get_smartctl_data("/dev/nvme0n1") == {
        "json_format_version": [1, 0],
        "smartctl": {
            "version": [7, 3],
        },
    }
    mock_check_output.return_value = "invalid json"
    assert pve_hardware_metrics.get_smartctl_data("/dev/nvme0n1") == {}


def test_parse_nvme_smartctl_data() -> None:
    """Test the parse_nvme_smartctl_data function."""
    data = {
        "json_format_version": [1, 0],
        "smartctl": {
            "version": [7, 3],
            "svn_revision": "5338",
            "platform_info": "x86_64-linux-6.8.12-5-pve",
            "build_info": "(local build)",
            "argv": ["smartctl", "-A", "-j", "/dev/nvme0n1"],
            "exit_status": 0,
        },
        "local_time": {"time_t": 1737897357, "asctime": "Sun Jan 26 08:15:57 2025 EST"},
        "device": {
            "name": "/dev/nvme0n1",
            "info_name": "/dev/nvme0n1",
            "type": "nvme",
            "protocol": "NVMe",
        },
        "nvme_smart_health_information_log": {
            "critical_warning": 0,
            "temperature": 48,
            "available_spare": 100,
            "available_spare_threshold": 10,
            "percentage_used": 0,
            "data_units_read": 37355465,
            "data_units_written": 3517384,
            "host_reads": 214737173,
            "host_writes": 78355153,
            "controller_busy_time": 1140,
            "power_cycles": 16,
            "power_on_hours": 513,
            "unsafe_shutdowns": 2,
            "media_errors": 0,
            "num_err_log_entries": 0,
            "warning_temp_time": 0,
            "critical_comp_time": 0,
            "temperature_sensors": [48, 61],
        },
        "temperature": {"current": 48},
        "power_cycle_count": 16,
        "power_on_time": {"hours": 513},
    }
    expected = {
        "measurement": "smartctl.nvme0",
        "tags": {"host": "test_host"},
        "fields": {
            "temperature": 48,
            "available_spare": 100,
            "available_spare_threshold": 10,
            "controller_busy_time": 1140,
            "critical_comp_time": 0,
            "critical_warning": 0,
            "data_units_read": 37355465,
            "data_units_written": 3517384,
            "host_reads": 214737173,
            "host_writes": 78355153,
            "media_errors": 0,
            "num_err_log_entries": 0,
            "percentage_used": 0,
            "power_cycles": 16,
            "power_on_hours": 513,
            "temperature_sensors_1": 48,
            "temperature_sensors_2": 61,
            "unsafe_shutdowns": 2,
            "warning_temp_time": 0,
        },
    }
    assert (
        pve_hardware_metrics.parse_smartctl_data("test_host", "nvme0", data) == expected
    )


def test_parse_sata_smartctl_data() -> None:
    """Test the parse_sata_smartctl_data function."""
    data = {
        "json_format_version": [1, 0],
        "smartctl": {
            "version": [7, 3],
            "svn_revision": "5338",
            "platform_info": "x86_64-linux-6.8.12-5-pve",
            "build_info": "(local build)",
            "argv": ["smartctl", "-A", "-j", "/dev/sda"],
            "drive_database_version": {"string": "7.3/5319"},
            "exit_status": 0,
        },
        "local_time": {"time_t": 1737904636, "asctime": "Sun Jan 26 10:17:16 2025 EST"},
        "device": {
            "name": "/dev/sda",
            "info_name": "/dev/sda [SAT]",
            "type": "sat",
            "protocol": "ATA",
        },
        "ata_smart_attributes": {
            "revision": 16,
            "table": [
                {
                    "id": 194,
                    "name": "Temperature_Celsius",
                    "value": 59,
                    "worst": 56,
                    "thresh": 0,
                    "when_failed": "",
                    "flags": {
                        "value": 34,
                        "string": "-O---K ",
                        "prefailure": False,
                        "updated_online": True,
                        "performance": False,
                        "error_rate": False,
                        "event_count": False,
                        "auto_keep": True,
                    },
                    "raw": {"value": 188980133929, "string": "41 (Min/Max 24/44)"},
                },
                {
                    "id": 202,
                    "name": "Percent_Lifetime_Remain",
                    "value": 100,
                    "worst": 100,
                    "thresh": 1,
                    "when_failed": "",
                    "flags": {
                        "value": 48,
                        "string": "----CK ",
                        "prefailure": False,
                        "updated_online": False,
                        "performance": False,
                        "error_rate": False,
                        "event_count": True,
                        "auto_keep": True,
                    },
                    "raw": {"value": 0, "string": "0"},
                },
                {
                    "id": 250,
                    "name": "Read_Error_Retry_Rate",
                    "value": 100,
                    "worst": 100,
                    "thresh": 0,
                    "when_failed": "",
                    "flags": {
                        "value": 50,
                        "string": "-O--CK ",
                        "prefailure": False,
                        "updated_online": True,
                        "performance": False,
                        "error_rate": False,
                        "event_count": True,
                        "auto_keep": True,
                    },
                    "raw": {"value": 0, "string": "0"},
                },
            ],
        },
    }
    expected = {
        "measurement": "smartctl.sda",
        "tags": {"host": "test_host"},
        "fields": {
            "temperature_celsius": 41.0,
            "percent_lifetime_remain": 100,
            "read_error_retry_rate": 0,
        },
    }
    assert (
        pve_hardware_metrics.parse_smartctl_data("test_host", "sda", data) == expected
    )


@patch("subprocess.check_output")
def test_get_vms(mock_check_output: Mock) -> None:
    """Test the get_vms function.

    Args:
        mock_check_output (Mock): Mocked check_output function.

    """
    mock_check_output.return_value = "VMID NAME STATUS\n100 vm_name running"
    assert pve_hardware_metrics.get_vms() == [("100", "vm_name")]


@patch("subprocess.check_output")
def test_get_vm_disk_data(mock_check_output: Mock) -> None:
    """Test the get_vm_disk_data function.

    Args:
        mock_check_output (Mock): Mocked check_output function.

    """
    mock_check_output.return_value = (
        '[{"name": "sda1", "mountpoint": "/", "used-bytes": 1024}]'
    )
    assert pve_hardware_metrics.get_vm_disk_data("100") == [
        {
            "name": "sda1",
            "mountpoint": "/",
            "used-bytes": 1024,
        }
    ]


@patch("subprocess.run")
def test_get_vm_disk_data_vm_shutdown(mock_run: Mock) -> None:
    """Test the get_vm_disk_data function when VM is shut down.

    Args:
        mock_run (Mock): Mocked run function.

    """
    mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
    assert pve_hardware_metrics.get_vm_disk_data("100") == []
    mock_run.side_effect = subprocess.TimeoutExpired("cmd", 2)
    assert pve_hardware_metrics.get_vm_disk_data("100") == []


def test_parse_vm_disk_data() -> None:
    """Test the parse_vm_disk_data function."""
    data = [
        {
            "disk": [
                {
                    "bus": 0,
                    "bus-type": "scsi",
                    "dev": "/dev/sda15",
                    "pci-controller": {"bus": 1, "domain": 0, "function": 0, "slot": 1},
                    "serial": "0QEMU_QEMU_HARDDISK_drive-scsi0",
                    "target": 0,
                    "unit": 0,
                }
            ],
            "mountpoint": "/boot/efi",
            "name": "sda15",
            "total-bytes": 129718272,
            "type": "vfat",
            "used-bytes": 12124160,
        },
        {
            "disk": [
                {
                    "bus": 0,
                    "bus-type": "scsi",
                    "dev": "/dev/sda1",
                    "pci-controller": {"bus": 1, "domain": 0, "function": 0, "slot": 1},
                    "serial": "0QEMU_QEMU_HARDDISK_drive-scsi0",
                    "target": 0,
                    "unit": 0,
                }
            ],
            "mountpoint": "/",
            "name": "sda1",
            "total-bytes": 4864684032,
            "type": "ext4",
            "used-bytes": 2426138624,
        },
    ]
    expected = {
        "measurement": "system",
        "tags": {
            "host": "vm_name",
            "nodename": "test_host",
            "object": "qemu",
            "vmid": "100",
        },
        "fields": {"disk": 2426138624.0},
    }
    assert (
        pve_hardware_metrics.parse_vm_disk_data("test_host", "100", "vm_name", data)
        == expected
    )


@patch("pve_hardware_metrics.InfluxDBClient")
def test_influxdb_client(mock_influxdb_client: Mock) -> None:
    """Test the influxdb_client context manager.

    Args:
        mock_influxdb_client (Mock): Mocked InfluxDBClient class.

    """
    influx_creds = {
        "url": "http://localhost:8086",
        "token": "test_token",
        "org": "test_org",
    }
    with pve_hardware_metrics.influxdb_client(influx_creds) as client:
        assert client == mock_influxdb_client.return_value
    mock_influxdb_client.assert_called_once_with(
        url="http://localhost:8086",
        token="test_token",  # noqa: S106
        org="test_org",
        timeout=30000,
    )
    mock_influxdb_client.return_value.close.assert_called_once()


@patch("pve_hardware_metrics.InfluxDBClient")
def test_influxdb_client_exceptions(mock_influxdb_client: Mock) -> None:
    """Test the influxdb_client context manager exception handling.

    Args:
        mock_influxdb_client (Mock): Mocked InfluxDBClient class.

    """
    influx_creds = {
        "url": "http://localhost:8086",
        "token": "test_token",
        "org": "test_org",
    }

    # Test InfluxDBError handling
    mock_influxdb_client.side_effect = InfluxDBError(response=mock.Mock())
    with pytest.raises(SystemExit), pve_hardware_metrics.influxdb_client(influx_creds):
        pass  # pragma: no cover

    # Reset side effect for other tests
    mock_influxdb_client.side_effect = None
    with pve_hardware_metrics.influxdb_client(influx_creds) as client:
        assert client == mock_influxdb_client.return_value


@patch("pve_hardware_metrics.influxdb_client")
@patch("pve_hardware_metrics.SYNCHRONOUS")
def test_upload_measurements(
    mock_synchronous: Mock, mock_influxdb_client: Mock
) -> None:
    """Test the upload_measurements function.

    Args:
        mock_synchronous (Mock): Mocked SYNCHRONOUS constant.
        mock_influxdb_client (Mock): Mocked influxdb_client context manager.

    """
    influx_creds = {
        "url": "http://localhost:8086",
        "token": "test_token",
        "org": "test_org",
        "bucket": "test_bucket",
    }
    measurements_list = [{"measurement": "test"}]
    mock_client = mock_influxdb_client.return_value.__enter__.return_value
    mock_write_api = mock_client.write_api.return_value

    pve_hardware_metrics.upload_measurements(influx_creds, measurements_list)

    mock_client.write_api.assert_called_once_with(write_options=mock_synchronous)
    mock_write_api.write.assert_called_once_with(
        "test_bucket", "test_org", measurements_list
    )


@patch("pve_hardware_metrics.influxdb_client")
def test_delete_measurement(mock_influxdb_client: Mock) -> None:
    """Test the delete_measurement function.

    Args:
        mock_influxdb_client (Mock): Mocked influxdb_client context manager.

    """
    influx_creds = {
        "url": "http://localhost:8086",
        "token": "test_token",
        "org": "test_org",
        "bucket": "test_bucket",
    }
    mock_client = mock_influxdb_client.return_value.__enter__.return_value
    mock_delete_api = mock_client.delete_api.return_value

    pve_hardware_metrics.delete_measurement(influx_creds, "test_measurement")

    mock_delete_api.delete.assert_called_with(
        "1970-01-01T00:00:00Z",
        mock.ANY,
        '_measurement="test_measurement"',
        bucket="test_bucket",
        org="test_org",
    )


@patch("pve_hardware_metrics.get_disks")
@patch("pve_hardware_metrics.upload_measurements")
@patch("pve_hardware_metrics.parse_sensors_data")
@patch("pve_hardware_metrics.get_sensors_data")
@patch("socket.gethostname")
def test_main(
    mock_gethostname: Mock,
    mock_get_sensors_data: Mock,
    mock_parse_sensors_data: Mock,
    mock_upload_measurements: Mock,
    mock_get_disks: Mock,
) -> None:
    """Test the main function.

    Args:
        mock_gethostname (Mock): Mocked get_env_variable function.
        mock_get_sensors_data (Mock): Mocked get_sensors_data function.
        mock_parse_sensors_data (Mock): Mocked parse_sensors_data function.
        mock_upload_measurements (Mock): Mocked upload_measurements function.
        mock_get_disks (Mock): Mocked get_disks function.

    """
    mock_gethostname.return_value = "test_value"
    mock_get_sensors_data.return_value = {}
    mock_parse_sensors_data.return_value = []
    mock_get_disks.return_value = []
    with patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(vm_disk=False, test=True, delete=None),
    ):
        pve_hardware_metrics.main()
    mock_upload_measurements.assert_not_called()
    mock_parse_sensors_data.assert_called_once_with("test_value", {})


@patch("pve_hardware_metrics.delete_measurement")
@patch("socket.gethostname")
def test_main_with_delete(
    mock_gethostname: Mock, mock_delete_measurement: Mock
) -> None:
    """Test the main function with delete argument.

    Args:
        mock_gethostname (Mock): Mocked gethostname function.
        mock_delete_measurement (Mock): Mocked delete_measurement function.

    """
    mock_gethostname.return_value = "test_value"
    with (
        patch(
            "argparse.ArgumentParser.parse_args",
            return_value=argparse.Namespace(
                vm_disk=False, test=False, delete="test_measurement"
            ),
        ),
        pytest.raises(SystemExit),
    ):
        pve_hardware_metrics.main()
    mock_delete_measurement.assert_called_once_with(
        {
            "url": "http://localhost:8086",
            "token": "token",
            "org": "organization",
            "bucket": "bucket",
        },
        "test_measurement",
    )


@patch("pve_hardware_metrics.get_smartctl_data")
@patch("pve_hardware_metrics.get_disks")
@patch("pve_hardware_metrics.get_sensors_data")
@patch("pve_hardware_metrics.upload_measurements")
def test_main_nvme_disk_name_trimming(
    mock_upload_measurements: Mock,
    mock_get_sensors_data: Mock,
    mock_get_disks: Mock,
    mock_get_smartctl_data: Mock,
) -> None:
    """Test the main function for NVMe disk name trimming.

    Args:
        mock_upload_measurements (Mock): Mocked upload_measurements function.
        mock_get_sensors_data (Mock): Mocked get_sensors_data function.
        mock_get_disks (Mock): Mocked get_disks function.
        mock_get_smartctl_data (Mock): Mocked get_smartctl_data function.

    """
    mock_get_sensors_data.return_value = {}
    mock_get_disks.return_value = ["nvme0n1"]
    mock_get_smartctl_data.return_value = {}

    with patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(vm_disk=False, test=False, delete=None),
    ):
        pve_hardware_metrics.main()

    mock_upload_measurements.assert_called_once()
    measurements = mock_upload_measurements.call_args[0][1]
    assert any(
        measurement["measurement"] == "smartctl.nvme0" for measurement in measurements
    )


@patch("pve_hardware_metrics.get_vms")
@patch("pve_hardware_metrics.get_vm_disk_data")
@patch("pve_hardware_metrics.parse_vm_disk_data")
@patch("pve_hardware_metrics.upload_measurements")
@patch("pve_hardware_metrics.get_sensors_data")
@patch("pve_hardware_metrics.parse_sensors_data")
@patch("pve_hardware_metrics.get_disks")
@patch("pve_hardware_metrics.get_smartctl_data")
def test_main_with_vm_disk_data(  # noqa: PLR0913
    mock_get_smartctl_data: Mock,
    mock_get_disks: Mock,
    mock_parse_sensors_data: Mock,
    mock_get_sensors_data: Mock,
    mock_upload_measurements: Mock,
    mock_parse_vm_disk_data: Mock,
    mock_get_vm_disk_data: Mock,
    mock_get_vms: Mock,
) -> None:
    """Test the main function with VM disk data collection.

    Args:
        mock_get_smartctl_data (Mock): Mocked get_smartctl_data function.
        mock_get_disks (Mock): Mocked get_disks function.
        mock_parse_sensors_data (Mock): Mocked parse_sensors_data function.
        mock_get_sensors_data (Mock): Mocked get_sensors_data function.
        mock_upload_measurements (Mock): Mocked upload_measurements function.
        mock_parse_vm_disk_data (Mock): Mocked parse_vm_disk_data function.
        mock_get_vm_disk_data (Mock): Mocked get_vm_disk_data function.
        mock_get_vms (Mock): Mocked get_vms function.

    """
    mock_get_sensors_data.return_value = {}
    mock_parse_sensors_data.return_value = []
    mock_get_disks.return_value = ["sda"]
    mock_get_smartctl_data.return_value = {}
    mock_get_vms.return_value = [("100", "vm_name")]
    mock_get_vm_disk_data.return_value = (
        '{"name": "sda1", "mountpoint": "/", "used-bytes": 1024}'
    )
    mock_parse_vm_disk_data.return_value = {
        "measurement": "system",
        "tags": {
            "host": "vm_name",
            "nodename": "test_value",
            "object": "qemu",
            "vmid": "100",
        },
        "fields": {"disk": 1024.0},
    }

    with patch(
        "argparse.ArgumentParser.parse_args",
        return_value=argparse.Namespace(vm_disk=True, test=False, delete=None),
    ):
        pve_hardware_metrics.main()

    mock_upload_measurements.assert_called_once()
    measurements = mock_upload_measurements.call_args[0][1]
    assert any(measurement["measurement"] == "system" for measurement in measurements)
