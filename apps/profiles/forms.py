"""Formulários da app `profiles` — validação de normalização de pesos.

Garante, na edição via admin/UI, que a soma dos pesos nominais não seja nula
(previne divisão por zero no motor de normalização runtime).
"""
from django import forms

from .models import ProfileConfig


class ProfileConfigForm(forms.ModelForm):
    class Meta:
        model = ProfileConfig
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        profile = self.instance
        if profile and profile.pk:
            total_weight = sum(axis.weight for axis in profile.axes.all())
            if total_weight <= 0:
                raise forms.ValidationError(
                    "A soma dos pesos dos eixos vinculados a este perfil deve ser maior que zero."
                )
        return cleaned
