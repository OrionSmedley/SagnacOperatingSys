import smtplib, os
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
try:
    from email.Encoders import encode_base64
except ImportError:
    from email.encoders import encode_base64

def send_gmail(username, password, send_to, subject, text, files=[]):
    """Sends main through Gmail server"""
    assert type(send_to) is list
    assert type(files) is list
    
    send_from = username + '@gmail.com'
    
    msg = MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    
    msg.attach(MIMEText(text))
    
    for f in files:
        part = MIMEBase('application', "octet-stream")
        part.set_payload(open(f, 'rb').read())
        encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(f))
        msg.attach(part)
        
    server = smtplib.SMTP('smtp.gmail.com:587')
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(username, password)
    server.sendmail(send_from, send_to, msg.as_string())
    server.close()

"""Example    
send_gmail('cornell.fmr', 'getingetin', ['clj72@cornell.edu'], 'FMR Measurement Finished',
           'The FMR measurement has finished.', ['data.csv'])
"""
