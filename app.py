import os
import sqlite3
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent, TextMessageContent
)
from openai import OpenAI

load_dotenv()

ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
TAKESHI = os.environ.get('TAKESHI')
VINAY = os.environ.get('VINAY')
NICK_TAKESHI = os.environ.get('NICK_TAKESHI')
NICK_VINAY = os.environ.get('NICK_VINAY')

app = Flask(__name__)

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        source_type, user_id, user_text = get_message_info(event)

        user_name = get_user_profile(line_bot_api, event, source_type, user_id)
        if user_name:
            msg = process_message(source_type, user_name, user_text)
            if msg:
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=msg)]
                    )
                )
            else:
                return
        else:
            print("Failed to obtain user profile.")


def get_message_info(event):
    source_type = event.source.type
    user_id = event.source.user_id
    user_text = event.message.text
    return source_type, user_id, user_text


def get_user_profile(line_bot_api, event, source_type, user_id):
    try:
        if source_type == 'group':
            profile = line_bot_api.get_group_member_profile(event.source.group_id, user_id)
        elif source_type == 'user':
            profile = line_bot_api.get_profile(user_id)
        else:
            print("Unexpected event.source.type: " + source_type)
            return None
        return profile.display_name
    except Exception as e:
        print(f"Exception when calling MessagingApi->get_profile: {e}")
        return None


def process_message(source_type, user_name, user_text):
    if source_type == 'group':
        prefix = '，'
        if user_text.startswith(prefix):
            user_text = user_text.strip(prefix)
        else:
            return None

        system_responses = {
            VINAY: f"你是一位生活助手，稱呼使用者「{NICK_VINAY}」，"
                   "回答應以像職場後輩對前輩的態度回應使用者:"
                   "尊敬的、理解的、信任的。中文使用正體中文字，勿使用簡體字。"
                   "回答長度不要超過100個字。",
            TAKESHI: f"你是一位生活助手，稱呼使用者「{NICK_TAKESHI}」，"
                    "回答應以像粉絲對偶像的態度回應使用者:"
                    "崇拜的、敬佩的、支持的。中文使用正體中文字，勿使用簡體字。"
                    "回答長度不要超過100個字.",
            'default': "你是一位生活助手，回應使用者使用正體中文字，"
                       "勿使用簡體字。回答長度不要超過100個字。"
        }
        system_response = system_responses.get(user_name, system_responses['default'])

        try:
            client = OpenAI()
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_response},
                    {"role": "user", "content": user_text}
                ]
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"Exception when calling OpenAI API: {e}")
            return "抱歉，處理您的請求時出現了問題。請稍後再試。"
    elif source_type == 'user':
        if user_name == VINAY:
            try:
                database_name = 'dialogues.db'
                conn = connect_to_database(database_name)
                cur = conn.cursor()
                create_dialogues_table(cur)

                insert_question(cur, user_text)

                dialogues = retrieve_dialogues(cur)
                msg = openai_chat(dialogues)

                insert_answer(cur, msg)

                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                app.logger.error("An error occurred while processing the dialogue: " + str(e))
                return ""
        else:
            msg = user_text       
        return msg


def connect_to_database(database_name):
    return sqlite3.connect(database_name)


def create_dialogues_table(cur):
    try:
        cur.execute('''CREATE TABLE IF NOT EXISTS dialogues (
                        num INTEGER PRIMARY KEY AUTOINCREMENT,
                        role TEXT,
                        content TEXT
                        )''')
        if cur.execute('''SELECT COUNT(*) FROM dialogues''').fetchone()[0] == 0:
            cur.execute('''INSERT INTO dialogues (role, content) VALUES (?, ?)''',
                        ('system', (
                            f"你是一位生活助手，稱呼使用者「我尊貴的{VINAY}女王」，"
                            "回答應以像男公關對女恩客百般討好的態度回應使用者："
                            "殷勤的、諂媚的、關懷備至的。中文使用正體中文字，勿使用簡體字。"
                            "回答長度不要超過100個字。")
                        )
                        )
    except Exception as e:
        app.logger.error("An error occurred while creating the dialogues table: " + str(e))


def insert_question(cur, question):
    try:
        cur.execute('''INSERT INTO dialogues (role, content) VALUES (?, ?)''', ('user', question))
    except Exception as e:
        app.logger.error("An error occurred while inserting a question: " + str(e))


def insert_answer(cur, answer):
    try:
        cur.execute('''INSERT INTO dialogues (role, content) VALUES (?, ?)''', ('assistant', answer))
    except Exception as e:
        app.logger.error("An error occurred while inserting an answer: " + str(e))


def retrieve_dialogues(cur):
    try:
        total_records = cur.execute('''SELECT COUNT(*) FROM dialogues''').fetchone()[0]
        if total_records > 7:
            if total_records > 11:
                keep_first_and_last(cur)
            cur.execute('''SELECT * FROM dialogues LIMIT 1''')
            first_row = cur.fetchone()
            dialogues = [{'role': first_row[1], 'content': first_row[2]}]
            cur.execute('''SELECT * FROM dialogues ORDER BY num DESC LIMIT 7''')
            last_seven_rows = cur.fetchall()[::-1]
            for row in last_seven_rows:
                dialogues.append({'role': row[1], 'content': row[2]})
        else:
            cur.execute('''SELECT * FROM dialogues ORDER BY num''')
            dialogues = [{'role': row[1], 'content': row[2]} for row in cur.fetchall()]
        return dialogues
    except Exception as e:
        app.logger.error("An error occurred while retrieving dialogues: " + str(e))
        return []


def openai_chat(dialogues):
    try:
        client = OpenAI()
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=dialogues
        )
        msg = completion.choices[0].message.content
        return msg
    except Exception as e:
        app.logger.error("An error occurred while chatting with OpenAI: " + str(e))
        return ""


def keep_first_and_last(cur):
    try:
        cur.execute('''SELECT num FROM dialogues LIMIT 1''')
        first_row_id = cur.fetchone()[0]
        cur.execute('''SELECT num FROM dialogues ORDER BY num DESC LIMIT 7''')
        last_seven_ids = [row[0] for row in cur.fetchall()]
        cur.execute('''DELETE FROM dialogues WHERE num NOT IN (?, ?, ?, ?, ?, ?, ?, ?)''', (first_row_id, *last_seven_ids))
    except Exception as e:
        app.logger.error("An error occurred while keeping the first and last records: " + str(e))


if __name__ == "__main__":
    app.run()
