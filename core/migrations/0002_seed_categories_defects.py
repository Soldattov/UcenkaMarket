from django.db import migrations


def seed(apps, schema_editor):
    Category = apps.get_model('core', 'Category')
    DefectType = apps.get_model('core', 'DefectType')
    for name, slug in (
        ('Электроника', 'elektronika'),
        ('Бытовая техника', 'bytovaya-tehnika'),
        ('Мебель', 'mebel'),
    ):
        Category.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'is_active': True},
        )
    for name in (
        'Царапина',
        'Маленькая царапина',
        'Повреждена упаковка',
    ):
        DefectType.objects.get_or_create(
            name=name,
            defaults={'description': '', 'is_active': True},
        )


def unseed(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
