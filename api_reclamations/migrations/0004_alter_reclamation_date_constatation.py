# Generated manually on 2025-12-27

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ('api_reclamations', '0003_reclamation_cloture_proposee_par_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reclamation',
            name='date_constatation',
            field=models.DateTimeField(default=timezone.now, verbose_name='Date de constatation'),
        ),
    ]
