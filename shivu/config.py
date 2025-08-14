class Config(object):
    LOGGER = True

    # Get this value from my.telegram.org/apps
    OWNER_ID = "6449644059"
    sudo_users = "6449644059", "6449644059"
    GROUP_ID = -1002655697240
    TOKEN = "7460131022:AAHL-h2HZ4LVUq9y-5nNsWNWxTfye8pStkA"
    mongo_url = "mongodb+srv://skvsmdarman335s:Starzplay225s@cluster0.7ezycjy.mongodb.net/?retryWrites=true&w=majority"
    PHOTO_URL = ["https://telegra.ph/file/b925c3985f0f325e62e17.jpg", "https://telegra.ph/file/4211fb191383d895dab9d.jpg"]
    SUPPORT_CHAT = "Collect_em_support"
    UPDATE_CHAT = "OsaragiUpdates"
    BOT_USERNAME = "Osaragi_X_Catcher_Bot"
    CHARA_CHANNEL_ID = "-1002856079592"
    api_id = 26928136
    api_hash = "1056cd55e07175e8f1bcbb356f4bb8a9"

    
class Production(Config):
    LOGGER = True


class Development(Config):
    LOGGER = True
