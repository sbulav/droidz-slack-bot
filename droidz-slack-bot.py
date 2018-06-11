#!/usr/bin/python
#encoding=utf-8
import requests
import os
import time
import re
import subprocess
import shutil
import logging
from slackclient import SlackClient
from m3u8_downloader import download_m3u8_url

# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
# droidbot's user ID in Slack: value is assigned after the bot starts up
droidbot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"
WORK_DIR = "/downloads/stream_video"
OUT_DIR  = "/downloads/ext/"

def move_mp4_files(root_src_dir, dst_dir):
    for src_dir, dirs, files in os.walk(root_src_dir):
        for file_ in files:
            src_file = os.path.join(src_dir, file_)
            dst_file = os.path.join(dst_dir, file_)
            if file_.endswith(".mp4") and not os.path.exists(dst_file):
                shutil.move(src_file,dst_dir)
                response = "--> File moved to: %s, %s MB" % (dst_file, get_file_mb(dst_file))
                print response
                send_message(response, channel)
    send_message("All found .mp4 files moved!", channel)
    return True

def list_files(root_src_dir):
    response = ""
    for src_dir, dirs, files in os.walk(root_src_dir):
        for file_ in files:
            src_file = os.path.join(src_dir, file_)
            response += "--> File: %s, %s MB \n\t" % (src_file, get_file_mb(src_file))
    send_message(response, channel)
    return True


def get_file_mb(filename):
    return str(os.path.getsize(filename) >> 20)


def send_message(response, channel):
    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response
    )
    return True

def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == droidbot_id:
                print "RECEIVED COMMAND: %s" % message
                return message, event["channel"]
    return None, None

def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    print "Found DM!"
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def handle_command(command, channel):
    """
        Executes bot command if the command is known
    """
    # Default response is help text for the user
    default_response = "Not sure what you mean. Try *{}*.".format("help")
    help_response = """
*Usage:* @droidz <command> <arguments>, where commands are:
   *do* <bash command>            -   execute bash command
   *dl* <title>  <url>            -   download video with a title from provided m3u8 url
   *mvc*                          -   find and move all mp4 files to ext folder
   *clear*                        -   clear /downloads/stream_video folder
   *list*                         -   list files in /downloads/ext folder
"""

    # Finds and executes the given command, filling in response
    response = None
    if command == "help":
        send_message(help_response, channel)
        return True

    if command.startswith("do"):
        mycmd = command.split()[1::]
        response = "Executing command: %s \t\n" % mycmd
        send_message(response, channel)
        try:
            process = subprocess.Popen(mycmd, stdout=subprocess.PIPE)
            output, error = process.communicate()
            response = "Command output: \t\n"
            response += output
            send_message(response, channel)
            return True
        except Exception as e:
            response = "Unable to execute command, error:\t\n"
            response += "%s" % e
            send_message(response, channel)
            pass
            return False

    if command == "mvc":
        response = "Moving .mp4 files from /downloads/stream_video to /downloads/ext/"
        send_message(response, channel)
        try:
            move_mp4_files(WORK_DIR, OUT_DIR)
        except Exception as e:
            response = "Unable to move files, error:\t\n"
            response += "%s" % e
            send_message(response, channel)
            pass
            return False

    if command == "list":
        list_files(OUT_DIR)
        return True


    if command.startswith("dl"):
        myarr = command.split()
        if len(myarr) == 3:
            title = command.split()[1]
            m3u8_url = command.split()[2][1:-1]
            work_dir_title = WORK_DIR + "/" + title + "/"
            expected_file = os.path.join(os.path.abspath(os.path.dirname(work_dir_title)),"outputs",title + ".mp4")
            response = "Download started:\t\n -->title:  %s\t\n -->url:  %s\t\n -->out_dir:  %s\t\n" % (title, m3u8_url, work_dir_title)
            send_message(response, channel)
            print response

            if not os.path.exists(work_dir_title):
                os.makedirs(work_dir_title)
            if os.path.exists(expected_file):
                os.remove(expected_file)
            try:
                with requests.Session() as sess:
                    download_m3u8_url(m3u8_url, sess, title=title, out_path=work_dir_title)
                    response = "Download %s completed:\t\n ---> Path:  %s \t\n ---> Size: %s" % (title, expected_file, get_file_mb(expected_file) + "MB")
                send_message(response, channel)
                return True
            except Exception as e:
                response = "Unable to download file, error:\t\n"
                response += "%s" % e
                send_message(response, channel)
                pass
                return False

        else:
            response = "Wrong number of arguments!\t\n"
            response += "To download m3u8 videos, use '@droidz dl <title> <url>'"
            send_message(response, channel)
            return False
    if not response:
        send_message(default_response, channel)
        return True


if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Droidz Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        droidbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            command, channel = parse_bot_commands(slack_client.rtm_read())
            if command:
                handle_command(command, channel)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
