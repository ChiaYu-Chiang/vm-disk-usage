# vm-disk-usage

This repository used to get remote vm's disk usage information with ssh.

## How to install

1. Clone this repository.

- clone with SSH

```shell
git clone git@github.com:ChiaYu-Chiang/vm-disk-usage.git
```

- clone with HTTPS

```shell
git clone https://github.com/ChiaYu-Chiang/vm-disk-usage.git
```

2. Enable virtual environment.

```shell
cd vm-disk-usage
```

- windows

```shell
python -m venv .venv
.venv\Scripts\activate
```

- linux

```shell
python -m venv .venv
source .venv/bin/activate
```

3. Install required packages.

```shell
pip install -r requirements.txt
```

4. Prepare your vm's login account.

```shell
touch targets.json
```

```json
[
  {
    "ip": "XXX.XXX.XXX.XXX",
    "user": "root",
    "pwd": "password",
    "port": 22,
    "os": "linux"
  },
  {
    "ip": "XXX.XXX.XXX.XXX",
    "user": "Administrator",
    "pwd": "password",
    "port": 22,
    "os": "windows"
  }
]
```

## Make sure ssh service is active

- windows

```shell
# checkout status
Get-Service sshd
# turn on ssh service
Start-Service sshd
```

- Linux

```shell
# checkout status
sudo systemctl status ssh
# turn on ssh service
sudo systemctl start ssh
```

## How to use

- excute python file.

```shell
python main.py
```

- excute script file.

```shell
bash ./check_vm_disk_usage.sh
```

```shell
.\check_vm_disk_usage.bat
```
