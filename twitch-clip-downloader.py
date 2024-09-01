import os
import argparse
import datetime
from dotenv import load_dotenv
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
import logging
import yt_dlp

logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s")
logger = logging.getLogger(__file__)

# uncomment these for requests debug
# import sys
# log = logging.getLogger('requests_oauthlib')
# log.addHandler(logging.StreamHandler(sys.stdout))
# log.setLevel(logging.DEBUG)

load_dotenv()
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
if client_id is None or client_secret is None:
    logger.error(
        "You must set CLIENT_ID and CLIENT_SECRET in environment variables or in a .env file. See README."
    )
    exit(1)

parser = argparse.ArgumentParser(description="Twitch clip downloader")
parser.add_argument(
    "-c", "--channel", help="Name of the channel to get clips from", required=True
)
parser.add_argument(
    "-d",
    "--date",
    type=datetime.date.fromisoformat,
    help="Date from which to start downloading clips formatted YYYY-MM-DD. (default: one week ago (%(default)s))",
    default=datetime.date.today() - datetime.timedelta(days=7),
)
parser.add_argument(
    "-o", "--output_dir", help="Directory to output clips. (default: %(default)s)"
)
parser.add_argument(
    "-a",
    "--all",
    help="Download all clips instead of only featured clips",
    action="store_true",
)
parser.add_argument(
    "-f",
    "--filename",
    help="Set the desired filename using tokens %%d=date(iso), %%u=date(us), %%a=author, %%t=title, %%v=views, %%g=game. (default: %(default)s)",
    default="%d - %a - %t",
)
parser.add_argument(
    "-m",
    "--metadata",
    help="Set metadata artist field using same tokens as above. (default: %(default)s)",
    default="Clipped by %a %u",
)
parser.add_argument("-l", "--log", help="Set log level", default="info")
args = parser.parse_args()
logger.setLevel(args.log.upper())

token_url = "https://id.twitch.tv/oauth2/token"
users_url = "https://api.twitch.tv/helix/users"
clips_url = "https://api.twitch.tv/helix/clips"
games_url = "https://api.twitch.tv/helix/games"

client = BackendApplicationClient(client_id=client_id)
oauth = OAuth2Session(client=client)
oauth_token = oauth.fetch_token(
    token_url=token_url,
    client_secret=client_secret,
    force_querystring=True,
    include_client_id=True,
)

headers = {"Client-Id": client_id}

res = oauth.get(url=users_url, headers=headers, params={"login": args.channel})
# print(res.json())
broadcaster_id = res.json()["data"][0]["id"]

params = {
    "broadcaster_id": broadcaster_id,
    "started_at": f"{args.date}T00:00:00Z",
    "ended_at": f"{datetime.date.today() + datetime.timedelta(days=1)}T00:00:00Z",
}
if not args.all:
    params["is_featured"] = True

clip_list = []
more = True
while more == True:
    res = oauth.get(url=clips_url, headers=headers, params=params)
    # print(json.dumps(res.json(), indent=4))

    if not res.json()["data"] and not clip_list:
        logger.warning(f"No clips found after {args.date}")
        exit()

    clip_list += res.json()["data"]

    if res.json()["pagination"]:
        params["after"] = res.json()["pagination"]["cursor"]
    else:
        more = False

logger.info(f"Retrieved {len(clip_list)} clips")

game_list = {}
if "%g" in args.filename or "%g" in args.metadata:
    for clip in clip_list:
        game_list[clip["game_id"]] = ""
    res = oauth.get(
        url=games_url + "?id=" + "&id=".join(list(game_list)), headers=headers
    )
    # print(res.json())
    if not res.json()["data"]:
        logger.error("No games found")
        exit()

    for game in res.json()["data"]:
        game_list[game["id"]] = game["name"]

for clip in clip_list:
    logger.info("---------------------------------------------------")
    logger.info(
        f"title: {clip['title']}, created_at: {clip['created_at']}, creator_name: {clip['creator_name']}, url: {clip['url']}"
    )
    created_at = datetime.datetime.strptime(clip["created_at"], "%Y-%m-%dT%H:%M:%SZ")
    filename = str(args.filename)
    artist = str(args.metadata)
    tokens = {
        "%d": created_at.strftime("%Y-%m-%d"),
        "%u": created_at.strftime("%#m/%#d/%Y"),
        "%a": clip["creator_name"],
        "%t": clip["title"],
        "%v": str(clip["view_count"]),
        "%g": game_list.get(clip["game_id"], ""),
    }
    for token in tokens:
        filename = filename.replace(token, tokens[token])
        artist = artist.replace(token, tokens[token])

    filename += ".mp4"
    invalid_chars = '\\/:*?"<>|'
    filename = "".join(c for c in filename if c not in invalid_chars)
    logger.debug(f"filename: {filename}")

    target_file = os.path.join(args.output_dir, filename)
    logger.debug("target file: " + target_file)

    dir = os.path.dirname(target_file)
    if not os.path.isdir(dir):
        os.makedirs(dir)
    if os.path.exists(target_file):
        logger.info("Already exists")
        continue

    # download clip
    url = clip["url"]
    ydl_opts = {
        "format": "mp4",
        "logger": logger,
        "outtmpl": {"default": filename},
        "paths": {"home": args.output_dir},
        "postprocessors": [
            {
                "actions": [
                    (
                        yt_dlp.postprocessor.metadataparser.MetadataParserPP.interpretter,
                        artist,
                        "%(artist)s",
                    ),
                ],
                "key": "MetadataParser",
                "when": "pre_process",
            },
            {
                "add_metadata": True,
                "key": "FFmpegMetadata",
            },
            {"key": "FFmpegConcat", "only_multi_video": True, "when": "playlist"},
        ],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(url)
        logger.info("Downloaded")
