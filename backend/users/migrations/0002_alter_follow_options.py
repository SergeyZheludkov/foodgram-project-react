# Generated by Django 3.2 on 2024-06-04 08:26

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='follow',
            options={'default_related_name': 'follows', 'verbose_name': 'подписчик', 'verbose_name_plural': 'Подписчики'},
        ),
    ]
