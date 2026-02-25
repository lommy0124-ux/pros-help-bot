import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ====== ENV / IDS ======
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# 운영진 비공개 그룹(문의 + UID 승인 처리) Chat ID
ADMIN_CHAT_ID = -1003893914544

# 실제 초대할 메인 팀방 Chat ID
TEAM_CHAT_ID = -1003421664311

# 초대링크 설정
INVITE_EXPIRE_MINUTES = 30  # 만료 30분
INVITE_MEMBER_LIMIT = 1     # 1회용

# ====== DB (SQLite) ======
DB_PATH = "pros_bot.db"


def db_conn():
    return sqlite3.connect(DB_PATH)


def db_init():
    with db_conn() as con:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS uid_submissions (
                uid TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',   -- pending/approved/rejected
                decided_at TEXT
            )
            """
        )
        con.commit()


def upsert_uid(uid: str, user_id: int, username: str | None, full_name: str):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with db_conn() as con:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO uid_submissions(uid, user_id, username, full_name, created_at, status, decided_at)
            VALUES (?, ?, ?, ?, ?, 'pending', NULL)
            ON CONFLICT(uid) DO UPDATE SET
                user_id=excluded.user_id,
                username=excluded.username,
                full_name=excluded.full_name,
                created_at=excluded.created_at,
                status='pending',
                decided_at=NULL
            """,
            (uid, user_id, username, full_name, now),
        )
        con.commit()


def get_uid_row(uid: str):
    with db_conn() as con:
        cur = con.cursor()
        cur.execute(
            "SELECT uid, user_id, username, full_name, created_at, status, decided_at FROM uid_submissions WHERE uid=?",
            (uid,),
        )
        return cur.fetchone()


def set_status(uid: str, status: str):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with db_conn() as con:
        cur = con.cursor()
        cur.execute(
            "UPDATE uid_submissions SET status=?, decided_at=? WHERE uid=?",
            (status, now, uid),
        )
        con.commit()


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


# ====== MENU (order fixed) ======
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


# ====== HELPERS ======
def safe_username(user) -> str:
    return f"@{user.username}" if getattr(user, "username", None) else "(no username)"


def kst_now_str() -> str:
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")


def admin_uid_buttons(uid: str) -> InlineKeyboardMarkup:
    keyboard = [[
        InlineKeyboardButton("✅ 승인", callback_data=f"appr:{uid}"),
        InlineKeyboardButton("❌ 거절", callback_data=f"rej:{uid}"),
    ]]
    return InlineKeyboardMarkup(keyboard)


# ====== USER HANDLERS ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ✅ 그룹/슈퍼그룹에서는 조용히 (DM에서만 안내)
    if update.effective_chat.type != "private":
        return

    context.user_data.clear()
    await update.message.reply_text(START_TEXT, reply_markup=main_menu())


async def user_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    # ✅ 유저 메뉴 버튼은 DM에서만 반응
    if query.message.chat.type != "private":
        await query.answer("개인 채팅(DM)에서 이용해주세요.", show_alert=True)
        return

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
    # ✅ 그룹/슈퍼그룹에서는 어떤 텍스트에도 응답하지 않음 (스팸 방지)
    if update.effective_chat.type != "private":
        return

    mode = context.user_data.get("mode")
    text = (update.message.text or "").strip()
    user = update.effective_user

    # ---- UID mode ----
    if mode == "uid":
        uid_match = re.search(r"\b\d{6,12}\b", text)
        if not uid_match:
            await update.message.reply_text("UID는 6~12자리 숫자만 가능합니다.\n예) 12345678")
            return

        uid = uid_match.group()

        # DB 저장(pending)
        upsert_uid(uid, user.id, getattr(user, "username", None), user.full_name)

        # 유저 안내
        await update.message.reply_text(
            f"✅ UID {uid} 접수 완료.\n운영진 확인 후 초대 링크를 발송합니다."
        )

        # 운영진 그룹 알림 + 승인/거절 버튼
        admin_text = (
            "✅ [UID 접수]\n\n"
            f"시간: {kst_now_str()}\n"
            f"유저: {user.full_name} ({safe_username(user)})\n"
            f"유저링크: tg://user?id={user.id}\n"
            f"UserID: {user.id}\n"
            f"UID: {uid}"
        )

        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_text,
            reply_markup=admin_uid_buttons(uid),
        )

        context.user_data.clear()
        return

    # ---- Inquiry mode ----
    if mode == "inquiry":
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                "📩 [1:1 문의 접수]\n\n"
                f"시간: {kst_now_str()}\n"
                f"유저: {user.full_name} ({safe_username(user)})\n"
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

    # ---- Default ----
    await update.message.reply_text("메뉴는 /start 를 눌러 진행해주세요.")


