import datetime
from django.utils import timezone
from django.core.exceptions import ValidationError

class PoliticaContraseña:
    def __init__(self, min_longitud=8, requiere_mayuscula=True, requiere_numero=True):
        self.min_longitud = min_longitud
        self.requiere_mayuscula = requiere_mayuscula
        self.requiere_numero = requiere_numero

    def validar(self, contraseña: str):
        if len(contraseña) < self.min_longitud:
            raise ValidationError("La contraseña es demasiado corta")
        if self.requiere_mayuscula and not any(c.isupper() for c in contraseña):
            raise ValidationError("Debe contener al menos una mayúscula")
        if self.requiere_numero and not any(c.isdigit() for c in contraseña):
            raise ValidationError("Debe contener al menos un número")
        return True


class TemporizadorAutoEliminacion:
    """
    Permite verificar si un objeto está listo para ser eliminado
    según su fecha de creación y un umbral de días.
    """
    def __init__(self, dias=30):
        self.dias = dias

    def esta_listo_para_eliminar(self, fecha_creacion):
        return timezone.now() - fecha_creacion > datetime.timedelta(days=self.dias)


class SoftDeleteService:
    """
    Implementa borrado lógico (soft delete) para entidades como Publicación.
    """
    @staticmethod
    def desactivar(objeto):
        objeto.estado = False
        objeto.save()

    @staticmethod
    def reactivar(objeto):
        objeto.estado = True
        objeto.save()
