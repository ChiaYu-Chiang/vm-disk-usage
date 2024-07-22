import paramiko
import nmap
import socket


class SSHClient:
    def __init__(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self, ip, port, user, pwd):
        try:
            self.ssh.connect(ip, username=user, port=port, password=pwd)
            print("Connected successfully.")
        except paramiko.AuthenticationException:
            print(f"Error: Authentication failed for {ip}")
            raise
        except paramiko.SSHException as e:
            print(f"Error: SSH error for {ip}: {e}")
            raise
        except socket.timeout:
            print(f"Error: Connection timed out for {ip}")
            raise
        except Exception as e:
            print(f"Error: Unexpected error for {ip}: {e}")
            raise

    def execute_command(self, command, encoding):
        try:
            _, stdout, _ = self.ssh.exec_command(command)
            if stdout:
                output = stdout.read().decode(encoding)
                return output
            else:
                print("Error: Command execution failed.")
                return None
        except Exception as e:
            print(f"Error: {e}")
            return None

    def close(self):
        self.ssh.close()
        print("SSH connection closed.")


def scan_network(network):
    nm = nmap.PortScanner()
    print(f"Scanning network: {network}")
    nm.scan(hosts=network, arguments='-p 22 --open')
    live_hosts = nm.all_hosts()
    print(f"Scan result: {live_hosts}")
    return live_hosts

if __name__ == "__main__":
    network = '10.210.68.0/24'
    live_hosts = scan_network(network)
    default_target_info = {
        "name": "S3_HAPROXY",
        "port": 22,
        "user": "root",
        "pwd": "Chief+26576688@",
        "os": "linux"
    }
    targets = []
    for ip in live_hosts:
        target_info = default_target_info.copy()
        target_info["name"] = target_info["name"] + "_" + ip
        target_info["ip"] = ip
        targets.append(target_info)
    print(f"targets after ip scan: \n{targets}")
