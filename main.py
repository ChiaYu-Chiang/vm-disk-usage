import json
import time
from ssh_utils import SSHClient, scan_network
from parser_utils import parse_linux_output, parse_windows_output
from sendmail import send_email
import socket, paramiko


if __name__ == "__main__":
    starttime = time.time()

    target_percent = 80
    default_target_info = {
        "name": "S3_HAPROXY",
        "port": 22,
        "user": "root",
        "pwd": "Chief+26576688@",
        "os": "linux"
    }
    scanned_vms = []
    scanned_failed_vms = []
    high_usage_ips = []
    targets = []
    
    network = "10.210.68.0/24"
    live_hosts = scan_network(network)

    for ip in live_hosts:
        target_info = default_target_info.copy()
        target_info["ip"] = ip
        targets.append(target_info)
    print(f"targets after ip scan: \n{targets}")

    with open("targets.json") as json_file:
        json_targets = json.load(json_file)
        targets.extend(json_targets)

    ssh = SSHClient()

    command_and_parser = {
        "linux": ("df /", parse_linux_output),
        "windows": (
            'powershell -Command "Get-CimInstance -ClassName Win32_logicalDisk -Filter "DriveType=3" | Select-Object -Property DeviceID, Size, FreeSpace | Format-Table -AutoSize"',
            parse_windows_output,
        ),
    }

    for target in targets:
        if target["os"] == "windows":
            scanned_failed_vms.append((target["ip"], target["name"]))
            print("skip this windows target.")
            continue
        try:
            ssh.connect(target["ip"], target["port"], target["user"], target["pwd"])
            command, parser = command_and_parser.get(target["os"], (None, None))
            if command and parser:
                output = ssh.execute_command(
                    command, "utf-8" if target["os"] == "linux" else "cp950"
                )
                if output is not None:
                    usages = parser(output)
                    for usage in usages:
                        if usage >= target_percent and target["ip"] not in high_usage_ips:
                            high_usage_ips.append(target["ip"])
                        scanned_vms.append((target["ip"], target["name"]))
                    print(f"ip: {target['ip']}, usage: {usages}%")
        except (paramiko.AuthenticationException, paramiko.SSHException, socket.timeout, Exception) as e:
            scanned_failed_vms.append((target["ip"], target["name"]))
            print(f"Error connecting to {target['ip']}: {e}")
            continue
        finally:
            ssh.close()
    
    if high_usage_ips:
        email_body = f"<span style='color: red;'>檢測到高於磁碟使用率 {target_percent}% 的VM IP:<br>"
        for ip in high_usage_ips:
            print(ip)
            email_body += ip + "<br>"
        email_body += "</span>"
    else:
        email_body = f"<span style='color: green;'>未檢測到高於磁碟使用率 {target_percent}% 的VM<br></span>"
    print(email_body)

    if scanned_vms:
        email_body += f"已掃描VM:<br>"
        for vm in scanned_vms:
            print(vm)
            print(vm[0])
            email_body += f"{vm[0]} {vm[1]}<br>"

    if scanned_failed_vms:
        email_body += f"<span style='color: red;'>未掃描VM:<br>"
        for vm in scanned_failed_vms:
            print(vm)
            print(vm[0])
            email_body += f"{vm[0]} {vm[1]}<br>"
        email_body += "</span>"

    subject = "高磁碟使用率通知"
    brian_email = "brian_chiang@chief.com.tw"
    to_email = "brian_chiang@chief.com.tw, marco_li@chief.com.tw, aaron_lin@chief.com.tw, allen_yang@chief.com.tw"
    send_email(subject, email_body, to_email)

    endtime = time.time()
    deltatime = endtime - starttime
    print(f"time used: {round(deltatime, 1)}s")
