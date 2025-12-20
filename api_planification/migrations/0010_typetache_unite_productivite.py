# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_planification', '0009_seed_types_taches'),
    ]

    operations = [
        migrations.AddField(
            model_name='typetache',
            name='unite_productivite',
            field=models.CharField(
                blank=True,
                choices=[
                    ('m2', 'Mètres carrés (m²)'),
                    ('ml', 'Mètres linéaires (ml)'),
                    ('unite', 'Unités'),
                    ('cuvettes', 'Cuvettes'),
                    ('arbres', 'Arbres'),
                ],
                default='m2',
                max_length=20,
                verbose_name='Unité de productivité'
            ),
        ),
    ]
