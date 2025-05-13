# autointelli/__init__.py

import os
import logging # <<< Importar logging
from flask import Flask, current_app # Importar current_app si lo necesitas en la fábrica

# Importar la instancia *única* de db desde models.py
from .models import db # <<< Importa la instancia db de models.py

# Importar las otras extensiones
from flask_login import LoginManager, current_user # Importar current_user para user_loader
from flask_migrate import Migrate
from flask_mail import Mail
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv
from notion_client import Client

# --- Configurar logger para este módulo ---
logger = logging.getLogger(__name__) # Usa __name__ para nombrar el logger como 'autointelli'
# Si tus logs DEBUG globales no se muestran, puedes configurar temporalmente el nivel aquí:
logger.setLevel(logging.DEBUG)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Inicializar otras extensiones (db ya está importada, no la crees aquí)
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()

# Serializer (se inicializará con SECRET_KEY)
s = URLSafeTimedSerializer("default_secret_key") # Valor temporal (será sobrescrito)


def create_app():
    # --- Cargar variables de entorno ---
    # Es buena práctica asegurarse de que esto se llama al inicio de la fábrica
    load_dotenv()

    # --- Configurar rutas de plantillas y estáticos (si son no estándar) ---
    # Estos parecen correctos según tu estructura sys_autointelli/templates
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))

    app = Flask(__name__,
                instance_relative_config=True,
                template_folder=template_dir,
                static_folder=static_dir
               )

    # --- Configuración de la Aplicación (basada en variables de entorno) ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una_clave_secreta_por_defecto_muy_segura_cambiar_en_produccion')

    # Leer la URL de la BD
    database_url = os.environ.get('DATABASE_URL') # Leer la variable en una temporal

    # Configurar la URI de la BD en Flask-SQLAlchemy
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Recomendado False para mejor rendimiento

    # <<< AGREGAR ESTE LOG DE DEPURACIÓN >>>
    # Mostrar el valor EXACTO que Flask-SQLAlchemy verá para la URI de la base de datos
    # Asegúrate de que tu configuración de logging global permita ver mensajes DEBUG
    logger.debug(f"SQLALCHEMY_DATABASE_URI configurada como: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    # <<< FIN LOG DE DEPURACIÓN >>>


    # Verificar si la URL de la BD está configurada. Si no, es un error fatal.
    if not database_url: # Usar la variable temporal para verificar
        print("ERROR FATAL: DATABASE_URL no configurada. La aplicación no puede iniciar.")
        # Es mejor lanzar una excepción clara que solo imprimir un mensaje
        raise EnvironmentError("La variable de entorno DATABASE_URL no está configurada. La aplicación no puede conectar a la base de datos.")
        # import sys; sys.exit(1) # O salir del programa si prefieres


    # Configuración de Flask-Mail
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    # Convertir puertos a int y manejar posibles errores si la variable no existe o no es numérica
    try:
        app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
    except ValueError:
        app.config['MAIL_PORT'] = 465 # Fallback a puerto por defecto si hay error
        logger.warning("MAIL_PORT en .env no es un número válido. Usando puerto por defecto 465.")

    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'False').lower() == 'true'
    app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'True').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    # Usar el username como default sender si no se especifica MAIL_DEFAULT_SENDER
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config.get('MAIL_USERNAME'))

    # Advertencia si las credenciales de correo no están configuradas
    if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
         logger.warning("Configuración de correo incompleta (MAIL_USERNAME o MAIL_PASSWORD faltantes). La funcionalidad de correo no funcionará.")
         # Considera deshabilitar Flask-Mail si no se configura, o manejar errores al enviar correo.
         # app.config['MAIL_SUPPRESS_SEND'] = True # Opcional: Suprimir envíos si la config es incompleta


    # Configuración de Notion
    app.config['NOTION_API_KEY'] = os.environ.get("NOTION_API_KEY")
    # Revisa los nombres de estas variables de entorno. Deben coincidir con tus constantes en notion/constants.py
    app.config['DATABASE_ID_PROYECTOS'] = os.environ.get("DATABASE_ID_PROYECTOS")
    app.config['DATABASE_ID_PARTIDAS'] = os.environ.get("DATABASE_ID_PARTIDAS") # Revisa si este nombre es correcto en .env
    app.config['DATABASE_ID_PLANES'] = os.environ.get("DATABASE_ID_PLANES")     # Revisa si este nombre es correcto en .env
    app.config['DATABASE_ID_MATERIALES_DB1'] = os.environ.get("DATABASE_ID")   # Revisa si este nombre es correcto en .env (¿es solo DATABASE_ID?)
    app.config['DATABASE_ID_MATERIALES_DB2'] = os.environ.get("DATABASE_ID_2") # Revisa si este nombre es correcto en .env

    # Inicializar Cliente Notion y guardarlo en la instancia de app para que esté disponible
    app.notion_client = None # Inicializa a None por defecto
    if app.config.get('NOTION_API_KEY'):
         logger.debug("NOTION_API_KEY encontrada en config, intentando inicializar Notion Client...")
         try:
              # Usar el CLIENTE OFICIAL de notion_client, no un nombre genérico como 'Client' si importaste diferente
              app.notion_client = Client(auth=app.config['NOTION_API_KEY'], timeout_ms=60000) # Añadir un timeout puede ser útil
              logger.debug("Cliente de Notion inicializado.")
         except Exception as e:
              # Loggear el error pero permitir que la aplicación continúe (la integración Notion simplemente no funcionará)
              logger.error(f"ERROR al inicializar Notion Client: {e}", exc_info=True) # Log con traceback
              app.notion_client = None # Asegurarse de que queda como None
    else:
          logger.warning("NOTION_API_KEY NO encontrada en config. Cliente de Notion no inicializado. La integración con Notion no funcionará.")


    # --- Inicializar Extensiones con la App ---
    # Usar la instancia db IMPORTADA de models.py
    db.init_app(app) # <<< CORRECTO: Inicializa la instancia db importada

    # Inicializar otras extensiones con la instancia de la app y la instancia db (si aplica)
    migrate.init_app(app, db) # migrate también necesita la instancia db
    login_manager.init_app(app)
    mail.init_app(app) # Inicializa Flask-Mail


    # Actualizar el serializer con la SECRET_KEY de la app configurada
    global s # Acceder a la variable global s
    # Usar app.config.get('SECRET_KEY') para asegurarse de obtener la clave configurada
    s = URLSafeTimedSerializer(app.config.get('SECRET_KEY', 'default_fallback_secret_again')) # Fallback por seguridad
    app.url_serializer = s # Guardar en la app para fácil acceso desde Blueprints (ej. para tokens de reseteo)


    # Configuración de Flask-Login
    login_manager.login_view = 'auth.login' # Endpoint para la página de login
    login_manager.login_message_category = 'info' # Categoría del mensaje flash
    login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.' # Mensaje para el usuario

    # Configurar la función user_loader
    @login_manager.user_loader
    def load_user(user_id):
        # Esta función es llamada por Flask-Login para cargar un usuario desde el ID
        # Importar User DENTRO de la función user_loader es una buena práctica (si es necesario)
        # para evitar importaciones circulares. Si User no tiene problemas, puedes importar al inicio del Blueprint.
        # Aquí usamos la importación local como estaba, lo cual es seguro.
        from .models import User # Importa el modelo User
        try:
            # db.session es accesible dentro de un contexto de solicitud/aplicación.
            # db.session.get() es la forma recomendada de cargar por clave primaria.
            return db.session.get(User, int(user_id)) # Usa la instancia db IMPORTADA
        except (ValueError, TypeError) as e:
             logger.error(f"Intento de cargar usuario con ID inválido '{user_id}': {e}")
             return None # Retornar None si el ID es inválido

    # --- Registrar Blueprints ---
    # Importa y registra tus Blueprints. Deben estar en archivos separados dentro de autointelli.
    from .auth import auth_bp
    from .solicitudes import solicitudes_bp
    from .ajustes import ajustes_bp
    from .proyectos import proyectos_bp
    from .main_routes import main_bp # Asumiendo main_routes tiene la ruta principal '/'
    from .accesorios import accesorios_bp
    from .almacen import almacen_bp
    from .compras import compras_bp
    # from .nuevosRegistros import nuevosRegistros_bp # Si tienes este Blueprint

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(solicitudes_bp, url_prefix='/solicitudes')
    app.register_blueprint(ajustes_bp, url_prefix='/ajustes')
    app.register_blueprint(proyectos_bp, url_prefix='/proyectos')
    app.register_blueprint(accesorios_bp, url_prefix='/accesorios')
    app.register_blueprint(almacen_bp, url_prefix='/almacen')
    app.register_blueprint(compras_bp, url_prefix='/compras')
    # if 'nuevosRegistros_bp' in locals(): # Opcional: Registrar si existe y no siempre
    #    app.register_blueprint(nuevosRegistros_bp, url_prefix='/nuevos-registros')

    # Retornar la instancia de la aplicación configurada
    return app