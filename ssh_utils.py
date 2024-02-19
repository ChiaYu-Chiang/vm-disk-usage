import paramiko


class SSHClient:
    def __init__(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self, ip, port, user, pwd):
        try:
            self.ssh.connect(ip, username=user, port=port, password=pwd)
            print("Connected successfully.")
        except Exception as e:
            print(f"Error: {e}")

    def execute_command(self, command, encoding):
        try:
            _, stdout, _ = self.ssh.exec_command(command)
            output = stdout.read().decode(encoding)
            return output
        except Exception as e:
            print(f"Error: {e}")

    def close(self):
        self.ssh.close()
        print("SSH connection closed.")
