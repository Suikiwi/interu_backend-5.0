from django.db import models
import uuid
import secrets
    #-----------------------Estudiantes y Administradores
class Estudiante(models.Model):
    id_estudiante = models.AutoField(primary_key=True)
    email = models.EmailField(unique=True)
    contraseña = models.CharField(max_length=128)
    verificado = models.BooleanField(default=False)
    api_key = models.CharField(max_length=100, unique=True, blank=True, null=True)
    es_admin = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = f"api_{uuid.uuid4().hex}"
        super().save(*args, **kwargs)

class Administrador(models.Model):
    id_administrador = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    email = models.EmailField(max_length=320, unique=True)
    contraseña = models.CharField(max_length=255)
    api_key = models.CharField(max_length=100, unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.api_key:
            while True:
                key = secrets.token_hex(16)
                if not Administrador.objects.filter(api_key=key).exists():
                    self.api_key = key
                    break
        super().save(*args, **kwargs)
        
#-----------------------Publicaciones y Calificaciones
class Publicacion(models.Model):
    id_publicacion = models.AutoField(primary_key=True)
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    habilidad = models.IntegerField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    estado = models.BooleanField(default=True)
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)
    
# ---------- calificaciones de estudiantes ----------

class Chat(models.Model):
    id_chat = models.AutoField(primary_key=True)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    estado_intercambio = models.BooleanField(default=False)
    publicacion = models.ForeignKey('core.Publicacion', on_delete=models.CASCADE, related_name='chats')

    def __str__(self):
        return f"Chat {self.id_chat}"


class ChatParticipante(models.Model):
    ROL_CHOICES = (('autor', 'Autor'), ('receptor', 'Receptor'))
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='participantes')
    estudiante = models.ForeignKey('core.Estudiante', on_delete=models.CASCADE, related_name='participaciones')
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='receptor')  # 👈 default
    calificado = models.BooleanField(default=False)

    class Meta:
        unique_together = ('chat', 'estudiante')


class Mensaje(models.Model):
    id_mensaje = models.AutoField(primary_key=True)
    texto = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='mensajes')
    estudiante = models.ForeignKey('core.Estudiante', on_delete=models.CASCADE, related_name='mensajes')
    leido = models.BooleanField(default=False)


class CalificacionChat(models.Model):
    id_calificacion = models.AutoField(primary_key=True)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='calificaciones')
    evaluador = models.ForeignKey('core.Estudiante', on_delete=models.CASCADE, related_name='calificaciones_dadas')
    puntaje = models.IntegerField()
    comentario = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('chat', 'evaluador')


class Notificacion(models.Model):
    TIPO_CHOICES = (
        ('nuevo_chat', 'Nuevo chat'),
        ('nuevo_mensaje', 'Nuevo mensaje'),
        ('intercambio_completado', 'Intercambio completado'),
        ('calificacion_recibida', 'Calificación recibida'),
    )
    id_notificacion = models.AutoField(primary_key=True)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES, default='nuevo_mensaje')  # 👈 default
    fecha = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)

    estudiante = models.ForeignKey('core.Estudiante', on_delete=models.CASCADE, related_name='notificaciones')
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, null=True, blank=True, related_name='notificaciones')
    publicacion = models.ForeignKey('core.Publicacion', on_delete=models.CASCADE, null=True, blank=True, related_name='notificaciones')
    calificacion = models.ForeignKey('core.CalificacionChat', on_delete=models.CASCADE, null=True, blank=True, related_name='notificaciones')
#-----------------------Perfiles y Notificaciones
class TokenVerificacion(models.Model):
    id_token = models.AutoField(primary_key=True)
    token = models.CharField(max_length=128, unique=True)
    fecha_expiracion = models.DateTimeField()
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)

class Perfil(models.Model):
    id_perfil = models.AutoField(primary_key=True)
    estudiante = models.OneToOneField(Estudiante, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100, default="Sin nombre")
    biografia = models.TextField(blank=True, null=True)
    foto = models.URLField(blank=True, null=True)
    habilidades_ofrecidas = models.TextField(blank=True, null=True)
    habilidades_buscadas = models.TextField(blank=True, null=True)
#-----------------------Reportes
class Reporte(models.Model):
    id_reporte = models.AutoField(primary_key=True)
    motivo = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    estado = models.IntegerField(choices=[(0, 'Pendiente'), (1, 'Aceptado'), (2, 'Rechazado')], default=0)
    administrador = models.ForeignKey(Administrador, on_delete=models.SET_NULL, null=True)
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)
    publicacion = models.ForeignKey(Publicacion, on_delete=models.CASCADE)


