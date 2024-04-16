import os
from dotenv import load_dotenv

from flask import Flask, request, abort

from linebot.v3 import (
    WebhookHandler
)

from linebot.v3.exceptions import (
    InvalidSignatureError
)

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)

from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

from openai import OpenAI

import json

# 加載 .env 文件中的環境變數
load_dotenv()

ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
OPPA = os.environ.get('OPPA')

app = Flask(__name__)

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event, dest):

    user_text = event.message.text
    client = OpenAI()
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": ("你現在扮演一位生活助手。尊稱使用者為\"我的女王\"，態度阿諛奉承。"
                                            "回答盡量在150字以內。中文回答只能使用正體中文與台灣地區用語，"
                                            "不可使用簡體字。如果使用者心情不好或身體不舒服，安慰使用者，並說"
                                            "\"別難過，我和" + OPPA + "哥說，請他帶您吃些好東西\"。")},
            {"role": "user", "content": user_text}
        ]
    )

    msg = completion.choices[0].message.content

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=msg)]
            )
        )

if __name__ == "__main__":
    app.run()