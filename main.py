import os
import re
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ====== ENV ======
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Railway Variables에 설정
ADMIN_CHAT_ID = -1003893914544           # 운영진 비공개 그룹 Chat ID

# ====== TEXTS ======
START_TEXT = """🔥 Pros Team 공식 입장 안내 🔥

시장에는 수많은 정보가 떠다니지만,
실제로 수익을 만들어내는 구조는 제한된 공간에서 공유됩니다.

Pros Team은 단순 커뮤니티가 아닙니다.
실전 트레이더들이 전략을 설계하고,
자본의 흐름을 준비하는 공간입니다.

아래 메뉴에서 진행해주세요.
"""

JOIN_TEXT = """🚀 Pros Team 입장 방법

1️⃣ 공식 파트너 링크로 Bitunix 가입
2️⃣ KYC 인증 완료
3️⃣ UID 제출
4️⃣ 확인 후 팀 내부 공간 초대

⚠ 반드시 아래 링크로 가입해야 혜택 적용

https://www.bitunix.com/register?vipCode=TeamPros
"""

UID_TEXT = """📝 UID 제출

UID 숫자만 보내주세요. (6~12자리)
예) 12345678

확인 후 초대 링크를 발송합니다.
"""

RECORD_TEXT = """📊 팀방 내역

Pros는 실전 매매 기반으로 운영됩니다.
최근 전략 및 기록은 아래에서 확인 가능합니다:

https://pros.qshop.ai/strategy
"""

FAQ_TEXT = """❓ FAQ

Q. 기존 계정도 가능?
A. 파트너 링크 가입 계정만 적용됩니다.

Q. KYC 필수인가요?
A. 네. KYC 완료 계정만 승인됩니다.

Q. 승인 시간은?
A. 순차 확인 후 초대 링크 발송됩니다.

Q. 활동이 없으면?
A. 유령 계정은 정리될 수 있습니다.
"""

INQUIRY_PROMPT_TEXT = """👨‍💻 1:1 문의

문의 내용을 그대로 입력해주세요.
운영진에게 직접 전달됩니다.
"""

BENEFIT_TEXT = """💎 Bitunix 혜택

1️⃣ Task Center → 시작 후 입금
   (해외 거래소 경유 필요)

2️⃣ 첫 입금 50% 증정금 이벤트

3️⃣ 캠페인 / Task Center 추가 이벤트 참여

파트너 경로 가입자에게만 적용됩니다.
"""


# ====== MENU (order fixed as user requested) ======
def main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🚀 입장 방법", callback_data="join")],
        [InlineKeyboardButton("📝 UID 제출", callback_data="uid")],
        [InlineKeyboardButton("📊 팀방 내역", callback_data="record")],
        [InlineKeyboardButton("❓ FAQ", callback_data="faq")],
        [InlineKeyboardButton("👨‍💻 1:1 문의", callback_data="inquiry")],
        [InlineKeyboardButton("💎 Bitunix 혜택", callback_data="benefit")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ====== HANDLERS ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(START_TEXT, reply_markup=main_menu())


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "join":
        context.user_data.pop("mode", None)
        await query.edit_message_text(JOIN_TEXT, reply_markup=main_menu())

    elif data == "uid":
        context.user_data["mode"] = "uid"
        await query.edit_message_text(UID_TEXT, reply_markup=main_menu())

    elif data == "record":
        context.user_data.pop("mode", None)
        await query.edit_message_text(RECORD_TEXT, reply_markup=main_menu())

    elif data == "faq":
        context.user_data.pop("mode", None)
        await query.edit_message_text(FAQ_TEXT, reply_markup=main_menu())

    elif data == "inquiry":
        context.user_data["mode"] = "inquiry"
        await query.edit_message_text(INQUIRY_PROMPT_TEXT, reply_markup=main_menu())

    elif data == "benefit":
        context.user_data.pop("mode", None)
        await query.edit_message_text(BENEFIT_TEXT, reply_markup=main_menu())


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    text = (update.message.text or "").strip()
    user = update.effective_user

    # ---- UID mode ----
    if mode == "uid":
        uid_match = re.search(r"\b\d{6,12}\b", text)
        if uid_match:
            uid = uid_match.group()
            now = datetime.now().strftime("%Y-%m-%d %H:%M")

            # 운영진 그룹으로 전달
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    "✅ [UID 접수]\n\n"
                    f"시간: {now}\n"
                    f"유저: {user.full_name} (@{user.username})\n"
                    f"유저링크: tg://user?id={user.id}\n"
                    f"UserID: {user.id}\n"
                    f"UID: {uid}"
                ),
            )

            await update.message.reply_text(
                f"✅ UID {uid} 접수 완료.\n운영진 확인 후 초대 링크를 발송합니다."
            )
            context.user_data.clear()
            return

        # UID 모드인데 숫자 형식이 아닌 경우
        await update.message.reply_text("UID는 숫자만 보내주세요. (6~12자리)\n예) 12345678")
        return

    # ---- Inquiry mode (free input) ----
    if mode == "inquiry":
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                "📩 [1:1 문의 접수]\n\n"
                f"시간: {now}\n"
                f"유저: {user.full_name} (@{user.username})\n"
                f"유저링크: tg://user?id={user.id}\n"
                f"UserID: {user.id}\n\n"
                "문의내용:\n"
                f"{text}"
            ),
        )

        await update.message.reply_text(
            "✅ 문의가 정상적으로 접수되었습니다.\n\n"
            "내용 확인 후\n"
            "운영진이 1:1로 개별 연락을 드릴 예정입니다."
        )
        context.user_data.clear()
        return

    # ---- Default (no mode) ----
    await update.message.reply_text("메뉴는 /start 를 눌러 진행해주세요.")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN이 설정되지 않았습니다. Railway Variables에 BOT_TOKEN을 추가하세요.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()


if __name__ == "__main__":
    main()
