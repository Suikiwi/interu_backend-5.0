from urllib import request
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import AuthenticationFailed, ValidationError, NotFound
from django.utils import timezone
from django.contrib.auth.hashers import check_password
from rest_framework.exceptions import AuthenticationFailed
from django.db import transaction
from .models import (
    Administrador, ChatParticipante, Estudiante, Publicacion, CalificacionChat, Mensaje, Reporte,
    TokenVerificacion, Perfil, Notificacion, Perfil, Chat
)
from .serializers import (
    ModerarReporteSerializer, PerfilCompletoSerializer, RegistroEstudianteSerializer, ActivarCuentaSerializer,
    PublicacionSerializer, ChatSerializer, MensajeSerializer,
    PerfilCompletoSerializer, NotificacionSerializer, ReporteSerializer,
    CalificacionChatSerializer
)

# ----------- ESTUDIANTES -----------
class RegistroEstudianteView(generics.CreateAPIView):
    serializer_class = RegistroEstudianteSerializer
    permission_classes = [permissions.AllowAny]

class ActivarCuentaView(generics.GenericAPIView):
    serializer_class = ActivarCuentaSerializer
    permission_classes = [permissions.AllowAny]
    def post(self, request, *args, **kwargs):
        token = request.data.get("token")
        try:
            token_obj = TokenVerificacion.objects.get(token=token)
            if token_obj.fecha_expiracion < timezone.now():
                return Response({"error": "El token ha expirado"}, status=status.HTTP_400_BAD_REQUEST)
            estudiante = token_obj.estudiante
            estudiante.verificado = True
            estudiante.save()
            token_obj.delete()
            return Response({"mensaje": "Cuenta activada con éxito"}, status=status.HTTP_200_OK)
        except TokenVerificacion.DoesNotExist:
            return Response({"error": "Token inválido"}, status=status.HTTP_400_BAD_REQUEST)

