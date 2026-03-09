from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_reading_item'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Document',
        ),
    ]
