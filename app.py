import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
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

ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
VINAY = os.environ.get('VINAY')
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
def handle_message(event):
    # Enter a context with an instance of the API client
    with ApiClient(configuration) as api_client:
        # Create an instance of the API class
        line_bot_api = MessagingApi(api_client)

        user_id = event.source.user_id                  
        try:
            profile = line_bot_api.get_profile(user_id)
            user_name = profile.display_name
        except Exception as e:
            print("Exception when calling MessagingApi->get_profile: %s\n" % e)
        
        user_text = event.message.text

        client = OpenAI()   
        if user_name == VINAY:
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": ("你現在是一位生活助手。尊稱使用者「尊貴的陛下」、「聖上」"
                                                    "或「我的女王」。回答盡量在100字以內。中文回答只能使用"
                                                    "正體中文與台灣地區用語，不可使用簡體字。使用者有一位"
                                                    "好朋友「" + OPPA + "」。如果使用者心情不好"
                                                    "或身體不舒服，安慰使用者，並替「" + OPPA + "」代為轉達關心。")},
                    {"role": "user", "content": user_text}
                ]
            )
        else:
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "你是一位有用的助手。"},
                    {"role": "user", "content": user_text}
                ]
            )
        
        msg = completion.choices[0].message.content

        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=msg)]
            )
        )


if __name__ == "__main__":
    app.run()
