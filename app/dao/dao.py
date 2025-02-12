from datetime import date, datetime
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.dao.base import BaseDAO
from app.dao.models import User, TimeSlot, Table, Booking


class UserDAO(BaseDAO[User]):
    model = User


class TimeSlotUserDAO(BaseDAO[TimeSlot]):
    model = TimeSlot


class TableDAO(BaseDAO[Table]):
    model = Table


class BookingDAO(BaseDAO[Booking]):
    model = Booking

    async def check_available_bookings(self,
                                       table_id: int,
                                       booking_date: date,
                                       time_slot_id: int):
        """Проверяет наличие существующих броней для стола на указанную дату и временной слот."""
        try:
            query = select(self.model).filter_by(
                table_id=table_id,
                date=booking_date,
                time_slot_id=time_slot_id
            )
            result = await self._session.execute(query)

            # Если результатов нет, стол свободен
            if not result.scalars().all():
                return True

            # Проверяем статус существующих бронирований
            for booking in result.scalars().all():
                if booking.status == "booked":
                    return False  # Стол занят

                # Для других статусов считаем стол свободным
                continue
            # Если все брони имеют неактивные статусы
            return True

        except SQLAlchemyError as e:
            logger.error(f"Ошибка при проверке доступности брони: {e}")

    async def get_available_time_slots(self, table_id: int, booking_date: date):
        """Получает список доступных временных слотов для стола на указанную дату."""
        try:
            # Получаем все брони для данного стола и даты
            bookings_query = select(self.model).filter_by(
                table_id=table_id,
                date=booking_date
            )
            bookings_result = await self._session.execute(bookings_query)
            # Составляем набор занятых слотов (только с активными бронями)
            booked_slots = {booking.time_slot_id for booking in bookings_result.scalars().all() if
                            booking.status == "booked"}
            # Получаем все доступные слоты, исключая занятые
            available_slots_query = select(TimeSlot).filter(
                ~TimeSlot.id.in_(booked_slots)
            )
            available_slots_result = await self._session.execute(available_slots_query)
            return available_slots_result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении доступных временных слотов: {e}")

    async def get_bookings_with_details(self, user_id: int):
        """
        Получает список всех бронирований пользователя с полной информацией о столике и временном слоте.

        :param user_id: ID пользователя, брони которого нужно получить.
        :return: Список объектов Booking с загруженными данными о столе и времени.
        """
        try:
            query = select(self.model).options(
                joinedload(self.model.table),
                joinedload(self.model.time_slot)
            ).filter_by(user_id=user_id)
            result = await self._session.execute(query)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении бронирований с деталями: {e}")
            return []

    async def complete_past_bookings(self):
        """
        Обновляет статус бронирований на 'completed', если дата и время бронирования уже прошли.
        """
        try:
            # Получаем текущее время
            now = datetime.now()
            subquery = select(TimeSlot.start_time).where(TimeSlot.id == self.model.time_slot_id).scalar_subquery()
            query = select(Booking.id).where(
                Booking.date < now.date(),
                self.model.status == "booked"
            ).union_all(
                select(Booking.id).where(
                    self.model.date == now.date(),
                    subquery < now.time(),
                    self.model.status == "booked"
                )
            )

            # Выполняем запрос и получаем id бронирований, которые нужно обновить
            result = await self._session.execute(query)
            booking_ids_to_update = result.scalars().all()

            if booking_ids_to_update:
                # Формируем запрос на обновление статуса бронирований
                update_query = update(Booking).where(
                    Booking.id.in_(booking_ids_to_update)
                ).values(status="completed")

                # Выполняем запрос на обновление
                await self._session.execute(update_query)

                # Подтверждаем изменения
                await self._session.commit()

                logger.info(f"Обновлен статус для {len(booking_ids_to_update)} бронирований на 'completed'")
            else:
                logger.info("Нет бронирований для обновления статуса.")

        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении статуса бронирований: {e}")
            await self._session.rollback()