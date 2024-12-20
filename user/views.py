from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import JsonResponse
import hashlib, datetime, random
from user.forms import RegistrationForm
from user.models import UserProfile
from django.core.mail import send_mail
import json

from scripts.Exchange import Exchange
from django.conf import settings 

@login_required
def home(request):


    from scripts.crontab_check_price_change import DATA_FILE,load_data_file
    #try:
    data = load_data_file(DATA_FILE)
    qty_symbols = len(data['symbols'])
    updated = data['updated']
    proc_duration = data['proc_duration']

    return render(request, 'home.html',{
        'DATA_FILE': DATA_FILE ,
        'qty_symbols': qty_symbols ,
        'updated': updated ,
        'proc_duration': proc_duration ,
    })
    #except:
    #    return render(request, 'home.html')

def signup(request):
    json_rsp = {}
    
    if request.method == 'GET':
        form = RegistrationForm()
        return render(request, 'signup.html')
    else:

        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            

            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            salt = hashlib.sha1(str(random.random()).encode('utf-8')).hexdigest()[:5]            
            activation_key = hashlib.sha1((salt+email).encode('utf-8')).hexdigest()            
            key_expires = timezone.now() + datetime.timedelta(2)

            #Obtener el nombre de usuario
            user=User.objects.get(username=username)

            # Crear el perfil del usuario                                                                                                                                 
            new_profile = UserProfile(user=user, activation_key=activation_key, 
                key_expires=key_expires)
            new_profile.save()

            """TODO
            Fuente del tutorial - https://contraslash.github.io/blog_legacy/30-user-registration-and-email-confirmation-in-django/
            Pendiente:
                - Envio del mail
                - url para recibir la confirmacion de mail
            """

            # # Enviar un email de confirmación
            # email_subject = 'Account confirmation'
            # email_body = "Hola %s, Gracias por registrarte. Para activar tu cuenta da clíck en este link en menos de 48 horas: http://127.0.0.1:8000/accounts/confirm/%s" % (username, activation_key)

            # send_mail(email_subject, email_body, 'leonardo.bisaro@gmail.com',
            #     [email], fail_silently=False)
            
            json_rsp['ok'] = 'Registro correcto'

        else: 
            #json_rsp['error'] = dict(form.errors.items())
            msgError = ''
            for field in form:
                if field.errors:
                    msgError += "<div><b>"+field.label+"</b> "
                    for err in field.errors:
                        msgError += "<span>"+err+"</span> "
                    msgError += "</div>"
            msgError = msgError.replace("First name", "Nombre")
            msgError = msgError.replace("Last name", "Apellido")
            json_rsp['error'] = msgError
        return JsonResponse(json_rsp)
    

def signin(request):
    json_rsp = {}

    env = 'TEST' if settings.DEBUG else 'PRODUCTION'
    if request.method == 'GET':
        return render(request, 'signin.html',{
            'environment': env,
        })
    else:
        user = authenticate(request,username=request.POST['login_username'], password=request.POST['login_password'])
        
        if user:
            if user.is_active:
                login(request, user)
                json_rsp['login_ok'] = 'Redireccionando al home'
            else:
                json_rsp['login_error'] = 'La cuenta de usuario se encuentra inactiva'
        else:
            json_rsp['login_error'] = 'El usuario o contraseña es invalido'
        return JsonResponse(json_rsp)

@login_required
def profile(request):
    json_rsp = {}
    profile = UserProfile.objects.get(user_id=request.user.id)
    if request.method == 'GET':
        return render(request, 'profile.html',{
            'title': 'Perfil de usuario' ,
            'ayn': f'{profile.user.first_name} {profile.user.last_name}' ,
            'username': profile.user.username,
            'mail': profile.user.email,
            'config': profile.parse_config(),
        })
    else:
        config = profile.parse_config()
        if 'remove' in request.POST:
            del config[request.POST['remove']]
            profile.config = json.dumps(config)
            profile.save()
            json_rsp['ok'] = True

        elif request.POST['config'] == 'bnc': # Binance
            prms = {'bnc_apk': request.POST['bnc_apk'],
                    'bnc_aps': request.POST['bnc_aps'],
                    'bnc_env': request.POST['bnc_env'],
                    }
            #try:
            exc = Exchange(type='user_apikey',exchange='bnc',prms=prms)
            if exc.check_connection():
                config['bnc'] = prms
                profile.config = json.dumps(config)
                profile.save()
                json_rsp['ok'] = True
            else:
                json_rsp['error'] = 'Verifique los datos provistos, No fue posible conectar con el exchange. '

        

    return JsonResponse(json_rsp)

@login_required
def signout(request):
    logout(request)
    return redirect('signin')
