import csv

from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from recipes.models import Ingredient

# full list (more than 2000 items)
DIR_DATA_0 = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
DIR_DATA = DIR_DATA_0 / 'data'

DATA = (
    ('ingredients.csv', Ingredient, ('name', 'measurement_unit')),
)


class Command(BaseCommand):

    def load_obj(self, filename, model, fields):
        try:
            file_data = open(f'{DIR_DATA}/{filename}', encoding='utf-8')
        except FileNotFoundError:
            self.stdout.write(f'Файл {filename} невозможно открыть')
            return None

        reader = csv.reader(file_data)
        for row in reader:
            object_value = {
                key: value for key, value in zip(fields, row)
            }
            try:
                model.objects.update_or_create(**object_value)
            except IntegrityError:
                self.stdout.write(
                    f'Файл {filename} не корректные данные: {object_value}'
                    f'для {model.__name__}')
                return None

        self.stdout.write(f'Файл {filename} загружен')

    def handle(self, *args, **kwargs):
        for filename, model, fields in DATA:
            if kwargs.get('erase'):
                model.objects.all().delete()
            self.load_obj(filename, model, fields)

    def add_arguments(self, parser):
        parser.add_argument(
            '-e',
            '--erase',
            action='store_true',
            default=False,
            help='Очистить таблицу перед загрузкой'
        )
