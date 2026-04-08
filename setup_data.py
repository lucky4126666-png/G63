from db import set_setting

# TEXT
set_setting("welcome_text", """欢迎 {name} 来到
{group}

⚠️注意：主动私聊你的都是骗子！
此用户是新币尊贵的VIP成员
""")

# BUTTON
set_setting("welcome_buttons", '[{"text":"新币供需","url":"https://t.me/xbkf"},{"text":"新币公群","url":"https://t.me/xbkf"}]')

print("✅ setup xong")
