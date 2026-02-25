import os
import re
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")

JOIN_TEXT = """🔥 Pros Team 입장 안내 🔥

1) Bitunix 공식 파트너 링크로 가입
2) KYC 인증 완료
3) UID를 이 봇에 제출

✅ 가입 링크
https://www.bitunix.com/register?vipCode=TeamPros

📌 UID는 Bitunix 프로필에서 확인 가능합니다.
UID 제출 후 확인되면 초대 링크를 발송합니다.
"""

UID_GUIDE = """✅ UID 제출 방법

아래 양식 그대로 보내주세요.

텔레그램 닉네임 :
거래소 : 비트유닉스
UID :
"""

FAQ_TEXT = """❓ 자주 묻는 질문

Q. UID 어디서 확인?
A. Bitunix 프로필에서 확인 가능합니다.

Q. 승인 시간?
A. 순차 확인 후 초대 링크 발송.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(JOIN_TEXT)
    await update.message.reply_text("UID 제출은 /uid 를 눌러주세요.")

async def uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(UID_GUIDE)

async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(FAQ_TEXT)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid_match = re.search(r"\b\d{6,12}\b", text)

    if uid_match:
        uid = uid_match.group()
        username = update.effective_user.username
        name = update.effective_user.full_name
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        print(f"[UID] {now} | @{username} | {name} | UID={uid}")

        await update.message.reply_text(
            f"✅ UID {uid} 접수 완료.\n운영진 확인 후 초대 링크 발송됩니다."
        )
        return

    await update.message.reply_text("입장 안내는 /start\nUID 제출은 /uid")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("uid", uid))
    app.add_handler(CommandHandler("faq", faq))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()

if __name__ == "__main__":
    main()
