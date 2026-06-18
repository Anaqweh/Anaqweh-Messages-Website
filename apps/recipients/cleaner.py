import re

DISPOSABLE_DOMAINS = {
    'tempmail.com','temp-mail.org','guerrillamail.com','10minutemail.com',
    'mailinator.com','throwaway.email','yopmail.com','trashmail.com',
    'sharklasers.com','getnada.com','maildrop.cc','fakeinbox.com',
}
COMMON_TYPOS = {
    'gmial.com':'gmail.com','gmai.com':'gmail.com','gmail.co':'gmail.com',
    'gmal.com':'gmail.com','gmaill.com':'gmail.com','hotmial.com':'hotmail.com',
    'hotmai.com':'hotmail.com','yahooo.com':'yahoo.com','yaho.com':'yahoo.com',
    'outlok.com':'outlook.com','outloo.com':'outlook.com',
}
EMAIL_RE = re.compile(r'^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$')

def analyze_email(email):
    email = str(email).strip().lower()
    if not EMAIL_RE.match(email):
        return {'status':'invalid','reason':'صيغة غير صحيحة','suggestion':None}
    domain = email.split('@')[1]
    if domain in DISPOSABLE_DOMAINS:
        return {'status':'disposable','reason':'إيميل مؤقت/وهمي','suggestion':None}
    if domain in COMMON_TYPOS:
        corrected = email.split('@')[0]+'@'+COMMON_TYPOS[domain]
        return {'status':'typo','reason':'خطأ إملائي في النطاق','suggestion':corrected}
    return {'status':'valid','reason':'صحيح','suggestion':None}
