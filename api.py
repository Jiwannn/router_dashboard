
import re
from flask import Flask, render_template, request
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException

app = Flask(__name__)

ROUTER = {
    "device_type": "cisco_ios_telnet",
    "host": "192.168.10.47",
    "port": 32770,
    "username": "admin",
    "password": "eve123",
    "secret": "eve123",
    "timeout": 15,
    "session_timeout": 30,
    "global_delay_factor": 2,
}

COMMANDS = [
    "show version",
    "show ip interface brief",
    "show running-config",
]


def parse_version(text):
    """Pull hostname, IOS version and uptime out of 'show version'."""
    info = {}
    m = re.search(r"^(\S+) uptime is (.+)$", text, re.MULTILINE)
    if m:
        info["hostname"], info["uptime"] = m.group(1), m.group(2).strip()
    m = re.search(r"Version ([^,\s]+)", text)
    if m:
        info["version"] = m.group(1)
    return info


def parse_interfaces(text):
    """Turn 'show ip interface brief' into a list of dicts."""
    rows = []
    pattern = re.compile(
        r"^(\S+)\s+(\S+)\s+\w+\s+\w+\s+(administratively down|up|down|deleted)\s+(up|down)\s*$"
    )
    for line in text.splitlines():
        m = pattern.match(line.strip())
        if m:
            rows.append({"name": m.group(1), "ip": m.group(2),
                         "status": m.group(3), "proto": m.group(4)})
    return rows


@app.route("/", methods=["GET", "POST"])
def index():
    results = {}
    error = None
    info = {}
    interfaces = []

    if request.method == "POST":
        net_connect = None
        try:
            net_connect = ConnectHandler(**ROUTER)
            net_connect.enable()

            for cmd in COMMANDS:
                # 'show running-config' is long, so relax timeouts + verification
                output = net_connect.send_command(
                    cmd,
                    read_timeout=60,
                    cmd_verify=False,
                )
                results[cmd] = output

        except NetmikoAuthenticationException as e:
            error = f"Authentication failed: {e}"
        except NetmikoTimeoutException as e:
            error = f"Timed out connecting to {ROUTER['host']}:{ROUTER['port']} - {e}"
        except Exception as e:
            error = f"Unexpected error: {type(e).__name__}: {e}"
        finally:
            if net_connect is not None:
                net_connect.disconnect()

    if "show version" in results:
        info = parse_version(results["show version"])
    if "show ip interface brief" in results:
        interfaces = parse_interfaces(results["show ip interface brief"])

    # ALWAYS return a response - both GET and POST
    return render_template(
        "index.html",
        results=results,
        error=error,
        router=ROUTER,
        commands=COMMANDS,
        info=info,
        interfaces=interfaces,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

