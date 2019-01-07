#!/usr/bin/python
# encoding=utf-8
#
# Author: Sergey Bulavintsev
#--------------------------------------
from __future__ import unicode_literals
import os
import requests
import time
import re
import subprocess
import shutil
import youtube_dl
import thread
import sys
from slackclient import SlackClient

# Initialize variables
SLACK_TOKEN  = os.environ.get('SLACK_BOT_TOKEN')
slack_client = SlackClient(SLACK_TOKEN)
WORK_DIR     = os.environ.get('WORK_DIR')
OUT_DIR      = os.environ.get('OUT_DIR')
# droidbot's user ID in Slack: value is assigned after the bot starts up
droidbot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"

class MyLogger(object):
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        print(msg)

def my_hook(d):
    if d['status'] == 'finished':
        print "{0} successfully downloaded, elapsed: {1}, size: {2}".format(d['filename'],d['_elapsed_str'],d['_total_bytes_str'])


# Sends help message
def send_help(channel):
    help_response = """
*Usage:* @droidz <command> <arguments>, where commands are:
   *do* <bash command>            -   execute bash command
   *dl* <title>  <url>            -   download video with a title from provided m3u8 url
   *mvc*                          -   find and move all mp4 files to ext folder
   *clear*                        -   clear /downloads/stream_video folder
   *list*                         -   list files in /downloads/ext folder
"""

    send_message(help_response, channel)
    return True

# Move mp4 files from work directory to out directory
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

# List files in out directory
def list_files(root_src_dir):
    response = ""
    for src_dir, dirs, files in os.walk(root_src_dir):
        for file_ in files:
            src_file = os.path.join(src_dir, file_)
            response += "--> File: %s, %s MB \n\t" % (src_file, get_file_mb(src_file))
    send_message(response, channel)
    return True

# Get file size in MB
def get_file_mb(filename):
    try:
        filesize = str(os.path.getsize(filename) >> 20)
    except:
        filesize = '0'
        pass

    return filesize

# Send a message in Slack channel
def send_message(response, channel):
    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response
    )
    return True

# Parse a list of events, return tuple of command and channel if bot is DMed
def parse_bot_commands(slack_events):
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if "files" in event:
                url = event["files"][0]["url_private_download"]
                name = event["files"][0]["title"]
#                import pdb;pdb.set_trace()
                if name.endswith('.m3u'):
                    print "Downloading %s playlist from URL: %s" % (name, url)
                    outfile = download_file(url, name)
                    if os.path.exists(outfile):
                        message = "pl %s %s" % (name, outfile)
                    return message, event["channel"]

            if user_id == droidbot_id:
                print "Received Command: %s" % message
                return message, event["channel"]
    return None, None

# Finds direct message of this bot, return uid of whom mentioned
def parse_direct_mention(message_text):
    print "Found DM!"
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def execute_command(mycmd,channel):
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

def download_media(outfile, url, channel):
    download_start_response = """\
Download Started:
-->Filename: {0}
-->URL: {1}"""
    download_fin_response = """\
Download Completed:
-->Filename: {0}
-->Size: {1}"""

    response = download_start_response.format(outfile, url)
    print response
    send_message(response, channel)
    if not os.path.exists(WORK_DIR):
        os.makedirs(WORK_DIR)
    ydl_opts = {
        #'outtmpl': '/downloads/stream_video/title-%(id)s.%(ext)s'.format(WORK_DIR,title),
        'outtmpl': outfile,
        'verbose': True,
        'ignoreerrors': True,
        'format': 'mp4',
        'prefer_ffmpeg': True,
        'logger': MyLogger(),
        'progress_hooks': [my_hook],
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        result = ydl.download([url])
        response = download_fin_response.format(outfile, get_file_mb(outfile)+"MB")
        print response
        send_message(response, channel)
    return result

# download a file to a specific location
def download_file(url, local_filename):
    outfile = ''
    if not os.path.exists(WORK_DIR):
        os.makedirs(WORK_DIR)
    try:
        outfile = os.path.join(WORK_DIR, local_filename)
        print "Downloading file: %s" % outfile
        headers = {'Authorization': 'Bearer '+SLACK_TOKEN}
        r = requests.get(url, headers=headers)
        with open(outfile, 'w') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: f.write(chunk)
        print "File %s successfully downloaded" % outfile
    except Exception as e:
        response = "Download failed!!! Error:\t\n"
        response += "%s" % e
        return False

    return outfile

# Parse received command and execute it if its known
def handle_command(command, channel):
    # Default response is help text for the user
    default_response = "Not sure what you mean. Try *{}*.".format("help")

    response = None

    # Send help message if received command is help
    if command == "help":
        send_help(channel)
        return True

    # Execute bash command if received command do
    if command.startswith("do"):
        mycmd = command.split()[1::]
        if execute_command(mycmd, channel):
            return True
        else:
            return False

    # Move files from WORK_DIR to OUT_DIR
    if command == "mvc":
        response = "Moving .mp4 files from %s to %s" % (WORK_DIR, OUT_DIR)
        send_message(response, channel)
        try:
            move_mp4_files(WORK_DIR, OUT_DIR)
        except Exception as e:
            response = "Unable to move files, error:\t\n"
            response += "%s" % e
            send_message(response, channel)
            pass
            return False

    # List files in OUT_DIR
    if command == "list":
        list_files(OUT_DIR)
        return True

    # Clear WORK_DIR
    if command == "clear":
        shutil.rmtree(WORK_DIR)
        return True

    # Download URL using youtube-dl
    if command.startswith("dl"):
        try:
            cmd, title, url_pre = command.split()
            url = url_pre[1:-1] # Remove < and > symbols
            outfile = os.path.join(WORK_DIR, '{0}.mp4'.format(title))
            # Execute function in a thread - we don't care about it's success or status
            thread.start_new_thread(download_media,(outfile, url, channel))

        except Exception as e:
            print "Error: %s " % e
            pass
            return False
        return True

    # Download files from local playlist
    if command.startswith("pl"):
        command = "pl test.m3u {0}/test.m3u".format(WORK_DIR)
        cmd, title, local_file = command.split()
        send_message("Received PL command %s" % command, channel)
        urls = []
        number = 1
        
        # Unfortunately, download from batch file is not suppored
        # So I'm passing urls by one
        with open(local_file, "r") as f:
            for line in f.readlines():
                li = line.strip()
                if li.startswith("http"):
                    urls.append(li)
        #https://github.com/rg3/youtube-dl/blob/3e4cedf9e8cd3157df2457df7274d0c842421945/youtube_dl/YoutubeDL.py#L137-L312

        for url in urls:
            #WORK_DIR/title-number.ext
            outfile = '{0}/{1}-{2}.%(ext)s'.format(WORK_DIR,title.split('.')[0],str(number))
            print "Starting download of {0} from {1}".format(outfile,url)
            thread.start_new_thread(download_media,(outfile, url, channel))
            number+=1

        return True

    # If command is not recognized
    if not response:
        send_message(default_response, channel)
        return True

# Main function
if __name__ == "__main__":
    print "Initializing variables..."
    # Check working directories are initialized
    if not WORK_DIR or not OUT_DIR:
        raise Exception("Working directories arent't set!")
    else:
        print "Working directory = %s" % WORK_DIR
        print "Output  directory = %s" % OUT_DIR
    reload(sys)
    sys.setdefaultencoding('utf-8')

    if slack_client.rtm_connect(with_team_state=False,reconnect=True):
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
