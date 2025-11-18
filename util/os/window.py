import os
import uuid
import subprocess

def get_smbios_serial():
    """Get SMBIOS (BIOS) serial number, fallback to hostname."""
    try:
        out = subprocess.check_output(
            ["wmic", "bios", "get", "SerialNumber"],
            text=True, stderr=subprocess.DEVNULL
        )
        # Skip header line, strip whitespace
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        if len(lines) >= 2 and lines[1] and lines[1].lower() != "serialnumber":
            return lines[1]
    except Exception:
        pass
    return os.environ.get("COMPUTERNAME") or os.uname().nodename

def get_disk_serial():
    """Get first physical disk serial number, fallback to hostname."""
    try:
        out = subprocess.check_output(
            ["wmic", "diskdrive", "get", "SerialNumber"],
            text=True, stderr=subprocess.DEVNULL
        )
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        if len(lines) >= 2 and lines[1] and lines[1].lower() != "serialnumber":
            return lines[1]
    except Exception:
        pass
    return os.environ.get("COMPUTERNAME") or os.uname().nodename

def get_mac():
    """Get first MAC address, fallback to hostname."""
    try:
        out = subprocess.check_output(
            ["getmac", "/NH", "/FO", "CSV"],
            text=True, stderr=subprocess.DEVNULL
        )
        # CSV: "MAC","TransportName"
        parts = out.splitlines()[0].replace('"', "").split(",")
        if parts and parts[0]:
            return parts[0]
    except Exception:
        pass
    # Last resort: hostname
    return os.environ.get("COMPUTERNAME") or os.uname().nodename

def generate_machine_uuid() -> str:
    """Combine identifiers and generate UUIDv5."""
    ids = [
        get_smbios_serial(),
        get_disk_serial(),
        get_mac(),
    ]
    # Sort for consistent order
    composite = "|".join(sorted(ids))
    # Use DNS namespace for reproducibility
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, composite))