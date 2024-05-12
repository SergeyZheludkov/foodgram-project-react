import csv

from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from recipes.models import Ingredient

# full list (more than 2000 items)
DIR_DATA = Path(__file__).resolve().parent.parent.parent.parent.parent.parent / 'data'

# shorten list (50 items)
# DIR_DATA = Path(__file__).resolve().parent

DATA = (
    ('ingredients.csv', Ingredient, ['name', 'measurement_unit']),
)


class Command(BaseCommand):

    def load_obj(self, filename, obj, fields):
        try:
            with open(f'{DIR_DATA}/{filename}', encoding='utf-8') as file_data:
                reader = csv.reader(file_data)
                for row in reader:
                    object_value = {
                        key: value for key, value in zip(fields, row)
                    }
                    try:
                        obj.objects.update_or_create(**object_value)
                    except IntegrityError:
                        self.stdout.write(f'Файл {filename} не корректные '
                                          f'данные: {object_value} для '
                                          f'{obj.__name__}')

        except FileNotFoundError:
            self.stdout.write(f'Файл {filename} невозможно открыть')
        except Exception as e:
            self.stdout.write(f'Ошибка {e} при работе с файлом {filename}')
        self.stdout.write(f'Файл {filename} загружен')

    def handle(self, *args, **kwargs):
        for filename, obj, fields in DATA:
            if kwargs['erase']:
                obj.objects.all().delete()
            self.load_obj(filename, obj, fields)

    def add_arguments(self, parser):
        parser.add_argument(
            '-e',
            '--erase',
            action='store_true',
            default=False,
            help='Очистить таблицу перед загрузкой'
        )
