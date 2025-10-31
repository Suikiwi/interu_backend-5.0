from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from datetime import timedelta
import uuid

from .models import (
    CalificacionChat, Estudiante, Administrador, Publicacion, 
    Chat, ChatParticipante, Mensaje, Reporte,
    TokenVerificacion, Perfil, Notificacion
)

class RegistroEstudianteSerializer(serializers.ModelSerializer):
    aceptar_politicas = serializers.BooleanField(write_only=True)

    class Meta:
        model = Estudiante
        fields = ['id_estudiante', 'email', 'contraseña', 'aceptar_politicas']
        extra_kwargs = {'contraseña': {'write_only': True}}

    def validate_email(self, value):
        if not value.endswith("@inacap.cl"):
            raise serializers.ValidationError("Debe usar un correo institucional válido.")
        return value

    def validate_contraseña(self, value):
        if len(value) < 8 or not any(c.isupper() for c in value) or not any(c.isdigit() for c in value):
            raise serializers.ValidationError("La contraseña debe tener al menos 8 caracteres, una mayúscula y un número.")
        return make_password(value)

    def validate_aceptar_politicas(self, value):
        if not value:
            raise serializers.ValidationError("Debe aceptar las políticas de uso para continuar.")
        return value

    def create(self, validated_data):
        validated_data.pop("aceptar_politicas")
        estudiante = Estudiante.objects.create(**validated_data, verificado=False)
        token = str(uuid.uuid4().hex)
        TokenVerificacion.objects.create(
            token=token,
            estudiante=estudiante,
            fecha_expiracion=timezone.now() + timedelta(hours=24)
        )
        return estudiante

class ActivarCuentaSerializer(serializers.Serializer):
    token = serializers.CharField()

class PublicacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publicacion
        fields = '__all__'
        read_only_fields = ('estudiante', 'fecha_creacion')

class ChatParticipanteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatParticipante
        fields = '__all__'


class MensajeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mensaje
        fields = '__all__'
        read_only_fields = ['id_mensaje', 'fecha', 'leido']


class CalificacionChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalificacionChat
        fields = '__all__'
        read_only_fields = ['id_calificacion', 'fecha']

    def validate_puntaje(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("El puntaje debe estar entre 1 y 5.")
        return value


class ChatSerializer(serializers.ModelSerializer):
    participantes = ChatParticipanteSerializer(many=True, read_only=True)
    mensajes = MensajeSerializer(many=True, read_only=True)

    class Meta:
        model = Chat
        fields = '__all__'


class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = '__all__'
        read_only_fields = ['id_notificacion', 'fecha']
        
class PerfilCompletoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Perfil
        fields = [
            'id_perfil',
            'nombre',
            'foto',
            'biografia',
            'habilidades_ofrecidas',
            'habilidades_buscadas',
        ]
        read_only_fields = ['id_perfil']

#-----------------------Reportes
class ReporteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reporte
        fields = '__all__'
        read_only_fields = ['estudiante', 'fecha', 'estado']
        

class ModerarReporteSerializer(serializers.ModelSerializer):
    accion = serializers.ChoiceField(choices=["aprobar", "rechazar", "eliminar"], write_only=True)

    class Meta:
        model = Reporte
        fields = ['id_reporte', 'accion']

    def update(self, instance, validated_data):
        accion = validated_data.pop("accion")
        if accion == "aprobar":
            instance.estado = 1
        elif accion == "rechazar":
            instance.estado = 2
        elif accion == "eliminar":
            instance.publicacion.estado = False
            instance.publicacion.save()
            instance.estado = 1
        instance.save()
        return instance