# ====== ADMIN BUTTON HANDLER ======
async def admin_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""

    # 운영진 그룹에서만 작동
    if query.message.chat_id != ADMIN_CHAT_ID:
        await query.answer("운영진 전용 기능입니다.", show_alert=True)
        return

    # appr:UID / rej:UID
    if ":" not in data:
        await query.answer()
        return

    action, uid = data.split(":", 1)
    uid = uid.strip()

    row = get_uid_row(uid)
    if not row:
        await query.answer("UID 데이터를 찾을 수 없습니다.", show_alert=True)
        return

    _, user_id, username, full_name, created_at, status, decided_at = row

    if status in ("approved", "rejected"):
        await query.answer("이미 처리된 UID입니다.", show_alert=True)
        return

    await query.answer()  # 로딩 해제

    if action == "appr":
        # 1회용 초대링크 생성
        expire_dt = datetime.now(timezone.utc) + timedelta(minutes=INVITE_EXPIRE_MINUTES)
        expire_ts = int(expire_dt.timestamp())

        try:
            invite = await context.bot.create_chat_invite_link(
                chat_id=TEAM_CHAT_ID,
                expire_date=expire_ts,
                member_limit=INVITE_MEMBER_LIMIT,
            )
        except Exception:
            await query.edit_message_text(
                (query.message.text or "") + "\n\n❌ 초대링크 생성 실패(메인 팀방에서 봇 권한 확인 필요)."
            )
            return

        # 유저에게 DM 발송
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "✅ 승인 완료되었습니다.\n\n"
                    f"아래 링크로 입장해주세요. (1회용 / 만료 {INVITE_EXPIRE_MINUTES}분)\n"
                    f"{invite.invite_link}"
                ),
            )
        except Exception:
            await query.edit_message_text(
                (query.message.text or "")
                + "\n\n❌ 유저 DM 발송 실패(유저가 봇 차단/대화 미시작 가능)."
            )
            return

        set_status(uid, "approved")

        await query.edit_message_text(
            (query.message.text or "")
            + f"\n\n✅ 승인 완료\n- 대상: {full_name} ({('@'+username) if username else 'no username'})\n- UID: {uid}\n- 1회용 링크 DM 발송됨",
        )
        return

    if action == "rej":
        # 유저에게 보류 안내(선택)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ 승인 조건이 충족되지 않아 입장이 보류되었습니다.\n\n"
                    "확인 후 다시 UID 제출 부탁드립니다."
                ),
            )
        except Exception:
            pass

        set_status(uid, "rejected")

        await query.edit_message_text(
            (query.message.text or "")
            + f"\n\n❌ 거절 처리 완료\n- 대상: {full_name} ({('@'+username) if username else 'no username'})\n- UID: {uid}",
        )
        return


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN이 설정되지 않았습니다. Railway Variables에 BOT_TOKEN을 추가하세요.")

    db_init()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # /start (유저 메뉴 오픈) - DM에서만 동작
    app.add_handler(CommandHandler("start", start))

    # 유저 메뉴 버튼 - DM에서만 동작
    app.add_handler(
        CallbackQueryHandler(
            user_button_handler,
            pattern=r"^(join|uid|record|faq|inquiry|benefit)$",
        )
    )

    # 운영진 승인/거절 버튼 (운영진 그룹에서만 동작)
    app.add_handler(CallbackQueryHandler(admin_action_handler, pattern=r"^(appr:|rej:)"))

    # 유저 텍스트 처리(UID 제출/문의) - DM에서만 동작
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()


if __name__ == "__main__":
    main()
