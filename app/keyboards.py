from aiogram.utils.keyboard import InlineKeyboardBuilder

def main():
    k=InlineKeyboardBuilder()
    k.button(text="✂️ Записаться",callback_data="book")
    k.button(text="📅 Мои записи",callback_data="mine")
    k.adjust(1); return k.as_markup()

def cancel(bid):
    k=InlineKeyboardBuilder(); k.button(text="❌ Отменить",callback_data=f"cancel:{bid}")
    k.button(text="🔄 Перенести",callback_data=f"move:{bid}")
    return k.as_markup()
