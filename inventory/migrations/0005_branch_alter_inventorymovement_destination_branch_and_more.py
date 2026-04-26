import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_auditlog'),
    ]

    operations = [
        migrations.CreateModel(
            name='Branch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('address', models.CharField(blank=True, max_length=255)),
            ],
            options={
                'verbose_name_plural': 'Branches',
                'ordering': ['name'],
            },
        ),
        migrations.RemoveField(
            model_name='inventorymovement',
            name='destination_branch',
        ),
        migrations.AddField(
            model_name='inventorymovement',
            name='destination_branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='movements', to='inventory.branch'),
        ),
        migrations.RemoveField(
            model_name='retailersales',
            name='branch',
        ),
        migrations.AddField(
            model_name='retailersales',
            name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sales', to='inventory.branch'),
        ),
    ]
