#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
Usage:
...
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""
from uuid import uuid4
import re
from telegram import InlineQueryResultArticle, ParseMode, \
    InputTextMessageContent, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, InlineQueryHandler, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram.ext.dispatcher import run_async
import logging
import requests
# https://github.com/martinblech/xmltodict
import xmltodict
import csv
import os.path
import math
import simplejson as json
from datetime import datetime
# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


with open('./tram_station_location.js', "rb+") as f:
    data = f.read()	
python_dict = json.loads(data.decode())


@run_async
def start(bot, update):
    keyboard = []
    keyboard.append([InlineKeyboardButton(text = "Eastbound", callback_data='eastbound')])
    keyboard.append([InlineKeyboardButton(text = "Westbound", callback_data='westbound')])
    keyboard.append([InlineKeyboardButton(text = "東行", callback_data='chinese eastbound')])
    keyboard.append([InlineKeyboardButton(text = "西行", callback_data='chinese westbound')])
    keyboard.append([InlineKeyboardButton(text = "Close", callback_data='close')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Traveling Direction:\n行駛方向:', reply_markup=reply_markup)
	
	
@run_async
def help(bot, update):
    update.message.reply_text('Help!')
    	
		
@run_async
def search(bot, update):
    help(bot, update)
	
	
@run_async
def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"' % (update, error))


@run_async
def callback(bot, update):
    query = update.callback_query
    try:
        if ("close" in query.data):
            bot.editMessageText(text="Ding Ding!",
			                    chat_id=query.message.chat_id,
			                    message_id=query.message.message_id)
        elif "eastloc" in query.data or "westloc" in query.data:
            sendlocation(bot,update, dir=query.data)
        elif "eastbound" in query.data or "westbound" in query.data:
            tramstation(bot, update,
			            lang='Stops Name in Chinese' if ("chinese" in query.data) else 'Stops Name',
			            dir='Eastbound' if ("east" in query.data) else 'Westbound')
        else:
            checktime(bot, update)
    except Exception as e:
        print(str(e))

@run_async
def checktime(bot, update):
    query = update.callback_query
    stopcode, name, lang = query.data.upper().split(",")
    stop = {'stop_code': stopcode}   
    r = requests.get("http://hktramways.com/nextTram/geteat.php?", params=stop)
    content = r.content.decode('utf8')
    ordered_dict = xmltodict.parse(content)  
    data = ordered_dict.get('root').get('metadata')			
    text = name + "\n"
    for element in data:
        arrive_in_second = int(element.get('@arrive_in_second'))
        if "CHINESE" in lang:
            text += "往%s\n"%element.get('@tram_dest_tc')
        else:
            text += "To %s\n"%element.get('@tram_dest_en')
        if arrive_in_second > 0:
            text += "%d:%02d\n" % divmod(arrive_in_second, 60)
        else:
            text += "己至\n" if "CHINESE" in lang.upper() else "Arrived\n"
    update_time = datetime.now().strftime('%H:%M:%S')
    text += "<i>[查詢時間: %s]</i>"%update_time if "CHINESE" in lang.upper() else\
	        "<i>[Enquire Time: %s]</i>"%update_time
    bot.editMessageText(text=text,
			chat_id=query.message.chat_id,
			message_id=query.message.message_id,
			reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
				'重新查詢' if "CHINESE" in lang.upper() else 'Refresh'
				,callback_data=query.data)]]),
			parse_mode="HTML")			
		
@run_async
def tramstation(bot, update, lang, dir):
    keyboard = []
    query = update.callback_query
    with open('tram_stops.csv') as file:
        reader = csv.DictReader(file)
        try:
            for row in reader:
                if dir == row['Traveling Direction']:
                    keyboard.append([InlineKeyboardButton(text= row[lang],
                                     callback_data=",".join(
									 [row['Stops Code'],row[lang], lang]) )])
        except KeyError: 
            print( 'ERROR: key not found!')
    keyboard.append([InlineKeyboardButton(text = "Close", 
	                                      callback_data='close')])
    bot.editMessageText(text='站:' if "CHINESE" in lang.upper() else 'Station:',
                        chat_id=query.message.chat_id,
                        message_id=query.message.message_id,
						reply_markup=InlineKeyboardMarkup(keyboard))	


						
# https://en.wikipedia.org/wiki/Haversine_formula
#give latitudes, longitudes of two places and calculate the distance between
def distance_from_lat_lon_to_m(lat1, lon1, lat2, lon2):
    R = 6371.0
    dLat = float(lat2) * math.pi / 180.0 - float(lat1) * math.pi / 180.0
    dLon = float(lon2) * math.pi / 180.0 - float(lon1) * math.pi / 180.0
    a = math.sin(float(dLat) / 2.0) * math.sin(float(dLat) / 2.0) + math.cos(float(lat1) * math.pi / 180.0) * math.cos(
        float(lat2) * math.pi / 180.0) * math.sin(float(dLon) / 2.0) * math.sin(float(dLon) / 2.0);
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = R * c
    return str(round(d * 1000))

	
@run_async
def location(bot, update):
    lat = update.message.location.latitude
    lon = update.message.location.longitude    
    keyboard = []
    keyboard.append([InlineKeyboardButton(text = "東行/Eastbound", 
	                                      callback_data='eastloc,%s,%s'%(lat, lon))])
    keyboard.append([InlineKeyboardButton(text = "西行/Westbound", 
	                                      callback_data='westloc,%s,%s'%(lat, lon))])										  
    update.message.reply_text(text='方向:\nDirection:',
						reply_markup=InlineKeyboardMarkup(keyboard))								  
										  
@run_async
def sendlocation(bot, update, dir):
    dir, lat, lon = dir.split(',')
    nearest = 99
    namehk = ""
    nameen = ""
    for element in python_dict:
        if element.get('bound') == re.sub('\loc$', '', dir):
            distance = math.sqrt(float(element.get('latitude') - float(lat)) ** 2\
                               + float(element.get('longitude') - float(lon)) ** 2)
            if nearest > distance:
                nearest = distance
                namehk, nameen = element.get('name').get('zh_hk'), element.get('name').get('en')
                nlat, nlon = element.get('latitude'), element.get('longitude')
    bot.sendLocation(chat_id=update.callback_query.message.chat_id,latitude=nlat, longitude=nlon)
    distance = distance_from_lat_lon_to_m(lat, lon, nlat, nlon)
    text = 'Stop "%s" is %sm away\n'%(nameen, distance)
    text +='車站「%s」在%s米外\n'%(namehk, distance)
    bot.editMessageText(text=text,\
	                    chat_id=update.callback_query.message.chat_id,\
                        message_id=update.callback_query.message.message_id)

	
def main():
    
    # Create the Updater and pass it your bot's token.
    updater = Updater("407172807:AAFvKq5g18qiflgvQY7fCfd5CXQce3ADaGA")

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # commands
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(MessageHandler(Filters.text, search))
    dp.add_handler(MessageHandler(Filters.location, location))
    #dp.add_handler(InlineQueryHandler(inlinequery))
    dp.add_handler(CallbackQueryHandler(callback))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Block until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()