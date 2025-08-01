import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate

# 郵件設定
email_settings = {
    "host": "mail.chief-tech.net",
    "port": 25,
    "use_tls": False,
    "username": "",  # 請填入您的郵件帳號
    "password": "",  # 請填入您的郵件密碼
    "from_email": "VM Disk Usage <vmdiskusage@mail.chief-tech.net>",
}


def send_email(subject, body, to_email):
    # 建立郵件
    msg = MIMEMultipart()
    msg["From"] = email_settings["from_email"]
    msg["To"] = to_email
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = subject

    # 添加郵件內容
    msg.attach(MIMEText(body, "html"))
    
    to_email_list = to_email.split(", ")

    # 連接郵件伺服器並發送郵件
    try:
        server = smtplib.SMTP(email_settings["host"], email_settings["port"])
        if email_settings["use_tls"]:
            server.starttls()
        if email_settings["username"] and email_settings["password"]:
            server.login(email_settings["username"], email_settings["password"])
        server.sendmail(email_settings["from_email"], to_email_list, msg.as_string())
        print("郵件已成功發送")
    except Exception as e:
        print(f"郵件發送失敗: {e}")
    finally:
        server.quit()


if __name__ == "__main__":
    # 使用範例
    subject = "test-高磁碟使用率通知"
    body = "請確認是否能成功收到這封信"
    html_body = """
    <span style="color: red;">這邊應該要紅字</span>
    這邊應該要黑字
    """
    to_email = "example@example.com.tw"  # 收件人的郵件地址
    send_email(subject, html_body, to_email)
