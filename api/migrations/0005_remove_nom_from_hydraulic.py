# Generated manually to remove nom field from hydraulic equipment models
# These models use marque/type instead of nom

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_aspersion_nom_ballon_nom_canalisation_nom_clapet_nom_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='aspersion',
            name='nom',
        ),
        migrations.RemoveField(
            model_name='ballon',
            name='nom',
        ),
        migrations.RemoveField(
            model_name='canalisation',
            name='nom',
        ),
        migrations.RemoveField(
            model_name='clapet',
            name='nom',
        ),
        migrations.RemoveField(
            model_name='goutte',
            name='nom',
        ),
        migrations.RemoveField(
            model_name='vanne',
            name='nom',
        ),
    ]
