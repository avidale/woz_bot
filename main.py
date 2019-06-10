#!/usr/bin/python
# -*- coding: utf-8 -*-
import argparse
import os
import telebot

from pymongo import MongoClient
from flask import Flask, request

TOKEN = os.environ['TOKEN']
bot = telebot.TeleBot(TOKEN)

server = Flask(__name__)
TELEBOT_URL = 'telebot_webhook/'
BASE_URL = 'https://wizard-of-oz-bot.herokuapp.com/'

MONGO_URL = os.environ.get('MONGODB_URI')
mongo_client = MongoClient(MONGO_URL)
mongo_db = mongo_client.get_default_database()

mongo_config = mongo_db.get_collection('config')
mongo_messages = mongo_db.get_collection('messages')


@server.route("/" + TELEBOT_URL)
def web_hook():
    bot.remove_webhook()
    bot.set_webhook(url=BASE_URL + TELEBOT_URL + TOKEN)
    return "!", 200


@server.route("/wakeup/")
def wake_up():
    web_hook()
    return "Маам, ну ещё пять минуточек!", 200


@bot.message_handler(func=lambda message: True, content_types=['document', 'text', 'photo'])
def process_message(msg):
    text = msg.text
    woz = mongo_config.find_one({'key': 'wizard'})
    if woz is not None:
        woz_uid = woz['uid']
    else:
        woz_uid = None
    if len(text) >= 3 and text == os.environ.get('WOZ_PASSWORD'):
        mongo_config.update_one(
            {'key': 'wizard'}, 
            {'$set': {'uid': msg.from_user.id, 'username': msg.from_user.username}}, 
            upsert=True
        )
        bot.reply_to(msg, 'Вы подобрали пароль! Теперь вы - волшебник изумрудного города!')
    elif msg.from_user.id == woz_uid:
        if msg.reply_to_message is not None:
            message_from_bot = msg.reply_to_message
            original_message = mongo_messages.find_one({'copy_id': message_from_bot.message_id})
            if original_message is None:
                bot.reply_to(msg, 'Исходное сообщение не найдено!')
            else:
                bot.send_message(
                    original_message['original_uid'], text, reply_to_message_id=original_message['original_id']
                )
                report = 'Ваше сообщение было отправлено @{}'.format(original_message.get('original_username'))
                bot.reply_to(msg, report)
        else:
            bot.reply_to(msg, 'Да, вы по-прежнему волшебник. Ждите сообщений от меня и отвечайте на них!')
    elif woz_uid is None:
        bot.reply_to(msg, 'Я пока не настроен, подождите, пожалуйста')
    else:
        new_text = 'Сообщение от @{}:\n_____\n{}'.format(msg.from_user.username, text)
        result = bot.send_message(woz_uid, new_text)
        mongo_messages.insert_one(
            {
                'copy_id': result.message_id, 'original_id': msg.message_id,
                'original_uid': msg.from_user.id, 'original_username': msg.from_user.username
            }
        )


@server.route('/' + TELEBOT_URL + TOKEN, methods=['POST'])
def get_message():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200


parser = argparse.ArgumentParser(description='Run the bot')
parser.add_argument('--poll', action='store_true')


def main():
    args = parser.parse_args()
    if args.poll:
        bot.remove_webhook()
        bot.polling()
    else:
        web_hook()
        server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))


if __name__ == '__main__':
    main()
