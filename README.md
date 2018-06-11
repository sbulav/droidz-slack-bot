# Droidz slack bot
Simple slack bot able to execute commands and download videos

## Getting Started
To send command to bot, mention bot in DM, @droidz <command> <arguments>
+ do <bash command>            -   execute bash command
+ dl <title>  <url>            -   download video with a title from provided m3u8 url
+ mvc                          -   find and move all mp4 files to ext folder
+ clear                        -   clear /downloads/stream_video folder
+ list                         -   list files in /downloads/ext folder
+ help                         -   show help message

### Prerequisites

I'm using following python modules:
```
m3u8-downloader
youtube-dl
```

### Installing

Set your slack workplace token and environment variable.
Then clone and execute
```
git clone https://github.com/sbulav/droidz-slack-bot.git
```

### Starting as a systemd service

Copy python script to /usr/local/bin:
```
sudo cp droird-slack-bot.py /usr/local/bin/droidz-slack-bot.py
```
Amend service file and set up proper token.

Copy SystemD unit file to /etc/systemd/system:
```
sudo cp droidz-slack-bot.service /etc/systemd/system/
```

Load new unit file:
```
sudo systemctl daemon-reload
```

Start droidz-slack-bot and enable it if you'd like script to start at system boot:
```
sudo systemctl start droidz-slack-bot
sudo systemctl enable droidz-slack-bot
```

Monitor status and errors:

```
systemctl status droidz-slack-bot
```

