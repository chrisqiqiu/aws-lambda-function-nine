
import json
import urllib.parse
import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
import re
import requests

print('Loading function')

s3 = boto3.client('s3')


def lambda_handler(event, context):

    try:

        print("Received event: " + json.dumps(event, indent=2))

        # Get the object from the event and show its content type
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(
            event['Records'][0]['s3']['object']['key'], encoding='utf-8')

        if not (key.endswith(".txt") or key.endswith(".csv")):
            return

        print(f"Downloading file s3://{bucket}/{key}")

        os.chdir("/tmp")

        print("working directory is " + os.getcwd())
        print("files in cwd are : " + str(os.listdir()))

        SENDER = "businessapplicationdevelopers@nine.com.au"

        s3.download_file(bucket, (re.search(r"(.*)/results", key).group(1) + "/email_config.json" if len(key.split("/")) >
                                  1 else "email_config.json"), "email_config.json")
        with open("email_config.json") as f:
            email_config = json.load(f)

        RECIPIENT = email_config["emails"]
        # AWS_REGION = "us-east-1"

        SUBJECT = "File landed on s3 bucket"

        if email_config.get("email_subject"):
            SUBJECT = SUBJECT+f" for {email_config.get('email_subject')}"

        BODY_TEXT = """File landed on s3 bucket
                Please find the result for {s3file} {{situation}}
                """.format(s3file=f"s3://{bucket}/{key}")

        BODY_HTML = """<html>
                        <head></head>
                        <body>
                        <h2>File landed on s3 bucket</h2>
                        <p>Please find the result for {s3file} {{situation}} .</p>
                        </body>
                    </html>
                """.format(s3file=f"s3://{bucket}/{key}")

        localfile = re.search(r'^(.*\/)?(.*)', key).group(2)

        if event['Records'][0]['s3']['object']['size'] >= 10*1024*1024:
            # url = s3.generate_presigned_url('get_object',
            #                         Params={
            #                             'Bucket': bucket,
            #                             'Key': key,
            #                             'ResponseContentDisposition' : f'attachment; filename="{localfile}"'
            #                         },
            #                         ExpiresIn=3600)

            # url = '{}/{}/{}'.format(s3.meta.endpoint_url, bucket, key)

            # situation = f"in url <a href='{url}'>{url}</a> as the result is over 10MB"
            situation = f" by <b>login your aws account</b> as the result is over 10MB"

            resp = send_mail(SENDER, RECIPIENT, SUBJECT, BODY_TEXT.format(
                situation=situation), BODY_HTML.format(situation=situation), attachments=None)

            print(str(resp))
        else:
            situation = "in attachement as the result is less than 10MB"

            s3.download_file(bucket, key, localfile)

            resp = send_mail(SENDER, RECIPIENT, SUBJECT, BODY_TEXT.format(
                situation=situation), BODY_HTML.format(situation=situation), attachments=[localfile])

            print(str(resp))

        print("working directory is " + os.getcwd())
        print("files in cwd are : " + str(os.listdir()))
        print("Email has been sent!")

    except Exception as e:
        print(str(e))
        slack_notification(str(e))


def create_multipart_message(sender: str, recipients: list, title: str, text: str = None, html: str = None, attachments: list = None) -> MIMEMultipart:
    """
    Creates a MIME multipart message object.
    Uses only the Python `email` standard library.

    :param sender: The sender.
    :param recipients: List of recipients. Needs to be a list, even if only one recipient.
    :param title: The title of the email.
    :param text: The text version of the email body (optional).
    :param html: The html version of the email body (optional).
    :param attachments: List of files to attach in the email.
    :return: A `MIMEMultipart` to be used to send the email.
    """
    multipart_content_subtype = 'alternative' if text and html else 'mixed'
    msg = MIMEMultipart(multipart_content_subtype)
    msg['Subject'] = title
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)

    # Record the MIME types of both parts - text/plain and text/html.
    # According to RFC 2046, the last part of a multipart message, in this case the HTML message, is best and preferred.
    if text:
        part = MIMEText(text, 'plain')
        msg.attach(part)
    if html:
        part = MIMEText(html, 'html')
        msg.attach(part)

    # Add attachments
    for attachment in attachments or []:
        with open(attachment, 'rb') as f:
            part = MIMEApplication(f.read())
            part.add_header('Content-Disposition', 'attachment',
                            filename=os.path.basename(attachment))
            msg.attach(part)

    return msg


def send_mail(sender: str, recipients: list, title: str, text: str = None, html: str = None, attachments: list = None) -> dict:
    """
    Send email to recipients. Sends one mail to all recipients.
    The sender needs to be a verified email in SES.
    """
    msg = create_multipart_message(
        sender, recipients, title, text, html, attachments)
    # Use your settings here
    ses_client = boto3.client('ses', region_name="us-east-1")
    return ses_client.send_raw_email(
        Source=sender,
        Destinations=recipients,
        RawMessage={'Data': msg.as_string()}
    )


def slack_notification(message):
    base_uri = "http://slack.datascience.ec2/postMessage"
    warningTemplateMessage = {
        "text": "<!here> Error: Athena runner email trigger {}  "}

    headers = {'Content-Type': 'application/json'}

    warningMessage = {}
    warningMessage['text'] = warningTemplateMessage['text'].format(
        str(message))

    resp = requests.post(base_uri, headers=headers,
                         data=json.dumps(warningMessage))

    return resp
