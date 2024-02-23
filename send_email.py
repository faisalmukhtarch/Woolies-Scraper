import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def send_email():
    message = Mail(
        from_email='faisalmukhtarch@gmail.com',
        to_emails='faisalmukhtarch@gmail.com',
        subject='Scheduled Script Results',
        html_content='<strong>Your script has completed its run.</strong>')
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        print(response.status_code)
        print(response.body)
        print(response.headers)
    except Exception as e:
        print(e.message)

if __name__ == "__main__":
    send_email()