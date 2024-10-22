import asyncio
import logging
from datetime import date
from os import getenv

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.utils.markdown import hbold
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import ValidationError

from models import (
    NoteComersResponse, AllStudentsResponse, FacultyResponse,
    StudentDetail, StudentChat, Faculty, AbsentGroup
)

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = getenv('BOT_TOKEN')
BACKEND_API_URL = getenv('BACKEND_URL')
MONGO_URI = getenv('MONGO_URL')
NOTIFICATION_TIME = "18:00"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = AsyncIOMotorClient(MONGO_URI)
db = client['attendance_db']
student_chats_collection = db['student_chats']
students_collection = db['students']

scheduler = AsyncIOScheduler()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Пожалуйста, введите student_id:")


@dp.message()
async def handle_student_id(message: types.Message):
    try:
        student_id = int(message.text)
        chat_id = message.chat.id

        student_data = await students_collection.find_one({'hemis_id': student_id})
        if student_data:
            #student = StudentDetail(**student_data)
            existing_chat = await student_chats_collection.find_one({'student_id': student_id})
            if existing_chat:
                await message.answer(
                    "Этот Student ID уже зарегистрирован. Если это ошибка, пожалуйста, свяжитесь с администратором.")
            else:
                student_chat = StudentChat(student_id=student_id, chat_id=chat_id)
                await student_chats_collection.insert_one(student_chat.dict())
                await message.answer(
                    "Student ID успешно зарегистрирован. Вы будете получать уведомления о посещаемости.")
        else:
            await message.answer("Неверный Student ID. Пожалуйста, попробуйте снова.")
    except ValueError:
        await message.answer("Пожалуйста, введите корректный Student ID (целое число).")


async def load_students_to_mongodb():
    try:
        async with aiohttp.ClientSession() as session:
            current_page = 1
            while True:
                async with session.get(f'{BACKEND_API_URL}/api/main/students?page={current_page}') as response:
                    if response.status == 200:
                        data = await response.json()
                        try:
                            validated_data = AllStudentsResponse(**data)
                            for student in validated_data.data:
                                await students_collection.update_one(
                                    {'hemis_id': student.hemis_id},
                                    {'$set': student.dict()},
                                    upsert=True
                                )
                            logging.info(f"Processed page {current_page} of {validated_data.pagination.last_page}")
                            if current_page >= validated_data.pagination.last_page:
                                break
                            current_page += 1
                        except ValidationError as e:
                            logging.error(f"Validation error in all_students response: {e}")
                            break
                    else:
                        logging.error(f"Error loading student data: HTTP {response.status}")
                        break
        logging.info("Finished loading all student data to MongoDB")
    except Exception as e:
        logging.error(f"Error loading student data to MongoDB: {e}")


async def get_faculties() -> list[Faculty]:
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{BACKEND_API_URL}/api/faculties') as response:
            if response.status == 200:
                data = await response.json()
                faculty_response = FacultyResponse(**data)
                return faculty_response.data
    return []


async def get_late_comers(faculty_id: int, day: str) -> list[AbsentGroup]:
    async with aiohttp.ClientSession() as session:
        current_page = 1
        all_late_comers = []
        while True:
            url = f'{BACKEND_API_URL}/api/main/note_comers?faculty_id={faculty_id}&day={day}&page={current_page}'
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    try:
                        validated_data = NoteComersResponse(**data)
                        all_late_comers.extend(validated_data.data)
                        if current_page >= validated_data.pagination.last_page:
                            break
                        current_page += 1
                    except ValidationError as e:
                        logging.error(f"Validation error in note_comers response: {e}")
                        break
                else:
                    logging.error(f"Error fetching late comers: HTTP {response.status}")
                    break
    return all_late_comers


async def send_attendance_notifications():
    try:
        today = date.today().isoformat()
        faculties = await get_faculties()

        for faculty in faculties:
            late_comers = await get_late_comers(faculty.id, today)
            #print(late_comers)
            for group in late_comers:
                #print(group.total_students, group.group_name)
                for student in group.absent_students:
                    #print(student)
                    student_chat = await student_chats_collection.find_one({'student_id': student.hemis_id})
                    if student_chat:
                        chat_id = student_chat['chat_id']
                        message = (
                            f"Уведомление о посещаемости:\n"
                            f"Ваш ребенок (Student ID: {hbold(student.name)}) не пришел(ла) в университет сегодня.\n"
                            f"Дата: {hbold(today)}"
                        )
                        await bot.send_message(
                            chat_id=chat_id,
                            text=message,
                            parse_mode="HTML"
                        )

            logging.info(f"Processed notifications for faculty: {faculty.faculty}")

        logging.info("Finished sending all attendance notifications")
    except Exception as e:
        logging.error(f"Error sending attendance notifications: {e}")


async def on_startup(dispatcher):
    await load_students_to_mongodb()
    hour, minute = map(int, NOTIFICATION_TIME.split(":"))
    scheduler.add_job(send_attendance_notifications, CronTrigger(hour=hour, minute=minute))
    scheduler.start()


async def main():
    dp.startup.register(on_startup)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
