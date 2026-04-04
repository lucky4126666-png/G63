import time

users = {}
muted = {}

def is_spam(uid):
    now = time.time()

    if uid in muted and now < muted[uid]:
        return True

    arr = users.get(uid, [])
    arr = [t for t in arr if now - t < 10]

    arr.append(now)
    users[uid] = arr

    if len(arr) > 5:
        muted[uid] = now + 60
        return True

    return False
