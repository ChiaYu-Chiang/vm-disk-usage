import json
import time
from ssh_utils import SSHClient, scan_network
from parser_utils import parse_linux_output, parse_windows_output
from sendmail import send_email
import socket, paramiko


def read_and_process_file(file_path):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        targets = data.get("targets", [])
        scanned_vms = data.get("scanned_vms", [])
        scanned_failed_vms = data.get("scanned_failed_vms", [])
        high_usage_ips = data.get("high_usage_ips", [])
    except Exception as e:
        print(f"Error reading or processing file: {e}")

if __name__ == "__main__":
    starttime = time.time()

    # 設定磁碟使用率警告閾值
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
 
    # 讀取堡壘網掃描的結果
    file_path = r"scanned_intranet\data.json"
    read_and_process_file(file_path)
    
    network = "10.210.68.0/24"
    live_hosts = scan_network(network)
    
    # 將掃描到的活躍主機添加到列表
    for ip in live_hosts:
        target_info = default_target_info.copy()
        target_info["ip"] = ip
        targets.append(target_info)
    print(f"targets after ip scan: \n{targets}")
    
    # 從JSON文件中讀取額外的目標主機
    with open("targets.json") as json_file:
    # with open("waf_target.json") as json_file:
        json_targets = json.load(json_file)
        targets.extend(json_targets)
    
    ssh = SSHClient()

    # 定義不同操作系統的檢查命令和解析函數
    command_and_parser = {
        "linux": ("df /", parse_linux_output),
        "windows": (
            'powershell -Command "Get-CimInstance -ClassName Win32_logicalDisk -Filter "DriveType=3" | Select-Object -Property DeviceID, Size, FreeSpace | Format-Table -AutoSize"',
            parse_windows_output,
        ),
    }

    for target in targets:
        # if target["os"] == "windows":
        #     scanned_failed_vms.append((target["ip"], target["name"]))
        #     print("skip this windows target.")
        #     continue
        try:
            # 嘗試SSH連接到目標主機
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
    
    # 生成郵件內容
    email_body = f"<span>總數: {len(targets)} 已掃描: {len(scanned_vms)} 未掃描: {len(scanned_failed_vms)}<br></span>"
    if high_usage_ips:
        email_body += f"<span style='color: red;'>檢測到高於磁碟使用率 {target_percent}% 的VM IP:<br>"
        for ip in high_usage_ips:
            print(ip)
            email_body += ip + "<br>"
        email_body += "</span>"
    else:
        email_body += f"<span style='color: green;'>未檢測到高於磁碟使用率 {target_percent}% 的VM<br></span>"
    print(email_body)

    # 添加已掃描VM的信息
    if scanned_vms:
        email_body += f"已掃描VM:<br>"
        for vm in scanned_vms:
            print(vm)
            print(vm[0])
            email_body += f"{vm[0]} {vm[1]}<br>"

    # 添加掃描失敗VM的信息
    if scanned_failed_vms:
        email_body += f"<span style='color: red;'>未掃描VM:<br>"
        for vm in scanned_failed_vms:
            print(vm)
            print(vm[0])
            email_body += f"{vm[0]} {vm[1]}<br>"
        email_body += "</span>"

    # 發送郵件通知
    subject = "高磁碟使用率通知"
    brian_email = "brian_chiang@chief.com.tw"
    to_email = "brian_chiang@chief.com.tw, marco_li@chief.com.tw, aaron_lin@chief.com.tw, allen_yang@chief.com.tw"
    send_email(subject, email_body, to_email)

    endtime = time.time()
    deltatime = endtime - starttime
    print(f"time used: {round(deltatime, 1)}s")