class LoginEstudianteView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        try:
            estudiante = Estudiante.objects.get(email=email)
        except Estudiante.DoesNotExist:
            return Response({"detail": "Credenciales inválidas"}, status=status.HTTP_401_UNAUTHORIZED)
        if not check_password(password, estudiante.contraseña):
            return Response({"detail": "Credenciales inválidas"}, status=status.HTTP_401_UNAUTHORIZED)
        if not estudiante.verificado:
            return Response({"detail": "Cuenta no activada"}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({"api_key": estudiante.api_key}, status=status.HTTP_200_OK)

# ----------- PUBLICACIONES -----------
class PublicacionListCreateView(generics.ListCreateAPIView):
    queryset = Publicacion.objects.all()
    serializer_class = PublicacionSerializer
    permission_classes = [permissions.AllowAny]
    def perform_create(self, serializer):
        api_key = self.request.headers.get('X-API-Key')
        if not api_key:
            raise AuthenticationFailed("Falta API Key")
        try:
            estudiante = Estudiante.objects.get(api_key=api_key)
        except Estudiante.DoesNotExist:
            raise AuthenticationFailed("API Key inválida")
        serializer.save(estudiante=estudiante)

class PublicacionDetailView(generics.RetrieveAPIView):
    queryset = Publicacion.objects.all()
    serializer_class = PublicacionSerializer
    permission_classes = [permissions.AllowAny]

class PublicacionUpdateView(generics.UpdateAPIView):
    queryset = Publicacion.objects.all()
    serializer_class = PublicacionSerializer
    permission_classes = [permissions.AllowAny]
    def perform_update(self, serializer):
        api_key = self.request.headers.get('X-API-Key')
        if not api_key:
            raise AuthenticationFailed("Falta API Key")
        try:
            estudiante = Estudiante.objects.get(api_key=api_key)
        except Estudiante.DoesNotExist:
            raise AuthenticationFailed("API Key inválida")
        publicacion = self.get_object()
        if publicacion.estudiante != estudiante:
            raise AuthenticationFailed("No puedes editar publicaciones de otro estudiante")
        serializer.save()

class PublicacionDeleteView(generics.DestroyAPIView):
    queryset = Publicacion.objects.all()
    serializer_class = PublicacionSerializer
    permission_classes = [permissions.AllowAny]
    def perform_destroy(self, instance):
        api_key = self.request.headers.get('X-API-Key')
        if not api_key:
            raise AuthenticationFailed("Falta API Key")
        try:
            estudiante = Estudiante.objects.get(api_key=api_key)
        except Estudiante.DoesNotExist:
            raise AuthenticationFailed("API Key inválida")
        if instance.estudiante != estudiante:
            raise AuthenticationFailed("No puedes eliminar publicaciones de otro estudiante")
        instance.delete()

class MisPublicacionesView(generics.ListAPIView):
    serializer_class = PublicacionSerializer
    permission_classes = [permissions.AllowAny]
    def get_queryset(self):
        api_key = self.request.headers.get('X-API-Key')
        if not api_key:
            raise AuthenticationFailed("Falta API Key")
        try:
            estudiante = Estudiante.objects.get(api_key=api_key)
        except Estudiante.DoesNotExist:
            raise AuthenticationFailed("API Key inválida")
        return Publicacion.objects.filter(estudiante=estudiante)

# ----------- CHAT Y MENSAJES -----------
def crear_notificacion(estudiante, tipo, mensaje, chat=None, publicacion=None, calificacion=None):
    Notificacion.objects.create(
        estudiante=estudiante,
        tipo=tipo,
        mensaje=mensaje,
        chat=chat,
        publicacion=publicacion,
        calificacion=calificacion
    )


class ChatListCreateView(generics.ListCreateAPIView):
    queryset = Chat.objects.all().order_by('-fecha_inicio')
    serializer_class = ChatSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        # 1. Resolver receptor desde la API Key
        api_key = request.headers.get('X-API-Key')
        receptor = get_object_or_404(Estudiante, api_key=api_key)

        # 2. Resolver publicación
        publicacion_id = request.data.get('publicacion')
        if not publicacion_id:
            return Response({'detail': 'publicacion es requerida.'}, status=400)

        publicacion = get_object_or_404(Publicacion, pk=publicacion_id)

        # ⚠️ Usa el nombre real del campo en tu modelo Publicacion
        autor = publicacion.estudiante  # cámbialo si tu FK se llama distinto

        # 3. Evitar chat consigo mismo
        if autor == receptor:
            return Response({'detail': 'No puedes iniciar un chat con tu propia publicación.'}, status=400)

        # 4. Crear chat
        chat = Chat.objects.create(publicacion=publicacion)

        # 5. Crear participantes de forma segura (sin duplicados)
        ChatParticipante.objects.get_or_create(chat=chat, estudiante=autor, defaults={'rol': 'autor'})
        ChatParticipante.objects.get_or_create(chat=chat, estudiante=receptor, defaults={'rol': 'receptor'})

        # 6. Notificar al autor
        crear_notificacion(
            estudiante=autor,
            tipo='nuevo_chat',
            mensaje=f'Nuevo chat sobre tu publicación {publicacion_id}',
            chat=chat,
            publicacion=publicacion
        )

        return Response(ChatSerializer(chat).data, status=201)
    
class ChatDetailView(generics.RetrieveAPIView):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer
    lookup_field = 'pk'

    def retrieve(self, request, *args, **kwargs):
        chat = self.get_object()
        # Solo participantes pueden ver
        if not ChatParticipante.objects.filter(chat=chat, estudiante=request.user).exists():
            return Response({'detail': 'No autorizado.'}, status=403)
        return Response(ChatSerializer(chat).data, status=200)


class CompletarIntercambioView(generics.UpdateAPIView):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        # 1. Resolver estudiante desde API Key
        api_key = request.headers.get('X-API-Key')
        estudiante = get_object_or_404(Estudiante, api_key=api_key)

        # 2. Resolver chat
        chat = self.get_object()

        # 3. Validar que el estudiante sea el autor
        es_autor = ChatParticipante.objects.filter(
            chat=chat,
            estudiante=estudiante,
            rol='autor'
        ).exists()

        if not es_autor:
            return Response({'detail': 'Solo el autor puede completar el intercambio.'}, status=403)

        # 4. Marcar chat como completado
        chat.completado = True
        chat.save()

        # 5. Notificar al receptor
        receptores = ChatParticipante.objects.filter(chat=chat).exclude(estudiante=estudiante)
        for receptor in receptores:
            crear_notificacion(
                estudiante=receptor.estudiante,
                tipo='intercambio_completado',
                mensaje=f'El autor ha marcado el chat {chat.pk} como completado.',
                chat=chat
            )

        return Response(ChatSerializer(chat).data, status=200)

# Mensajes
class MensajeListCreateView(generics.ListCreateAPIView):
    queryset = Mensaje.objects.all().order_by('fecha')
    serializer_class = MensajeSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        remitente = get_object_or_404(Estudiante, api_key=api_key)

        chat_id = request.data.get('chat')
        if not chat_id:
            return Response({'detail': 'chat es requerido.'}, status=400)

        chat = get_object_or_404(Chat, pk=chat_id)

        if not ChatParticipante.objects.filter(chat=chat, estudiante=remitente).exists():
            return Response({'detail': 'No eres participante de este chat.'}, status=403)

        texto = request.data.get('texto')
        if not texto:
            return Response({'detail': 'texto es requerido.'}, status=400)

        mensaje = Mensaje.objects.create(
            chat=chat,
            estudiante=remitente,
            texto=texto
        )

        # Notificar al otro participante
        otros = ChatParticipante.objects.filter(chat=chat).exclude(estudiante=remitente)
        for otro in otros:
            crear_notificacion(
                estudiante=otro.estudiante,
                tipo='nuevo_mensaje',
                mensaje=f'Nuevo mensaje en el chat {chat.id_chat}',
                chat=chat
            )

        return Response(MensajeSerializer(mensaje).data, status=201)



# Calificaciones de chat
class CalificacionChatCreateView(generics.CreateAPIView):
    queryset = CalificacionChat.objects.all()
    serializer_class = CalificacionChatSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        # 1. Resolver estudiante desde API Key
        api_key = request.headers.get('X-API-Key')
        evaluador = get_object_or_404(Estudiante, api_key=api_key)

        # 2. Resolver chat
        chat_id = request.data.get('chat')
        if not chat_id:
            return Response({'detail': 'chat es requerido.'}, status=400)

        chat = get_object_or_404(Chat, pk=chat_id)

        # 3. Validar que el evaluador sea participante
        if not ChatParticipante.objects.filter(chat=chat, estudiante=evaluador).exists():
            return Response({'detail': 'No eres participante de este chat.'}, status=403)

        # 4. Validar que no haya calificado antes
        if CalificacionChat.objects.filter(chat=chat, evaluador=evaluador).exists():
            return Response({'detail': 'Ya has calificado este chat.'}, status=400)

        # 5. Extraer datos del body
        puntaje = request.data.get('puntaje')
        comentario = request.data.get('comentario', '')

        if not puntaje:
            return Response({'detail': 'puntaje es requerido.'}, status=400)

        # 6. Crear calificación
        calificacion = CalificacionChat.objects.create(
            chat=chat,
            evaluador=evaluador,
            puntaje=puntaje,
            comentario=comentario
        )

        # 7. Notificar al otro participante
        otros = ChatParticipante.objects.filter(chat=chat).exclude(estudiante=evaluador)
        for otro in otros:
            crear_notificacion(
                estudiante=otro.estudiante,
                tipo='calificacion_chat',
                mensaje=f'El estudiante {evaluador.pk} calificó el chat {chat.pk}.',
                chat=chat
            )

        return Response(CalificacionChatSerializer(calificacion).data, status=201)


# Notificaciones
class NotificacionListView(generics.ListAPIView):
    serializer_class = NotificacionSerializer

    def get_queryset(self):
        # Resolver estudiante desde API Key
        api_key = self.request.headers.get('X-API-Key')
        estudiante = get_object_or_404(Estudiante, api_key=api_key)

        return Notificacion.objects.filter(estudiante=estudiante).order_by('-fecha')

class MarcarNotificacionLeidaView(generics.UpdateAPIView):
    serializer_class = NotificacionSerializer
    queryset = Notificacion.objects.all()

    def patch(self, request, pk=None):
        notif = get_object_or_404(Notificacion, pk=pk, estudiante=request.user)
        notif.leida = True
        notif.save(update_fields=['leida'])
        return Response(NotificacionSerializer(notif).data, status=200)


class MarcarTodasNotificacionesLeidasView(generics.CreateAPIView):
    def post(self, request):
        Notificacion.objects.filter(estudiante=request.user, leida=False).update(leida=True)
        return Response({'detail': 'Todas las notificaciones marcadas como leídas.'}, status=200)
# ----------- PERFIL Y NOTIFICACIONES -----------
class CrearPerfilView(generics.CreateAPIView):
    serializer_class = PerfilCompletoSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        api_key = self.request.headers.get('X-API-Key')
        if not api_key:
            raise AuthenticationFailed("Falta API Key")
        try:
            estudiante = Estudiante.objects.get(api_key=api_key)
        except Estudiante.DoesNotExist:
            raise AuthenticationFailed("API Key inválida")

        if Perfil.objects.filter(estudiante=estudiante).exists():
            raise ValidationError({"detalle": "El perfil ya existe"})

        serializer.save(estudiante=estudiante)

class PerfilDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PerfilCompletoSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        api_key = self.request.headers.get('X-API-Key')
        if not api_key:
            raise AuthenticationFailed("Falta API Key")
        try:
            estudiante = Estudiante.objects.get(api_key=api_key)
        except Estudiante.DoesNotExist:
            raise AuthenticationFailed("API Key inválida")

        try:
            return Perfil.objects.get(estudiante=estudiante)
        except Perfil.DoesNotExist:
            raise NotFound("Perfil no encontrado. Debe crearlo primero.")


#--------------------------- REPORTES -----------
class CrearReporteView(generics.CreateAPIView):
    serializer_class = ReporteSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        api_key = self.request.headers.get('X-API-Key')
        if not api_key:
            raise AuthenticationFailed("Falta API Key")
        estudiante = Estudiante.objects.get(api_key=api_key)
        serializer.save(estudiante=estudiante)

class ListarReportesView(generics.ListAPIView):
    queryset = Reporte.objects.all()
    serializer_class = ReporteSerializer
    permission_classes = [permissions.IsAdminUser]
    
class ModerarReporteView(generics.UpdateAPIView):
    serializer_class = ModerarReporteSerializer
    queryset = Reporte.objects.all()
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        obj = super().get_object()
        api_key = self.request.headers.get("X-API-Key")
        if not api_key or not Administrador.objects.filter(api_key=api_key).exists():
            raise AuthenticationFailed("No tienes permisos de moderador")
        return obj
